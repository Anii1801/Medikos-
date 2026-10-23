import os
import tempfile

os.environ["MEDIKIOSK_DB"] = os.path.join(tempfile.mkdtemp(), "interview.db")

from fastapi.testclient import TestClient
from app.main import app, db
import json


def test_interview_session_persists_and_returns_structured_contract():
    client = TestClient(app)
    token = client.post("/api/auth/guest").json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/interview/sessions", json={"budget": 3}, headers=headers)
    assert created.status_code == 200
    data = created.json()
    sid = data["session_id"]
    assert data["adapter"] == "deterministic-development"
    assert data["trained"] is False
    next_turn = client.post(f"/api/interview/sessions/{sid}/answers",
                            json={"field": "cc", "value": "Chest pain"}, headers=headers)
    assert next_turn.status_code == 200
    assert next_turn.json()["question"]["id"] == "dur"
    loaded = client.get(f"/api/interview/sessions/{sid}", headers=headers)
    assert loaded.json()["session_id"] == sid


def test_confirmed_speech_answer_keeps_original_and_corrected_transcript_provenance():
    client = TestClient(app)
    token = client.post("/api/auth/guest").json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    sid = client.post("/api/interview/sessions", json={"budget": 3}, headers=headers).json()["session_id"]
    transcript = client.post("/api/asr/transcripts", json={
        "transcript": "chest pain", "language": "en"
    }, headers=headers).json()
    corrected = client.put(f"/api/asr/transcripts/{transcript['transcript_id']}", json={
        "corrected_transcript": "severe chest pain"
    }, headers=headers).json()
    response = client.post(f"/api/interview/sessions/{sid}/answers", json={
        "field": "cc", "value": "Chest pain", "transcript_id": transcript["transcript_id"],
        "language": "en", "verification_status": "patient_confirmed"
    }, headers=headers)
    assert response.status_code == 200
    with db.tx() as connection:
        state = connection.execute("SELECT state FROM history_sessions WHERE id=?", (sid,)).fetchone()
    answer = json.loads(state["state"])["state"]["answer_history"][-1]
    assert answer["value"] == "Chest pain"
    assert answer["speech_verification"] == {
        "transcript_id": transcript["transcript_id"],
        "language": "en",
        "raw_transcript": "chest pain",
        "corrected_transcript": "severe chest pain",
        "normalized_interpretation": "Chest pain",
        "verification_status": "patient_confirmed",
    }

    other = client.post("/api/auth/guest").json()["token"]
    denied = client.post(f"/api/interview/sessions/{sid}/answers", json={
        "field": "dur", "value": "Today", "transcript_id": transcript["transcript_id"],
        "language": "en", "verification_status": "patient_confirmed"
    }, headers={"Authorization": f"Bearer {other}"})
    assert denied.status_code == 404
