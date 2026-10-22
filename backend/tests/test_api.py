import io, os, tempfile
import shutil
import pytest
os.environ["MEDIKIOSK_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from app.main import app
from app import ontology, ocr, summary

c = TestClient(app)
H = lambda t: {"Authorization": f"Bearer {t}"}

def test_adaptive_flow_and_redflag():
    a = {"cc": "Chest pain", "dur": "Today", "sev": "Severe"}
    n = ontology.next_question({**a})
    assert n["question"]["id"] == "progression"       # core HPI before chest-pain branch (SOCRATES)
    a.update(cp_site="Left side", cp_char="Pressure / heaviness", cp_rad="Arm / jaw / back")
    assert any(f["code"] == "ACS" for f in ontology.red_flags(a))
    assert "ay_prak" not in [q["id"] for q in ontology.applicable({"cc": "Fever"})]
    assert "ay_prak" in [q["id"] for q in ontology.applicable({"cc": "Fever", "_ay": True})]

def test_ocr_extraction():
    t = "Date: 12/03/2025\nHb 9.1 g/dL\nHbA1c 8.2 %\nFasting blood sugar 142 mg/dL\nTab Metformin 500 mg BD\nTab Warfarin 5 mg OD\nTab Aspirin 75 mg OD\nDx: Diabetes, anaemia"
    e = ocr.extract(t)
    assert e["date"] == "2025-03-12"
    labs = {l["test"]: l for l in e["labs"]}
    assert labs["Haemoglobin"]["flag"] == "low" and labs["HbA1c"]["flag"] == "high"
    assert {m["name"] for m in e["medications"]} >= {"Metformin", "Warfarin", "Aspirin"}
    assert any("bleeding" in i for i in ocr.interactions([m["name"] for m in e["medications"]]))

def test_document_facts_preserve_negation_uncertainty_and_provenance():
    e = ocr.extract("No fever. Patient is unsure about aspirin. Allergy: penicillin.",
                    {"source_id": "note-1", "pages": [{"page": 2, "text": "No fever. Patient is unsure about aspirin. Allergy: penicillin.",
                                                       "blocks": [{"text": "fever", "bbox": [1, 2, 3, 4], "confidence": 91}]}]})
    symptom = next(f for f in e["facts"] if f["field"] == "symptom")
    assert symptom["status"] == "negated"
    assert symptom["source"]["page"] == 2
    assert symptom["source"]["bbox"] == [1, 2, 3, 4]
    medication = next(f for f in e["facts"] if f["field"] == "medication")
    assert medication["status"] == "uncertain"
    assert "penicillin" in e["allergies"]

def test_poor_quality_or_unsupported_upload_is_explicit():
    text, engine, pages = ocr.ocr_document(b"not an image", "poor.png")
    assert text == "" and engine.startswith("ocr-unavailable:")
    assert pages == []

def test_grounded_summary_marks_conflicting_medication_for_review():
    user = {"name": "A", "age": "40"}
    docs = [{"id": 3, "filename": "rx.pdf", "date": "2025-01-01", "engine": "pdf-text",
             "entities": ocr.extract("Tab metformin 500 mg OD") }]
    sections = summary.build_sections(user, {"meds": "metformin 850 mg", "cc": "Cough"}, docs)
    conflict = next(x for x in sections if x["title"] == "Conflicts requiring review")
    assert "conflicting_medication_information" in conflict["review_flags"]
    assert conflict["source_refs"]

def test_asr_correction_reaches_extraction_and_history():
    token = c.post("/api/auth/guest?name=Voice").json()["token"]
    h = H(token)
    captured = c.post("/api/asr/transcripts", json={"transcript": "I take metformin five hundred mg", "language": "en"}, headers=h)
    assert captured.status_code == 200
    tid = captured.json()["transcript_id"]
    corrected = c.put(f"/api/asr/transcripts/{tid}", json={"corrected_transcript": "I take metformin 500 mg"}, headers=h)
    assert corrected.status_code == 200
    assert corrected.json()["document"]["entities"]["medications"][0]["dose"] == "500 mg"
    assert c.get("/api/documents", headers=h).json()[0]["text"] == "I take metformin 500 mg"
    session = c.post("/api/interview/sessions", json={"budget": 5}, headers=h).json()["session_id"]
    applied = c.post(f"/api/asr/transcripts/{tid}/apply", json={"session_id": session, "field": "free"}, headers=h)
    assert applied.status_code == 200
    assert applied.json()["interview"]["session_id"] == session

def test_full_journey():
    if shutil.which("tesseract") is None:
        pytest.skip("Tesseract is required for the image OCR integration path")
    g = c.post("/api/auth/guest?name=Ramesh&age=58&abha=12-3456-7890-1234").json()["token"]
    # submit without consent is blocked
    assert c.post("/api/submit", json={"answers": {}}, headers=H(g)).status_code == 403
    for p in ("history_capture", "abdm_share"): c.post("/api/consent", json={"purpose": p}, headers=H(g))
    # real image OCR through tesseract
    img = Image.new("RGB", (900, 220), "white"); d = ImageDraw.Draw(img)
    d.text((20, 20), "Pathology Report 2025-03-12", fill="black"); d.text((20, 70), "Haemoglobin 9.1 g/dL", fill="black"); d.text((20, 120), "HbA1c 8.2 %", fill="black")
    b = io.BytesIO(); img.save(b, "PNG")
    r = c.post("/api/documents", files={"file": ("lab.png", b.getvalue(), "image/png")}, headers=H(g))
    assert r.status_code == 200, r.text
    c.post("/api/documents/text", json={"text": "Rx Tab Warfarin 5 mg OD, Tab Aspirin 75 mg OD. 2024-11-02 discharge summary Dx coronary artery disease"}, headers=H(g))
    ans = {"cc": "Chest pain", "dur": "Today", "sev": "Severe", "cp_site": "Centre of chest", "cp_char": "Pressure / heaviness",
           "cp_rad": "Arm / jaw / back", "cp_agg": "Worse on walking / effort", "assoc": ["Sweating"], "pmh": ["Diabetes"], "meds": "warfarin 5mg", "free": "feeling very weak"}
    s = c.post("/api/summary", json={"answers": ans}, headers=H(g)).json()
    titles = [x["title"] for x in s["sections"]]
    assert "Prior records (timeline)" in titles and "Possible drug interactions (verify)" in titles
    assert s["red_flags"]
    sub = c.post("/api/submit", json={"answers": ans, "lang": "hi"}, headers=H(g))
    assert sub.status_code == 200, sub.text
    j = sub.json(); assert j["priority"] == 1 and j["abdm"]["ref"].startswith("MOCK-")
    # doctor view
    dt = c.post("/api/auth/login", json={"username": "doctor", "password": "doctor123"}).json()["token"]
    lst = c.get("/api/doctor/records", headers=H(dt)).json(); assert lst[0]["priority"] == 1
    full = c.get(f"/api/doctor/records/{j['record_id']}", headers=H(dt)).json()
    assert full["fhir"]["resourceType"] == "Bundle" and any(e["resource"]["resourceType"] == "Observation" for e in full["fhir"]["entry"])
    assert c.put(f"/api/doctor/records/{j['record_id']}", json={"sections": full["sections"], "status": "confirmed"}, headers=H(dt)).status_code == 200
    # patients cannot see doctor API
    assert c.get("/api/doctor/records", headers=H(g)).status_code == 403
    # guest docs wiped after submit
    assert c.get("/api/documents", headers=H(g)).json() == []

def test_register_login_erase():
    t = c.post("/api/auth/register", json={"username": "asha", "password": "secret1", "name": "Asha"}).json()["token"]
    assert c.post("/api/auth/register", json={"username": "asha", "password": "secret1"}).status_code == 409
    assert c.post("/api/auth/login", json={"username": "asha", "password": "bad"}).status_code == 401
    assert c.delete("/api/me/data", headers=H(t)).json()["erased"]
    assert c.get("/api/me", headers=H(t)).status_code == 401


def test_stateful_adaptive_interview_api_persists_answers_and_ayush_branch():
    token = c.post("/api/auth/guest?name=Adaptive").json()["token"]
    h = H(token)
    created = c.post("/api/interview/sessions", json={"budget": 12, "ayush": True}, headers=h)
    assert created.status_code == 200, created.text
    first = created.json()
    assert first["question"]["id"] == "cc"
    sid = first["session_id"]
    second = c.post(f"/api/interview/sessions/{sid}/answers", json={"field": "cc", "value": "Fever"}, headers=h)
    assert second.status_code == 200, second.text
    assert second.json()["question"]["id"] == "dur"
    persisted = c.get(f"/api/interview/sessions/{sid}", headers=h)
    assert persisted.status_code == 200
    assert persisted.json()["session_id"] == sid
    assert persisted.json()["answered"] >= 1
    repeated = c.get(f"/api/interview/sessions/{sid}", headers=h)
    assert repeated.json()["question"]["id"] == persisted.json()["question"]["id"]


def test_ml_route_does_not_claim_unavailable_trained_clinical_model():
    token = c.post("/api/auth/guest?name=ModelStatus").json()["token"]
    h = H(token)
    for purpose in ("history_capture", "abdm_share"):
        c.post("/api/consent", json={"purpose": purpose}, headers=h)
    submitted = c.post("/api/submit", json={"answers": {"cc": "Fever"}}, headers=h)
    assert submitted.status_code == 200
    assert c.get(f"/api/eda/red-flag-ml/{submitted.json()['record_id']}").status_code == 401   # EDA is clinician-only
    doctor_token = c.post("/api/auth/login", json={"username": "doctor", "password": "doctor123"}).json()["token"]
    response = c.get(f"/api/eda/red-flag-ml/{submitted.json()['record_id']}", headers=H(doctor_token))
    assert response.status_code == 200
    payload = response.json()
    assert payload["model_available"] is False
    assert payload["ml_red_flag_probability"] is None
    assert payload["likely_conditions"] == []
