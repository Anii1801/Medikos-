import os, json, time, secrets, uuid, hashlib, logging, io, sqlite3
from urllib.parse import quote
from typing import Literal, Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel
from . import asr, db, ontology, ocr, summary, fhir, llm, datasets, clinical_report, security
from fastapi import Request
from .history_agent import AdaptiveHistoryTakingAgent, QuestionResponse
from .redflag_engine import RedFlagEngine, RedFlagResult, rules_manifest
from .eda_api import router as eda_router

security.enforce_production_config()      # refuses to start in production with demo credentials / open CORS
app = FastAPI(title="MediKiosk API", version="1.0")
allowed_origins = [origin.strip() for origin in os.environ.get("MEDIKIOSK_CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(security.RateLimitMiddleware,
                   auth_per_min=int(os.environ.get("MEDIKIOSK_RATE_AUTH", "20")), api_per_min=int(os.environ.get("MEDIKIOSK_RATE_API", "300")),
                   enabled=os.environ.get("MEDIKIOSK_RATE_LIMIT", "on").lower() != "off")
db.init()
MAX_UPLOAD = 8 * 1024 * 1024
MAX_BATCH_UPLOAD = 32 * 1024 * 1024
MAX_BATCH_FILES = 10
ALLOWED_UPLOADS = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                   ".webp": "image/webp", ".tif": "image/tiff", ".tiff": "image/tiff", ".txt": "text/plain"}
PURPOSES = ("history_capture",)
logger = logging.getLogger(__name__)

# ---------- auth ----------
def user(authorization: Optional[str] = Header(None)):
    tok = (authorization or "").removeprefix("Bearer ").strip()
    with db.tx() as c:
        u = db.user_for(c, tok) if tok else None
    if not u: raise HTTPException(401, "Not authenticated")
    return dict(u)

def doctor(u=Depends(user)):
    if u["role"] != "doctor": raise HTTPException(403, "Doctor access only")
    return u

# /api/eda/* exposes aggregate data and per-record analysis (incl. patient answers by record id): clinician-only.
app.include_router(eda_router, dependencies=[Depends(doctor)])

class Reg(BaseModel):
    username: str; password: str; name: str = ""; age: str = ""; abha: str = ""
class Login(BaseModel):
    username: str; password: str

@app.post("/api/auth/register")
def register(r: Reg):
    username = db.normalize_username(r.username)
    if len(username) < 3 or len(username) > 64 or len(r.password) < 6 or len(r.password) > 1024:
        raise HTTPException(422, "Username must be 3–64 characters and password 6–1024 characters")
    with db.tx() as c:
        if c.execute(
            "SELECT 1 FROM users WHERE username=? COLLATE NOCASE", (username,)
        ).fetchone():
            raise HTTPException(409, "Username already taken")
        try:
            uid = db.add_user(c, username, r.password, "patient", r.name, r.age, r.abha)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Username already taken") from exc
        return {"token": db.new_session(c, uid), "role": "patient"}

@app.post("/api/auth/login")
def login(r: Login, request: Request):
    with db.tx() as c:
        u = db.check_login(c, r.username, r.password)
        if not u:
            security.audit("login_failed", target=r.username[:64], ip=request.client.host if request.client else None)
            raise HTTPException(401, "Wrong username or password")
        security.audit("login", actor_id=u["id"], role=u["role"], ip=request.client.host if request.client else None)
        return {"token": db.new_session(c, u["id"]), "role": u["role"]}

@app.post("/api/auth/logout")
def logout(request: Request, u=Depends(user)):
    authorization = request.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    with db.tx() as c:
        c.execute("DELETE FROM sessions WHERE token=? AND user_id=?", (token, u["id"]))
    return {"ok": True}

class PasswordReset(BaseModel):
    username: str
    new_password: str

@app.post("/api/auth/reset-password")
def reset_patient_password(r: PasswordReset, d=Depends(doctor)):
    username = db.normalize_username(r.username)
    if len(r.new_password) < 6 or len(r.new_password) > 1024:
        raise HTTPException(422, "Password must be 6–1024 characters")
    with db.tx() as c:
        patient = c.execute(
            "SELECT id FROM users WHERE username=? COLLATE NOCASE AND role='patient'",
            (username,),
        ).fetchone()
        if not patient:
            raise HTTPException(404, "Patient account not found")
        sessions_invalidated = db.set_password(c, patient["id"], r.new_password)
    security.audit(
        "patient_password_reset",
        actor_id=d["id"],
        role=d["role"],
        target=f"user:{patient['id']}",
        detail={"sessions_invalidated": sessions_invalidated},
    )
    return {"ok": True, "sessions_invalidated": sessions_invalidated}

@app.post("/api/auth/guest")
def guest(name: str = "", age: str = "", abha: str = ""):
    """Kiosk mode: zero-typing start. Guest accounts are purged with their data on submission/logout."""
    with db.tx() as c:
        uid = db.add_user(c, "guest-" + secrets.token_hex(5), secrets.token_hex(8), "guest", name, age, abha)
        return {"token": db.new_session(c, uid), "role": "guest"}

@app.get("/api/me")
def me(u=Depends(user)):
    return {k: u[k] for k in ("id", "username", "role", "name", "age", "abha")}

class Profile(BaseModel):
    name: str = ""; age: str = ""; abha: str = ""
@app.put("/api/me")
def update_me(p: Profile, u=Depends(user)):
    with db.tx() as c: c.execute("UPDATE users SET name=?,age=?,abha=? WHERE id=?", (p.name, p.age, p.abha, u["id"]))
    return {"ok": True}

