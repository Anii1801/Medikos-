# Dataset Audit

Profiled from the files **actually on disk** by `backend/training/audit_datasets.py` (output: `evaluation_results/dataset_profile.json`). A manifest entry is never taken as proof a file exists.

**On-disk facts that limit everything else:** 0 image/PDF files and 0 audio files exist anywhere in `Datasets/`. All image manifests and audio sources are references to material that is **not present**.

## File profile (rows, columns, empty cells, exact duplicate rows)

| file | rows | cols | empty cells | exact dup rows |
|---|---:|---:|---:|---:|
| `00_patient_master/patient_master.csv` | 500 | 29 | 9.3% | 0 |
| `00_patient_master/patient_master.jsonl` | 500 | 10 | 0.0% | 0 |
| `00_patient_master/patient_timeline.csv` | 1,392 | 6 | 0.0% | 0 |
| `01_history_interview/interview_turns.csv` | 7,863 | 9 | 0.0% | 0 |
| `01_history_interview/interviews.jsonl` | 300 | 5 | 0.0% | 0 |
| `01_history_interview/meditod_sample_dialogs.csv` | 359 | 7 | 8.0% | 0 |
| `01_history_interview/slot_inventory.csv` | 28 | 3 | 0.0% | 0 |
| `01_history_interview/structured_histories.csv` | 300 | 25 | 5.5% | 0 |
| `02_ocr_handwriting/handwriting_label_map.csv` | 78 | 3 | 0.0% | 0 |
| `02_ocr_handwriting/handwriting_words_manifest.csv` | 4,680 | 6 | 0.0% | 0 |
| `02_ocr_handwriting/lab_result_entities.csv` | 1,238 | 12 | 0.0% | 0 |
| `02_ocr_handwriting/noisy_docs_manifest.csv` | 1,000 | 11 | 0.0% | 0 |
| `02_ocr_handwriting/ocr_noise_summary.csv` | 6 | 5 | 0.0% | 0 |
| `02_ocr_handwriting/prescription_entities.csv` | 1,011 | 13 | 0.0% | 0 |
| `02_ocr_handwriting/synthetic_documents_ocr_pairs.csv` | 892 | 13 | 0.0% | 0 |
| `03_patient_summary/aci_bench_dialogue_note_pairs.csv` | 207 | 12 | 4.3% | 0 |
| `03_patient_summary/history_to_summary_synthetic.csv` | 300 | 9 | 0.0% | 0 |
| `03_patient_summary/mtsamples_notes_clean.csv` | 4,966 | 7 | 3.3% | 0 |
| `04_asr_voice/asr_noise_summary.csv` | 6 | 5 | 0.0% | 0 |
| `04_asr_voice/asr_noisy_test_set.csv` | 900 | 9 | 0.0% | 0 |
| `04_asr_voice/external_audio_sources.csv` | 4 | 4 | 0.0% | 0 |
| `05_triage_redflag/disease_knowledge.csv` | 41 | 6 | 0.8% | 0 |
| `05_triage_redflag/red_flag_labeled_cases.csv` | 300 | 12 | 7.8% | 0 |
| `05_triage_redflag/red_flag_rules.csv` | 8 | 5 | 0.0% | 0 |
| `05_triage_redflag/symptom2disease_text.csv` | 1,153 | 3 | 0.0% | 0 |
| `05_triage_redflag/symptom_binary_large_SAMPLE_5000.csv` | 5,000 | 378 | 0.0% | 41 |
| `05_triage_redflag/symptom_binary_test.csv` | 42 | 133 | 0.0% | 0 |
| `05_triage_redflag/symptom_binary_train_dedup.csv` | 304 | 133 | 0.0% | 0 |
| `05_triage_redflag/symptom_severity_weights.csv` | 133 | 2 | 0.0% | 0 |
| `06_ayush_prakriti/ayush_value_distribution.csv` | 22 | 3 | 0.0% | 0 |
| `06_ayush_prakriti/dashavidha_pariksha_with_context.csv` | 356 | 26 | 4.6% | 0 |
| `07_drug_safety/drug_interaction_alerts.csv` | 84 | 7 | 0.0% | 0 |
| `07_drug_safety/drug_interaction_reference.csv` | 9 | 5 | 0.0% | 0 |
| `07_drug_safety/patient_drug_lists.csv` | 377 | 5 | 0.0% | 0 |
| `DATASET_INDEX.csv` | 35 | 5 | 1.7% | 0 |
| `EXTERNAL_SOURCES.csv` | 16 | 4 | 0.0% | 0 |

