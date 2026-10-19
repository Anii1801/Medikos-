import os
import tempfile

os.environ["MEDIKIOSK_DB"] = os.path.join(tempfile.mkdtemp(), "interview.db")

from fastapi.testclient import TestClient
from app.main import app


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
