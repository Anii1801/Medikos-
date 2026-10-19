# MediKiosk Datasets (SIH 2026 PS-4) - per-module build

Everything is keyed by `patient_id` / `interview_id` (see 00_patient_master). Splits are by patient (400 train / 50 valid / 50 test) so no patient leaks across splits.

| Module | Folder | Main data |
|---|---|---|
| Patient master and timeline | 00_patient_master | 500 patients, timelines, FHIR bundles |
| History-taking dialogue | 01_history_interview | 300 interviews, 7,863 turns |
| OCR and handwriting | 02_ocr_handwriting | 892 doc pairs, 1,000 noisy docs, 4,680 handwriting words |
| Patient summary | 03_patient_summary | 300 synthetic + 207 ACI-Bench + 4,966 MTSamples |
| ASR / voice | 04_asr_voice | 900 noisy-ASR rows |
| Triage / red flags | 05_triage_redflag | rules, 300 labelled cases, symptom sets |
| AYUSH / Prakriti | 06_ayush_prakriti | 356 Dashavidha records |
| Drug safety | 07_drug_safety | interaction table + alerts |

Also: DATASET_INDEX.csv (every file), EXTERNAL_SOURCES.csv (all links + status), QUALITY_REPORT.md (limitations).
Not copied (too large): the 1,000 noisy-doc images (304 MB), 4,680 handwriting images (31 MB), full data.csv (182 MB). Manifests point to them inside your original zips.
