# Dataset Audit

Profiled from the files **actually on disk** by `backend/training/audit_datasets.py` (output: `evaluation_results/dataset_profile.json`). A manifest entry is never taken as proof a file exists.

**On-disk facts that limit everything else:** 0 image/PDF files and 0 audio files exist anywhere in `Datasets/`. All image manifests and audio sources are references to material that is **not present**.
No research-paper PDFs or Jupyter notebooks were found in the repository; the available literature and dataset references are the citations and source notes recorded in project documentation and manifests.

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

## Task labels and trainability audit

The following field-level inspection was performed on the current files, not inferred from historical counts:

| Task/source file | Rows and useful fields | Labels / supervision present | Training decision |
|---|---|---|---|
| `01_history_interview/interview_turns.csv` | 7,863 turns; `interview_id`, `patient_id`, `split`, `role`, `text`, `slot` | Contextual AI question slots with patient/interview grouping; reconstructed strictly from preceding turns | Supports only a synthetic next-slot imitation experiment. The separate structured file has 300 interview targets, split 240/30/30. |
| `02_ocr_handwriting/lab_result_entities.csv` | 1,238 rows; `report_id`, `patient_id`, `lab`, `test`, `value`, `unit`, reference interval, flag | Structured normalized lab fields, but no originating report text or character spans in this file | Useful for rule-extractor regression after joining the 394 available simulated text-pair reports; insufficient for token-classification fine-tuning. |
| `02_ocr_handwriting/prescription_entities.csv` | 1,011 rows; `rx_id`, `patient_id`, `drug`, `generic_key`, `dose_schedule`, `duration` | Structured prescription fields; no source text or spans | Not NER supervision. Upstream data terms need confirmation. |
| `02_ocr_handwriting/handwriting_words_manifest.csv`; `noisy_docs_manifest.csv` | 4,680 word labels; 1,000 document manifests | Image-path-in-ZIP references and text labels/JSON fields | Source ZIPs and pixels are absent; no image training or OCR evaluation can run from this checkout. |
| `02_ocr_handwriting/synthetic_documents_ocr_pairs.csv` | 892 pairs; `ground_truth_text`, `simulated_ocr_text`, synthetic metadata | Simulated text-to-text corruption pairs, no source pixels | May test text cleanup only; not OCR model training or image CER/WER. |
| `03_patient_summary/history_to_summary_synthetic.csv` | 300 synthetic interview/summary pairs; `input_dialogue`, `input_structured_json`, `summary_en` | Templated synthetic targets without required source-evidence IDs/spans | Pipeline smoke tests only; not grounded-generation fine-tuning evidence. |
| `03_patient_summary/aci_bench_dialogue_note_pairs.csv` | 207 dialogue/note pairs; `encounter_id`, `dialogue`, `note`, metadata | Paired note targets, but no source-linked fact annotations; license status unresolved | Defer model training pending permissions and evidence-grounding annotations. Splits: 67 train, 20 validation, 40 each in test1/test2/test3. |
| `03_patient_summary/mtsamples_notes_clean.csv` | 4,966 notes; `transcription`, specialty, metadata | Note-only text; no paired dialogue or source evidence | Style analysis only; cannot be treated as dialogue-to-note training pairs. |
| `04_asr_voice/asr_noisy_test_set.csv` | 900 rows; reference/transcript text, language, synthetic noise profile | Text-level simulated ASR pairs; no audio | Text normalization smoke evaluation only, not acoustic ASR training/evaluation. |
| `05_triage_redflag/red_flag_labeled_cases.csv` | 300 cases; complaint, symptoms, red-flag and triage labels | Synthetic/demo labels | Software regression only. Deterministic red-flag rules remain authoritative. |

The history-training examples have exactly one pre-answer target per recorded AI question after the initial complaint question. They are not independent turn samples: 7,863 turns reduce to 300 interviews/patients, and only 14 complaints occur. All external-origin dataset licenses remain subject to the per-resource register and any required upstream terms; local presence is not redistribution permission.

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

## Verification run status

No dataset, label, or source image was added or re-labelled for the clinical
pipeline checks. Synthetic PDF and raster documents are generated only inside
software tests; they are integration fixtures, not training or research data.
The current environment is macOS ARM with Python 3.14.7, scikit-learn 1.9.1,
NumPy 2.5.4, SciPy 1.18.1, Pillow 13.0.0, pypdf 6.21.1, and ReportLab 5.0.1.
The adaptive model uses the verified bundled 300-interview corpus and its
patient-grouped 240/30/30 split, seed 42, and validation-selected `C=100`;
results are synthetic template agreement only (see
[`MODEL_TRAINING.md`](./MODEL_TRAINING.md) and
[`EVALUATION_RESULTS.md`](./EVALUATION_RESULTS.md)).

Tesseract is not installed. Embedded-text PDF and synthetic text extraction
integration tests execute, but real raster OCR tests are blocked/skipped.
Accordingly there are no new OCR field-accuracy, CER, or WER results. Install
Tesseract on macOS with `brew install tesseract` (optionally
`brew install tesseract-lang` for Hindi), then validate with
`tesseract --version` and `tesseract --list-langs`. No permissions were
assumed for the external-origin ACI-Bench or MTSamples files.
