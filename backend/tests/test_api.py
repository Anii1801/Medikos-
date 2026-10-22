import io, json, os, tempfile
import shutil
import pytest
os.environ["MEDIKIOSK_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from app.main import app
from app import ontology, ocr, summary, db, main as main_module

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


def test_batch_upload_isolates_failures_and_restricts_original_file_access():
    token = c.post("/api/auth/guest?name=Batch").json()["token"]
    text = b"Patient reports fever. Tab Metformin 500 mg OD."
    response = c.post("/api/documents", files=[
        ("files", ("history.txt", text, "text/plain")),
        ("files", ("broken.pdf", b"not a PDF", "application/pdf")),
        ("files", ("unsupported.exe", b"not supported", "application/octet-stream")),
    ], headers=H(token))
    assert response.status_code == 207, response.text
    result = response.json()
    assert result["total"] == 3 and result["succeeded"] == 1 and result["failed"] == 2
    good, bad, unsupported = result["documents"]
    assert good["processing_status"] == "extracted" and good["has_original"]
    assert bad["processing_status"] == "failed" and "not a valid PDF" in bad["processing_error"]
    assert unsupported["processing_status"] == "failed" and "Unsupported file type" in unsupported["processing_error"]
    original = c.get(f"/api/documents/{good['id']}/file", headers=H(token))
    assert original.status_code == 200 and original.content == text
    other = c.post("/api/auth/guest?name=Other").json()["token"]
    assert c.get(f"/api/documents/{good['id']}/file", headers=H(other)).status_code == 404


def test_duplicate_upload_is_reported_without_duplicating_document():
    token = c.post("/api/auth/guest?name=Duplicate").json()["token"]
    content = b"Medical note: no fever."
    response = c.post("/api/documents/batch", files=[
        ("files", ("note.txt", content, "text/plain")),
        ("files", ("copy.txt", content, "text/plain")),
    ], headers=H(token))
    assert response.status_code == 200, response.text
    first, second = response.json()["documents"]
    assert first["processing_status"] == "extracted"
    assert second["status"] == "duplicate" and second["duplicate_of"] == first["id"]
    assert len(c.get("/api/documents", headers=H(token)).json()) == 1


def test_guest_submission_keeps_encounter_document_and_source_evidence_snapshot():
    token = c.post("/api/auth/guest?name=Snapshot").json()["token"]
    headers = H(token)
    for purpose in ("history_capture", "abdm_share"):
        assert c.post("/api/consent", json={"purpose": purpose}, headers=headers).status_code == 200
    source = b"Lab report 2025-03-12\nHaemoglobin 9.1 g/dL\nPatient reports fever."
    upload = c.post("/api/documents", files={"file": ("lab.txt", source, "text/plain")}, headers=headers)
    assert upload.status_code == 200, upload.text
    submitted = c.post("/api/submit", json={"answers": {"cc": "Fever"}}, headers=headers)
    assert submitted.status_code == 200, submitted.text
    record_id = submitted.json()["record_id"]
    assert c.get("/api/documents", headers=headers).json() == []
    patient_record = c.get(f"/api/records/{record_id}", headers=headers)
    assert patient_record.status_code == 200 and patient_record.json()["documents"][0]["filename"] == "lab.txt"
    patient_doc_id = patient_record.json()["documents"][0]["id"]
    assert c.get(f"/api/records/{record_id}/documents/{patient_doc_id}/file", headers=headers).content == source
    other = c.post("/api/auth/guest?name=NotOwner").json()["token"]
    assert c.get(f"/api/records/{record_id}", headers=H(other)).status_code == 404

    doctor_token = c.post("/api/auth/login", json={"username": "doctor", "password": "doctor123"}).json()["token"]
    record = c.get(f"/api/doctor/records/{record_id}", headers=H(doctor_token)).json()
    assert len(record["documents"]) == 1
    snapshot = record["documents"][0]
    assert snapshot["filename"] == "lab.txt" and snapshot["has_original"]
    fact = snapshot["entities"]["facts"][0]
    assert fact["source"]["source_type"] == "document" and fact["source"]["page"] == 1
    assert fact["source"]["start"] < fact["source"]["end"]
    downloaded = c.get(f"/api/doctor/records/{record_id}/documents/{snapshot['id']}/file", headers=H(doctor_token))
    assert downloaded.status_code == 200 and downloaded.content == source
    with db.tx() as conn:
        count = conn.execute("SELECT COUNT(*) FROM clinical_evidence WHERE record_id=?", (record_id,)).fetchone()[0]
    assert count > 0


def test_synthetic_pdf_evidence_reaches_persisted_doctor_report_after_guest_cleanup():
    token = c.post("/api/auth/guest?name=Evidence&age=46").json()["token"]
    headers = H(token)
    for purpose in ("history_capture", "abdm_share"):
        assert c.post("/api/consent", json={"purpose": purpose}, headers=headers).status_code == 200

    def make_pdf(lines):
        stream = io.BytesIO()
        page = canvas.Canvas(stream)
        for index, line in enumerate(lines):
            page.drawString(48, 780 - index * 24, line)
        page.save()
        return stream.getvalue()

    sources = {
        "lab.pdf": make_pdf(["Laboratory Report", "Report date: 2025-03-12",
                             "Haemoglobin 9.1 g/dL (13-17) L", "Creatinine 1.0 mg/dL (0.6-1.3) N"]),
        "prescription.pdf": make_pdf(["Prescription 2025-03-13",
                                      "Tab Warfarin 5 mg OD", "Tab Aspirin 75 mg OD"]),
    }
    uploaded = {}
    for filename, content in sources.items():
        response = c.post("/api/documents", files={"file": (filename, content, "application/pdf")}, headers=headers)
        assert response.status_code == 200, response.text
        uploaded[filename] = response.json()
        assert uploaded[filename]["processing_status"] == "extracted"
        assert uploaded[filename]["engine"] == "pdf-text"

    response = c.post("/api/submit", json={"answers": {"cc": "Fever", "meds": "Warfarin 2 mg"}}, headers=headers)
    assert response.status_code == 200, response.text
    record_id = response.json()["record_id"]
    assert c.get("/api/documents", headers=headers).json() == []

    doctor = c.post("/api/auth/login", json={"username": "doctor", "password": "doctor123"}).json()["token"]
    record = c.get(f"/api/doctor/records/{record_id}", headers=H(doctor)).json()
    by_name = {document["filename"]: document for document in record["documents"]}
    assert set(by_name) == set(sources)
    lab_doc = by_name["lab.pdf"]
    rx_doc = by_name["prescription.pdf"]
    assert c.get(f"/api/doctor/records/{record_id}/documents/{lab_doc['id']}/file",
                 headers=H(doctor)).content == sources["lab.pdf"]
    report = record["clinical_report"]["clinical_summary"]
    lab_section = next(section for section in report["sections"]
                       if section["title"] == "Laboratory and Investigation Findings")
    findings = {finding["test_name"]: finding for finding in lab_section["findings"]}
    assert findings["Haemoglobin"]["result"] == 9.1
    assert findings["Haemoglobin"]["unit"] == "g/dL"
    assert findings["Haemoglobin"]["report_date"] == "2025-03-12"
    assert findings["Haemoglobin"]["reference_interval"] == "13–17"
    assert findings["Haemoglobin"]["source_document_id"] == lab_doc["id"]
    assert findings["Haemoglobin"]["source"]["page"] == 1
    assert findings["Haemoglobin"]["source"]["start"] < findings["Haemoglobin"]["source"]["end"]
    evidence_section = next(section for section in report["sections"]
                            if section["title"] == "Current medications and allergies")
    med_facts = [finding for finding in evidence_section["findings"] if finding["field"] == "medication"]
    assert {finding["source_document_id"] for finding in med_facts} == {rx_doc["id"]}
    assert {finding["value"]["name"] for finding in med_facts} >= {"Warfarin", "Aspirin"}
    med_values = {finding["value"]["name"]: finding["value"] for finding in med_facts}
    assert (med_values["Warfarin"]["dose"], med_values["Warfarin"]["frequency"]) == ("5 mg", "ONCE DAILY")
    assert (med_values["Aspirin"]["dose"], med_values["Aspirin"]["frequency"]) == ("75 mg", "ONCE DAILY")
    assert all(finding["report_date"] == "2025-03-13" for finding in med_facts)
    assert any(section["title"] == "Conflicts requiring review" for section in report["sections"])
    assert any(section["title"] == "Items requiring clinician verification" for section in report["sections"])
    reviewed = c.put(f"/api/doctor/records/{record_id}",
                     json={"sections": record["sections"], "status": "amended"},
                     headers=H(doctor))
    assert reviewed.status_code == 200, reviewed.text
    reviewed_record = c.get(f"/api/doctor/records/{record_id}", headers=H(doctor)).json()
    reviewed_lab = next(section for section in reviewed_record["sections"]
                        if section["title"] == "Laboratory and Investigation Findings")
    assert reviewed_lab["findings"][0]["source_document_id"] == lab_doc["id"]
    reviewed_report_lab = next(section for section in reviewed_record["clinical_report"]["clinical_summary"]["sections"]
                               if section["title"] == "Laboratory and Investigation Findings")
    assert reviewed_report_lab == reviewed_lab

    with db.tx() as conn:
        row = conn.execute("""SELECT e.user_id,e.record_id,e.record_document_id,e.status,e.source,
                                     r.user_id AS record_user_id,rd.record_id AS snapshot_record_id,rd.filename
                              FROM clinical_evidence e
                              JOIN records r ON r.id=e.record_id
                              JOIN record_documents rd ON rd.id=e.record_document_id
                              WHERE e.record_id=? LIMIT 1""", (record_id,)).fetchone()
    assert row and row["user_id"] == row["record_user_id"]
    assert row["record_id"] == record_id
    assert row["snapshot_record_id"] == record_id and row["filename"] in sources
    assert json.loads(row["source"])["source_type"] == "document"


def test_batch_enforces_per_file_and_aggregate_size_limits(monkeypatch):
    token = c.post("/api/auth/guest?name=Limits").json()["token"]
    monkeypatch.setattr(main_module, "MAX_UPLOAD", 4)
    monkeypatch.setattr(main_module, "MAX_BATCH_UPLOAD", 20)
    response = c.post("/api/documents/batch", files=[
        ("files", ("large.txt", b"12345", "text/plain")),
        ("files", ("small.txt", b"ok\n", "text/plain")),
    ], headers=H(token))
    assert response.status_code == 207
    large, small = response.json()["documents"]
    assert large["processing_status"] == "failed" and "8 MiB" in large["processing_error"]
    assert small["processing_status"] == "needs_review"

    monkeypatch.setattr(main_module, "MAX_UPLOAD", 20)
    monkeypatch.setattr(main_module, "MAX_BATCH_UPLOAD", 5)
    response = c.post("/api/documents/batch", files=[
        ("files", ("one.txt", b"abc", "text/plain")),
        ("files", ("two.txt", b"def", "text/plain")),
    ], headers=H(token))
    assert response.status_code == 207
    assert response.json()["failed"] == 2
    assert all("Batch too large" in item["processing_error"] for item in response.json()["documents"])


def test_valid_image_upload_retains_original_with_verified_content_type(monkeypatch):
    token = c.post("/api/auth/guest?name=Image").json()["token"]
    image = Image.new("RGB", (12, 12), "white")
    data = io.BytesIO()
    image.save(data, format="PNG")
    payload = data.getvalue()
    monkeypatch.setattr(main_module.ocr, "ocr_document", lambda content, filename: (
        "Patient reports fever.", "test-ocr", [{"page": 1, "text": "Patient reports fever.", "blocks": []}]
    ))
    response = c.post("/api/documents", files={"file": ("report.png", payload, "image/png")}, headers=H(token))
    assert response.status_code == 200, response.text
    document = response.json()
    assert document["processing_status"] == "extracted" and document["content_type"] == "image/png"
    original = c.get(f"/api/documents/{document['id']}/file", headers=H(token))
    assert original.content == payload


@pytest.mark.parametrize(("format_name", "filename", "content_type"), [
    ("WEBP", "scan.webp", "image/webp"),
    ("TIFF", "scan.tiff", "image/tiff"),
])
def test_webp_and_tiff_uploads_are_validated_and_retained(monkeypatch, format_name, filename, content_type):
    token = c.post(f"/api/auth/guest?name={format_name}").json()["token"]
    image = Image.new("RGB", (12, 12), "white")
    payload = io.BytesIO()
    image.save(payload, format=format_name)
    raw = payload.getvalue()
    monkeypatch.setattr(main_module.ocr, "ocr_document", lambda content, source_name: (
        "Patient reports fever.", "test-ocr", [{"page": 1, "text": "Patient reports fever.", "blocks": []}]
    ))
    response = c.post("/api/documents", files={"file": (filename, raw, content_type)}, headers=H(token))
    assert response.status_code == 200, response.text
    document = response.json()
    assert document["content_type"] == content_type and document["processing_status"] == "extracted"
    assert c.get(f"/api/documents/{document['id']}/file", headers=H(token)).content == raw


def test_multipage_tiff_preserves_page_numbers(monkeypatch):
    first = Image.new("RGB", (8, 8), "white")
    second = Image.new("RGB", (8, 8), "black")
    stream = io.BytesIO()
    first.save(stream, format="TIFF", save_all=True, append_images=[second])
    monkeypatch.setattr(ocr, "_ocr_pil_image", lambda image: (
        "Page " + ("one" if image.getpixel((0, 0))[0] > 0 else "two"),
        "tesseract(test)", []
    ))
    text, engine, pages = ocr.ocr_document(stream.getvalue(), "multi.tiff")
    assert text == "Page one\nPage two" and engine == "tesseract(test)"
    assert [page["page"] for page in pages] == [1, 2]


def test_multiframe_webp_preserves_frame_numbers(monkeypatch):
    first = Image.new("RGB", (8, 8), "white")
    second = Image.new("RGB", (8, 8), "black")
    stream = io.BytesIO()
    first.save(stream, format="WEBP", save_all=True, append_images=[second], duration=100, loop=0)
    monkeypatch.setattr(ocr, "_ocr_pil_image", lambda image: (
        "Frame " + ("one" if image.getpixel((0, 0))[0] > 0 else "two"),
        "tesseract(test)", []
    ))
    text, engine, pages = ocr.ocr_document(stream.getvalue(), "multi.webp")
    assert text == "Frame one\nFrame two" and engine == "tesseract(test)"
    assert [page["page"] for page in pages] == [1, 2]


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
