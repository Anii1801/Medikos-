"""Adaptive question selection: leakage, checkpoint integrity, safety-first ordering, fallback, API contract.

These are SOFTWARE tests. They show the code behaves as specified; they are not evidence of clinical performance.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("MEDIKIOSK_DB", os.path.join(tempfile.mkdtemp(), "adaptive.db"))

from app import ontology
from app.adaptive.features import featurize
from app.adaptive.ranker import LearnedSlotRanker, RankerUnavailable, MODELS_DIR, DEFAULT_MODEL
from app.adaptive.schema import MANDATORY_FIRST, ONTOLOGY_TO_CANONICAL, V1_ADDITIONS
from app.history_agent import AdaptiveHistoryTakingAgent, default_policy
from training.adaptive.data import (assert_group_integrity, load_interviews, pre_answer_examples, split_interviews)
from training.adaptive.simulator import replay

RANKER = LearnedSlotRanker.load()
IVS = load_interviews()


def run(agent, cc="Chest pain", extra=None):
    resp, ids = agent.next_response(), []
    while resp.question is not None and len(ids) < 80:
        qid = resp.question["id"]
        ids.append(qid)
        resp = agent.answer(qid, cc if qid == "cc" else (extra or "Cough") if qid == "cc_text" else "x")
    return ids, resp


# ----------------------------------------------------------------------------- data / leakage
def test_splits_are_patient_grouped_and_use_the_datasets_own_split():
    info = assert_group_integrity(split_interviews(IVS))
    assert info["train"]["interviews"] == 240 and info["valid"]["interviews"] == 30 and info["test"]["interviews"] == 30


def test_pre_answer_states_contain_no_future_information():
    iv = next(i for i in IVS if i.complaint == "chest pain")
    base = [(e.state, e.target) for e in pre_answer_examples(iv, "recorded")]
    # corrupt EVERYTHING that happens after the chief complaint: all later patient answers and all later AI text
    seen_cc = False
    mutated = []
    for t in iv.turns:
        t = dict(t)
        if seen_cc:
            t["text"] = "ZZZ-FUTURE-LEAK"
        if t["role"] == "PATIENT" and t["slot"] == "chief_complaint":
            seen_cc = True
        mutated.append(t)
    iv2 = type(iv)(iv.interview_id, iv.patient_id, iv.split, iv.complaint, mutated, iv.gold)
    assert [(e.state, e.target) for e in pre_answer_examples(iv2, "recorded")] == base
    for state, _ in base:
        assert "ZZZ" not in json.dumps(state)


def test_state_k_contains_only_slots_asked_before_question_k():
    iv = IVS[0]
    exs = pre_answer_examples(iv, "recorded")
    for k, e in enumerate(exs):
        assert e.target not in e.state["asked"]
        assert len(e.state["asked"]) == k + 1          # cc plus the k earlier questions


# ----------------------------------------------------------------------------- checkpoint
def test_checkpoint_hash_is_verified(tmp_path):
    src = MODELS_DIR / DEFAULT_MODEL
    dst = tmp_path / "adaptive_ranker" / "v1"
    shutil.copytree(src, dst)
    assert LearnedSlotRanker.load("adaptive_ranker/v1", tmp_path).version
    (dst / "weights.json").write_bytes((dst / "weights.json").read_bytes() + b" ")
    with pytest.raises(RankerUnavailable):
        LearnedSlotRanker.load("adaptive_ranker/v1", tmp_path)


def test_checkpoint_is_json_not_pickle():
    assert not list((MODELS_DIR / DEFAULT_MODEL).glob("*.pkl")) and not list((MODELS_DIR / DEFAULT_MODEL).glob("*.joblib"))


def test_ranker_fallback_signals():
    assert RANKER.rank({"cc_text": "", "asked": []}, ["dur"]).fallback_reason == "empty_state"
    assert RANKER.rank({"cc_text": "qzxv wjk", "asked": ["cc"]}, ["dur", "sev"]).fallback_reason == "unfamiliar_complaint"
    assert RANKER.rank({"cc_text": "chest pain", "asked": ["cc"]}, []).fallback_reason == "no_known_candidates"
    ok = RANKER.rank({"cc_text": "chest pain", "asked": ["cc"]}, ["dur", "sev", "pmh"])
    assert ok.usable and ok.ranked[0][0] == "dur"


def test_ranker_follows_hindi_and_english_complaint_wording():
    for text in ("सीने में दर्द", "chest pain", "Chest pain"):
        assert RANKER.rank({"cc_text": text, "asked": ["cc"]}, ["dur", "sev", "pmh"]).ranked[0][0] == "dur"


# ----------------------------------------------------------------------------- agent behaviour
def test_default_policy_is_the_reviewed_ontology_policy(monkeypatch):
    monkeypatch.delenv("MEDIKIOSK_QUESTION_POLICY", raising=False)
    assert default_policy() == "ontology"
    monkeypatch.setenv("MEDIKIOSK_QUESTION_POLICY", "garbage")
    assert default_policy() == "ontology"


def test_ontology_policy_order_is_unchanged():
    ids, _ = run(AdaptiveHistoryTakingAgent(policy="ontology"))
    assert ids[:4] == ["cc", "dur", "sev", "progression"]


@pytest.mark.parametrize("cc", sorted(MANDATORY_FIRST))
def test_safety_questions_come_first_under_learned_policy(cc):
    agent = AdaptiveHistoryTakingAgent(policy="learned", ranker=RANKER)
    ids, _ = run(agent, cc)
    need = list(MANDATORY_FIRST[cc])
    assert ids[1:1 + len(need)] == need


def test_learned_policy_never_drops_or_repeats_a_question():
    for cc in ("Chest pain", "Fever", "Other", "Joint / back pain"):
        base, _ = run(AdaptiveHistoryTakingAgent(policy="ontology"), cc)
        learned, _ = run(AdaptiveHistoryTakingAgent(policy="learned", ranker=RANKER), cc)
        assert sorted(learned) == sorted(base) and len(set(learned)) == len(learned)


def test_current_question_is_stable_across_repeated_reads():
    agent = AdaptiveHistoryTakingAgent(policy="learned", ranker=RANKER)
    agent.next_response()
    agent.answer("cc", "Fever")
    first = agent.next_response().question["id"]
    assert all(agent.next_response().question["id"] == first for _ in range(4))


def test_next_question_changes_with_state_and_answered_questions_are_suppressed():
    agent = AdaptiveHistoryTakingAgent(policy="learned", ranker=RANKER)
    agent.next_response()
    a = agent.answer("cc", "Fever").question["id"]
    b = agent.answer(a, "x").question["id"]
    assert a != b
    assert a in agent.state["answers"] and b not in agent.state["answers"]


def test_broken_ranker_falls_back_to_ontology_order_without_breaking_the_interview():
    class Boom:
        version = "boom"
        def rank(self, *a, **k):
            raise RuntimeError("model exploded")
    agent = AdaptiveHistoryTakingAgent(policy="learned", ranker=Boom())
    agent.next_response(); agent.answer("cc", "Fever")
    resp = agent.next_response()
    assert resp.question["id"] == "fv_exp"            # mandatory safety question first
    resp = agent.answer("fv_exp", "x")
    assert resp.selection_basis == "fallback" and resp.fallback_reason == "ranker_error"
    assert resp.question["id"] == "dur"               # plain ontology order


def test_unfamiliar_free_text_complaint_defers_to_ontology_policy():
    agent = AdaptiveHistoryTakingAgent(policy="learned", ranker=RANKER)
    agent.next_response(); agent.answer("cc", "Other")
    resp = agent.answer("cc_text", "qzxv wjk plmn")
    assert resp.selection_basis == "fallback" and resp.fallback_reason == "unfamiliar_complaint"
    assert resp.question["id"] == "dur"


def test_red_flags_still_fire_under_learned_policy():
    agent = AdaptiveHistoryTakingAgent(policy="learned", ranker=RANKER)
    agent.next_response(); agent.answer("cc", "Chest pain")
    agent.answer("cp_rad", "Yes, to my left arm")
    resp = agent.answer("assoc", "sweating and shortness of breath")
    assert resp.red_flags


def test_policy_survives_session_serialisation():
    agent = AdaptiveHistoryTakingAgent(policy="learned", ranker=RANKER)
    assert AdaptiveHistoryTakingAgent.from_dict(agent.to_dict()).policy == "learned"
    legacy = agent.to_dict(); legacy.pop("policy")
    assert AdaptiveHistoryTakingAgent.from_dict(legacy).policy == "ontology"


def test_every_mapped_ontology_id_exists():
    for qid in ONTOLOGY_TO_CANONICAL:
        assert qid in ontology.BY_ID, qid
    assert V1_ADDITIONS <= set(ontology.BY_ID)


def test_replay_matches_real_agent_sequences():
    iv = next(i for i in IVS if i.complaint == "fever")
    rows = replay(iv, "ontology_v1_current", None)
    ids, _ = run(AdaptiveHistoryTakingAgent(policy="ontology"), "Fever")
    assert rows["questions"] == ids


# ----------------------------------------------------------------------------- API contract
def test_api_exposes_policy_and_basis(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv("MEDIKIOSK_QUESTION_POLICY", "learned")
    c = TestClient(app)
    h = {"Authorization": "Bearer " + c.post("/api/auth/guest").json()["token"]}
    s = c.post("/api/interview/sessions", json={}, headers=h).json()
    assert s["policy"] == "learned"
    r = c.post(f"/api/interview/sessions/{s['session_id']}/answers", json={"field": "cc", "value": "Chest pain"}, headers=h).json()
    assert r["question"]["id"] == "cp_rad" and r["selection_basis"] == "safety_mandatory"
    r = c.post(f"/api/interview/sessions/{s['session_id']}/answers", json={"field": "cp_rad", "value": "No"}, headers=h).json()
    r = c.post(f"/api/interview/sessions/{s['session_id']}/answers", json={"field": "cp_char", "value": "Pressure"}, headers=h).json()
    r = c.post(f"/api/interview/sessions/{s['session_id']}/answers", json={"field": "assoc", "value": "None"}, headers=h).json()
    assert r["question"]["id"] == "dur" and r["selection_basis"] == "learned_rank" and r["ranker_version"]
