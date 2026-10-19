# MediKiosk project audit

## Baseline

Audit performed against the existing `medikiosk` tree on 2026-10-14. The
repository is a small Python 3.12 FastAPI application with a static HTML/CSS/
JavaScript frontend and SQLite persistence. The supplied datasets are present
under `Datasets/MediKiosk_Datasets`.

## Existing entry points

- `backend/app/main.py`: FastAPI app, auth, consent, interview, documents,
  summary, submit, doctor review, health.
- `backend/app/ontology.py`: deterministic adaptive question policy and
  red-flag rules.
- `backend/app/ocr.py`: PDF/image OCR and regex entity extraction.
- `backend/app/summary.py`: structured draft summary and patient confirmation.
- `backend/app/fhir.py`: FHIR R4 bundle and mock ABDM adapter.
- `backend/app/eda_api.py` and `backend/app/ml_pipeline.py`: aggregate EDA,
  data cleaning, and clearly labelled heuristic/optional ML helpers.
- `frontend/index.html` and `frontend/doctor.html`: patient and doctor flows.
- `backend/tests/test_api.py`: adaptive flow, OCR, full journey, auth and
  erasure coverage.

## Runtime and configuration

Dependencies are declared in `backend/requirements.txt`. Docker installs
English and Hindi Tesseract. `.env.example` contains doctor credentials,
ABDM mode, and optional Anthropic settings; secret values are not documented
here. SQLite defaults to `backend/data/medikiosk.db` and can be moved with
`MEDIKIOSK_DB`.

## Findings

1. The end-to-end demo path is already implemented and tested.
2. The history policy is deterministic, which is appropriate for the safety
   gate, but it previously had no explicit model-adapter boundary.
3. “JEV” is not identified in the supplied project files or configuration.
   It must remain configurable and must not be invented or silently replaced.
4. The browser provides voice capture through Web Speech APIs; a server ASR
   provider is not configured.
5. ABDM live exchange is intentionally not implemented; the default is mock.
6. The bundled clinical reference tables are demo/reference data and require
   clinical validation before real deployment.

## Verification baseline

Run `cd backend && python -m pytest -q`. The tests exercise OCR, adaptive
branching, red flags, consent, document extraction, summary generation, FHIR,
doctor review and guest-data cleanup.


## Addendum 2026-10-17
See `IMPLEMENTATION_STATUS.md` for verified defects (silent empty flags on engine failure, unrelated-negation false negatives), fixes, and unresolved items. `Datasets/` is tracked in git but absent from the zipped working tree; restore with `git checkout -- Datasets`.
