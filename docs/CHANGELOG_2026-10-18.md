# MediKiosk changes — 2026-10-18

## Changes made

- Renamed the patient-page navigation link to **Doctor Portal**. The doctor console remains a separate `doctor.html` page; doctor API endpoints remain protected by the existing backend role dependency.
- Removed the doctor-console ML risk panel and the old UI claims of a trained MIMIC-IV risk model, Kaggle F1 score, and specific NER/AYUSH model training. No validated model checkpoints or reproducible training artefacts were present in the uploaded project.
- Changed the legacy red-flag ML API response to report `model_available: false`, a `null` probability, and no predicted conditions when no validated checkpoint is bundled. This avoids presenting a heuristic as a calibrated clinical probability or a disease diagnosis.
- Connected the patient interview UI to the persisted `HistoryTakingAgent` session endpoints. The session carries the AYUSH-mode setting and answer updates are posted to the backend.
- Fixed repeated interview-session reads so refreshing/polling the current question does not skip it. The current unanswered question is retained in persisted state.
- Reworked browser voice recognition lifecycle handling: feature detection, interim/final transcript handling, language selection, visible listening state, permission/network/no-speech errors, retry guidance, editable text, transcript persistence, and confidence-aware option matching that asks the patient to verify the selected option before continuing.
- Added a model-selection and dataset-governance document with published candidates and explicit caveats.
- Corrected local startup to load `.env` when present and fixed Docker packaging so the `Datasets/` directory is copied into the image.
- Updated doctor login UI to remove prefilled demo username and public demo-password text. The `.env.example` now makes the administrator set a password before first run.

## Research-based model recommendation

- Use the current deterministic state/policy layer as the safety and duplicate-prevention baseline for adaptive history-taking. Evaluate against the published MediTOD benchmark where its official data and terms permit.
- Consider `google/mt5-base` + LoRA based on NLP4Health (2025) for multilingual clinical summarization/QA, not as an automatic replacement for the adaptive question policy.
- Compare the Qwen LoRA/QLoRA approaches from the 2025 NLP-AI4Health shared-task papers only after checking the exact released artefacts, license, hardware requirements and task-specific performance.
- Do not use generative models as the sole red-flag decision mechanism. Keep clinician-reviewed rules independent.

## Dataset status

The uploaded repository already contained `Datasets/MediKiosk_Datasets` with local manifests, synthetic/internal data, small samples, and some research-derived resources. No bulk external dataset download was added because the remaining assets include image corpora not included in the archive and research corpora with access/license conditions requiring verification. The dataset index and external-source register remain in the project; `docs/MODEL_SELECTION_AND_DATASETS.md` distinguishes included data from absent external data. The bundled data must not be represented as all publication-ready or clinically validated.

## Verification

- Python compilation: passed.
- JavaScript syntax check of inline scripts in `frontend/index.html` and `frontend/doctor.html`: passed.
- Backend tests: **92 passed, 6 skipped**.
- Browser microphone testing was not performed in this environment; real microphone permission, speech service availability, browser-specific behaviour, and audio quality still require manual verification in Chrome/Edge on `localhost` or HTTPS.
- No model training, external corpus download, clinical validation, or live ABDM integration was performed.
