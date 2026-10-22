"""Hindi / Hinglish clinical NLP: hand-written cases varied beyond the dataset's templated phrasings.

Small, hand-made, SYNTHETIC sets: they pin intended behaviour and known limits; they are not a validation of
Hindi clinical understanding, and no audio/ASR accuracy is implied.
"""
import pytest

from app.clinical_nlp import ClinicalNLPService, parse_temporal
from app.history_agent import classify_answer
from app import hindi_nlp

SVC = ClinicalNLPService()


def facts(text):
    return {(f.concept, f.assertion, f.experiencer) for f in SVC.extract(text, source_id="t")}


@pytest.mark.parametrize("text,expected", [
    ("कोई एलर्जी नहीं", "negative"), ("नहीं", "negative"), ("कोई नहीं", "negative"), ("ऐसी कोई बीमारी नहीं है", "negative"),
    ("allergy nahi hai", "negative"), ("koi dawa nahi leta", "negative"), ("nothing helps", "negative"),
    ("पता नहीं", "uncertain"), ("मालूम नहीं", "uncertain"), ("शायद पेनिसिलिन से", "uncertain"), ("pata nahi", "uncertain"),
    ("yaad nahi hai", "uncertain"), ("मैं बताना नहीं चाहता", "uncertain"), ("batana nahi", "uncertain"),
    ("पेनिसिलिन से एलर्जी है", "reported"), ("तंबाकू खाता हूँ", "reported"), ("हाँ, धूल से", "reported"),
    ("Metformin 500 mg लेता हूँ", "reported"), ("dust se allergy hai", "reported"),
])
def test_answer_polarity(text, expected):
    assert classify_answer(text) == expected


@pytest.mark.parametrize("text,days,approx", [
    ("4 महीने से", 120, False), ("करीब 4 महीने से", 120, True), ("२ हफ्ते से", 14, False), ("दो दिन से", 2, False),
    ("डेढ़ साल से", 547.5, False), ("3 din se", 3, False), ("teen hafte se", 21, False), ("5 saal pehle", 1825, False),
    ("पाँच दिन", 5, False), ("About 2 weeks.", 14, True), ("2 weeks", 14, False), ("12 घंटे से", 0.5, False),
])
def test_durations_and_numbers(text, days, approx):
    t = parse_temporal(text)
    assert t is not None and t.duration_days == pytest.approx(days) and t.approximate == approx


def test_vague_and_relative_durations_are_not_given_a_false_number():
    assert parse_temporal("कुछ दिन से").duration_days is None and parse_temporal("कुछ दिन से").approximate
    assert parse_temporal("बचपन से").duration_days is None
    assert parse_temporal("कल से").duration_days == 1.0


def test_ago_is_distinguished_from_duration():
    assert parse_temporal("3 साल पहले").kind == "ago"


def test_numbers():
    assert hindi_nlp.parse_number_hi("७") == 7 and hindi_nlp.parse_number_hi("सात") == 7 and hindi_nlp.parse_number_hi("saat") == 7


@pytest.mark.parametrize("text,concept,assertion", [
    ("मुझे बुखार है", "fever", "present"), ("बुखार नहीं है", "fever", "absent"), ("bukhar nahi hai", "fever", "absent"),
    ("बिना बुखार के खांसी", "fever", "absent"), ("शायद बुखार है", "fever", "uncertain"), ("सीने में दर्द है", "chest_pain", "present"),
    ("seene mein dard hai", "chest_pain", "present"), ("सांस फूल रही है", "breathlessness", "present"),
    ("बोलने में दिक्कत", "speech_disturbance", "present"), ("मुझे आत्महत्या के विचार आते हैं", "self_harm", "present"),
    ("sir dard aur ulti", "headache", "present"),
])
def test_symptom_assertions(text, concept, assertion):
    assert (concept, assertion, "patient") in facts(text)


def test_negation_does_not_leak_across_a_comma():
    f = facts("सिरदर्द है, चक्कर नहीं")
    assert ("headache", "present", "patient") in f and ("dizziness", "absent", "patient") in f


def test_family_experiencer():
    assert ("diabetes", "present", "family") in facts("मेरे पिताजी को शुगर है")
    assert ("diabetes", "present", "patient") in facts("मुझे शुगर है")


def test_code_switched_sentence_and_medicine_names():
    text = "मुझे fever है और Metformin 500 mg लेता हूँ"
    f = SVC.extract(text, source_id="t")
    assert ("fever", "present") in {(x.concept, x.assertion) for x in f}
    assert any(x.field == "medication" and "etformin" in x.concept.lower() for x in f)


def test_provenance_spans_point_into_the_original_devanagari_text():
    text = "मुझे बुख़ार है"                       # contains a nukta; matching runs on a normalised copy
    f = next(x for x in SVC.extract(text, source_id="t") if x.concept == "fever")
    assert text[f.span[0]:f.span[1]].startswith("बुख़ार") and "बुख़ार" in f.original_text


def test_red_flag_engine_fires_on_hindi_input():
    from app import redflag_engine
    out = redflag_engine.evaluate_legacy({"cc": "Chest pain", "cp_char": "सीने में भारीपन और बाएं हाथ में दर्द", "assoc": "पसीना और सांस फूलना"})
    assert out


def test_documented_limits():
    # Known limit: answer-level polarity is word-based. A positive statement that contains a negation word is read as negative.
    assert classify_answer("दर्द कभी नहीं रुकता") == "negative"        # means 'the pain never stops' (positive); would be a false negative
