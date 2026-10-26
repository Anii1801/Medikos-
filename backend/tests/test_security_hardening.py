"""Access control, audit trail, rate limiting and production-config enforcement (software tests, not a security review)."""
import json
import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("MEDIKIOSK_DB", os.path.join(tempfile.mkdtemp(), "sec.db"))
from app import db, security
from app.main import app

c = TestClient(app)


def token(user=None, pw=None):
    if user:
        return c.post("/api/auth/login", json={"username": user, "password": pw}).json()["token"]
    return c.post("/api/auth/guest").json()["token"]


def H(t): return {"Authorization": f"Bearer {t}"}


EDA = ["/api/eda/summary", "/api/eda/labs", "/api/eda/data-quality", "/api/eda/red-flag-ml/1", "/api/eda/ayush-analysis/1"]


@pytest.mark.parametrize("path", EDA)
def test_eda_requires_authentication(path):
    assert c.get(path).status_code == 401


@pytest.mark.parametrize("path", EDA)
def test_eda_is_forbidden_to_patients(path):
    assert c.get(path, headers=H(token())).status_code == 403


def test_eda_is_open_to_a_doctor():
    doc = token("doctor", os.environ.get("DOCTOR_PASS", "doctor123"))
    assert c.get("/api/eda/summary", headers=H(doc)).status_code == 200


def test_ayush_analysis_no_longer_leaks_answers_by_record_id():
    r = c.get("/api/eda/ayush-analysis/1")
    assert r.status_code == 401 and "answers" not in r.text


def test_audit_log_records_events_without_clinical_content():
    c.post("/api/auth/login", json={"username": "doctor", "password": "wrong-password"})
    doc = token("doctor", os.environ.get("DOCTOR_PASS", "doctor123"))
    c.get("/api/doctor/records", headers=H(doc))
    rows = c.get("/api/admin/audit", headers=H(doc)).json()
    events = {r["event"] for r in rows}
    assert {"login_failed", "login", "doctor_list_records"} <= events
    assert c.get("/api/admin/audit", headers=H(token())).status_code == 403
    blob = json.dumps(rows)
    assert "wrong-password" not in blob                         # credentials never reach the log


def test_erasure_is_audited():
    t = token()
    c.delete("/api/me", headers=H(t))
    with db.tx() as con:
        assert con.execute("SELECT COUNT(*) FROM audit_log WHERE event='erasure'").fetchone()[0] >= 1


def test_rate_limiter_blocks_credential_guessing_and_reports_retry_after():
    inner = FastAPI()
    @inner.post("/api/auth/login")
    def login(): return {"ok": True}
    inner.add_middleware(security.RateLimitMiddleware, auth_per_min=3, api_per_min=100, enabled=True)
    cl = TestClient(inner)
    codes = [cl.post("/api/auth/login").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    assert cl.post("/api/auth/login").headers["Retry-After"]


def test_rate_limiter_leaves_non_api_paths_alone():
    inner = FastAPI()
    @inner.get("/index")
    def idx(): return {"ok": True}
    inner.add_middleware(security.RateLimitMiddleware, auth_per_min=1, api_per_min=1, enabled=True)
    assert all(TestClient(inner).get("/index").status_code == 200 for _ in range(5))


def test_production_refuses_demo_credentials_and_open_cors(monkeypatch):
    monkeypatch.setenv("MEDIKIOSK_ENV", "production")
    monkeypatch.setenv("MEDIKIOSK_RATE_LIMIT", "on")
    monkeypatch.delenv("DOCTOR_PASS", raising=False)
    monkeypatch.setenv("MEDIKIOSK_CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError) as e:
        security.enforce_production_config()
    assert "DOCTOR_PASS" in str(e.value) and "CORS" in str(e.value)
    monkeypatch.setenv("DOCTOR_PASS", "a-long-unique-passphrase")
    monkeypatch.setenv("MEDIKIOSK_CORS_ORIGINS", "https://kiosk.example.org")
    security.enforce_production_config()                         # no raise


def test_development_mode_does_not_block_startup(monkeypatch):
    monkeypatch.delenv("MEDIKIOSK_ENV", raising=False)
    security.enforce_production_config()


def test_database_initialization_synchronizes_configured_doctor_credentials(tmp_path, monkeypatch):
    original_path = db.DB_PATH
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "doctor-config.db"))
    monkeypatch.setenv("DOCTOR_USER", "clinic-admin")
    monkeypatch.setenv("DOCTOR_PASS", "initial-password")
    try:
        db.init()
        with db.tx() as connection:
            first_login = db.check_login(connection, " CLINIC-ADMIN ", "initial-password")
            assert first_login and first_login["role"] == "doctor"

        monkeypatch.setenv("DOCTOR_USER", "updated-admin")
        monkeypatch.setenv("DOCTOR_PASS", "rotated-password")
        db.init()
        with db.tx() as connection:
            assert db.check_login(connection, "clinic-admin", "initial-password") is None
            updated_login = db.check_login(connection, " UPDATED-ADMIN ", "rotated-password")
            assert updated_login and updated_login["role"] == "doctor"
            assert connection.execute(
                "SELECT COUNT(*) FROM users WHERE role='doctor'"
            ).fetchone()[0] == 1
    finally:
        monkeypatch.setattr(db, "DB_PATH", original_path)


def test_database_initialization_rejects_doctor_username_conflict(tmp_path, monkeypatch):
    original_path = db.DB_PATH
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "doctor-conflict.db"))
    monkeypatch.setenv("DOCTOR_USER", "existing-patient")
    monkeypatch.setenv("DOCTOR_PASS", "long-enough-password")
    try:
        with db.tx() as connection:
            connection.executescript(db.SCHEMA)
            db.add_user(connection, "existing-patient", "patient-password", "patient")
        with pytest.raises(RuntimeError, match="conflicts with an existing non-doctor"):
            db.init()
    finally:
        monkeypatch.setattr(db, "DB_PATH", original_path)
