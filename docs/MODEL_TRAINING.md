# Model Training Guide

One end-to-end, reproducible experiment exists: the **adaptive next-question-slot ranker**. Everything else in the repository is rule-based
(red flags, lab parsing, Hindi/Hinglish rules, summary builder) and is evaluated, not trained. No neural model was trained: the data (300
synthetic, templated interviews; 14 complaints) does not justify one, and the label audit shows why (see below).

## Commands (from a clean checkout)

```bash
cd backend
pip install -r requirements.txt scikit-learn numpy scipy          # sklearn/scipy are needed for TRAINING only, not for serving
export PYTHONPATH=.

python -m training.audit_datasets          # profile every file on disk -> evaluation_results/dataset_profile.json
python -m training.adaptive.train          # fit on TRAIN split, choose C on VALID, write models/adaptive_ranker/v1/ (test split never read)
python -m training.adaptive.evaluate       # label audit + four-way next-slot comparison + policy replays + LOCO
python -m training.lab_extraction_eval --label current
python -m training.prescription_extraction_eval
python -m training.lab_scan_eval --output ../evaluation_results/lab_scan_eval_macos.json
python -m training.hindi_nlp_eval --label current
python -m training.render_reports          # tables for docs/EVALUATION_RESULTS.md
python scripts/generate_project_status.py  # runs pytest, writes docs/PROJECT_STATUS.md

python -m pytest -q                        # software tests
MEDIKIOSK_QUESTION_POLICY=learned uvicorn app.main:app --port 8000   # run the app with the learned policy (default: ontology)
```

On macOS, Homebrew provides Tesseract (`brew install tesseract`, optional
additional languages via `brew install tesseract-lang`). Playwright's optional
browser tests use:

```bash
./.venv/bin/python -m pip install playwright
./.venv/bin/python -m playwright install chromium
```

Re-run the test suite with `cd backend && ../.venv/bin/python -m pytest -q -rs`.
The Tesseract image/report experiment supports `--output` so new host-specific
results do not overwrite the preserved prior artifact.

## What the ranker is

