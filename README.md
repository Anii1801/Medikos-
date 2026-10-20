# 🪔 MediKiosk — AI-Powered Patient Case-Taking Software
*Smart India Hackathon · Problem Statement 4 · All India Institute of Ayurveda, Ministry of Ayush*

A patient-facing platform that captures a structured clinical history by **voice + touch**, digitises old
medical documents, and hands the physician an **editable, structured summary** before the consultation.

## Run
```bash
./run.sh                 # → http://localhost:8000  (patient)   /doctor.html (physician)
# or
cp .env.example .env && docker compose up --build
cd backend && python -m pytest -q    # 4 tests incl. real OCR on an image
```
Before first run, copy `.env.example` to `.env` and set a strong `DOCTOR_PASS` and your desired `DOCTOR_USER`. The example password is intentionally a placeholder; do not use a demo credential for real patient data.
When `DOCTOR_USER` or `DOCTOR_PASS` is set for an existing SQLite database, the doctor account is updated on startup. Existing patient accounts and their data are preserved. Usernames are matched case-insensitively and surrounding whitespace is ignored.
A doctor can reset a patient password with `POST /api/auth/reset-password` using the doctor bearer token and `{ "username": "...", "new_password": "..." }`. This invalidates the patient’s existing sessions without deleting patient data. Doctor passwords remain controlled by `DOCTOR_USER` and `DOCTOR_PASS`.
A local run needs Tesseract for image OCR (`apt install tesseract-ocr tesseract-ocr-hin`); Docker includes it.

### Bundled datasets

All dataset-backed features use the single `Datasets/MediKiosk_Datasets` tree through
`backend/app/datasets.py`. The application currently reads:

* `05_triage_redflag/symptom2disease_text.csv` for the transparent symptom-label fallback
* `07_drug_safety/drug_interaction_reference.csv` for document medication interaction alerts
* `00_patient_master/patient_master.csv` and `patient_timeline.csv` as the maintained patient-data sources
* `05_triage_redflag/red_flag_labeled_cases.csv` for the documented triage dataset inventory

Override the location for a mounted dataset volume with `MEDIKIOSK_DATASETS`. The
`/api/health` response reports whether each required file is available.

## How it maps to the problem statement
| Module | Implementation | Where |
|---|---|---|
| **A. Conversational history engine** | Ontology-constrained dialogue manager: adaptive branching by chief complaint (chest pain → full **SOCRATES**; fever, cough, abdomen, headache, joints), dual-mode voice/tap, Hindi/English, audio prompts (browser TTS), **AYUSH mode** with all 10 **Dashavidha Pariksha** parameters + Ahara-Vihara | `backend/app/ontology.py`, `frontend/index.html` |
| Red-flag detection | Rule engine (ACS, stroke, severe dyspnoea, thunderclap headache/meningism, GI bleed, haemoptysis/TB, syncope, emergency keywords in English/Hindi) → priority 1/2/3 queue | `ontology.red_flags` |
| **B. Document digitisation** | Tesseract OCR (English+Hindi if installed) / PDF text → date, document type, medications (dose, frequency), 13 lab tests with reference ranges, diagnoses; chronological timeline; abnormal flags; drug–drug and herb–drug interaction checks | `backend/app/ocr.py` |
| **C. Summary generator** | Standard format (CC → HPI → PMH/PSH → Drugs & allergy → Family → Personal → ROS → Prior investigations), editable and confirmable by the physician; optional LLM rewording limited to given facts; bilingual patient confirmation | `summary.py`, `llm.py`, `doctor.html` |
| **D. Consent, privacy, ABDM** | Granular consent records required before submit; DPDP right-to-erasure endpoint; kiosk guest sessions wiped after submission; image bytes never stored; FHIR R4 Bundle (Patient, Composition, Observation, MedicationStatement, Flag); ABDM adapter | `main.py`, `fhir.py` |
| Accessibility | Large-text and high-contrast toggles, big-button UI, audio prompts, Hindi UI | `frontend/` |
| Patient dashboard | Register/login, record history, delete-all-data | `index.html` |

