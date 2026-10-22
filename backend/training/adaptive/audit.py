"""Label-quality audit for the adaptive-questioning data, run BEFORE training.

Question answered: is 'predict the recorded next question' a meaningful target,
or does it only reward imitating a fixed template? Also derives the (provisional)
required-slot configuration from the TRAINING split only.
"""
from __future__ import annotations

import collections
import json
import math
from pathlib import Path
from typing import Any

from app.adaptive.schema import (CANONICAL_SLOTS, REVIEW_STATUS, SAFETY_CRITICAL_EXTRA_BY_COMPLAINT,
                                 SAFETY_CRITICAL_SLOTS, STOP, COMPLAINT_TO_ONTOLOGY_CC)
from .data import (HIST_DIR, Interview, assert_group_integrity, file_sha256, load_interviews,
                   split_interviews, verify_jsonl_matches_csv)

CONFIG_DIR = Path(__file__).parent / "config"
GOLD_FIELD_BY_SLOT = {"dur": "duration", "char": "hpi_character", "rad": "hpi_radiation", "agg": "hpi_aggravating",
                      "rel": "hpi_relieving", "sev": "severity_1_10", "assoc": "associated_symptoms",
                      "pmh": "past_history", "drug": "drug_history", "allergy": "allergy",
                      "fam": "family_history", "pers": "personal_history"}


def _entropy(values: list[str]) -> float:
    n = len(values)
    return -sum(c / n * math.log2(c / n) for c in collections.Counter(values).values()) if n else 0.0


def build_required_slots(train: list[Interview], min_share: float = 0.95) -> dict[str, Any]:
    """Required slots per complaint = slots asked in >=95% of that complaint's TRAINING interviews."""
    by_c: dict[str, list[Interview]] = collections.defaultdict(list)
    for iv in train:
        by_c[iv.complaint].append(iv)
    complaints: dict[str, Any] = {}
    for c, ivs in sorted(by_c.items()):
        seqs = collections.Counter(tuple(s for s in iv.question_slots if s != STOP) for iv in ivs)
        order = list(seqs.most_common(1)[0][0])
        share = {s: sum(s in iv.question_slots for iv in ivs) / len(ivs) for s in CANONICAL_SLOTS}
        required = [s for s in order if share[s] >= min_share]
        critical = [s for s in required if s in SAFETY_CRITICAL_SLOTS or s in SAFETY_CRITICAL_EXTRA_BY_COMPLAINT.get(c, ())]
        complaints[c] = {"n_train_interviews": len(ivs), "slot_order": order, "required": required,
                         "safety_critical": critical, "ontology_cc": COMPLAINT_TO_ONTOLOGY_CC[c]}
    return {"review_status": REVIEW_STATUS,
            "derived_from": "slots asked in >=95% of TRAINING-split recorded interviews for the complaint; "
                            "this reproduces the dataset template and is NOT a clinical definition of 'required'",
            "complaints": complaints}