* **Task:** given the interview state *before* a question is asked, rank the next question slot (13 slots from the dataset's `slot_inventory.csv`, plus STOP).
  Not a disease predictor. State = chief-complaint wording (char 2-4-grams, Hindi or English) + the **set** of slots already asked.
* **Model:** multinomial logistic regression, fitted with scikit-learn, exported as plain JSON (`weights.json`, 245 KB). Serving uses pure Python
  (`app/adaptive/ranker.py`): no pickle is ever loaded and the file's SHA-256 is verified against `manifest.json`.
* **Ranking several candidates:** the model is rolled forward; a predicted slot the app cannot ask (e.g. `rad` outside chest pain) is treated as skipped.
* **Splits:** the dataset's own patient-level `split` column (240/30/30 interviews). Interview-grouped CV and leave-one-complaint-out are used for extra evidence.
* **Leakage control:** the state is built chronologically from turns before the predicted question; `tests/test_adaptive_ranker.py` corrupts every later turn and asserts the state is unchanged.
* **Training views:** each interview is used twice, with the patient's recorded wording and with the ontology label the live app holds (oracle complaint normalisation; see `app/adaptive/schema.py`).
* **Artifacts:** `backend/models/adaptive_ranker/v1/{weights,config,manifest,train_report}.json`, `MODEL_CARD.md`. Rebuild with the commands above; nothing needs downloading.

## How it is integrated

`AdaptiveHistoryTakingAgent` order of authority per question: (1) structural questions and the one currently on screen, (2) **mandatory safety questions** for the complaint
(`schema.MANDATORY_FIRST`, pending clinician sign-off), (3) the learned ranking over the *remaining eligible ontology questions*, (4) the reviewed ontology order whenever the
ranker is unavailable, errors, sees an empty state, an unfamiliar complaint (n-gram out-of-vocabulary > 0.5) or is under-confident (< 0.5). The model **never removes** a question
(tested), so required coverage cannot fall. API responses expose `policy`, `selection_basis` and `fallback_reason`.

## Why no larger model

The audit (`evaluation_results/adaptive/label_quality_audit.json`): 2 question orderings, 2 text variants per question, triage = f(severity), 26/161 (complaint, slot) pairs with one constant
answer. A neural model or LLM fine-tune would memorise templates and its metrics would look excellent for the wrong reason. Revisit when recorded interviews with genuinely varying order
or clinician "best next question" labels exist.

## Other ideas from the reference list (not copied)

Healthcare-chatbot and Llama/Gemma fine-tuning notebooks are disease/Q&A models, not adaptive interviewers, and were not used. The clinical-notes-summarisation and lab-literacy ideas informed the
extraction-first design already in the repository (facts with provenance feed the summary). No external metrics are reproduced here.

## Known limitations

Synthetic data; provisional required-slot and safety-critical lists; thresholds fixed a priori; no real-patient validation; the unseen-complaint deferral does not work (see EVALUATION_RESULTS A3).

## Model selection and training decisions

| Task | Selected model / baseline | Data actually available | Decision, license and integration |
|---|---|---|---|
| PDF/image OCR | `pypdf` embedded-text extraction; Tesseract OCR for raster/scanned pages | No source pixels are present. The 892 OCR pairs are synthetic text, and the image manifests reference source ZIPs that are absent. | Tesseract 5.5.3 was installed and evaluated on generated PNG/JPEG/WEBP/TIFF and scanned PDFs; this is not real-scan or handwriting evidence. Tesseract is Apache-2.0; language-data files have their own terms. No OCR model was trained. |
| Clinical entities | Existing deterministic `ocr.extract` / `ClinicalNLPService` rules | 1,238 lab rows join 394 synthetic report texts; 1,011 prescription rows join 498 synthetic prescription texts. All ID/patient/split joins agree, but there are no entity character spans or source images. | Run text-to-field regression only; do not fine-tune NER from field rows. `emilyalsentzer/Bio_ClinicalBERT` is an English candidate encoder; its official model card/API declares MIT. A general alternative is DistilBERT (`Apache-2.0`). Both are deferred until licensed source text and adjudicated token spans exist. Rules remain the live baseline. |
| Negation, uncertainty and temporality | Existing rule-based `ClinicalNLPService` | No independently adjudicated assertion/temporality labels; structured histories are synthetic and not mention-level annotations. | Do not train a classifier yet. Keep the explicit assertion, temporal context, source span, and unverified/clinician-review states; collect annotated positive, denied, uncertain, historical, hypothetical, and missing examples first. |
| Adaptive question ranking | Multinomial logistic regression; deterministic ontology order is the safe default/baseline | 300 synthetic interviews (240/30/30 patient-group split); 7,863 turns, reconstructed into pre-answer states. | Retrained and evaluated below. scikit-learn is BSD-3-Clause. Checkpoint is `adaptive_ranker/v1`, loaded by `app/adaptive/ranker.py`; opt-in only with `MEDIKIOSK_QUESTION_POLICY=learned`. Do not claim clinical utility: its test result matches an oracle complaint/template lookup. |
| Evidence-grounded report generation | Deterministic extraction-first summary | 300 synthetic history-summary pairs; 207 ACI-Bench dialogue/note pairs; 4,966 note-only MTSamples records. ACI-Bench terms are unresolved in the local register, and the pairs lack the report's required document/source evidence links. | Keep the deterministic summary and clinician approval. Do not SFT on note-only rows or treat ungrounded dialogue/note pairs as evidence-grounded targets. Qwen2.5-1.5B-Instruct is a candidate (official card: Apache-2.0), not installed, benchmarked, or fine-tuned. |
| Contradiction detection | Deterministic source-preserving checks in `ClinicalNLPService` and the summary pipeline | No adjudicated conflict/non-conflict corpus. | Keep both sources and request review; a supervised classifier is deferred until conflict labels and relevant time/unit context are collected. |
| Red flags | `RedFlagEngine` deterministic rules; classifier adapter remains unavailable | 300 synthetic/demo cases only; rule metadata is marked provisional pending local clinician sign-off. | Never replace or suppress deterministic safety findings with a learned model. The bundled audit is software-only, not clinical sensitivity/specificity evidence. |

Model-card license metadata was checked on the official Hugging Face model pages on 2026-10-22:
[Bio_ClinicalBERT](https://huggingface.co/emilyalsentzer/Bio_ClinicalBERT),
[DistilBERT base uncased](https://huggingface.co/distilbert/distilbert-base-uncased), and
[Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct).
Upstream dataset permissions remain separate and must be verified before use.

No model was retrained during the evidence-fidelity and environment-validation
continuation. The existing adaptive ranker checkpoint, manifest, grouped split,
and validation-selected configuration were preserved.

## Reproduced experiment on 2026-10-22

The ranker was retrained from the bundled interview data with seed 42. The patient-group split contained 240 train, 30 validation, and 30 held-out test interviews; 6,056 training and 746 validation examples were generated from the recorded and app-label views. Validation selected `C=100` from `{0.1, 1, 10, 100}`. Training took 2.21 seconds on the local CPU environment; the 240,117-byte JSON checkpoint SHA-256 is recorded in `backend/models/adaptive_ranker/v1/manifest.json`.

| Held-out test view | Interviews / next-slot examples | Top-1 | Top-3 | NDCG@1 | NDCG@3 | Majority baseline | Oracle template lookup |
|---|---:|---:|---:|---:|---:|---:|---:|
| Recorded complaint wording | 30 / 371 | 1.000 | 1.000 | 1.000 | 1.000 | 0.081 | 1.000 |
| App ontology-label wording | 30 / 371 | 0.997 | 1.000 | 0.997 | 0.999 | 0.081 | 1.000 |

These are repeated-template imitation results on synthetic data, not evidence of clinical relevance or generalization. The model has no answer-content features, and the oracle template baseline reaches the same score on the recorded wording. The independent deterministic ontology and mandatory safety-question layer remain authoritative.

The held-out experiment also compares next-slot agreement across four
selection approaches (30 test interviews / 371 pre-answer states):

| selector | top-1 | NDCG@1 | NDCG@3 |
|---|---:|---:|---:|
| Existing ontology/rule selection | 0.162 | 0.162 | 0.162 |
| Logistic regression, recorded patient wording | 1.000 | 1.000 | 1.000 |
| Logistic regression, application labels | 0.997 | 0.997 | 0.999 |
| Training-only oracle complaint/state template lookup | 1.000 | 1.000 | 1.000 |

The single-choice ontology and oracle policies have no ranking beyond their
chosen next question, so their NDCG@3 equals NDCG@1. The oracle is a deliberately
strong template-imitation baseline, not a deployable or clinical comparator.
The top-1/NDCG results measure agreement with recorded synthetic choices only.
The operational replays separately measure required-slot coverage, mandatory
safety-question coverage, safety-critical omissions, duplicate-question rate,
and questions asked per interview. `learned_ranker_recorded` and
`learned_ranker` (application-label wording) both preserve the same mandatory
safety layer; the learned ranker remains opt-in.

## Hardware and dependency audit

Audited on Apple M4 macOS ARM with 16 GiB system memory. The project environment has Python 3.14.7, scikit-learn 1.9.1, NumPy 2.5.4, SciPy 1.18.1, Pillow 13.0.0, pypdf 6.21.1, and ReportLab 5.0.1. Tesseract 5.5.3 (`eng`, `osd`), Playwright 1.64.0, and Playwright Chromium 156 were installed to complete environment-dependent validation. PyTorch, Transformers, Datasets, and PEFT are not installed; no NVIDIA/CUDA device was used. Apple Metal hardware exists, but a PyTorch/MPS path was not tested. The small feature-based ranker can be trained with the existing CPU stack. No transformer fine-tuning was attempted.

## Annotation required before further training

- **NER / assertion / temporality:** store the de-identified source text and immutable document/group ID; annotate exact character offsets and entity type (symptom, condition, medication, strength/dose, route, frequency, lab name/value/unit, date, allergy, procedure), plus assertion (present/absent/uncertain/historical/hypothetical), experiencer, and temporal context. Independently annotate and adjudicate a held-out patient/document-group split. The current lab/prescription tables do not contain those spans.
- **Question ranking:** capture the interview state before each turn, the eligible candidate questions, unresolved slots, answer/budget context, and clinician relevance judgments. Vary question order naturally and split by patient; one synthetic template cannot establish a useful learned ranking.
- **Report generation:** create reviewed structured targets whose every clinical claim points to evidence IDs, source document/page/span, date, assertion, uncertainty, and conflicts. Include missing-information labels and clinically important omissions; do not use note-only corpora as paired inputs.
- **OCR / ASR:** retain permissioned source images/audio with exact transcripts and document/speaker-group keys. Simulated text corruption is not a substitute for images or audio.

The proposed review record is defined in [`clinical_annotation.schema.json`](../backend/training/configs/clinical_annotation.schema.json); it requires de-identification, permission status, source-text SHA-256, opaque group IDs, exact character offsets, and adjudication state. No annotated corpus was fabricated. The dataset profile is recalculated by `cd backend && PYTHONPATH=. python -m training.audit_datasets`; the detailed on-disk counts, provenance and limitations are in [`DATASET_AUDIT.md`](./DATASET_AUDIT.md). The existing manifest-based `training.validate` and `training.prepare` commands provide schema-field checks, duplicate fingerprints, grouped splits, split-leakage assertions, seeds and file hashes. Current upstream licenses for bundled external-origin corpora are not all verified, so the audit treats them as local-only pending confirmation.

## Research-paper experimental setup

For a reproducible report of the existing experiment, identify the task as next-question-slot imitation, the algorithm as multinomial logistic regression, seed 42, feature schema as chief-complaint character 2–4-grams plus language script and the set of already asked canonical slots, and data as the synthetic 300-interview corpus. Report patient-level 240/30/30 splits, validation-only selection of `C`, the held-out 30-interview/371-example results above, and the template-lookup baseline. State explicitly that no clinical validation, prospective workflow study, neural fine-tuning, OCR image evaluation, acoustic ASR evaluation, or report-generation model comparison was performed. Do not present the test top-1 score as clinical accuracy.