(`symptom_binary_large_SAMPLE_5000.csv` has 41 exact duplicate rows; the `_train_dedup` file is already de-duplicated. 9.3% empty cells in `patient_master.csv` are legitimately optional fields.)

## Provenance, task fit and risks

All records in this project's supplied data are **synthetic or simulated unless stated otherwise**; none are real patients. External sources marked "not downloaded" in `EXTERNAL_SOURCES.csv` are absent. The dataset index carries no licence column, so licences for the external-origin files (ACI-Bench, MTSamples, MediTOD sample, Symptom2Disease/Kaggle-derived files) are **unverified and must be confirmed before redistribution or any use beyond local research**.

| Dataset | Nature | Intended use | Patient linkage | Leakage / quality risks | Recommended use |
|---|---|---|---|---|---|
| `00_patient_master` | synthetic, 500 patients, dataset-defined 400/50/50 split | patient context, split identifiers | master key for interviews/documents | which columns are derived labels vs attributes is not documented; avoid feeding derived labels into models | split source; context only |
| `01_history_interview/interview_turns.csv` + `structured_histories.csv` | synthetic, 300 interviews / 7,863 turns, 14 complaints; 1 interview per patient | adaptive questioning | 1:1 patient<->interview, no patient spans splits (verified) | **fixed question template (2 orderings), 2 wording variants per question, triage = f(severity)**; turns are not independent; 2 complaints have fewer than 10 interviews (difficulty sleeping; sudden one-sided weakness with slurred speech), the latter being the stroke-like emergency case; 0 duplicate patient-answer sequences | pipeline/regression and extraction tests; **not** evidence of adaptive skill |
| `interviews.jsonl` | verified identical re-packaging of the CSV (300/300) | none | same | double-counting if used with the CSVs | ignore for training |
| `meditod_sample_dialogs.csv` | 3 canonical dialogues (359 rows) | format reference | none | UMLS-licensed full set absent | do not call this MediTOD |
| `02_ocr_handwriting/lab_result_entities.csv` + `synthetic_documents_ocr_pairs.csv` | synthetic; labels **verified to join** the source text (394/394) | lab extraction benchmark | report ids only | one uniform layout; developed against it | benchmark + regression |
| `prescription_entities.csv`, handwriting/noisy manifests | synthetic labels; **images absent** | text-level robustness only | none | cannot be OCR-evaluated | not used here |
| `03_patient_summary/history_to_summary_synthetic.csv` | synthetic pairs | pipeline tests | per interview | template-generated targets | smoke tests only |
| `aci_bench_dialogue_note_pairs.csv` | external dialogue-note pairs (207) | summary experiments | none | provenance/licence unverified | verify, then evaluate separately from synthetic |
| `mtsamples_notes_clean.csv` | external clinical notes, **note-only** (4,966) | clinical-NLP experiments | none | no dialogue pairing exists | never fabricate dialogue/summary pairs |
| `04_asr_voice` | simulated noisy **text**; audio absent | text-noise robustness | none | not acoustic data | no ASR training or accuracy claims |
| `05_triage_redflag` | synthetic labelled cases, illustrative rules | rule regression | per case | synthetic labels; symptom-to-disease files are not question-selection ground truth | rule regression/error analysis; not validation |
| `06_ayush_prakriti`, `07_drug_safety` | small, illustrative | separate optional modules | none | interaction table is tiny and unvalidated | keep isolated; not comprehensive safety |

## Interview-data profile used for the adaptive experiment

Language: 255 Hindi (Devanagari) / 45 English-script interviews. Splits 240/30/30 interviews, no patient in two splits, no identical patient-answer sequences across splits (see `evaluation_results/adaptive/label_quality_audit.json` for the duplicate and complaint-coverage counts, per-slot answer entropy and the 2-ordering finding).

## Recommended next data work

1. Obtain a small **consented, de-identified, clinician-annotated** interview set with genuinely varying question order. 2. Obtain real, permissioned scanned reports with field-level annotation. 3. Confirm licences for the external-origin files. 4. Document which patient-master columns are attributes vs derived labels.
