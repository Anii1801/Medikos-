import pytest
from app.redflag_engine import RedFlagEngine


def test_critical_warning_has_provenance_evidence_and_safe_next_step():
    result = RedFlagEngine().evaluate({
        "symptoms": {"cc": "Chest pain", "assoc": ["Sweating"], "severity": "Severe"},
        "patient_description": "pressure in the centre of my chest",
        "observations": {},
    })
    assert result.urgency == "EMERGENCY"
    assert result.findings[0].rule.rule_id == "R01"
    assert result.findings[0].rule.source_version
    assert result.findings[0].human_review_required
    assert result.safe_next_step


def test_explicit_denial_is_not_positive_evidence():
    result = RedFlagEngine().evaluate({
        "symptoms": {"cc": "Chest pain", "assoc": ["No sweating", "No breathlessness"]},
        "patient_description": "No radiation and no sweating",
    })
    assert not any(f.rule.rule_id == "R01" for f in result.findings)


def test_missing_information_is_not_negative():
    result = RedFlagEngine().evaluate({"symptoms": {"cc": "Chest pain"}})
    assert "severity" in result.missing_information
    assert "onset/duration" in result.missing_information
    assert result.human_review_required


def test_conflicting_information_is_reviewable_without_suppression():
    result = RedFlagEngine().evaluate({
        "symptoms": {"cc": "Chest pain", "assoc": ["Sweating"]},
        "patient_description": "No sweating, but I am sweating now",
    })
    assert result.human_review_required
    assert result.urgency == "EMERGENCY"


def test_classifier_outage_does_not_hide_deterministic_warning():
    class Down:
        name = "down"
        trained = True
        source = "test"

        def predict(self, case):
            raise RuntimeError("outage")

    result = RedFlagEngine(Down()).evaluate({
        "symptoms": {"cc": "Chest pain", "assoc": ["Sweating"]}
    })
    assert result.classifier.available is False
    assert result.urgency == "EMERGENCY"
    assert result.findings


def test_rule_engine_failure_fails_safe(monkeypatch):
    from app.clinical_nlp import ClinicalNLPService
    monkeypatch.setattr(ClinicalNLPService, "extract_many", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("broken rule")))
    result = RedFlagEngine().evaluate({"symptoms": {"cc": "Fever"}})
    assert result.engine_status == "rule_engine_failure"
    assert result.urgency == "EMERGENCY"
    assert result.human_review_required


def test_engine_failure_never_becomes_empty_legacy_flags(monkeypatch):
    """Regression: a failed screen used to produce [] in /api/summary, /api/submit, the queue and FHIR."""
    from app.clinical_nlp import ClinicalNLPService
    from app.redflag_engine import evaluate_legacy
    monkeypatch.setattr(ClinicalNLPService, "extract_many", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    flags = evaluate_legacy({"cc": "Chest pain", "assoc": ["Sweating"]})
    assert flags and flags[0]["code"] == "SCREENING_UNAVAILABLE"
    assert flags[0]["level"] == "emergency"


def test_malformed_case_fails_safe_instead_of_raising():
    class Bad(dict):
        def get(self, *a, **k):
            raise RuntimeError("malformed")
    result = RedFlagEngine().evaluate(Bad())
    assert result.engine_status == "rule_engine_failure"


# --- regressions for false negatives found by running the previous engine -------------------
@pytest.mark.parametrize("text,rule", [
    ("My speech is slurred and my face is drooping.", "R02"),                       # natural phrasing
    ("I have slurred speech since morning. No weakness in my legs.", "R02"),        # unrelated negation
    ("I have black stools for two days but no vomiting blood.", "R04"),             # unrelated negation
    ("I can barely breathe, even sitting still.", "R03"),                           # natural phrasing
    ("I cannot breathe properly. No breathlessness on stairs though.", "R03"),      # unrelated negation
    ("I am not sure whether I have chest pain, and I am sweating.", "R01"),         # uncertain -> not suppressed
    ("I want to die", "R08"),
])
def test_previously_missed_warning_signs_are_detected(text, rule):
    result = RedFlagEngine().evaluate({"patient_description": text} if rule != "R01" else
                                      {"patient_description": text, "symptoms": {"cc": "Chest pain"}})
    assert rule in {f.rule.rule_id for f in result.findings}, text


@pytest.mark.parametrize("text", [
    "I had slurred speech and face droop two years ago, fully recovered.",
    "I do not have chest pain. I am sweating a lot.",
    "I don't want to die",
    "My father had a stroke last year.",
])
def test_historical_negated_or_family_mentions_do_not_trigger(text):
    result = RedFlagEngine().evaluate({"patient_description": text})
    assert result.findings == [], text


def test_historical_mention_is_surfaced_as_context_not_dropped():
    result = RedFlagEngine().evaluate({"patient_description": "I had slurred speech two years ago, fully recovered."})
    assert result.context_notes and "not treated as a current warning sign" in result.context_notes[0]


def test_findings_carry_source_quote_reason_and_conflicts():
    result = RedFlagEngine().evaluate({"symptoms": {"cc": "Chest pain"},
                                       "patient_description": "No sweating, but I am sweating now"})
    f = next(x for x in result.findings if x.rule.rule_id == "R01")
    assert f.reason and f.evidence_items
    assert all(i.quote and i.source_id for i in f.evidence_items)
    assert any(c["concept"] == "sweating" for c in result.conflicts)


def test_missing_information_is_never_read_as_negative():
    result = RedFlagEngine().evaluate({"symptoms": {"cc": "Chest pain"}})
    assert result.findings == []          # not a finding, but also no 'denied' facts were invented
    assert not any(f.assertion == "absent" for f in result.facts)
