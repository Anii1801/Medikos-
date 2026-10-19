"""Fail-safe, provenance-aware red-flag detection.

This module is deliberately separate from disease diagnosis. The deterministic
rules are provisional until a clinician signs off on the local implementation;
the source guidance is recorded for every rule so that review is auditable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .clinical_nlp import ClinicalFact, ClinicalNLPService, get_service


SOURCE_GUIDANCE = {
    "name": "WHO Basic Emergency Care: approach to the acutely ill and injured",
    "version": "2018",
    "url": "https://www.who.int/publications/i/item/basic-emergency-care",
    "review_status": "provisional_pending_local_clinician_signoff",
}


class RuleMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str
    condition: str
    source: str
    source_version: str
    source_url: str
    target_population: str
    review_status: str


class EvidenceItem(BaseModel):
    """One piece of evidence behind a finding, traceable to its source statement."""
    model_config = ConfigDict(extra="forbid")
    concept: str
    quote: str                       # the original clause, patient/document wording
    source_id: str
    source_type: str                 # patient | document | observation
    assertion: str                   # present | uncertain
    temporal: str | None = None
    reason: str
    uncertainty_note: str | None = None


class RedFlagFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule: RuleMetadata
    urgency: str
    message: str
    supporting_evidence: list[str]
    missing_information: list[str]
    human_review_required: bool = True
    safe_next_step: str
    reason: str = ""
    evidence_items: list[EvidenceItem] = Field(default_factory=list)


class ClassifierResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    available: bool
    score: float | None = Field(default=None, ge=0, le=1)
    model: str
    trained: bool
    source: str
    error: str | None = None


class RedFlagResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[RedFlagFinding]
    missing_information: list[str]
    urgency: str
    human_review_required: bool
    safe_next_step: str
    classifier: ClassifierResult
    engine_status: str
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    context_notes: list[str] = Field(default_factory=list)
    facts: list[ClinicalFact] = Field(default_factory=list)

    def legacy_flags(self) -> list[dict[str, str]]:
        """Shape consumed by summary/FHIR/queue. A failed screen must NEVER look like 'no flags'."""
        if self.engine_status != "ok":
            return [{"code": "SCREENING_UNAVAILABLE", "level": "emergency",
                     "msg": "Red-flag screening could not be completed. Treat this patient as UNSCREENED "
                            "and obtain immediate clinician review."}]
        return [{"code": f.rule.rule_id, "level": f.urgency.lower(), "msg": f.message} for f in self.findings]


class ClassifierAdapter(Protocol):
    name: str
    trained: bool
    source: str

    def predict(self, case: dict[str, Any]) -> float:
        """Return a probability-like score in [0, 1]."""


@dataclass(frozen=True)
class UnavailableClassifier:
    name: str = "unavailable"
    trained: bool = False
    source: str = "No classifier trained or provenance-verified"

    def predict(self, case: dict[str, Any]) -> float:
        raise RuntimeError("No classifier is configured")


def _rule(rule_id: str, condition: str, target: str = "Adults and adolescents presenting to outpatient triage") -> RuleMetadata:
    return RuleMetadata(rule_id=rule_id, condition=condition, source=SOURCE_GUIDANCE["name"],
                        source_version=SOURCE_GUIDANCE["version"], source_url=SOURCE_GUIDANCE["url"],
                        target_population=target, review_status=SOURCE_GUIDANCE["review_status"])


RULES = {
    "R01": _rule("R01", "Chest pain with radiation, sweating, or breathlessness"),
    "R02": _rule("R02", "Sudden focal neurological deficit or speech/facial change"),
    "R03": _rule("R03", "Severe breathlessness or inability to speak full sentences"),
    "R04": _rule("R04", "Haematemesis or melaena"),
    "R05": _rule("R05", "Severe symptom burden (8/10 or greater)"),
    "R06": _rule("R06", "Fever with rash or bleeding features"),
    "R07": _rule("R07", "Pregnancy with bleeding or severe abdominal pain", "People who may be pregnant"),
    "R08": _rule("R08", "Self-harm thoughts or immediate suicide risk"),
}

_UNCERTAIN_NOTE = "Patient expressed uncertainty about this item - confirm with the patient."
# Concepts whose *historical* mention is recorded as context rather than ignored.
_CONTEXT_CONCEPTS = ("chest_pain", "speech_disturbance", "facial_droop", "focal_weakness", "respiratory_distress",
                     "vomiting_blood", "melaena", "self_harm")


def _values(case: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for group in ("symptoms", "patient_description", "reports", "observations"):
        item = case.get(group, {})
        if isinstance(item, dict):
            values.update({str(k): " ".join(map(str, v)) if isinstance(v, list) else str(v or "") for k, v in item.items()})
        elif item:
            values[group] = str(item)
    return values


def _sources(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Every field/statement is its own source so evidence can cite exactly where it came from."""
    types = {"reports": "document", "observations": "observation"}
    out: list[dict[str, Any]] = []
    for group in ("symptoms", "patient_description", "reports", "observations"):
        item = case.get(group, {})
        if isinstance(item, dict):
            for k, v in item.items():
                if str(k).startswith("_") or isinstance(v, bool):
                    continue
                out.append({"source_id": f"{group}.{k}", "source_type": types.get(group, "patient"), "text": v})
        elif item:
            out.append({"source_id": group, "source_type": types.get(group, "patient"), "text": item})
    return out


