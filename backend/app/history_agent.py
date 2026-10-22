"""Stateful adaptive history-taking with a deterministic safety policy.

JEV is intentionally not hard-coded: no verifiable identifier, provider,
licence, or weights were found in the supplied project. A future adapter must
return the validated question contract and cannot change red-flag decisions.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from . import hindi_nlp, ontology
from .adaptive.ranker import LearnedSlotRanker, get_default_ranker
from .adaptive.schema import MANDATORY_FIRST, STOP, TARGET_CLASSES, canonical_slots_for

POLICIES = ("ontology", "learned")


def default_policy() -> str:
    """Question-selection policy for new sessions. The reviewed ontology policy is the default;
    the learned ranker is opt-in (MEDIKIOSK_QUESTION_POLICY=learned) until it is shown to beat it."""
    value = os.environ.get("MEDIKIOSK_QUESTION_POLICY", "ontology").strip().lower()
    return value if value in POLICIES else "ontology"


class QuestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: dict[str, Any] | None
    answered: int = Field(ge=0)
    total: int = Field(ge=0)
    complete: bool
    red_flags: list[dict[str, Any]]
    session_id: str
    adapter: str
    trained: bool
    source: str
    missing_fields: list[str]
    uncertainty: list[str]
    conflicts: list[str]
    confidence: float = Field(ge=0, le=1)
    decision_route: str
    safety_validated: bool
    review_required: bool
    policy: str = "ontology"                 # requested selection policy
    selection_basis: str = "ontology_default"  # why THIS question was chosen
    fallback_reason: str | None = None       # set when the learned policy deferred to the ontology policy
    ranker_version: str | None = None


class LLMAdapter(Protocol):
    name: str
    trained: bool
    source: str

    def generate_question(self, *, state: dict[str, Any], policy_question: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class DevelopmentAdapter:
    name: str = "deterministic-development"
    trained: bool = False
    source: str = "ontology policy; no model prompting"

    def generate_question(self, *, state: dict[str, Any], policy_question: dict[str, Any]) -> dict[str, Any]:
        return policy_question


def _text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value or "")


NEGATION_RE = re.compile(r"\b(no|not|never|none|nothing|nowhere|nil|without|denies|denied|don't|doesn't|didn't)\b", re.I)
UNCERTAINTY_RE = re.compile(
    r"\b(unknown|unsure|uncertain|maybe|possibly|not sure|can't remember|cannot remember|decline|prefer not)\b",
    re.I,
)


def classify_answer(value: Any) -> str:
    """reported / negative / uncertain, English and Hindi/Hinglish. Uncertainty from either language wins, then
    negation: a missed 'पता नहीं' (don't know) read as 'reported' would be recorded as a positive finding."""
    text = _text(value)
    hi = hindi_nlp.classify_answer_hi(text)
    en = "uncertain" if UNCERTAINTY_RE.search(text) else "negative" if NEGATION_RE.search(text) else "reported"
    if "uncertain" in (en, hi):
        return "uncertain"
    if "negative" in (en, hi):
        return "negative"
    return "reported"


def merge_answer(state: dict[str, Any], field: str, value: Any) -> tuple[dict[str, Any], list[str], list[str]]:
    """Merge one answer while retaining uncertainty and conflicting history."""
    answers = dict(state.get("answers", {}))
    history = list(state.get("answer_history", []))
    conflicts = list(state.get("conflicts", []))
    uncertainty = list(state.get("uncertainty", []))
    previous = answers.get(field)
    if previous is not None and previous != value and classify_answer(previous) != "uncertain":
        conflicts.append(field)
    answers[field] = value
    status = classify_answer(value)
    if status == "uncertain" and field not in uncertainty:
        uncertainty.append(field)
    slot_state = dict(state.get("slot_state", {}))
    attempts = int(slot_state.get(field, {}).get("attempts", 0)) + 1
    slot_state[field] = {
        "value": value,
        "status": status,
        "source": "patient",
        "provenance": {"source_type": "patient", "source_id": "interview"},
        "attempts": attempts,
        "last_attempt": len(history) + 1,
    }
    history.append({"field": field, "value": value, "status": status, "source": "patient",
                    "attempt": attempts})
    return (
        {**state, "answers": answers, "answer_history": history, "conflicts": sorted(set(conflicts)),
         "uncertainty": sorted(set(uncertainty)), "slot_state": slot_state},
        sorted(set(conflicts)),
        sorted(set(uncertainty)),
    )


def extract_clinical_state(state: dict[str, Any]) -> dict[str, Any]:
    """Separate answer classification from follow-up question selection."""
    answers = state.get("answers", {})
    return {
        "answers": dict(answers),
        "answer_status": {item["field"]: item["status"] for item in state.get("answer_history", [])},
        "missing_fields": [q["id"] for q in ontology.applicable(answers) if q["id"] not in answers],
        "uncertainty": list(state.get("uncertainty", [])),
        "conflicts": list(state.get("conflicts", [])),
    }


def confidence_and_route(clinical_state: dict[str, Any], red_flags: list[dict[str, Any]]) -> tuple[float, str, bool]:
    """Conservative confidence gate; it never downgrades a safety warning."""
    missing = len(clinical_state["missing_fields"])
    uncertainty = len(clinical_state["uncertainty"])
    conflicts = len(clinical_state["conflicts"])
    confidence = max(0.0, min(1.0, 1.0 - 0.12 * missing - 0.18 * uncertainty - 0.22 * conflicts))
    if red_flags:
        return confidence, "safety_review", True
    if conflicts or uncertainty or confidence < 0.55:
        if not (conflicts or uncertainty) and missing:
            return confidence, "adaptive_follow_up", False
        return confidence, "human_review", True
    if missing:
        return confidence, "adaptive_follow_up", False
    return confidence, "complete_review", False


@dataclass
class HistoryTakingAgent:
    adapter: LLMAdapter = field(default_factory=DevelopmentAdapter)
    budget: int = 30
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    policy: str = field(default_factory=default_policy)
    ranker: LearnedSlotRanker | None = None      # injected by tests/evaluation; else the default checkpoint is loaded lazily
    state: dict[str, Any] = field(default_factory=lambda: {
        "answers": {}, "asked_questions": [], "answer_history": [], "conflicts": [], "uncertainty": [],
        "slot_state": {},
    })

    def answer(self, field: str, value: Any) -> QuestionResponse:
        self.state, conflicts, uncertainty = merge_answer(self.state, field, value)
        if self.state.get("current_question_id") == field:
            self.state.pop("current_question_id", None)
        return self.next_response(conflicts=conflicts, uncertainty=uncertainty)

    def next_response(self, answers: dict[str, Any] | None = None, *, conflicts: list[str] | None = None,
                      uncertainty: list[str] | None = None) -> QuestionResponse:
        if answers is not None:
            self.state["answers"] = dict(answers)
        clinical_state = extract_clinical_state(self.state)
        raw = ontology.next_question(dict(clinical_state["answers"]))
        question = raw["question"]
        asked = list(self.state.get("asked_questions", []))
        if question and question["id"] in asked:
            # Repeated GETs must return the current unanswered question, not skip it.
            if not (question["id"] == self.state.get("current_question_id") and question["id"] not in self.state["answers"]):
                question = next((ontology.public(q) for q in ontology.applicable(self.state["answers"])
                                 if q["id"] not in asked and q["id"] not in self.state["answers"]), None)
        basis, fallback_reason, ranker_version = "ontology_default", None, None
        if self.policy == "learned" and question is not None:
            question, basis, fallback_reason, ranker_version = self._learned_select(question, asked)
        if question and len(asked) >= self.budget:
            question = None
            raw["complete"] = True
        if question:
            proposed = self.adapter.generate_question(state=self.state, policy_question=question)
            question = self._validate(proposed, question)
            if question["id"] not in asked:
                asked.append(question["id"])
                self.state["asked_questions"] = asked
            self.state["current_question_id"] = question["id"]
        else:
            self.state.pop("current_question_id", None)
        red_flags = ontology.red_flags(self.state["answers"])
        confidence, route, review_required = confidence_and_route(clinical_state, red_flags)
        learned_used = basis == "learned_rank"
        response = QuestionResponse(
            question=question, answered=raw["answered"], total=raw["total"], complete=question is None,
            red_flags=red_flags, session_id=self.session_id,
            adapter=self.adapter.name, trained=self.adapter.trained or learned_used,
            source=(f"learned slot ranker {ranker_version} (synthetic-data checkpoint) ranks within a deterministic safety layer"
                    if learned_used else self.adapter.source),
            policy=self.policy, selection_basis=basis if question is not None else "complete",
            fallback_reason=fallback_reason, ranker_version=ranker_version,
            missing_fields=clinical_state["missing_fields"],
            uncertainty=sorted(set(uncertainty or self.state.get("uncertainty", []))),
            conflicts=sorted(set(conflicts or self.state.get("conflicts", []))),
            confidence=confidence, decision_route=route, safety_validated=True,
            review_required=review_required,
        )
        return response

    # ------------------------------------------------------------------ learned policy
    def _asked_canonical_slots(self, answers: dict[str, Any], asked: list[str]) -> list[str]:
        """Canonical slots covered by questions the RANKER chose, in order (pre-answer state only).

        Questions the safety layer pulled forward are left out: the model was trained on template prefixes
        and has never seen 'safety questions answered but history-taking not started'. Without this the
        model mistakes that state for 'late in the interview' and defers duration / severity to the end.
        The pulled-forward slots are simply skipped when the model asks for them (they are not candidates)."""
        pulled = set(MANDATORY_FIRST.get(answers.get("cc"), ()))
        order = [qid for qid in asked if qid in answers and qid not in pulled]
        order += [q["id"] for q in ontology.QUESTIONS if q["id"] in answers and q["id"] not in order and q["id"] not in pulled]
        slots: list[str] = []
        for qid in order:
            for slot in canonical_slots_for(qid):
                if slot not in slots:
                    slots.append(slot)
        return slots

    def _learned_select(self, default_q: dict[str, Any], asked: list[str]):
        """Choose among ELIGIBLE ontology questions. Returns (question, basis, fallback_reason, ranker_version).

        Order of authority: (1) structural questions (cc / cc_text) and the question currently on screen,
        (2) the clinician-configurable mandatory safety questions for the complaint, (3) the learned ranking,
        (4) the ontology order whenever the ranker cannot be trusted. The model never removes a question."""
        answers = self.state["answers"]
        current = self.state.get("current_question_id")
        if current and current not in answers and current in ontology.BY_ID:
            return ontology.public(ontology.BY_ID[current]), "ontology_default", None, None  # keep the question on screen
        cc = answers.get("cc")
        cc_text = answers.get("cc_text") if cc == "Other" else cc
        if not cc or not cc_text:
            return default_q, "structural", None, None                                    # cc / cc_text are never model-ranked
        eligible = [q for q in ontology.applicable(answers) if q["id"] not in answers and q["id"] not in asked]
        if not eligible:
            return default_q, "ontology_default", None, None
        for qid in MANDATORY_FIRST.get(cc, ()):
            hit = next((q for q in eligible if q["id"] == qid), None)
            if hit:
                return ontology.public(hit), "safety_mandatory", None, None
        ranker = self.ranker or get_default_ranker()
        if ranker is None:
            return default_q, "fallback", "ranker_unavailable", None
        candidates = sorted({s for q in eligible for s in canonical_slots_for(q["id"])} & set(TARGET_CLASSES) - {STOP})
        if not candidates:                       # only non-schema questions (progression, ROS, free text...) remain
            return default_q, "ontology_default", None, ranker.version
        try:
            result = ranker.rank({"cc_text": str(cc_text), "asked": self._asked_canonical_slots(answers, asked)}, candidates)
        except Exception:                                                                    # never let a model error break an interview
            return default_q, "fallback", "ranker_error", ranker.version
        if not result.usable:
            return default_q, "fallback", result.fallback_reason, ranker.version
        position = {slot: i for i, (slot, _) in enumerate(result.ranked)}

        def score(q: dict[str, Any]) -> float:
            pos = [position[s] for s in canonical_slots_for(q["id"]) if s in position]
            return -min(pos) if pos else float("-inf")      # non-schema questions are never preferred over schema ones
        best = max(eligible, key=score)   # max() keeps the first (ontology-order) question on ties
        return ontology.public(best), "learned_rank", None, ranker.version

    def to_dict(self) -> dict[str, Any]:
        return {"session_id": self.session_id, "budget": self.budget, "state": self.state, "policy": self.policy,
                "adapter": self.adapter.name, "trained": self.adapter.trained, "source": self.adapter.source}

    @classmethod
    def from_dict(cls, data: dict[str, Any], adapter: LLMAdapter | None = None) -> "HistoryTakingAgent":
        policy = data.get("policy")
        agent = cls(adapter=adapter or DevelopmentAdapter(), budget=int(data.get("budget", 30)),
                    session_id=str(data.get("session_id") or uuid.uuid4()),
                    policy=policy if policy in POLICIES else "ontology")
        agent.state = data.get("state") or agent.state
        agent.state.setdefault("slot_state", {})
        return agent

    @staticmethod
    def _validate(candidate: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
        required = ("id", "section", "type", "en", "hi", "options")
        if not isinstance(candidate, dict) or any(key not in candidate for key in required):
            return fallback
        if candidate["id"] != fallback["id"] or candidate["type"] != fallback["type"]:
            return fallback
        if not all(isinstance(candidate[key], str) and candidate[key].strip() for key in ("en", "hi")):
            return fallback
        if not isinstance(candidate["options"], list):
            return fallback
        return {**fallback, "en": candidate["en"], "hi": candidate["hi"]}


class AdaptiveHistoryTakingAgent(HistoryTakingAgent):
    """Explicit contract for the safety-first adaptive history baseline."""

    pass


DEFAULT_AGENT = HistoryTakingAgent()