@app.delete("/api/me/data")
def erase(u=Depends(user)):
    """DPDP Act right to erasure."""
    security.audit("erasure", actor_id=u["id"], role=u["role"])
    with db.tx() as c:
        for t in ("clinical_evidence", "record_documents", "documents", "records", "consents", "sessions", "history_sessions", "asr_transcripts"):
            c.execute(f"DELETE FROM {t} WHERE user_id=?", (u["id"],))
        c.execute("DELETE FROM users WHERE id=? AND role!='doctor'", (u["id"],))
    return {"erased": True}

# ---------- consent ----------
class Consent(BaseModel):
    purpose: str
    granted: bool
@app.post("/api/consent")
def set_consent(cn: Consent, u=Depends(user)):
    if cn.purpose not in PURPOSES: raise HTTPException(422, "Unknown purpose")
    with db.tx() as c: c.execute("INSERT INTO consents(user_id,purpose,granted,ts) VALUES(?,?,?,?)", (u["id"], cn.purpose, int(cn.granted), time.time()))
    return {"ok": True}

def active_consents(uid):
    with db.tx() as c:
        rows = c.execute("SELECT purpose,granted FROM consents WHERE user_id=? ORDER BY id", (uid,)).fetchall()
    st = {}
    for r in rows: st[r["purpose"]] = bool(r["granted"])
    return st
@app.get("/api/consent")
def get_consent(u=Depends(user)): return active_consents(u["id"])

# ---------- interview ----------
class Turn(BaseModel):
    answers: dict = {}; ayush: bool = False

class InterviewSessionCreate(BaseModel):
    budget: int = 30
    ayush: bool = False

class InterviewAnswer(BaseModel):
    field: str
    value: object
    transcript_id: str | None = None
    language: Literal["en", "hi"] = "en"
    verification_status: Literal["patient_confirmed", "patient_submitted", "uncertain"] = "patient_submitted"

def _save_interview(agent: AdaptiveHistoryTakingAgent, uid: int):
    now = time.time()
    payload = db.j(agent.to_dict())
    with db.tx() as c:
        c.execute("""INSERT INTO history_sessions(id,user_id,state,adapter,created,updated)
                     VALUES(?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET state=excluded.state, adapter=excluded.adapter, updated=excluded.updated""",
                  (agent.session_id, uid, payload, agent.adapter.name, now, now))

def _load_interview(session_id: str, uid: int) -> AdaptiveHistoryTakingAgent:
    with db.tx() as c:
        row = c.execute("SELECT state FROM history_sessions WHERE id=? AND user_id=?", (session_id, uid)).fetchone()
    if not row:
        raise HTTPException(404, "Interview session not found")
    return AdaptiveHistoryTakingAgent.from_dict(json.loads(row["state"]))

@app.post("/api/interview/sessions", response_model=QuestionResponse)
def create_interview_session(req: InterviewSessionCreate, u=Depends(user)):
    if not 1 <= req.budget <= 60:
        raise HTTPException(422, "Budget must be between 1 and 60 questions")
    agent = AdaptiveHistoryTakingAgent(budget=req.budget)
    agent.state["answers"]["_ay"] = req.ayush
    response = agent.next_response()
    _save_interview(agent, u["id"])
    return response

@app.post("/api/interview/sessions/{session_id}/answers", response_model=QuestionResponse)
def answer_interview(session_id: str, answer: InterviewAnswer, u=Depends(user)):
    agent = _load_interview(session_id, u["id"])
    transcript = None
    if answer.transcript_id:
        with db.tx() as c:
            transcript = c.execute(
                "SELECT id,original_transcript,corrected_transcript,language FROM asr_transcripts WHERE id=? AND user_id=?",
                (answer.transcript_id, u["id"]),
            ).fetchone()
        if not transcript:
            raise HTTPException(404, "Transcript not found")
        if transcript["language"] != answer.language:
            raise HTTPException(422, "Transcript language does not match the interview language")
    response = agent.answer(answer.field, answer.value)
    if transcript:
        history = agent.state.get("answer_history", [])
        if history and history[-1].get("field") == answer.field:
            history[-1]["speech_verification"] = {
                "transcript_id": transcript["id"],
                "language": transcript["language"],
                "raw_transcript": transcript["original_transcript"],
                "corrected_transcript": transcript["corrected_transcript"],
                "normalized_interpretation": answer.value,
                "verification_status": answer.verification_status,
            }
    _save_interview(agent, u["id"])
    return response

@app.get("/api/interview/sessions/{session_id}", response_model=QuestionResponse)
def get_interview(session_id: str, u=Depends(user)):
    agent = _load_interview(session_id, u["id"])
    return agent.next_response()

@app.post("/api/interview/next")
def interview(t: Turn, u=Depends(user)):
    a = dict(t.answers); a["_ay"] = t.ayush
    return AdaptiveHistoryTakingAgent().next_response(a).model_dump()

# ---------- speech recognition ----------
class BrowserTranscript(BaseModel):
    transcript: str
    language: str
    language_detected: str | None = None

class ASRApply(BaseModel):
    session_id: str | None = None
    field: str | None = None

def _transcript_row(row):
    return {"transcript_id": row["id"], "original_transcript": row["original_transcript"],
            "corrected_transcript": row["corrected_transcript"], "transcript": row["corrected_transcript"] or row["original_transcript"],
            "language": row["language"], "language_detected": row["language_detected"], "provider": row["provider"],
            "model": row["model"], "status": row["status"], "error": row["error"],
            "created": row["created"], "updated": row["updated"]}

