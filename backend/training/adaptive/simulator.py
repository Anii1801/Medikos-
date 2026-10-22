"""Replay held-out interviews through each questioning policy and score the outcome.

The patient is simulated from the gold interview: whatever question a policy asks is answered with a
placeholder, because coverage / redundancy / length / safety-omission depend on WHICH questions are
asked, not on the answer text. ontology_v1 / safety_layer_uniform / learned run the REAL backend agent
(app.history_agent.AdaptiveHistoryTakingAgent) so the evaluation tests the code that ships.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from app import ontology
from app.adaptive.ranker import LearnedSlotRanker, RankResult
from app.adaptive.schema import (COMPLAINT_TO_ONTOLOGY_CC, MANDATORY_FIRST, V1_ADDITIONS,
                                 canonical_slots_for, covered_slots)
from app.history_agent import AdaptiveHistoryTakingAgent
from .data import Interview

CONFIG = json.loads((Path(__file__).parent / "config" / "required_slots.json").read_text(encoding="utf-8"))
POLICY_NAMES = ("fixed_template", "ontology_v0_frozen", "ontology_v1_current", "safety_layer_uniform",
                "learned_ranker", "learned_ranker_recorded")
BUDGETS = (6, 8, 10, 12, None)          # max questions asked; None = no limit


class UniformRanker:
    """Ablation: the same safety layer and 'schema questions first' structure, but NO learned signal."""
    version = "uniform-ablation"
    def rank(self, state: dict[str, Any], candidates=None) -> RankResult:
        cands = list(candidates or [])
        return RankResult(ranked=[(c, 1 / len(cands)) for c in cands], confidence=1.0, oov_ratio=0.0)


def _answers_for(iv: Interview, qid: str, view: str = "app") -> str:
    """view='app': the English complaint a typed 'Other' answer would hold; view='recorded': the patient's own
    (often Hindi) wording. Option-based complaints always hold the English ontology label, as in the live app."""
    option = COMPLAINT_TO_ONTOLOGY_CC[iv.complaint]
    if qid == "cc":
        return option
    if qid == "cc_text":
        return iv.cc_utterance if view == "recorded" else iv.complaint
    return "x"


def _run_agent(iv: Interview, budget, policy: str, ranker, view: str = "app") -> tuple[list[str], list[str]]:
    agent = AdaptiveHistoryTakingAgent(budget=budget or 60, policy=policy, ranker=ranker)
    resp, ids, bases = agent.next_response(), [], []
    while resp.question is not None and len(ids) < 80:
        qid = resp.question["id"]
        ids.append(qid); bases.append(resp.selection_basis)
        resp = agent.answer(qid, _answers_for(iv, qid, view))
    return ids, bases


def _run_ontology_v0(iv: Interview, budget) -> list[str]:
    answers: dict[str, Any] = {}
    ids: list[str] = []
    while len(ids) < (budget or 60):
        todo = [q for q in ontology.applicable(answers) if q["id"] not in answers and q["id"] not in V1_ADDITIONS]
        if not todo:
            break
        qid = todo[0]["id"]
        ids.append(qid); answers[qid] = _answers_for(iv, qid)
    return ids


def _run_fixed(iv: Interview, budget) -> list[str]:
    order = CONFIG["complaints"][iv.complaint]["slot_order"]
    return list(order[: budget or len(order)])


def replay(iv: Interview, policy: str, budget, ranker: LearnedSlotRanker | None = None, view: str = "app") -> dict[str, Any]:
    """Return the questions a policy asks and its outcome metrics for one interview."""
    bases: list[str] = []
    if policy == "fixed_template":
        slots_asked = _run_fixed(iv, budget); ids = slots_asked          # canonical slots directly
        covered, per_q_slots = set(slots_asked), [(s,) for s in slots_asked]
    else:
        if policy == "ontology_v0_frozen":
            ids = _run_ontology_v0(iv, budget)
        elif policy == "ontology_v1_current":
            ids, bases = _run_agent(iv, budget, "ontology", None)
        elif policy == "safety_layer_uniform":
            ids, bases = _run_agent(iv, budget, "learned", UniformRanker())
        elif policy in ("learned_ranker", "learned_ranker_recorded"):
            ranker_view = "recorded" if policy == "learned_ranker_recorded" else view
            ids, bases = _run_agent(iv, budget, "learned", ranker, ranker_view)
        else:
            raise ValueError(policy)
        per_q_slots = [canonical_slots_for(q) for q in ids]
        covered = covered_slots(ids)
    cfg = CONFIG["complaints"][iv.complaint]
    required, critical = set(cfg["required"]), set(cfg["safety_critical"])
    mandatory = {
        slot
        for question_id in MANDATORY_FIRST.get(COMPLAINT_TO_ONTOLOGY_CC[iv.complaint], ())
        for slot in canonical_slots_for(question_id)
    }
    seen: set[str] = set()
    duplicates = non_schema = 0
    for qid, slots in zip(ids, per_q_slots):
        if qid == "cc_text":          # structural follow-up to the 'Other' option, not a history-schema question
            continue
        if not slots:
            non_schema += 1
        elif set(slots) <= seen:
            duplicates += 1
        seen.update(slots)
    missing_critical = sorted(critical - covered)
    return {
        "interview_id": iv.interview_id, "complaint": iv.complaint, "script": iv.script, "policy": policy,
        "budget": budget or "none", "questions": ids, "n_questions": len(ids),
        "required_coverage": len(required & covered) / len(required),
        "mandatory_safety_question_coverage": len(mandatory & covered) / len(mandatory) if mandatory else 1.0,
        "missing_mandatory_safety_questions": sorted(mandatory - covered),
        "missing_required": sorted(required - covered),
        "safety_critical_omitted": bool(missing_critical), "missing_safety_critical": missing_critical,
        "duplicate_questions": duplicates, "non_schema_questions": non_schema,
        "selection_bases": bases,
    }
