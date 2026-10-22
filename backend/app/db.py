import os, sqlite3, json, hashlib, secrets, time
from contextlib import contextmanager

DB_PATH = os.environ.get("MEDIKIOSK_DB", os.path.join(os.path.dirname(__file__), "..", "data", "medikiosk.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, pw_hash TEXT, salt TEXT, role TEXT DEFAULT 'patient',
  name TEXT, age TEXT, abha TEXT, created REAL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER, expires REAL);
CREATE TABLE IF NOT EXISTS consents(id INTEGER PRIMARY KEY, user_id INTEGER, purpose TEXT, granted INTEGER, ts REAL);
CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, user_id INTEGER, filename TEXT, doc_date TEXT, doc_type TEXT,
  text TEXT, entities TEXT, engine TEXT, created REAL, content BLOB, content_type TEXT, sha256 TEXT,
  processing_status TEXT NOT NULL DEFAULT 'needs_review', processing_error TEXT, byte_size INTEGER NOT NULL DEFAULT 0,
  duplicate_of INTEGER);
CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, user_id INTEGER, token_no INTEGER, priority INTEGER, status TEXT,
  answers TEXT, sections TEXT, flags TEXT, fhir TEXT, abdm_ref TEXT, created REAL, reviewed_by TEXT, reviewed REAL);
CREATE TABLE IF NOT EXISTS record_documents(
  id INTEGER PRIMARY KEY, record_id INTEGER NOT NULL, user_id INTEGER NOT NULL, source_document_id INTEGER,
  filename TEXT NOT NULL, doc_date TEXT, doc_type TEXT, text TEXT, entities TEXT NOT NULL, engine TEXT,
  created REAL NOT NULL, content BLOB, content_type TEXT, sha256 TEXT,
  processing_status TEXT NOT NULL DEFAULT 'needs_review', processing_error TEXT, byte_size INTEGER NOT NULL DEFAULT 0,
  UNIQUE(record_id, source_document_id));
CREATE INDEX IF NOT EXISTS record_documents_record ON record_documents(record_id);
CREATE TABLE IF NOT EXISTS clinical_evidence(
  id INTEGER PRIMARY KEY, record_id INTEGER NOT NULL, user_id INTEGER NOT NULL, record_document_id INTEGER NOT NULL,
  fact_index INTEGER NOT NULL, field TEXT NOT NULL, value TEXT NOT NULL, status TEXT NOT NULL,
  confidence REAL NOT NULL, source TEXT NOT NULL, created REAL NOT NULL,
  UNIQUE(record_document_id, fact_index));
CREATE INDEX IF NOT EXISTS clinical_evidence_record ON clinical_evidence(record_id);
CREATE TABLE IF NOT EXISTS history_sessions(id TEXT PRIMARY KEY, user_id INTEGER, state TEXT NOT NULL,
  adapter TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY, ts REAL NOT NULL, event TEXT NOT NULL, actor_id INTEGER, role TEXT, target TEXT, detail TEXT, ip TEXT);
CREATE INDEX IF NOT EXISTS audit_ts ON audit_log(ts);
CREATE TABLE IF NOT EXISTS asr_transcripts(id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
  original_transcript TEXT NOT NULL, corrected_transcript TEXT, language TEXT NOT NULL,
  language_detected TEXT, provider TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL,
  error TEXT, created REAL NOT NULL, updated REAL NOT NULL);
"""

def conn():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

@contextmanager
def tx():
    c = conn()
    try:
        yield c
        c.commit()
    finally:
        c.close()

def init():
    with tx() as c:
        c.executescript(SCHEMA)
        columns = {r[1] for r in c.execute("PRAGMA table_info(documents)")}
        migrations = {
            "content": "BLOB",
            "content_type": "TEXT",
            "sha256": "TEXT",
            "processing_status": "TEXT NOT NULL DEFAULT 'needs_review'",
            "processing_error": "TEXT",
            "byte_size": "INTEGER NOT NULL DEFAULT 0",
            "duplicate_of": "INTEGER",
        }
        for name, declaration in migrations.items():
            if name not in columns:
                c.execute(f"ALTER TABLE documents ADD COLUMN {name} {declaration}")
        # additive migration: store the AI clinical report (summary + red-flag block + review state)
        if "report" not in [r[1] for r in c.execute("PRAGMA table_info(records)")]:
            c.execute("ALTER TABLE records ADD COLUMN report TEXT")
        if not c.execute("SELECT 1 FROM users WHERE role='doctor'").fetchone():
            add_user(c, os.environ.get("DOCTOR_USER", "doctor"), os.environ.get("DOCTOR_PASS", "doctor123"), "doctor", "Dr. Demo")

def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 120_000).hex()

def add_user(c, username, pw, role="patient", name="", age="", abha=""):
    salt = secrets.token_hex(16)
    cur = c.execute("INSERT INTO users(username,pw_hash,salt,role,name,age,abha,created) VALUES(?,?,?,?,?,?,?,?)",
                    (username, _hash(pw, salt), salt, role, name, age, abha, time.time()))
    return cur.lastrowid

def check_login(c, username, pw):
    r = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return r if r and secrets.compare_digest(r["pw_hash"], _hash(pw, r["salt"])) else None

def new_session(c, uid, ttl=8 * 3600):
    t = secrets.token_urlsafe(32)
    c.execute("INSERT INTO sessions VALUES(?,?,?)", (t, uid, time.time() + ttl))
    return t

def user_for(c, token):
    r = c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?", (token, time.time())).fetchone()
    return r

def j(x): return json.dumps(x, ensure_ascii=False)