def _save_transcript(result: asr.ASRResult, uid: int):
    now = time.time()
    with db.tx() as c:
        c.execute("""INSERT INTO asr_transcripts
                     (id,user_id,original_transcript,corrected_transcript,language,language_detected,provider,model,status,error,created,updated)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (result.transcript_id, uid, result.original_transcript, None, result.language,
                   result.language_detected, result.provider, result.model,
                   "captured" if result.available else "failed", result.error, result.created, now))
        row = c.execute("SELECT * FROM asr_transcripts WHERE id=?", (result.transcript_id,)).fetchone()
    return _transcript_row(row)

@app.get("/api/asr/status")
def asr_status(u=Depends(user)):
    adapter = asr.configured_adapter()
    return {"supported_languages": asr.SUPPORTED_LANGUAGES, "adapter": adapter.status(),
            "policy": "successful loading is not language support; run the language evaluation before clinical use"}

@app.post("/api/asr/transcribe")
async def asr_transcribe(file: UploadFile = File(...), language: str = Form("en"), u=Depends(user)):
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Audio too large (max 8 MB)")
    try:
        language = asr.validate_language(language)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    result = asr.transcribe(data, language, file.filename or "audio", asr.configured_adapter())
    return _save_transcript(result, u["id"])

@app.post("/api/asr/transcripts")
def save_browser_transcript(body: BrowserTranscript, u=Depends(user)):
    try:
        language = asr.validate_language(body.language)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not body.transcript.strip():
        raise HTTPException(422, "Empty transcript")
    result = asr.ASRResult(transcript_id=str(uuid.uuid4()), original_transcript=body.transcript.strip(),
                           language=language, language_detected=body.language_detected,
                           provider="browser-web-speech", model="browser",
                           available=True, evaluated=False)
    return _save_transcript(result, u["id"])

@app.get("/api/asr/transcripts")
def list_asr_transcripts(u=Depends(user)):
    with db.tx() as c:
        rows = c.execute("SELECT * FROM asr_transcripts WHERE user_id=? ORDER BY created", (u["id"],)).fetchall()
    return [_transcript_row(row) for row in rows]

def _apply_transcript_document(uid: int, transcript: dict):
    text = transcript["corrected_transcript"] or transcript["original_transcript"]
    entities = ocr.extract(text, {"source_id": transcript["transcript_id"], "engine": transcript["provider"]})
    entities["language"] = transcript["language"]
    entities["asr"] = {"transcript_id": transcript["transcript_id"], "original_transcript": transcript["original_transcript"],
                       "corrected": bool(transcript["corrected_transcript"]), "provider": transcript["provider"],
                       "model": transcript["model"], "evaluated": False}
    filename = f"asr:{transcript['transcript_id']}"
    with db.tx() as c:
        c.execute("DELETE FROM documents WHERE user_id=? AND filename=?", (uid, filename))
        cur = c.execute("INSERT INTO documents(user_id,filename,doc_date,doc_type,text,entities,engine,created) VALUES(?,?,?,?,?,?,?,?)",
                        (uid, filename, "", "asr_transcript", text, db.j(entities), transcript["provider"], time.time()))
        row = c.execute("SELECT * FROM documents WHERE id=?", (cur.lastrowid,)).fetchone()
    return doc_row(row)

@app.put("/api/asr/transcripts/{transcript_id}")
def correct_asr_transcript(transcript_id: str, body: dict, u=Depends(user)):
    corrected = (body.get("corrected_transcript") or "").strip()
    if not corrected:
        raise HTTPException(422, "corrected_transcript is required")
    with db.tx() as c:
        c.execute("""UPDATE asr_transcripts SET corrected_transcript=?, status='corrected', updated=?
                     WHERE id=? AND user_id=?""", (corrected, time.time(), transcript_id, u["id"]))
        row = c.execute("SELECT * FROM asr_transcripts WHERE id=? AND user_id=?", (transcript_id, u["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Transcript not found")
    transcript = _transcript_row(row)
    transcript["document"] = _apply_transcript_document(u["id"], transcript)
    return transcript

@app.post("/api/asr/transcripts/{transcript_id}/apply")
def apply_asr_transcript(transcript_id: str, body: ASRApply, u=Depends(user)):
    with db.tx() as c:
        row = c.execute("SELECT * FROM asr_transcripts WHERE id=? AND user_id=?", (transcript_id, u["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Transcript not found")
    transcript = _transcript_row(row)
    document = _apply_transcript_document(u["id"], transcript)
    response = {"transcript": transcript, "document": document}
    if body.session_id and body.field:
        agent = _load_interview(body.session_id, u["id"])
        response["interview"] = agent.answer(body.field, transcript["transcript"]).model_dump()
        _save_interview(agent, u["id"])
    return response

@app.get("/api/ontology")
def onto(u=Depends(user)): return [ontology.public(q) for q in ontology.QUESTIONS]

@app.get("/api/red-flags/rules")
def red_flag_rules(u=Depends(user)):
    return rules_manifest()

@app.post("/api/red-flags/evaluate", response_model=RedFlagResult)
def evaluate_red_flags(case: dict, u=Depends(user)):
    return RedFlagEngine().evaluate(case)

# ---------- documents ----------
def doc_row(r):
    keys = set(r.keys())
    return {"id": r["id"], "filename": r["filename"], "date": r["doc_date"], "doc_type": r["doc_type"], "engine": r["engine"],
            "entities": json.loads(r["entities"] or "{}"), "text": r["text"] or "",
            "processing_status": r["processing_status"] if "processing_status" in keys else "needs_review",
            "processing_error": r["processing_error"] if "processing_error" in keys else None,
            "byte_size": r["byte_size"] if "byte_size" in keys else 0,
            "content_type": r["content_type"] if "content_type" in keys else None,
            "created": r["created"] if "created" in keys else None,
            "has_original": bool(r["content"]) if "content" in keys else False,
            "sha256": r["sha256"] if "sha256" in keys else None}

def _safe_filename(filename: str | None) -> str:
    name = (filename or "upload").replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = "".join(ch for ch in name if ch >= " " and ch not in "\x7f")
    if not name or len(name) > 255:
        raise ValueError("Filename must be non-empty and no longer than 255 characters")
    return name


def _validate_upload(data: bytes, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    expected = ALLOWED_UPLOADS.get(ext)
    if not expected:
        raise ValueError("Unsupported file type. Upload PDF, PNG, JPG, WEBP, TIFF, or UTF-8 TXT.")
    if not data:
        raise ValueError("The uploaded file is empty.")
    if expected == "text/plain":
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Text documents must use UTF-8 encoding.") from exc
        return expected
    if expected == "application/pdf":
        if b"%PDF-" not in data[:1024]:
            raise ValueError("The file extension is PDF but the content is not a valid PDF.")
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
        try:
            reader = PdfReader(io.BytesIO(data), strict=True)
        except (PdfReadError, OSError, ValueError, EOFError) as exc:
            raise ValueError("The uploaded PDF is invalid or unreadable.") from exc
        if reader.is_encrypted:
            raise ValueError(
                "This PDF is encrypted or password-protected. MediKiosk does not retain PDF passwords. "
                "Save an unlocked copy from a trusted PDF application, then upload that copy."
            )
        try:
            page_count = len(reader.pages)
        except (PdfReadError, OSError, ValueError, EOFError) as exc:
            raise ValueError("The uploaded PDF is invalid or unreadable.") from exc
        if not page_count:
            raise ValueError("The PDF contains no pages.")
        if page_count > ocr.MAX_PDF_PAGES:
            raise ValueError(f"PDFs may contain at most {ocr.MAX_PDF_PAGES} pages.")
    else:
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(io.BytesIO(data)) as image:
                actual = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "TIFF": "image/tiff"}.get(image.format)
                if actual != expected:
                    raise ValueError(f"File content does not match the .{ext.lstrip('.')} extension.")
                frame_count = getattr(image, "n_frames", 1)
                if frame_count > ocr.MAX_PDF_PAGES:
                    raise ValueError(f"Images may contain at most {ocr.MAX_PDF_PAGES} frames.")
                for frame_number in range(frame_count):
                    image.seek(frame_number)
                    if image.width * image.height > 20_000_000:
                        raise ValueError("Image dimensions are too large to process safely.")
                    image.load()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValueError("Image dimensions are too large to process safely.") from exc
        except (UnidentifiedImageError, OSError, EOFError, SyntaxError) as exc:
            raise ValueError("The uploaded image is invalid or unreadable.") from exc
    return expected


def _process_upload(data: bytes, filename: str, note: str, date: str, user_id: int,
                    existing_id: int | None = None) -> dict:
    safe_name = _safe_filename(filename)
    digest = hashlib.sha256(data).hexdigest()
    try:
        content_type = _validate_upload(data, safe_name)
    except ValueError as exc:
        # Validation failures are isolated to this file in a batch.
        return _store_failed_upload(
            user_id, safe_name, len(data), digest, str(exc), data,
            ALLOWED_UPLOADS.get(os.path.splitext(safe_name)[1].lower(), "application/octet-stream"),
            existing_id,
        )
    with db.tx() as c:
        duplicate = c.execute("""SELECT * FROM documents WHERE user_id=? AND sha256=?
                                 AND content IS NOT NULL AND processing_status!='failed' AND id!=?
                                 ORDER BY id LIMIT 1""",
                              (user_id, digest, existing_id or -1)).fetchone()
    if duplicate:
        result = doc_row(duplicate)
        result.update(status="duplicate", duplicate_of=duplicate["id"], message="This file is already in your document list.")
        return result
    try:
        if content_type == "text/plain":
            raw_text = data.decode("utf-8-sig")
            engine, pages = "plain-text", [{"page": 1, "text": raw_text, "blocks": []}]
        else:
            raw_text, engine, pages = ocr.ocr_document(data, safe_name)
        try:
            from .ml_pipeline import clean_ocr_text
        except ImportError:
            clean_ocr_text = None
        text = clean_ocr_text(raw_text) if clean_ocr_text else raw_text
        if note:
            text = (text + "\n" + note).strip()
        provenance = {"source_id": digest, "engine": engine, "pages": pages}
        entities = ocr.extract(text, provenance)
        entities["ocr_pages"] = pages
        entities["document_provenance"] = {"filename": safe_name, "engine": engine, "byte_size": len(data),
                                           "page_count": len(pages), "stored_bytes": True, "sha256": digest}
        doc_date = date or entities["date"] or ""
        if engine.startswith("ocr-unavailable:") or engine == "pdf-scanned-unsupported":
            status = "failed"
            error = "Text extraction was unavailable. Review the original file or add a typed note."
        elif not text.strip():
            status = "needs_review"
            error = "No readable text was extracted. Review the original file or add a typed note."
        elif entities.get("review_flags") or not entities.get("facts"):
            status = "needs_review"
            error = "Extraction requires review against the original document."
        else:
            status, error = "extracted", None
    except Exception as exc:
        logger.warning("Document processing failed (%s)", type(exc).__name__)
        return _store_failed_upload(user_id, safe_name, len(data), digest,
                                    f"Document processing failed ({type(exc).__name__}).", data, content_type,
                                    existing_id)
    created = time.time()
    with db.tx() as c:
        if existing_id is None:
            cur = c.execute("""INSERT INTO documents(user_id,filename,doc_date,doc_type,text,entities,engine,created,
                              content,content_type,sha256,processing_status,processing_error,byte_size)
                              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (user_id, safe_name, doc_date, entities["doc_type"], text, db.j(entities), engine, created,
                             data, content_type, digest, status, error, len(data)))
            document_id = cur.lastrowid
        else:
            c.execute("""UPDATE documents SET filename=?,doc_date=?,doc_type=?,text=?,entities=?,engine=?,created=?,
                          content=?,content_type=?,sha256=?,processing_status=?,processing_error=?,byte_size=?
                          WHERE id=? AND user_id=?""",
                      (safe_name, doc_date, entities["doc_type"], text, db.j(entities), engine, created,
                       data, content_type, digest, status, error, len(data), existing_id, user_id))
            document_id = existing_id
        row = c.execute("SELECT * FROM documents WHERE id=? AND user_id=?", (document_id, user_id)).fetchone()
    result = doc_row(row)
    result.update(status=status, needs_manual_note=not text.strip())
    return result