def _hits(facts: list[ClinicalFact], *concepts: str) -> list[ClinicalFact]:
    """Current (present or uncertain) patient/document mentions. Absent, historical,
    hypothetical and family mentions are deliberately excluded."""
    return [f for f in facts if f.concept in concepts and f.experiencer == "patient"
            and f.assertion in ("present", "uncertain") and f.source_type != "observation"]


def _items(hits: list[ClinicalFact], reason: str, conflicts: list[dict[str, Any]]) -> list[EvidenceItem]:
    conflicted = {c["concept"] for c in conflicts}
    items = []
    for f in hits:
        notes = []
        if f.assertion == "uncertain":
            notes.append(_UNCERTAIN_NOTE)
        if f.concept in conflicted:
            notes.append("Another statement denies this item - conflict left unresolved for clinician review.")
        items.append(EvidenceItem(concept=f.concept, quote=f.original_text, source_id=f.source_id, source_type=f.source_type,
                                  assertion=f.assertion, temporal=f.temporal.text if f.temporal else None,
                                  reason=reason, uncertainty_note=" ".join(notes) or None))
    return items


def _finding(rule_id: str, urgency: str, message: str, hits: list[ClinicalFact], reason: str,
             missing: list[str], step: str, conflicts: list[dict[str, Any]]) -> RedFlagFinding:
    items = _items(hits, reason, conflicts)
    return RedFlagFinding(rule=RULES[rule_id], urgency=urgency, message=message, reason=reason,
                          supporting_evidence=[f"{i.source_id}: {i.quote}" for i in items], evidence_items=items,
                          missing_information=missing, safe_next_step=step)


