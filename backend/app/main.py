import os, json, time, secrets, uuid
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel
from . import asr, db, ontology, ocr, summary, fhir, llm, datasets, clinical_report
from .history_agent import AdaptiveHistoryTakingAgent, QuestionResponse
from .redflag_engine import RedFlagEngine, RedFlagResult, rules_manifest
from .eda_api import router as eda_router

app = FastAPI(title="MediKiosk API", version="1.0")
allowed_origins = [origin.strip() for origin in os.environ.get("MEDIKIOSK_CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(eda_router)  # /api/eda/* — analytics, EDA, ML endpoints
db.init()
MAX_UPLOAD = 8 * 1024 * 1024
PURPOSES = ("history_capture", "abdm_share")

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

class Reg(BaseModel):
    username: str; password: str; name: str = ""; age: str = ""; abha: str = ""
class Login(BaseModel):
    username: str; password: str

@app.post("/api/auth/register")
def register(r: Reg):
    if len(r.password) < 6 or len(r.username) < 3: raise HTTPException(422, "Username ≥3 and password ≥6 chars")
    with db.tx() as c:
        try: uid = db.add_user(c, r.username, r.password, "patient", r.name, r.age, r.abha)
        except Exception: raise HTTPException(409, "Username already taken")
        return {"token": db.new_session(c, uid), "role": "patient"}

@app.post("/api/auth/login")
def login(r: Login):
    with db.tx() as c:
        u = db.check_login(c, r.username, r.password)
        if not u: raise HTTPException(401, "Wrong username or password")
        return {"token": db.new_session(c, u["id"]), "role": u["role"]}

@app.post("/api/auth/guest")
def guest(name: str = "", age: str = "", abha: str = ""):
    """Kiosk mode: zero-typing start. Guest accounts are purged with their data on submission/logout."""
    with db.tx() as c:
        uid = db.add_user(c, "guest-" + secrets.token_hex(5), secrets.token_hex(8), "guest", name, age, abha)
        return {"token": db.new_session(c, uid), "role": "guest"}

@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    tok = (authorization or "").removeprefix("Bearer ").strip()
    if tok:
        with db.tx() as c:
            c.execute("DELETE FROM sessions WHERE token=?", (tok,))
    return {"ok": True}

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
    with db.tx() as c:
        for t in ("documents", "records", "consents", "sessions", "history_sessions", "asr_transcripts"): c.execute(f"DELETE FROM {t} WHERE user_id=?", (u["id"],))
        c.execute("DELETE FROM users WHERE id=? AND role!='doctor'", (u["id"],))
    return {"erased": True}

# ---------- consent ----------
class Consent(BaseModel):
    purpose: str; granted: bool = True
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
    response = agent.answer(answer.field, answer.value)
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
    return {"id": r["id"], "filename": r["filename"], "date": r["doc_date"], "doc_type": r["doc_type"], "engine": r["engine"],
            "entities": json.loads(r["entities"]), "text": r["text"]}

@app.post("/api/documents")
async def upload(file: UploadFile = File(...), note: str = Form(""), date: str = Form(""), u=Depends(user)):
    data = await file.read()
    if len(data) > MAX_UPLOAD: raise HTTPException(413, "File too large (max 8 MB)")
    raw_text, engine, pages = ocr.ocr_document(data, file.filename or "scan.png")   # image bytes never stored
    # ── Data cleaning pipeline (MedNLP-SC + ADAM v3 abbreviation expansion) ──
    try:
        from .ml_pipeline import clean_ocr_text
        text = clean_ocr_text(raw_text)
    except Exception:
        text = raw_text  # graceful fallback if ml_pipeline not available
    if note: text = (text + "\n" + note).strip()
    ent = ocr.extract(text, {"source_id": file.filename or "upload", "engine": engine, "pages": pages})
    ent["ocr_pages"] = pages
    ent["document_provenance"] = {"filename": file.filename, "engine": engine, "byte_size": len(data),
                                  "page_count": len(pages), "stored_bytes": False}
    d = date or ent["date"] or ""
    with db.tx() as c:
        cur = c.execute("INSERT INTO documents(user_id,filename,doc_date,doc_type,text,entities,engine,created) VALUES(?,?,?,?,?,?,?,?)",
                        (u["id"], file.filename, d, ent["doc_type"], text, db.j(ent), engine, time.time()))
        r = c.execute("SELECT * FROM documents WHERE id=?", (cur.lastrowid,)).fetchone()
    out = doc_row(r)
    out["needs_manual_note"] = not text.strip()
    return out


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

@app.delete("/api/documents/{did}")
def del_doc(did: int, u=Depends(user)):
    with db.tx() as c: c.execute("DELETE FROM documents WHERE id=? AND user_id=?", (did, u["id"]))
    return {"ok": True}

# ---------- summary / submit ----------
class Submit(BaseModel):
    answers: dict; ayush: bool = False; lang: str = "en"

def _prepare(u, s: Submit):
    a = dict(s.answers); a["_ay"] = s.ayush
    with db.tx() as c:
        rows = c.execute("SELECT * FROM documents WHERE user_id=?", (u["id"],)).fetchall()
    dl = [doc_row(r) for r in rows]
    # One evaluation feeds the report, the legacy flag list, the queue priority and FHIR, so they can
    # never disagree. A failed screen yields an explicit SCREENING_UNAVAILABLE flag, never an empty list.
    report, rf = clinical_report.build_clinical_report(u, {k: v for k, v in a.items()}, dl)
    sections = report["clinical_summary"]["sections"]
    flags = rf.legacy_flags() if rf is not None else [{"code": "SCREENING_UNAVAILABLE", "level": "emergency",
        "msg": "Red-flag screening could not be completed. Treat this patient as UNSCREENED and obtain immediate clinician review."}]
    return a, dl, sections, flags, report

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
    if not (cs.get("history_capture") and cs.get("abdm_share")):
        raise HTTPException(403, "Consent for history capture and ABDM sharing is required")
    a, dl, sec, flags, report = _prepare(u, s)
    prio = 1 if any(f["level"] == "emergency" for f in flags) else 2 if flags else 3
    with db.tx() as c:
        today = time.strftime("%Y-%m-%d")
        n = c.execute("SELECT COUNT(*) FROM records WHERE date(created,'unixepoch')=?", (today,)).fetchone()[0] + 1
        cur = c.execute("INSERT INTO records(user_id,token_no,priority,status,answers,sections,flags,created,report) VALUES(?,?,?,?,?,?,?,?,?)",
                        (u["id"], n, prio, "submitted", db.j({k: v for k, v in a.items() if not k.startswith("_")}), db.j(sec), db.j(flags), time.time(), db.j(report)))
        rid = cur.lastrowid
        bundle = fhir.build_bundle(u, sec, flags, dl, rid)
        push = fhir.abdm_push(bundle, u.get("abha"))
        c.execute("UPDATE records SET fhir=?, abdm_ref=? WHERE id=?", (db.j(bundle), push["ref"], rid))
        if u["role"] == "guest":   # kiosk privacy: wipe temporary patient-side data (record is retained for the doctor by id only)
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
        r = c.execute("SELECT * FROM records WHERE id=? AND user_id=?", (rid, u["id"])).fetchone()
    if not r:
        raise HTTPException(404, "Record not found")
    return rec(r, True)

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
    with db.tx() as c:
        rows = c.execute("SELECT r.*, u.name, u.abha FROM records r JOIN users u ON u.id=r.user_id ORDER BY r.priority, r.id").fetchall()
    return [rec(r) for r in rows]

@app.get("/api/doctor/records/{rid}")
def d_get(rid: int, d=Depends(doctor)):
    with db.tx() as c:
        r = c.execute("SELECT r.*, u.name, u.abha FROM records r JOIN users u ON u.id=r.user_id WHERE r.id=?", (rid,)).fetchone()
        document_rows = c.execute("SELECT * FROM documents WHERE user_id=? ORDER BY id", (r["user_id"],)).fetchall() if r else []
    if not r: raise HTTPException(404, "Not found")
    result = rec(r, True)
    result["documents"] = [doc_row(row) for row in document_rows]
    return result

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
            report["clinician_review"].update(status=rv.status, approved=(rv.status == "confirmed"),
                                              reviewed_by=d["username"], reviewed_at=now, finding_reviews=rv.finding_reviews)
            report["clinical_summary"]["status"] = {"confirmed": "APPROVED_BY_CLINICIAN", "amended": "AMENDED_BY_CLINICIAN",
                                                    "rejected": "REJECTED_BY_CLINICIAN"}[rv.status]
        c.execute("UPDATE records SET sections=?, status=?, reviewed_by=?, reviewed=?, report=? WHERE id=?",
                  (db.j(rv.sections), rv.status, d["username"], now, db.j(report) if report else None, rid))
    return {"ok": True}

@app.get("/api/health")
def health():
    return {"ok": True, "llm": llm.enabled(), "abdm_mode": os.environ.get("ABDM_MODE", "mock"),
            "datasets": datasets.status()}

FRONT = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(FRONT):
    @app.get("/doctor", include_in_schema=False)
    def doctor_page():
        return FileResponse(os.path.join(FRONT, "doctor.html"))

    app.mount("/", StaticFiles(directory=FRONT, html=True), name="ui")