def _store_failed_upload(user_id: int, filename: str, size: int, digest: str | None, error: str,
                         data: bytes | None = None, content_type: str | None = None,
                         existing_id: int | None = None) -> dict:
    now = time.time()
    entities = {"schema_version": "clinical-facts-v1", "doc_type": "other", "medications": [], "labs": [],
                "diagnoses": [], "symptoms": [], "allergies": [], "facts": [], "review_flags": []}
    with db.tx() as c:
        if existing_id is None:
            cur = c.execute("""INSERT INTO documents(user_id,filename,doc_date,doc_type,text,entities,engine,created,
                              content,content_type,sha256,processing_status,processing_error,byte_size)
                              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (user_id, filename, "", "other", "", db.j(entities), "unavailable", now,
                             data, content_type, digest, "failed", error, size))
            document_id = cur.lastrowid
        else:
            previous = c.execute("SELECT doc_type FROM documents WHERE id=? AND user_id=?",
                                 (existing_id, user_id)).fetchone()
            if not previous:
                raise HTTPException(404, "Document not found")
            entities["doc_type"] = previous["doc_type"]
            c.execute("""UPDATE documents SET filename=?,doc_date='',doc_type=?,text='',entities=?,engine='unavailable',
                          created=?,content=?,content_type=?,sha256=?,processing_status='failed',processing_error=?,byte_size=?
                          WHERE id=? AND user_id=?""",
                      (filename, previous["doc_type"], db.j(entities), now, data, content_type, digest, error, size,
                       existing_id, user_id))
            document_id = existing_id
        row = c.execute("SELECT * FROM documents WHERE id=? AND user_id=?", (document_id, user_id)).fetchone()
    result = doc_row(row)
    result.update(status="failed", needs_manual_note=True)
    return result


async def _read_upload(file: UploadFile) -> bytes:
    return await file.read(MAX_UPLOAD + 1)


def _batch_response(items: list[dict]) -> dict:
    failures = sum(item.get("processing_status") == "failed" for item in items)
    return {"status": "partial" if failures else "completed", "total": len(items),
            "succeeded": len(items) - failures, "failed": failures, "documents": items}


@app.post("/api/documents/batch")
async def upload_batch(files: list[UploadFile] = File(...), note: str = Form(""), date: str = Form(""), u=Depends(user)):
    if not files:
        raise HTTPException(422, "Choose at least one file.")
    known_sizes = [file.size for file in files]
    if all(isinstance(size, int) for size in known_sizes) and sum(known_sizes) > MAX_BATCH_UPLOAD:
        failures = []
        for index, file in enumerate(files):
            try:
                filename = _safe_filename(file.filename)
            except ValueError as exc:
                filename = "upload"
                failures.append(_store_failed_upload(u["id"], filename, file.size or 0, None, str(exc)))
                continue
            if index >= MAX_BATCH_FILES:
                error = f"A batch may contain at most {MAX_BATCH_FILES} files."
            elif file.size > MAX_UPLOAD:
                error = "File too large (maximum 8 MiB per file)."
            else:
                error = "Batch too large (maximum 32 MiB total)."
            failures.append(_store_failed_upload(u["id"], filename, file.size, None, error))
        result = _batch_response(failures)
        return Response(content=db.j(result), status_code=207, media_type="application/json")
    staged, items, total_bytes = [], [], 0
    for index, file in enumerate(files):
        total_bytes += file.size if isinstance(file.size, int) else 0
        try:
            filename = _safe_filename(file.filename)
        except ValueError as exc:
            filename = "upload"
            items.append(_store_failed_upload(u["id"], filename, 0, None, str(exc)))
            continue
        if index >= MAX_BATCH_FILES:
            items.append(_store_failed_upload(u["id"], filename, 0, None, f"A batch may contain at most {MAX_BATCH_FILES} files."))
            continue
        data = await _read_upload(file)
        size = file.size if isinstance(file.size, int) else len(data)
        if not isinstance(file.size, int):
            total_bytes += size
        staged.append((filename, data, size))
    batch_too_large = total_bytes > MAX_BATCH_UPLOAD
    for filename, data, size in staged:
        if size > MAX_UPLOAD:
            items.append(_store_failed_upload(u["id"], filename, size, None, "File too large (maximum 8 MiB per file)."))
        elif batch_too_large:
            items.append(_store_failed_upload(u["id"], filename, size, None, "Batch too large (maximum 32 MiB total)."))
        else:
            items.append(_process_upload(data, filename, note, date, u["id"]))
    result = _batch_response(items)
    return Response(content=db.j(result), status_code=207 if result["failed"] else 200, media_type="application/json")


@app.post("/api/documents")
async def upload(file: UploadFile | None = File(None), files: list[UploadFile] | None = File(None),
                 note: str = Form(""), date: str = Form(""), u=Depends(user)):
    if files:
        if file:
            raise HTTPException(422, "Send either 'file' or repeated 'files' fields, not both.")
        return await upload_batch(files, note, date, u)
    if not file:
        raise HTTPException(422, "Choose a file to upload.")
    data = await _read_upload(file)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File too large (max 8 MiB)")
    result = _process_upload(data, file.filename, note, date, u["id"])
    if result["processing_status"] == "failed":
        return Response(content=db.j(result), status_code=422, media_type="application/json")
    return result


@app.post("/api/documents/text")
def upload_text(body: dict, u=Depends(user)):
    """Add a record from typed/dictated text (fallback when no scan is available)."""
    text = (body.get("text") or "").strip()
    if not text: raise HTTPException(422, "Empty text")
    ent = ocr.extract(text, {"source_id": "typed-note", "engine": "typed"}); d = body.get("date") or ent["date"] or ""
    ent["document_provenance"] = {"filename": "typed-note", "engine": "typed", "stored_bytes": False, "page_count": 1}
    with db.tx() as c:
        cur = c.execute("INSERT INTO documents(user_id,filename,doc_date,doc_type,text,entities,engine,created) VALUES(?,?,?,?,?,?,?,?)",
                        (u["id"], "typed-note", d, ent["doc_type"], text, db.j(ent), "typed", time.time()))
        r = c.execute("SELECT * FROM documents WHERE id=?", (cur.lastrowid,)).fetchone()
    return doc_row(r)

@app.get("/api/documents")
def docs(u=Depends(user)):
    with db.tx() as c:
        rows = c.execute("SELECT * FROM documents WHERE user_id=? ORDER BY COALESCE(NULLIF(doc_date,''),'9999'), id", (u["id"],)).fetchall()
    return [doc_row(r) for r in rows]

@app.get("/api/documents/{did}/file")
def document_file(did: int, u=Depends(user)):
    with db.tx() as c:
        row = c.execute("SELECT filename,content,content_type FROM documents WHERE id=? AND user_id=?", (did, u["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    if row["content"] is None:
        raise HTTPException(404, "No original file is available for this document.")
    filename = quote(row["filename"] or "document", safe="")
    return Response(content=row["content"], media_type=row["content_type"] or "application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
                             "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"})

class DocumentCorrection(BaseModel):
    doc_type: str

@app.put("/api/documents/{did}")
def correct_document(did: int, correction: DocumentCorrection, u=Depends(user)):
    if correction.doc_type not in {"lab_report", "prescription", "discharge_summary", "radiology_report", "other"}:
        raise HTTPException(422, "Unsupported document category.")
    with db.tx() as c:
        row = c.execute("SELECT entities FROM documents WHERE id=? AND user_id=?", (did, u["id"])).fetchone()
        if not row:
            raise HTTPException(404, "Document not found")
        entities = json.loads(row["entities"] or "{}")
        entities["doc_type"] = correction.doc_type
        c.execute("UPDATE documents SET doc_type=?,entities=? WHERE id=? AND user_id=?",
                  (correction.doc_type, db.j(entities), did, u["id"]))
        updated = c.execute("SELECT * FROM documents WHERE id=? AND user_id=?", (did, u["id"])).fetchone()
    return doc_row(updated)

@app.post("/api/documents/{did}/retry")
async def retry_document(did: int, file: UploadFile | None = File(None), u=Depends(user)):
    with db.tx() as c:
        row = c.execute("SELECT filename,content FROM documents WHERE id=? AND user_id=?", (did, u["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Document not found")
    if file:
        data = await _read_upload(file)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "File too large (max 8 MiB)")
        filename = file.filename or row["filename"]
    elif row["content"] is not None:
        data, filename = row["content"], row["filename"]
    else:
        raise HTTPException(409, "The original file is unavailable; upload it again to retry extraction.")
    return _process_upload(data, filename, "", "", u["id"], existing_id=did)

@app.delete("/api/documents/{did}")
def del_doc(did: int, u=Depends(user)):
    with db.tx() as c: c.execute("DELETE FROM documents WHERE id=? AND user_id=?", (did, u["id"]))
    return {"ok": True}

# ---------- summary / submit ----------
class Submit(BaseModel):
    answers: dict; ayush: bool = False; lang: str = "en"

def _prepare(u, s: Submit, documents: list[dict] | None = None):
    a = dict(s.answers); a["_ay"] = s.ayush
    if documents is None:
        with db.tx() as c:
            rows = c.execute("SELECT * FROM documents WHERE user_id=?", (u["id"],)).fetchall()
        dl = [doc_row(r) for r in rows]
    else:
        dl = documents
    # One evaluation feeds the report, the legacy flag list, the queue priority and FHIR, so they can
    # never disagree. A failed screen yields an explicit SCREENING_UNAVAILABLE flag, never an empty list.
    report, rf = clinical_report.build_clinical_report(u, {k: v for k, v in a.items()}, dl)
    sections = report["clinical_summary"]["sections"]
    flags = rf.legacy_flags() if rf is not None else [{"code": "SCREENING_UNAVAILABLE", "level": "emergency",
        "msg": "Red-flag screening could not be completed. Treat this patient as UNSCREENED and obtain immediate clinician review."}]
    return a, dl, sections, flags, report


def _snapshot_documents(c, record_id: int, user_id: int, documents: list[dict]):
    for document in documents:
        source_id = document.get("id")
        row = c.execute("SELECT * FROM documents WHERE id=? AND user_id=?", (source_id, user_id)).fetchone()
        if not row:
            continue
        cur = c.execute("""INSERT INTO record_documents(record_id,user_id,source_document_id,filename,doc_date,doc_type,
                           text,entities,engine,created,content,content_type,sha256,processing_status,processing_error,byte_size)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (record_id, user_id, row["id"], row["filename"], row["doc_date"], row["doc_type"], row["text"],
                         row["entities"], row["engine"], row["created"], row["content"], row["content_type"], row["sha256"],
                         row["processing_status"], row["processing_error"], row["byte_size"]))
        snapshot_id = cur.lastrowid
        facts = json.loads(row["entities"] or "{}").get("facts") or []
        for index, fact in enumerate(facts):
            try:
                confidence = float(fact.get("confidence", 0))
            except (TypeError, ValueError):
                confidence = 0.0
            c.execute("""INSERT INTO clinical_evidence(record_id,user_id,record_document_id,fact_index,field,value,status,
                         confidence,source,created) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                      (record_id, user_id, snapshot_id, index, str(fact.get("field") or "unknown"),
                       db.j(fact.get("value")), str(fact.get("status") or "uncertain"), confidence,
                       db.j(fact.get("source") or {}), time.time()))


@app.post("/api/summary")
def make_summary(s: Submit, u=Depends(user)):
    a, dl, sec, flags, report = _prepare(u, s)
    return {"sections": sec, "red_flags": flags, "llm_refined": False, "clinical_report": report,
            "patient_message": summary.patient_confirmation(a, s.lang)}

@app.post("/api/clinical-summary")
def clinical_summary(s: Submit, u=Depends(user)):
    """Ordered report: AI summary -> 'Red-Flag Suggestions — Generated by AI' -> clinician review. Own data only."""
    return _prepare(u, s)[4]

@app.post("/api/submit")
def submit(s: Submit, u=Depends(user)):
    cs = active_consents(u["id"])
    if not cs.get("history_capture"):
        raise HTTPException(403, "Consent to record health information for the doctor is required")
    with db.tx() as c:
        source_rows = c.execute("SELECT * FROM documents WHERE user_id=? ORDER BY id", (u["id"],)).fetchall()
        source_documents = [doc_row(row) for row in source_rows]
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        n = c.execute("SELECT COUNT(*) FROM records WHERE date(created,'unixepoch')=?", (today,)).fetchone()[0] + 1
        cur = c.execute("INSERT INTO records(user_id,token_no,priority,status,answers,sections,flags,created,report) VALUES(?,?,?,?,?,?,?,?,?)",
                        (u["id"], n, 3, "submitted", db.j({}), db.j([]), db.j([]), now, None))
        rid = cur.lastrowid
        _snapshot_documents(c, rid, u["id"], source_documents)
        snapshot_rows = c.execute("SELECT * FROM record_documents WHERE record_id=? AND user_id=? ORDER BY id",
                                  (rid, u["id"])).fetchall()
        snapshot_documents = [doc_row(row) for row in snapshot_rows]
        a, dl, sec, flags, report = _prepare(u, s, snapshot_documents)
        prio = 1 if any(f["level"] == "emergency" for f in flags) else 2 if flags else 3
        c.execute("UPDATE records SET priority=?,answers=?,sections=?,flags=?,report=? WHERE id=?",
                  (prio, db.j({k: v for k, v in a.items() if not k.startswith("_")}),
                   db.j(sec), db.j(flags), db.j(report), rid))
        bundle = fhir.build_bundle(u, sec, flags, dl, rid)
        push = fhir.abdm_push(bundle, u.get("abha"))
        c.execute("UPDATE records SET fhir=?, abdm_ref=? WHERE id=?", (db.j(bundle), push["ref"], rid))
        if u["role"] == "guest":
            c.execute("DELETE FROM documents WHERE user_id=?", (u["id"],))
    return {"record_id": rid, "token_no": n, "priority": prio, "abdm": push, "red_flags": flags,
            "patient_message": summary.patient_confirmation(a, s.lang)}

@app.get("/api/records")
def my_records(u=Depends(user)):
    with db.tx() as c:
        rows = c.execute("SELECT id,token_no,priority,status,flags,created,abdm_ref FROM records WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall()
    return [{**dict(r), "flags": json.loads(r["flags"])} for r in rows]

@app.get("/api/records/{rid}")
def my_record(rid: int, u=Depends(user)):
    with db.tx() as c:
        row = c.execute("SELECT r.*, u.name, u.abha FROM records r JOIN users u ON u.id=r.user_id WHERE r.id=? AND r.user_id=?",
                        (rid, u["id"])).fetchone()
        document_rows = c.execute("SELECT * FROM record_documents WHERE record_id=? AND user_id=? ORDER BY id",
                                  (rid, u["id"])).fetchall() if row else []
    if not row:
        raise HTTPException(404, "Record not found")
    result = rec(row, True)
    result["documents"] = [doc_row(document) for document in document_rows]
    return result

@app.get("/api/records/{rid}/documents/{did}/file")
def my_record_document_file(rid: int, did: int, u=Depends(user)):
    with db.tx() as c:
        row = c.execute("""SELECT filename,content,content_type FROM record_documents
                           WHERE id=? AND record_id=? AND user_id=?""", (did, rid, u["id"])).fetchone()
    if not row:
        raise HTTPException(404, "Encounter document not found")
    if row["content"] is None:
        raise HTTPException(404, "No original file is available for this document.")
    filename = quote(row["filename"] or "document", safe="")
    return Response(content=row["content"], media_type=row["content_type"] or "application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
                             "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"})

# ---------- doctor ----------
def rec(r, full=False):
    d = {"id": r["id"], "token_no": r["token_no"], "priority": r["priority"], "status": r["status"], "flags": json.loads(r["flags"]),
         "created": r["created"], "abdm_ref": r["abdm_ref"], "patient": r["name"] if "name" in r.keys() else None}
    if full: d.update(sections=json.loads(r["sections"]), fhir=json.loads(r["fhir"] or "null"), abha=r["abha"],
                      clinical_report=json.loads(r["report"]) if r["report"] else None,
                      reviewed_by=r["reviewed_by"], reviewed=r["reviewed"])
    return d

@app.get("/api/doctor/records")
def d_list(d=Depends(doctor)):
    security.audit("doctor_list_records", actor_id=d["id"], role="doctor")
    with db.tx() as c:
        rows = c.execute("SELECT r.*, u.name, u.abha FROM records r JOIN users u ON u.id=r.user_id ORDER BY r.priority, r.id").fetchall()
    return [rec(r) for r in rows]

@app.get("/api/doctor/records/{rid}")
def d_get(rid: int, d=Depends(doctor)):
    with db.tx() as c:
        r = c.execute("SELECT r.*, u.name, u.abha FROM records r JOIN users u ON u.id=r.user_id WHERE r.id=?", (rid,)).fetchone()
        document_rows = c.execute("SELECT * FROM record_documents WHERE record_id=? ORDER BY id", (rid,)).fetchall() if r else []
    if not r: raise HTTPException(404, "Not found")
    security.audit("doctor_view_record", actor_id=d["id"], role="doctor", target=f"record:{rid}")
    result = rec(r, True)
    result["documents"] = [doc_row(row) for row in document_rows]
    return result

@app.get("/api/doctor/records/{rid}/documents/{did}/file")
def doctor_document_file(rid: int, did: int, d=Depends(doctor)):
    with db.tx() as c:
        row = c.execute("SELECT filename,content,content_type FROM record_documents WHERE id=? AND record_id=?",
                        (did, rid)).fetchone()
    if not row:
        raise HTTPException(404, "Encounter document not found")
    if row["content"] is None:
        raise HTTPException(404, "No original file is available for this document.")
    filename = quote(row["filename"] or "document", safe="")
    security.audit("doctor_download_document", actor_id=d["id"], role="doctor", target=f"record:{rid}/document:{did}")
    return Response(content=row["content"], media_type=row["content_type"] or "application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
                             "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"})

class Review(BaseModel):
    sections: list[dict]; status: str = "confirmed"
    finding_reviews: dict[str, str] = {}      # rule_id / fact key -> confirmed | rejected | needs_review
@app.put("/api/doctor/records/{rid}")
def d_review(rid: int, rv: Review, d=Depends(doctor)):
    if rv.status not in ("confirmed", "rejected", "amended"): raise HTTPException(422, "Bad status")
    if any(v not in ("confirmed", "rejected", "needs_review") for v in rv.finding_reviews.values()):
        raise HTTPException(422, "Bad finding review value")
    now = time.time()
    with db.tx() as c:
        row = c.execute("SELECT report FROM records WHERE id=?", (rid,)).fetchone()
        if not row: raise HTTPException(404, "Not found")
        report = json.loads(row["report"]) if row["report"] else None
        if report:   # record who reviewed what; only an explicit approval flips 'approved'
            report["clinical_summary"]["sections"] = rv.sections
            report["clinician_review"].update(status=rv.status, approved=(rv.status == "confirmed"),
                                              reviewed_by=d["username"], reviewed_at=now, finding_reviews=rv.finding_reviews)
            report["clinical_summary"]["status"] = {"confirmed": "APPROVED_BY_CLINICIAN", "amended": "AMENDED_BY_CLINICIAN",
                                                    "rejected": "REJECTED_BY_CLINICIAN"}[rv.status]
        c.execute("UPDATE records SET sections=?, status=?, reviewed_by=?, reviewed=?, report=? WHERE id=?",
                  (db.j(rv.sections), rv.status, d["username"], now, db.j(report) if report else None, rid))
    security.audit("doctor_review_record", actor_id=d["id"], role="doctor", target=f"record:{rid}", detail={"status": rv.status})
    return {"ok": True}

@app.get("/api/admin/audit")
def audit_log(limit: int = 200, d=Depends(doctor)):
    """Most recent audit events (metadata only), newest first."""
    with db.tx() as c:
        rows = c.execute("SELECT ts,event,actor_id,role,target,detail,ip FROM audit_log ORDER BY id DESC LIMIT ?", (max(1, min(limit, 1000)),)).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/health")
def health():
    return {"ok": True, "llm": llm.enabled(), "abdm_mode": os.environ.get("ABDM_MODE", "mock"),
            "datasets": datasets.status()}

@app.get("/api/health/ocr")
def ocr_health():
    """Expose OCR runtime metadata only; never reads uploaded documents."""
    return ocr.tesseract_status()

FRONT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(FRONT):
    @app.get("/doctor", include_in_schema=False)
    def doctor_page():
        return FileResponse(os.path.join(FRONT, "doctor.html"))

    app.mount("/", StaticFiles(directory=FRONT, html=True), name="ui")