class RedFlagEngine:
    def __init__(self, classifier: ClassifierAdapter | None = None, nlp: ClinicalNLPService | None = None):
        self.classifier = classifier or UnavailableClassifier()
        self.nlp = nlp or get_service()

    def evaluate(self, case: dict[str, Any]) -> RedFlagResult:
        missing: list[str] = []
        try:
            values = _values(case)
            facts = self.nlp.extract_many(_sources(case))
            conflicts = self.nlp.find_conflicts(facts)
            findings: list[RedFlagFinding] = []
            severity = values.get("severity", values.get("sev", ""))
            if not severity:
                missing.append("severity")
            if not values.get("duration") and not values.get("dur"):
                missing.append("onset/duration")

            chest = _hits(facts, "chest_pain")
            assoc = _hits(facts, "sweating", "breathlessness", "respiratory_distress", "radiation_arm_jaw", "pressure_heaviness")
            if chest and assoc:
                findings.append(_finding("R01", "EMERGENCY", "Possible acute coronary syndrome warning sign", chest + assoc,
                    "Chest pain reported together with an associated warning feature (sweating, breathlessness, radiation or pressure).",
                    [] if _hits(facts, "radiation_arm_jaw") else ["radiation pattern", "exertional trigger"],
                    "Immediate clinician assessment; follow local chest-pain emergency pathway.", conflicts))
            neuro = _hits(facts, "speech_disturbance", "facial_droop", "focal_weakness")
            if neuro:
                findings.append(_finding("R02", "EMERGENCY", "Possible acute focal neurological deficit", neuro,
                    "Speech, facial or one-sided limb change is reported as current.", ["time last known well"],
                    "Immediate clinician assessment; activate local stroke pathway.", conflicts))
            resp = _hits(facts, "respiratory_distress")
            if resp:
                findings.append(_finding("R03", "EMERGENCY", "Possible respiratory distress", resp,
                    "Severe breathing difficulty or inability to speak in full sentences is reported as current.",
                    ["oxygen saturation", "respiratory rate"], "Immediate clinician assessment and airway/breathing check.", conflicts))
            gi = _hits(facts, "vomiting_blood", "melaena")
            if gi:
                findings.append(_finding("R04", "EMERGENCY", "Possible gastrointestinal bleeding", gi,
                    "Vomiting blood or black/bloody stools is reported as current.",
                    ["haemodynamic observations", "anticoagulant use"], "Immediate clinician assessment for bleeding and shock.", conflicts))
            try:
                severity_value = float(re.search(r"\d+(?:\.\d+)?", severity).group()) if severity else None
            except (AttributeError, ValueError):
                severity_value = None
            if severity_value is not None and severity_value >= 8:
                f = RedFlagFinding(rule=RULES["R05"], urgency="URGENT", message="Severe symptom burden reported",
                    reason="Self-reported severity is 8/10 or higher.", supporting_evidence=[f"severity: {severity}"],
                    evidence_items=[EvidenceItem(concept="severity", quote=severity, source_id="symptoms.severity",
                                                 source_type="patient", assertion="present", reason="Self-reported severity is 8/10 or higher.")],
                    missing_information=["vital signs", "functional impact"],
                    safe_next_step="Prioritise clinician review; do not infer a diagnosis from severity alone.")
                findings.append(f)
            fever, bleed_rash = _hits(facts, "fever"), _hits(facts, "rash", "bleeding")
            if fever and bleed_rash:
                findings.append(_finding("R06", "URGENT", "Fever with rash or bleeding warning sign", fever + bleed_rash,
                    "Fever reported together with a rash or bleeding.", ["temperature", "hydration status"],
                    "Prompt clinician assessment and local infectious/bleeding evaluation.", conflicts))
            preg = _hits(facts, "pregnancy")
            preg_sign = _hits(facts, "vaginal_bleeding", "bleeding", "severe_abdominal_pain")
            if preg and preg_sign:
                findings.append(_finding("R07", "EMERGENCY", "Possible obstetric emergency warning sign", preg + preg_sign,
                    "Possible pregnancy reported together with bleeding or severe abdominal pain.",
                    ["gestational age", "pain severity", "vital signs"],
                    "Immediate clinician assessment in an appropriate obstetric pathway.", conflicts))
            harm = _hits(facts, "self_harm")
            if harm:
                findings.append(_finding("R08", "EMERGENCY", "Self-harm or suicide warning sign reported", harm,
                    "Thoughts of self-harm or wanting to die are reported.", ["immediate safety status", "access to means"],
                    "Immediate in-person safety assessment; do not leave the person alone.", conflicts))
            notes = [f"Historical mention of '{f.concept.replace('_', ' ')}' (\"{f.original_text}\", {f.source_id}) was not "
                     "treated as a current warning sign. Clinician to confirm it is not ongoing."
                     for f in facts if f.assertion == "historical" and f.concept in _CONTEXT_CONCEPTS and f.experiencer == "patient"]
        except Exception as exc:  # any failure inside screening is a failed screen, never "no flags"
            return self._failure(exc, missing)
        try:
            score = self.classifier.predict(case)
            classifier = ClassifierResult(available=True, score=score, model=self.classifier.name,
                                          trained=self.classifier.trained, source=self.classifier.source)
        except Exception as exc:
            classifier = ClassifierResult(available=False, model=self.classifier.name,
                                          trained=self.classifier.trained, source=self.classifier.source, error=str(exc))
        urgency = "EMERGENCY" if any(f.urgency == "EMERGENCY" for f in findings) else "URGENT" if findings else "ROUTINE"
        if classifier.available and classifier.score is not None and classifier.score >= 0.8 and urgency == "ROUTINE":
            urgency = "URGENT"
            missing.append("classifier-supported risk requires clinician review")
        return RedFlagResult(findings=findings, missing_information=sorted(set(missing)),
                             urgency=urgency, human_review_required=True,
                             safe_next_step="Clinician review required; no warning may be suppressed by classifier score.",
                             classifier=classifier, engine_status="ok", conflicts=conflicts,
                             context_notes=sorted(set(notes)), facts=facts)

    def _failure(self, exc: Exception, missing: list[str]) -> RedFlagResult:
        classifier = ClassifierResult(available=False, model=self.classifier.name, trained=self.classifier.trained,
                                      source=self.classifier.source, error=type(exc).__name__)
        return RedFlagResult(findings=[], missing_information=sorted(set(missing + ["rule-engine result"])),
                             urgency="EMERGENCY", human_review_required=True,
                             safe_next_step="Stop automated triage and obtain immediate clinician review.",
                             classifier=classifier, engine_status="rule_engine_failure")


def rules_manifest() -> list[dict[str, Any]]:
    return [rule.model_dump() for rule in RULES.values()]


def evaluate_legacy(answers: dict[str, Any]) -> list[dict[str, str]]:
    """Compatibility shape for existing summary/FHIR callers."""
    case = {"symptoms": answers, "patient_description": answers.get("free", "")}
    flags = RedFlagEngine().evaluate(case).legacy_flags()
    return [{**flag, "code": "ACS" if flag["code"] == "R01" else flag["code"]} for flag in flags]
