"""Load the interview dataset and reconstruct leakage-safe PRE-ANSWER states.

Splits are the dataset's own patient-level ``split`` column (400/50/50 patients;
the 300 interviews fall 240/30/30). No random re-split is made, so results are
comparable with every other module that uses the same split.
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.adaptive.schema import (COMPLAINT_TO_ONTOLOGY_CC, DATASET_AI_SLOT_TO_CLASS, NON_QUESTION_SLOTS,
                                 CANONICAL_SLOTS)
from app.adaptive.features import script_of, normalise_text
from app.datasets import DATASET_ROOT

HIST_DIR = DATASET_ROOT / "01_history_interview"


@dataclass
class Interview:
    interview_id: str
    patient_id: str
    split: str
    complaint: str                      # gold English complaint label (structured_histories.csv)
    turns: list[dict[str, Any]]
    gold: dict[str, str] = field(default_factory=dict)

    @property
    def question_slots(self) -> list[str]:
        """Question slots the recorded interview asked, in order (RED_FLAG_ALERT excluded, cc included, STOP last)."""
        return [DATASET_AI_SLOT_TO_CLASS[t["slot"]] for t in self.turns
                if t["role"] == "AI" and t["slot"] not in NON_QUESTION_SLOTS]

    @property
    def cc_utterance(self) -> str:
        return next((t["text"] for t in self.turns if t["role"] == "PATIENT" and t["slot"] == "chief_complaint"), "")

    @property
    def script(self) -> str:
        return script_of(normalise_text(self.cc_utterance))

    def app_cc_text(self) -> str:
        """What the live app would hold for the complaint: the ontology option label, or the typed text for 'Other'."""
        option = COMPLAINT_TO_ONTOLOGY_CC[self.complaint]
        return self.complaint if option == "Other" else option


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_interviews() -> list[Interview]:
    turns = _read(HIST_DIR / "interview_turns.csv")
    histories = {r["interview_id"]: r for r in _read(HIST_DIR / "structured_histories.csv")}
    by_id: dict[str, list[dict[str, Any]]] = {}
    meta: dict[str, tuple[str, str]] = {}
    for r in turns:
        by_id.setdefault(r["interview_id"], []).append({**r, "turn": int(r["turn"])})
        meta[r["interview_id"]] = (r["patient_id"], r["split"])
    out = []
    for iid, tt in by_id.items():
        tt.sort(key=lambda x: x["turn"])
        h = histories[iid]
        if h["split"] != meta[iid][1]:
            raise ValueError(f"split mismatch for {iid}")
        out.append(Interview(iid, meta[iid][0], meta[iid][1], h["chief_complaint"], tt, h))
    return sorted(out, key=lambda i: i.interview_id)


def verify_jsonl_matches_csv(interviews: list[Interview]) -> dict[str, Any]:
    """interviews.jsonl is a re-packaging of the CSV; confirm it, so the data is not counted twice."""
    rows = [json.loads(l) for l in (HIST_DIR / "interviews.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    by = {i.interview_id: i for i in interviews}
    mismatched = 0
    for r in rows:
        a = [(t["turn"], t["role"], t["slot"], t["text"]) for t in r["turns"]]
        b = [(t["turn"], t["role"], t["slot"], t["text"]) for t in by[r["interview_id"]].turns]
        mismatched += a != b
    return {"jsonl_interviews": len(rows), "identical_to_csv": len(rows) - mismatched, "mismatched": mismatched}


@dataclass(frozen=True)
class Example:
    interview_id: str
    split: str
    complaint: str
    script: str
    view: str
    state: dict[str, Any]
    target: str


def pre_answer_examples(iv: Interview, view: str = "recorded") -> list[Example]:
    """One example per recorded question after the first.

    The state is built ONLY from turns that precede the question being predicted.
    ``view='recorded'`` uses the patient's own wording of the complaint;
    ``view='app_label'`` uses the ontology label the live app would hold.
    The first question (cc) is excluded: with an empty state the rule 'ask the chief complaint first' decides.
    """
    examples: list[Example] = []
    asked: list[str] = []
    cc_text = ""
    for turn in iv.turns:                      # strictly chronological
        if turn["role"] == "PATIENT" and turn["slot"] == "chief_complaint":
            cc_text = turn["text"] if view == "recorded" else iv.app_cc_text()
        elif turn["role"] == "AI" and turn["slot"] not in NON_QUESTION_SLOTS:
            cls_ = DATASET_AI_SLOT_TO_CLASS[turn["slot"]]
            if cls_ != "cc":
                examples.append(Example(iv.interview_id, iv.split, iv.complaint, iv.script, view,
                                        {"cc_text": cc_text, "asked": list(asked)}, cls_))
            if cls_ in CANONICAL_SLOTS:
                asked.append(cls_)
    return examples


def split_interviews(interviews: list[Interview]) -> dict[str, list[Interview]]:
    out: dict[str, list[Interview]] = {"train": [], "valid": [], "test": []}
    for iv in interviews:
        out[iv.split].append(iv)
    return out


def assert_group_integrity(splits: dict[str, list[Interview]]) -> dict[str, Any]:
    """No patient and no interview may appear in two splits."""
    seen_p: dict[str, str] = {}
    for name, ivs in splits.items():
        for iv in ivs:
            if seen_p.setdefault(iv.patient_id, name) != name:
                raise AssertionError(f"patient {iv.patient_id} appears in {seen_p[iv.patient_id]} and {name}")
    return {n: {"interviews": len(v), "patients": len({i.patient_id for i in v})} for n, v in splits.items()}