## Architecture
```
Browser (patient kiosk / physician console) ──REST──▶ FastAPI
  Web Speech API (ASR/TTS)                            ├─ ontology.py  dialogue manager + red flags
                                                      ├─ ocr.py       OCR + entity extraction
                                                      ├─ summary.py / llm.py (optional)
                                                      ├─ fhir.py      FHIR bundle + ABDM adapter
                                                      └─ SQLite (users, consents, documents, records)
```

Design and governance details are documented in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
[`docs/SAFETY_AND_PRIVACY.md`](docs/SAFETY_AND_PRIVACY.md), and
[`docs/PROJECT_AUDIT.md`](docs/PROJECT_AUDIT.md). The adaptive interview is
exposed through `HistoryTakingAgent`; its default adapter is deterministic
until the unresolved “JEV” model identifier is verified.

## Honest status — real vs simulated
* **Real & tested:** dialogue/branching, red flags, OCR on printed images and text PDFs, extraction, timeline, interaction checks, auth, consent gating, priority queue, doctor review, FHIR bundle generation, erasure. Backend tests plus a Playwright run through the whole patient→doctor journey pass.
* **ABDM is mocked** (`ABDM_MODE=mock`). Live use needs HIP registration, gateway credentials and the consent-artefact/HIU callback flow; implement it in `fhir.abdm_push`. ABHA IDs are not verified against ABDM.
* **Voice** uses the browser Web Speech API (quality varies by browser, language and noise). For production Indic ASR/TTS, put Bhashini/AI4Bharat behind an `/api/asr` endpoint.
* **OCR:** handwritten prescriptions and scanned PDFs are unreliable with Tesseract; plug a stronger handwriting/Indic OCR model into `ocr.ocr_bytes`. When reading fails, the patient is asked to type the content.
* **LLM** is optional and untested without an API key; the deterministic path is the default. It may only reword reported facts, never diagnose.
* Reference ranges and interaction tables are small demo sets, **not clinically validated**. Clinicians must review the ontology, red-flag rules and tables before real use.
* Not production-hardened: add HTTPS, rate limiting, encryption at rest, audit logging and OTP/RBAC login before handling real patient data.

## API (OpenAPI docs at `/docs`)
`POST /api/auth/{register,login,guest}` · `POST /api/consent` · `POST /api/interview/next` · `POST /api/documents` (+`/text`) ·
`POST /api/summary` · `POST /api/submit` · `GET /api/doctor/records[/{id}]` · `PUT /api/doctor/records/{id}` · `DELETE /api/me/data`

Safety endpoints: `GET /api/red-flags/rules` returns rule provenance and review
status; `POST /api/red-flags/evaluate` returns structured findings, evidence,
missing information, urgency, classifier availability, and safe next steps.
See [`docs/REDFLAG_ENGINE.md`](docs/REDFLAG_ENGINE.md) before deployment.

Dataset and training infrastructure is documented in
[`docs/TRAINING_INFRASTRUCTURE.md`](docs/TRAINING_INFRASTRUCTURE.md) and the
truthful current status is recorded in
[`docs/TRAINING_STATUS.md`](docs/TRAINING_STATUS.md).

The grounded document-to-summary pipeline and its evaluation status are
described in [`docs/DOCUMENT_PIPELINE.md`](docs/DOCUMENT_PIPELINE.md).

Configurable ASR, transcript correction, provider status, and multilingual
evaluation are described in [`docs/ASR_MULTILINGUAL.md`](docs/ASR_MULTILINGUAL.md).

The research comparison registry, paired statistics, error-analysis protocol,
and achieved/pending results are in
[`docs/RESEARCH_EVALUATION.md`](docs/RESEARCH_EVALUATION.md).