def run_audit() -> dict[str, Any]:
    ivs = load_interviews()
    splits = split_interviews(ivs)
    integrity = assert_group_integrity(splits)

    seq_counts = collections.Counter(tuple(iv.question_slots) for iv in ivs)
    # next question given (asked set): how deterministic is it WITHOUT knowing anything about the patient?
    next_given_asked: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    next_given_asked_cc: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    n_steps = 0
    for iv in ivs:
        q = iv.question_slots
        for k in range(1, len(q)):
            next_given_asked[tuple(sorted(q[:k]))][q[k]] += 1
            next_given_asked_cc[(iv.complaint, tuple(q[:k]))][q[k]] += 1
            n_steps += 1
    def purity(table):
        return sum(c.most_common(1)[0][1] for c in table.values()) / n_steps
    ambiguous_states = {k: dict(v) for k, v in next_given_asked.items() if len(v) > 1}

    # answer entropy per (complaint, slot): can asking this question tell the clinician anything new?
    ent_rows, constant_pairs, total_pairs = [], 0, 0
    per_slot: dict[str, list[float]] = collections.defaultdict(list)
    by_c: dict[str, list[Interview]] = collections.defaultdict(list)
    for iv in ivs:
        by_c[iv.complaint].append(iv)
    for c, group in sorted(by_c.items()):
        for slot, fld in GOLD_FIELD_BY_SLOT.items():
            vals = [iv.gold.get(fld, "") for iv in group]
            if slot == "rad" and not any(vals):
                continue
            h = _entropy(vals)
            per_slot[slot].append(h)
            total_pairs += 1
            constant_pairs += len(set(vals)) == 1
            ent_rows.append({"complaint": c, "slot": slot, "distinct_answers": len(set(vals)), "entropy_bits": round(h, 3)})

    # triage: is it a pure function of severity?  (it would mean 'sev' alone explains the label)
    def triage_rule(iv):
        sev = int(iv.gold["severity_1_10"])
        if iv.gold["red_flag"] == "True":
            return "EMERGENCY"
        return "URGENT" if sev >= 8 else "ROUTINE"
    triage_match = sum(triage_rule(iv) == iv.gold["triage_priority"] for iv in ivs)

    # duplicate / leakage checks
    answer_sig = collections.defaultdict(list)
    for iv in ivs:
        sig = tuple(t["text"] for t in iv.turns if t["role"] == "PATIENT")
        answer_sig[sig].append(iv)
    dup_groups = [g for g in answer_sig.values() if len(g) > 1]
    cross_split_dups = sum(len({i.split for i in g}) > 1 for g in dup_groups)
    train_sigs = {sig for sig, g in answer_sig.items() if any(i.split == "train" for i in g)}
    test_overlap = sum(1 for iv in splits["test"] if tuple(t["text"] for t in iv.turns if t["role"] == "PATIENT") in train_sigs
                       and len(answer_sig[tuple(t["text"] for t in iv.turns if t["role"] == "PATIENT")]) > 1)

    ai_texts = collections.defaultdict(set)
    for iv in ivs:
        for t in iv.turns:
            if t["role"] == "AI":
                ai_texts[t["slot"]].add(t["text"])
    cc_utts = collections.defaultdict(set)
    for iv in ivs:
        cc_utts[iv.complaint].add(iv.cc_utterance)

    train = splits["train"]
    required = build_required_slots(train)
    CONFIG_DIR.mkdir(exist_ok=True)
    (CONFIG_DIR / "required_slots.json").write_text(json.dumps(required, indent=2, ensure_ascii=False), encoding="utf-8")

    complaint_counts = {c: {s: sum(iv.complaint == c and iv.split == s for iv in ivs) for s in ("train", "valid", "test")}
                        for c in sorted(by_c)}
    return {
        "source_files": {"interview_turns.csv": file_sha256(HIST_DIR / "interview_turns.csv"),
                         "structured_histories.csv": file_sha256(HIST_DIR / "structured_histories.csv")},
        "interviews": len(ivs), "turns": sum(len(i.turns) for i in ivs),
        "independent_units_note": "7,863 turns come from only 300 interviews / 300 patients; turns are correlated within an interview",
        "split_integrity": integrity, "jsonl_vs_csv": verify_jsonl_matches_csv(ivs),
        "distinct_question_orderings": len(seq_counts),
        "orderings": [{"count": n, "slots": list(s)} for s, n in seq_counts.most_common()],
        "next_slot_determinism": {
            "prediction_steps": n_steps,
            "accuracy_of_best_guess_from_asked_set_only": round(purity(next_given_asked), 4),
            "accuracy_of_best_guess_from_asked_sequence_plus_complaint": round(purity(next_given_asked_cc), 4),
            "states_where_asked_set_alone_is_ambiguous": len(ambiguous_states),
            "ambiguity_cause": "only 'rad' (asked for 172/300 interviews, determined by complaint) varies the order",
        },
        "ai_question_text_variants_per_slot": {k: len(v) for k, v in sorted(ai_texts.items())},
        "patient_cc_utterance_variants_per_complaint": {k: len(v) for k, v in sorted(cc_utts.items())},
        "answer_entropy": {
            "complaint_slot_pairs": total_pairs, "pairs_with_a_single_constant_answer": constant_pairs,
            "mean_entropy_bits_by_slot": {s: round(sum(v) / len(v), 3) for s, v in sorted(per_slot.items())},
            "rows": ent_rows},
        "triage_is_function_of_severity": {"match": triage_match, "of": len(ivs),
                                           "rule": "red_flag -> EMERGENCY; severity>=8 -> URGENT; else ROUTINE"},
        "duplicates": {"identical_patient_answer_sequences_groups": len(dup_groups),
                       "of_which_cross_split": cross_split_dups, "test_interviews_duplicated_in_train": test_overlap},
        "complaint_coverage": complaint_counts,
        "complaints_with_fewer_than_10_interviews": [c for c, n in {k: sum(v.values()) for k, v in complaint_counts.items()}.items() if n < 10],
        "script_distribution": dict(collections.Counter(iv.script for iv in ivs)),
        "required_slots_config": str((CONFIG_DIR / "required_slots.json").relative_to(Path(__file__).parents[2])),
        "conclusion": (
            "The recorded 'next question' is a fixed template: 2 question orderings (4 if the inserted RED_FLAG_ALERT turn is counted), "
            "differing only by whether 'rad' is asked, which the complaint fixes. "
            "A model that reproduces it learns the template, not a question-selection skill; top-1 accuracy is therefore "
            "uninformative and policy-level metrics (coverage, redundancy, turns, safety omissions) are reported instead."),
    }
