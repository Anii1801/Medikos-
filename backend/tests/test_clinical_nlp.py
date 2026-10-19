"""Unit tests for ClinicalNLPService.

These are hand-written behavioural cases (synthetic sentences) for software testing only.
They are NOT an accuracy benchmark and say nothing about clinical performance.
"""
import pytest
from app.clinical_nlp import ClinicalNLPService, parse_temporal, normalise_dose

S = ClinicalNLPService()


def facts(text, concept=None, source_type="patient"):
    out = S.extract(text, source_id="t", source_type=source_type)
    return [f for f in out if concept is None or f.concept == concept]


@pytest.mark.parametrize("text,assertion", [
    ("I have chest pain.", "present"),
    ("I do not have chest pain.", "absent"),
    ("I had chest pain last year.", "historical"),
    ("I am not sure whether I have chest pain.", "uncertain"),
    ("My report says chest pain was previously documented.", "historical"),
])
def test_five_statements_from_the_spec_are_not_merged(text, assertion):
    fs = facts(text, "chest_pain")
    assert len(fs) == 1 and fs[0].assertion == assertion


def test_only_the_first_statement_is_a_current_positive_symptom():
    texts = ["I have chest pain.", "I do not have chest pain.", "I had chest pain last year.",
             "I am not sure whether I have chest pain.", "My report says chest pain was previously documented."]
    current = [t for t in texts if any(f.assertion == "present" for f in facts(t, "chest_pain"))]
    assert current == ["I have chest pain."]


def test_negation_scope_is_limited_to_its_clause():
    fs = {f.concept: f.assertion for f in facts("I have black stools for two days but no vomiting blood.")}
    assert fs["melaena"] == "present" and fs["vomiting_blood"] == "absent"
    assert "vomiting" not in fs or fs["vomiting"] != "absent"   # no spurious 'no vomiting' from 'no vomiting blood'


def test_negated_list_covers_each_item():
    fs = {f.concept: f.assertion for f in facts("No fever, rash or cough.")}
    assert fs == {"fever": "absent", "rash": "absent", "cough": "absent"}


def test_missing_information_creates_no_fact():
    assert facts("I have a headache.", "chest_pain") == []
    assert facts("") == [] and S.extract(None, source_id="x") == []


def test_family_history_is_not_a_patient_symptom():
    f = facts("My father had a stroke.", "stroke_history")[0]
    assert f.experiencer == "family"


def test_hypothetical_is_not_present():
    assert facts("I am worried about chest pain.", "chest_pain")[0].assertion == "hypothetical"


def test_recent_days_ago_is_current_but_years_ago_is_historical():
    assert facts("I had chest pain 2 days ago.", "chest_pain")[0].assertion == "present"
    assert facts("I had chest pain 3 years ago.", "chest_pain")[0].assertion == "historical"
    assert facts("The chest pain started 3 years ago and continues.", "chest_pain")[0].assertion == "present"


def test_provenance_fields_and_span():
    text = "Today I feel fine. I have chest pain."
    f = S.extract(text, source_id="msg-7", source_type="patient")[0]
    assert f.source_id == "msg-7" and f.original_text and f.verification_status == "unverified"
    assert text[f.span[0]:f.span[1]].lower().startswith("chest pain")
    assert f.confidence is None            # uncalibrated rule baseline must not invent confidence
    assert f.method == "rule_v1"


def test_original_wording_is_preserved_with_curly_apostrophe():
    t = "I can\u2019t breathe properly"
    f = facts(t, "respiratory_distress")[0]
    assert "\u2019" in f.original_text


@pytest.mark.parametrize("text,days,approx", [
    ("for 3 days", 3.0, False), ("for two weeks", 14.0, False), ("since yesterday", 1.0, True),
    ("2 years ago", 730.0, False), ("for a few days", None, True), ("for the last 6 hours", 0.25, False),
])
def test_temporal_normalisation(text, days, approx):
    t = parse_temporal(text)
    assert t is not None and t.duration_days == days and t.approximate == approx


def test_medication_dose_and_unit_normalisation():
    fs = facts("I take metformin 500 mg twice daily and levothyroxine 100 mcg od.")
    med = {f.concept: f.normalized_value for f in fs if f.field == "medication"}
    assert med["metformin"]["dose_mg"] == 500 and med["metformin"]["times_per_day"] == 2
    assert med["levothyroxine"]["dose_mg"] == pytest.approx(0.1)
    assert normalise_dose(1, "g") == {"dose_mg": 1000.0}


def test_medication_stopwords_not_treated_as_drugs():
    assert [f for f in facts("I take 500 mg at night") if f.field == "medication"] == []


def test_dose_conflict_between_sources_is_reported_not_resolved():
    fs = facts("metformin 500 mg twice daily") + S.extract("metformin 850 mg twice daily", source_id="doc1", source_type="document")
    conflicts = S.find_conflicts(fs)
    assert any(c["type"] == "medication_dose_mismatch" and c["resolution"].startswith("unresolved") for c in conflicts)


def test_allergy_and_reaction_not_double_counted_as_symptom():
    fs = facts("I am allergic to penicillin causing rash.")
    assert any(f.field == "allergy" and f.concept == "penicillin" and f.normalized_value["reaction"] == "rash" for f in fs)
    assert not any(f.concept == "rash" for f in fs)


def test_no_known_allergies_is_a_reported_negative_not_a_verified_fact():
    f = facts("No known allergies")[0]
    assert f.concept == "allergy_none" and f.assertion == "absent" and f.verification_status == "unverified"


def test_present_vs_absent_conflict_detected():
    fs = facts("No sweating, but I am sweating now")
    assert [c for c in S.find_conflicts(fs) if c["concept"] == "sweating"]


def test_measurements_normalised():
    m = {f.concept: f.normalized_value for f in facts("Temp 101.5 F, SpO2 91%, BP 150/95") if f.field == "measurement"}
    assert m["temperature"]["value_c"] == pytest.approx(38.6, abs=0.1)
    assert m["spo2"]["value_percent"] == 91 and m["blood_pressure"]["systolic_mmHg"] == 150


def test_document_source_type_is_recorded():
    assert facts("chest pain noted", "chest_pain", source_type="document")[0].source_type == "document"


def test_list_inputs_get_indexed_source_ids():
    fs = S.extract(["Sweating", "No breathlessness"], source_id="symptoms.assoc")
    assert {(f.source_id, f.concept, f.assertion) for f in fs} == {
        ("symptoms.assoc[0]", "sweating", "present"), ("symptoms.assoc[1]", "breathlessness", "absent")}
