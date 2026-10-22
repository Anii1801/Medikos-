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
python -m training.adaptive.evaluate       # label audit + next-slot metrics + 3-policy replay + LOCO -> evaluation_results/adaptive/
python -m training.lab_extraction_eval --label current
python -m training.lab_scan_eval           # needs tesseract
python -m training.hindi_nlp_eval --label current
python -m training.render_reports          # tables for docs/EVALUATION_RESULTS.md
python scripts/generate_project_status.py  # runs pytest, writes docs/PROJECT_STATUS.md

python -m pytest -q                        # software tests
MEDIKIOSK_QUESTION_POLICY=learned uvicorn app.main:app --port 8000   # run the app with the learned policy (default: ontology)
```

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
