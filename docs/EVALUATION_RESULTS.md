# Evaluation Results

> **Read this first.** Every number below comes from **synthetic, templated data** and from software replays. None of it is evidence of
> clinical performance. Adaptive-ranker tables are rendered from their committed JSON outputs; the report-fidelity and OCR tables below
> summarize the explicitly named output artifacts and use exact numerators and denominators.

## 0. Summary: what the results do and do not show

| Question | Answer from the data |
|---|---|
| Does the learned ranker predict the recorded next question? | Yes, ~100% top-1. **This is not evidence of adaptivity**: a lookup of the recorded template given the complaint also scores 100% (A1, A2). |
| Does the learned policy ask in a demonstrably different order from the fixed questionnaire? | It differs from the fixed *dataset template* in 77% of interviews (safety questions are pulled forward and the app's own questions interleave) but at **no budget does it beat the no-learning ablation on required-slot coverage by more than 0.03** (A5). |
| Does it beat the existing ontology policy? | At full interview length: **no, identical** (A5). Under a question budget it wins, but the identical-to-ablation result shows the gain comes from the **safety-first + schema-first structure**, not the learned signal. |
| Where does the learned signal show up? | At a 10-question budget it avoids safety-critical omissions (0% vs 100% for the ablation) because it follows the recorded template order, which asks drug/allergy history before family/personal history. That is imitation of a template, not a discovery. At budgets <= 8 **every** policy omits safety-critical slots. |
| Is the model safe to rely on for unseen complaints? | Not by its own confidence. Leave-one-complaint-out shows it stays confident when wrong (A3). The errors are all `rad` applicability, which the app cannot ask outside chest pain, so ranking is unaffected, but the deferral thresholds do **not** detect unseen complaints. |
| Does the doctor-facing report preserve a known synthetic encounter? | Yes: 31/31 exact predeclared reference checks in one two-document end-to-end encounter (H). This is a software-fidelity test, not clinical validation. |
| Default policy | **Reviewed ontology policy stays the default.** The learned ranker is opt-in (`MEDIKIOSK_QUESTION_POLICY=learned`). |

The genuinely actionable findings were about the *existing* system: the frozen ontology covered only 75% of the dataset's history slots, and lab/Hindi extraction had large, silent failures (sections B and C). These are fixed and re-measured.

## A. Adaptive question selection

Protocols: `official_test` = checkpoint trained on 240 train interviews, scored on the 30 untouched test interviews. `grouped_cv` = 5-fold, complaint-stratified, interview/patient-grouped out-of-fold over all 300. C chosen on the validation split only. Intervals: 95% cluster bootstrap over interviews (B=2000). `required slots` = provisional template-derived list (`training/adaptive/config/required_slots.json`), **pending clinician review**; `safety-critical` = sev, assoc, pmh, drug, allergy (+ char, rad for chest pain and stroke-like complaints), also provisional.

### A1. Label-quality audit (run before training)

- 300 interviews / 7,863 turns; **2 distinct question orderings** (differing only by whether `rad` is asked).
- Best guess of the next recorded question from the asked-set alone: **96.6%**; from asked-sequence + complaint: **100.0%**.
- Question text variants per slot: {2} (one Hindi, one English). Triage priority = deterministic function of severity: 300/300.
- 26 of 161 (complaint, slot) pairs have a single constant answer.
- Conclusion: The recorded 'next question' is a fixed template: 2 question orderings (4 if the inserted RED_FLAG_ALERT turn is counted), differing only by whether 'rad' is asked, which the complaint fixes. A model that reproduces it learns the template, not a question-selection skill; top-1 accuracy is therefore uninformative and policy-level metrics (coverage, redundancy, turns, safety omissions) are reported instead.

### A2. Next-slot prediction (recorded next question)

| protocol | view | learned top-1 | top-3 | NDCG@1 | NDCG@3 | majority-class top-1 | template lookup (oracle complaint) top-1 |
|---|---|---|---|---|---|---|---|
| official_test | recorded | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.081 | 1.000 |
| official_test | app_label | 0.997 [0.992, 1.000] | 1.000 [1.000, 1.000] | 0.997 [0.992, 1.000] | 0.999 [0.997, 1.000] | 0.081 | 1.000 |
| grouped_cv | recorded | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.080 | 1.000 |
| grouped_cv | app_label | 0.997 [0.996, 0.999] | 1.000 [1.000, 1.000] | 0.997 [0.996, 0.999] | 0.999 [0.998, 1.000] | 0.080 | 1.000 |

### A3. Unseen-complaint generalisation (leave-one-complaint-out)

| held-out complaint | states | deferred to reviewed policy | top-1 when model used | wrong but used | top-1 overall |
|---|---:|---:|---:|---:|---:|
| burning in the chest and stomach after meals | 624 | 0.0% | 96.3% | 23 | 96.3% |
| chest pain | 312 | 0.0% | 100.0% | 0 | 100.0% |
| constipation | 408 | 38.0% | 100.0% | 0 | 100.0% |
| cough and breathlessness | 624 | 85.9% | 100.0% | 0 | 100.0% |
| difficulty sleeping | 216 | 54.2% | 100.0% | 0 | 100.0% |
| excessive thirst and frequent urination | 768 | 87.1% | 100.0% | 0 | 100.0% |
| fever | 672 | 59.1% | 100.0% | 0 | 100.0% |
| headache with dizziness | 864 | 50.0% | 91.7% | 36 | 91.7% |
| itching with skin rash | 456 | 100.0% | n/a | 0 | 91.7% |
| joint pain and morning stiffness | 240 | 8.3% | 90.9% | 20 | 91.7% |
| knee pain | 816 | 0.0% | 100.0% | 0 | 100.0% |
| low back pain | 648 | 0.0% | 100.0% | 0 | 100.0% |
| pain in the abdomen | 408 | 0.0% | 100.0% | 0 | 100.0% |
| sudden weakness on one side and slurred speech | 144 | 100.0% | n/a | 0 | 100.0% |

### A4. Policy comparison — official test split (30 interviews)

**Budget: no limit**

| policy | required-slot coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | questions outside dataset schema |
|---|---|---|---|---|---|
| fixed_template | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.4 | 0.00 | 0.00 |
| ontology_v0_frozen | 0.766 [0.746, 0.789] | 0.067 [0.000, 0.167] | 13.5 | 0.33 | 3.30 |
| ontology_v1_current | 0.974 [0.962, 0.987] | 0.000 [0.000, 0.000] | 15.1 | 0.33 | 3.30 |
| safety_layer_uniform | 0.974 [0.962, 0.987] | 0.000 [0.000, 0.000] | 15.1 | 0.33 | 3.30 |
| learned_ranker | 0.974 [0.962, 0.987] | 0.000 [0.000, 0.000] | 15.1 | 0.33 | 3.30 |

**Budget: 12 questions max**

| policy | required-slot coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | questions outside dataset schema |
|---|---|---|---|---|---|
| fixed_template | 0.972 [0.959, 0.985] | 0.000 [0.000, 0.000] | 12.0 | 0.00 | 0.00 |
| ontology_v0_frozen | 0.761 [0.745, 0.778] | 0.067 [0.000, 0.167] | 12.0 | 0.33 | 1.87 |
| ontology_v1_current | 0.886 [0.866, 0.906] | 0.000 [0.000, 0.000] | 12.0 | 0.33 | 1.30 |
| safety_layer_uniform | 0.974 [0.962, 0.987] | 0.000 [0.000, 0.000] | 12.0 | 0.33 | 0.20 |
| learned_ranker | 0.974 [0.962, 0.987] | 0.000 [0.000, 0.000] | 12.0 | 0.33 | 0.20 |

**Budget: 10 questions max**

| policy | required-slot coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | questions outside dataset schema |
|---|---|---|---|---|---|
| fixed_template | 0.810 [0.799, 0.821] | 0.367 [0.200, 0.533] | 10.0 | 0.00 | 0.00 |
| ontology_v0_frozen | 0.645 [0.627, 0.663] | 0.100 [0.000, 0.233] | 10.0 | 0.33 | 1.30 |
| ontology_v1_current | 0.724 [0.706, 0.742] | 0.933 [0.833, 1.000] | 10.0 | 0.33 | 1.30 |
| safety_layer_uniform | 0.828 [0.815, 0.844] | 1.000 [1.000, 1.000] | 10.0 | 0.33 | 0.00 |
| learned_ranker | 0.828 [0.815, 0.844] | 0.000 [0.000, 0.000] | 10.0 | 0.33 | 0.00 |

**Budget: 8 questions max**

| policy | required-slot coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | questions outside dataset schema |
|---|---|---|---|---|---|
| fixed_template | 0.648 [0.639, 0.656] | 1.000 [1.000, 1.000] | 8.0 | 0.00 | 0.00 |
| ontology_v0_frozen | 0.483 [0.467, 0.500] | 1.000 [1.000, 1.000] | 8.0 | 0.33 | 1.30 |
| ontology_v1_current | 0.562 [0.545, 0.578] | 1.000 [1.000, 1.000] | 8.0 | 0.33 | 1.30 |
| safety_layer_uniform | 0.666 [0.654, 0.681] | 1.000 [1.000, 1.000] | 8.0 | 0.33 | 0.00 |
| learned_ranker | 0.666 [0.654, 0.681] | 1.000 [1.000, 1.000] | 8.0 | 0.33 | 0.00 |

**Budget: 6 questions max**

| policy | required-slot coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | questions outside dataset schema |
|---|---|---|---|---|---|
| fixed_template | 0.486 [0.479, 0.492] | 1.000 [1.000, 1.000] | 6.0 | 0.00 | 0.00 |
| ontology_v0_frozen | 0.346 [0.325, 0.367] | 1.000 [1.000, 1.000] | 6.0 | 0.00 | 1.30 |
| ontology_v1_current | 0.351 [0.328, 0.376] | 1.000 [1.000, 1.000] | 6.0 | 0.00 | 1.30 |
| safety_layer_uniform | 0.504 [0.492, 0.518] | 1.000 [1.000, 1.000] | 6.0 | 0.33 | 0.00 |
| learned_ranker | 0.517 [0.506, 0.530] | 1.000 [1.000, 1.000] | 6.0 | 0.17 | 0.00 |


### A5. Policy comparison — grouped CV, out-of-fold over all 300 interviews

**Budget: no limit**

| policy | required-slot coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | questions outside dataset schema |
|---|---|---|---|---|---|
| fixed_template | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.6 | 0.00 | 0.00 |
| ontology_v0_frozen | 0.754 [0.746, 0.763] | 0.020 [0.007, 0.037] | 13.8 | 0.44 | 3.66 |
| ontology_v1_current | 0.959 [0.955, 0.964] | 0.000 [0.000, 0.000] | 15.4 | 0.44 | 3.66 |
| safety_layer_uniform | 0.959 [0.955, 0.964] | 0.000 [0.000, 0.000] | 15.4 | 0.44 | 3.66 |
| learned_ranker | 0.959 [0.955, 0.964] | 0.000 [0.000, 0.000] | 15.4 | 0.44 | 3.66 |

Paired differences (same interviews; coverage / safety-omission rate / questions):

- learned_ranker minus fixed_template: coverage -0.041 [-0.045, -0.036]; safety-omission 0.000 [0.000, 0.000]; questions 2.830 [2.777, 2.880]
- learned_ranker minus ontology_v1_current: coverage 0.000 [0.000, 0.000]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- learned_ranker minus safety_layer_uniform: coverage 0.000 [0.000, 0.000]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- ontology_v1_current minus ontology_v0_frozen: coverage 0.205 [0.198, 0.211]; safety-omission -0.020 [-0.037, -0.007]; questions 1.613 [1.550, 1.680]

**Budget: 12 questions max**

| policy | required-slot coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | questions outside dataset schema |
|---|---|---|---|---|---|
| fixed_template | 0.956 [0.952, 0.960] | 0.000 [0.000, 0.000] | 12.0 | 0.00 | 0.00 |
| ontology_v0_frozen | 0.748 [0.741, 0.754] | 0.020 [0.007, 0.037] | 12.0 | 0.44 | 1.96 |
| ontology_v1_current | 0.849 [0.841, 0.856] | 0.000 [0.000, 0.000] | 12.0 | 0.44 | 1.66 |
| safety_layer_uniform | 0.959 [0.955, 0.964] | 0.000 [0.000, 0.000] | 12.0 | 0.44 | 0.26 |
| learned_ranker | 0.959 [0.955, 0.964] | 0.000 [0.000, 0.000] | 12.0 | 0.44 | 0.26 |

Paired differences (same interviews; coverage / safety-omission rate / questions):

- learned_ranker minus fixed_template: coverage 0.003 [0.002, 0.005]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- learned_ranker minus ontology_v1_current: coverage 0.111 [0.106, 0.115]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- learned_ranker minus safety_layer_uniform: coverage 0.000 [0.000, 0.000]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- ontology_v1_current minus ontology_v0_frozen: coverage 0.101 [0.096, 0.106]; safety-omission -0.020 [-0.037, -0.007]; questions 0.000 [0.000, 0.000]

**Budget: 10 questions max**

| policy | required-slot coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | questions outside dataset schema |
|---|---|---|---|---|---|
| fixed_template | 0.797 [0.793, 0.800] | 0.573 [0.517, 0.627] | 10.0 | 0.00 | 0.00 |
| ontology_v0_frozen | 0.613 [0.606, 0.620] | 0.063 [0.037, 0.093] | 10.0 | 0.44 | 1.66 |
| ontology_v1_current | 0.689 [0.682, 0.696] | 0.980 [0.963, 0.993] | 10.0 | 0.44 | 1.66 |
| safety_layer_uniform | 0.820 [0.816, 0.825] | 1.000 [1.000, 1.000] | 10.0 | 0.44 | 0.00 |
| learned_ranker | 0.820 [0.816, 0.825] | 0.000 [0.000, 0.000] | 10.0 | 0.44 | 0.00 |

Paired differences (same interviews; coverage / safety-omission rate / questions):

- learned_ranker minus fixed_template: coverage 0.023 [0.019, 0.028]; safety-omission -0.573 [-0.627, -0.517]; questions 0.000 [0.000, 0.000]
- learned_ranker minus ontology_v1_current: coverage 0.131 [0.123, 0.138]; safety-omission -0.980 [-0.993, -0.963]; questions 0.000 [0.000, 0.000]
- learned_ranker minus safety_layer_uniform: coverage 0.000 [0.000, 0.000]; safety-omission -1.000 [-1.000, -1.000]; questions 0.000 [0.000, 0.000]
- ontology_v1_current minus ontology_v0_frozen: coverage 0.076 [0.074, 0.078]; safety-omission 0.917 [0.877, 0.953]; questions 0.000 [0.000, 0.000]

**Budget: 8 questions max**

| policy | required-slot coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | questions outside dataset schema |
|---|---|---|---|---|---|
| fixed_template | 0.637 [0.634, 0.640] | 1.000 [1.000, 1.000] | 8.0 | 0.00 | 0.00 |
| ontology_v0_frozen | 0.454 [0.447, 0.460] | 1.000 [1.000, 1.000] | 8.0 | 0.44 | 1.66 |
| ontology_v1_current | 0.541 [0.536, 0.547] | 1.000 [1.000, 1.000] | 8.0 | 0.30 | 1.66 |
| safety_layer_uniform | 0.661 [0.657, 0.665] | 1.000 [1.000, 1.000] | 8.0 | 0.44 | 0.00 |
| learned_ranker | 0.661 [0.657, 0.665] | 1.000 [1.000, 1.000] | 8.0 | 0.44 | 0.00 |

Paired differences (same interviews; coverage / safety-omission rate / questions):

- learned_ranker minus fixed_template: coverage 0.023 [0.019, 0.028]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- learned_ranker minus ontology_v1_current: coverage 0.120 [0.112, 0.127]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- learned_ranker minus safety_layer_uniform: coverage 0.000 [0.000, 0.000]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- ontology_v1_current minus ontology_v0_frozen: coverage 0.087 [0.084, 0.091]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]

**Budget: 6 questions max**

| policy | required-slot coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | questions outside dataset schema |
|---|---|---|---|---|---|
| fixed_template | 0.478 [0.476, 0.480] | 1.000 [1.000, 1.000] | 6.0 | 0.00 | 0.00 |
| ontology_v0_frozen | 0.326 [0.319, 0.334] | 1.000 [1.000, 1.000] | 6.0 | 0.00 | 1.66 |
| ontology_v1_current | 0.328 [0.320, 0.336] | 1.000 [1.000, 1.000] | 6.0 | 0.00 | 1.66 |
| safety_layer_uniform | 0.501 [0.497, 0.505] | 1.000 [1.000, 1.000] | 6.0 | 0.44 | 0.00 |
| learned_ranker | 0.529 [0.526, 0.533] | 1.000 [1.000, 1.000] | 6.0 | 0.09 | 0.00 |

Paired differences (same interviews; coverage / safety-omission rate / questions):

- learned_ranker minus fixed_template: coverage 0.051 [0.047, 0.056]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- learned_ranker minus ontology_v1_current: coverage 0.202 [0.193, 0.210]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- learned_ranker minus safety_layer_uniform: coverage 0.028 [0.024, 0.032]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- ontology_v1_current minus ontology_v0_frozen: coverage 0.002 [0.001, 0.003]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]

### A6. Required slots never asked at full budget (share of interviews)

| policy | slots (share of interviews missing them) |
|---|---|
| fixed_template | none |
| ontology_v0_frozen | agg: 96%, rel: 96%, char: 66%, rad: 53% |
| ontology_v1_current | rad: 53% |
| safety_layer_uniform | rad: 53% |
| learned_ranker | rad: 53% |

### A7. Does the learned policy ask in a different order?

Identical canonical-slot order to fixed template: **22.7%**; to ontology v1: **0.0%**; to the uniform-ranker safety-layer ablation: **0.0%** (300 interviews).

Language robustness for typed 'Other' complaints (English text vs patient's own wording):

`{"devanagari": {"n": 68, "same_question_order_as_english_text": 1.0, "coverage_with_patient_wording": 0.9819, "fallback_share_with_patient_wording": 0.0}, "latin": {"n": 9, "same_question_order_as_english_text": 1.0, "coverage_with_patient_wording": 0.9744, "fallback_share_with_patient_wording": 0.0}}`

**Reading A5/A6.** `ontology_v0_frozen` is the repository's policy before this work. It never asked character / aggravating / relieving for most complaints (A6) and its ~20-point lower coverage at full length (0.754 vs 0.959) is what the v1 questions fixed. The residual `rad` gap (53%) is a dataset-schema item the app only asks for chest pain; whether radiation is clinically required for, say, itching is a question for clinicians, not the model. `duplicate-slot questions` counts a generic *associated symptoms* question asked after a complaint-specific one covering the same slot: a design observation for clinician review, not necessarily an error. `questions outside dataset schema` (progression, site, ROS, free text) are legitimate clinical questions the 13-slot dataset schema simply cannot score.

**What would make a real adaptivity claim possible:** recorded interviews whose question order varies with the answers (the full MediTOD set needs a UMLS licence; the project holds a 3-dialogue sample), or clinician-adjudicated "best next question" labels for sampled states. Without one of these, a learned policy cannot be shown to improve on a template.

## B. Laboratory report extraction

Benchmark: `lab_result_entities.csv` joined to `synthetic_documents_ocr_pairs.csv` (`report_id == doc_id`, 394/394 joined). Fields are scored separately.

| metric | before: clean text | after: clean text | before: simulated-OCR text | after: simulated-OCR text |
|---|---|---|---|---|
| test-name recall | 55.7% | 100.0% | 53.8% | 97.6% |
| test-name precision | 100.0% | 100.0% | 100.0% | 100.0% |
| exact value | 100.0% | 100.0% | 97.6% | 97.5% |
| unit | 89.3% | 100.0% | 89.0% | 99.8% |
| printed reference interval | 0.0% | 100.0% | 0.0% | 96.1% |
| printed N/H/L flag captured | 0.0% | 100.0% | 0.0% | 100.0% |
| abnormal status vs printed flag | 89.7% | 100.0% | 88.7% | 97.9% |
| lab-normal wrongly flagged abnormal | 9.9% | 0.0% | 10.8% | 0.9% |
| marked ambiguous / for confirmation | 0.0% | 0.0% | 0.0% | 6.9% |

394 reports / 1238 labelled results (all splits; the extractor was developed while looking at this data, so these are **development-set numbers**). Critical-result recall: not computable (the labels contain only N/H/L; there are no 'critical' labels, so critical-result recall cannot be computed).

**Rendered scans with known text** (42 test-split reports; synthetic rendering of one monospace layout, Tesseract with row-preserving segmentation):

| channel | CER good / fair / poor | test-name recall | exact value | unit | printed interval | false-abnormal | ambiguous |
|---|---|---|---|---|---|---|---|
| image_png | 0.0% / 0.4% / 10.3% | 92.3% | 97.5% | 98.3% | 95.8% | 1.1% | 8.3% |
| scanned_pdf | 0.0% / 0.5% / 10.7% | 93.1% | 97.5% | 98.4% | 95.9% | 1.1% | 9.9% |
| text_pdf | 0.0% / 0.0% / 0.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% |

Notes. (1) Before the fix the extractor ignored printed reference intervals, compared `x10^3/uL` values against a `/uL` baseline (silently mis-flagging results), and recognised only 55.7% of the labelled results (5 of the 16 test names were not in its vocabulary). (2) A bug found *by this evaluation*: with a garbled row the fallback searched neighbouring lines and silently borrowed another test's interval; lookups are now restricted to the result's own line. (3) Tesseract's default layout analysis split report rows into columns; `--psm 6` fixed it (clean-render CER is now ~0.02%; test-name recall on rendered scans rose to 92-93% from roughly 80% in the first run). (4) Of 71 wrong values/intervals on noisy text, 68 now carry an explicit "confirm" flag; 3 are silent single-digit misreads that no rule can catch. (5) Poor-quality scans still have ~10% character error and overall test-name recall on rendered scans is 92-93%, so roughly 1 in 13 results is still missed: a real weakness. (6) **Scanned (image-only) PDFs previously returned empty text**; they are now OCR'd page by page.

## C. Hindi / Hinglish clinical text

Real Hindi and English patient answers from the dataset (text only; no audio is present or used). Polarity gold = whether the English structured-history value means "none / nothing".

| task | script | before | after |
|---|---|---|---|
| answer polarity accuracy | devanagari | 60.3% | 100.0% |
| negative-answer recall | devanagari | 0.0% | 100.0% |
| positive answers misread as negative | devanagari | 0 | 0 |
| duration parsed / exact days | devanagari | 0.0% / 0.0% | 100.0% / 100.0% |
| complaint concept recall | devanagari | 0.0% | 100.0% |
| answer polarity accuracy | latin | 97.9% | 100.0% |
| negative-answer recall | latin | 91.6% | 100.0% |
| positive answers misread as negative | latin | 0 | 0 |
| duration parsed / exact days | latin | 0.0% / 0.0% | 100.0% / 100.0% |
| complaint concept recall | latin | 81.6% | 100.0% |

The "after" 100% reflects the dataset's few templated phrasings and should be read as a floor on regression, not as accuracy on Hindi in general. `tests/test_hindi_hinglish_nlp.py` adds ~50 hand-written, varied cases (negation scope across commas, family experiencer, code-switching, Devanagari digits, nukta variants, provenance spans). One known limit is pinned in a test: a positive statement containing a negation word ("दर्द कभी नहीं रुकता", *the pain never stops*) is read as negative. See `docs/HINDI_HINGLISH_NLP.md`.

## D. Software tests (these verify behaviour, not clinical accuracy)

Full backend validation was re-run after installing Tesseract and Playwright.
The final result was **241 passed, 0 failed, 0 skipped**, with one
Starlette/httpx deprecation warning. The command is
`cd backend && ../.venv/bin/python -m pytest -q -rs`.

## E. Not evaluated (and why)

| Item | Status |
|---|---|
| Summary generation (unsupported-claim rate, critical-fact omission) | Not run. No genuine dialogue->summary training pairs beyond ACI-Bench (207) were verified for provenance/licence, and the rule-based summary builder consumes ontology answers, not dataset slots. No model was trained, deliberately. |
| Red-flag precision/recall on `red_flag_labeled_cases.csv` | Pre-existing evaluation in `evaluation_results/`; labels are synthetic. Not re-run or extended here. |
| OCR on real scans, handwriting, ASR on audio | No images or audio exist in the supplied dataset (0 image/PDF files, 0 audio files on disk). |
| Prescription extraction on real images | Not evaluated: no source images are present. Synthetic text-pair parsing is reported in H. |
| Critical-result recall | The labels contain only N/H/L. |

## F. Evidence-to-report integration and document limitations

The deterministic synthetic report benchmark actually executed and passed.
Before upload, the test defines the expected history (`Cough`, `2 days`,
`Moderate`, explicit `No fever`), two laboratory findings (Haemoglobin
`9.1 g/dL`, Creatinine `1.0 mg/dL`, dates, and printed intervals), and
prescription findings (Warfarin `5 mg` and Aspirin `75 mg`, once daily, dated
2025-03-13). The patient separately reports Warfarin `2 mg`; the report keeps
both facts and requests clinician review rather than resolving the conflict.
The test uploads two generated PDF fixtures, verifies extraction and source
page/spans, persists an encounter, retrieves the doctor's report and source
PDFs after guest working-document cleanup, then applies a clinician amendment
and verifies evidence provenance remains intact.

The benchmark scored **31/31 exact reference checks**: history 4/4; labs 12/12
(value, unit, date, interval, document ID, page/span for each result);
medications 10/10 (name, dose, frequency, date, source document for each);
conflict/verification disclosures 2/2; clinician edit and evidence retention
2/2; persisted patient/encounter/document linkage 1/1. Each check is binary
(exact equality or the stated provenance condition); the score is passing
checks divided by predeclared checks, not a clinical accuracy estimate.

Additional executed tests preserve explicitly negative and uncertain facts,
missing units, multiple dated measurements, same-day conflicting values,
entered-vs-extracted date conflicts, duplicate files, missing/poor extraction,
unsupported/corrupt uploads, missing provenance, and fail-safe red-flag
behavior. A missing unit is not replaced with a configured baseline unit.
These are synthetic software-test cases, not additional records in a training
dataset. The report remains deterministic; no generative model was introduced.

Tesseract 5.5.3 was installed on macOS (available languages: `eng`, `osd`).
The synthetic PNG, JPEG, WEBP, TIFF, multi-frame WEBP, multi-page TIFF, and
single-/multi-page scanned-PDF tests executed against manually known text.
An additional 42-report synthetic rendering run is reported in H. This does
not validate real-world scans, handwriting, or Hindi OCR. Install on macOS
with `brew install tesseract`; optional additional language data:
`brew install tesseract-lang`. Playwright 1.64.0 and Chromium 156 were also
installed; setup commands are listed in H.

## G. Four-way next-question comparison (official test, 30 interviews)

| selector | top-1 | NDCG@1 | NDCG@3 |
|---|---:|---:|---:|
| Existing ontology/rule selection | 0.162 | 0.162 | 0.162 |
| Logistic regression, recorded patient wording | 1.000 | 1.000 | 1.000 |
| Logistic regression, application labels | 0.997 | 0.997 | 0.999 |
| Training-only oracle complaint/state template lookup | 1.000 | 1.000 | 1.000 |

Top-1/top-3 denominators are 371 held-out pre-answer states; NDCG is averaged
over 30 interview-level rankings. Cluster-bootstrap confidence intervals are
in `evaluation_results/adaptive/adaptive_evaluation.json`. The oracle lookup
uses training-split examples only. Its perfect score explains
the near-perfect model result: the score is template/recorded-choice agreement,
not evidence of clinical utility. NDCG for the ontology and oracle uses only
their single chosen question, so NDCG@3 equals NDCG@1.

Operational replay on the official split (30 interviews, unlimited budget):

| policy | required-slot coverage (mean) | mandatory safety coverage (mean) | interviews with safety-critical omission | questions (total / mean per interview) | duplicates (total / rate of questions) |
|---|---:|---:|---:|---:|---:|
| Fixed template | 1.000 | 1.000 | 0/30 | 371 / 12.37 | 0/371 (0.0000) |
| Current ontology | 0.974 | 1.000 | 0/30 | 453 / 15.10 | 10/453 (0.0221) |
| Learned, application-label wording | 0.974 | 1.000 | 0/30 | 453 / 15.10 | 10/453 (0.0221) |
| Learned, recorded wording | 0.974 | 1.000 | 0/30 | 453 / 15.10 | 10/453 (0.0221) |

Required-slot and safety-critical definitions are provisional synthetic
templates, not clinician-approved measures. The ranker is opt-in; the
ontology and deterministic mandatory-safety layer remain authoritative.

Policy metric definitions: required-slot coverage is the mean of each
interview's required canonical slots asked divided by required slots for that
interview; mandatory-safety coverage is the corresponding mean over applicable
mandatory safety slots. Safety-critical omission is the count of interviews
with at least one missing critical slot divided by 30. Questions per interview
is total questions divided by 30. Duplicate-question rate is total duplicate
question count divided by total questions across the test interviews.
These denominators use provisional synthetic template lists. No clinician or
expert relevance labels are available; top-1 and NDCG score agreement with a
single recorded next question, not graded relevance, safety, benefit, or
clinical superiority. The patient-grouped train/validation/test split remains
240/30/30, seed 42, and validation-selected `C=100`; test data were not used
for training or tuning in this evaluation.

Reproduce the model evaluation and rendered table with:
`cd backend && PYTHONPATH=. ../.venv/bin/python -m training.adaptive.evaluate`
and `PYTHONPATH=. ../.venv/bin/python -m training.render_reports`.

## H. Existing source-linked data, report benchmark, and OCR validation

| Experiment | Evaluated records | Result | Scope |
|---|---:|---:|---|
| Evidence-to-report synthetic encounter | 31 predeclared checks | 31/31 | Exact field/provenance/edit behavior; software test only |
| Lab parser, linked ground-truth text | 394 reports / 1,238 results | 1,238/1,238 test names, values, units, intervals | Synthetic text-to-field regression |
| Prescription parser, held-out split | 55 reports / 111 labels | After alias additions: exact source-name 110/110 precision, 110/111 recall, F1 0.996 | Synthetic text only; extractor was previously developed on this corpus |
| Rendered PNG OCR | 42 synthetic reports / 130 labels | 121/130 test names | Menlo-rendered benchmark; not real scans |
| Rendered scanned-PDF OCR | 42 synthetic reports / 130 labels | 123/130 test names | Image-only generated PDFs; not real scans |
| Adaptive ranker | 30 grouped test interviews / 371 states | LR 1.000 recorded-wording top-1; oracle 1.000 | Recorded-choice agreement only; no expert relevance labels |

### Existing records inspected and task eligibility

The exact source inventory and exclusions are in
[`DATASET_AUDIT.md`](./DATASET_AUDIT.md). Lab labels join all 394 available
synthetic lab text-pair reports (1,238 labeled result rows); prescription
labels join all 498 prescription text-pair reports (1,011 rows). IDs, patient
IDs, and existing split assignments match for every joined row. These records
are suitable for text-to-field extraction regressions, but the supplied data
contain no source pixels, entity spans, encounter-level cross-links to history,
or gold doctor-facing report. The 300 history-summary pairs similarly join by
interview, patient, and split but have no document evidence links. ACI-Bench
(207) has no evidence annotations and unresolved licensing; MTSamples (4,966)
is note-only. Neither was used as report ground truth.

The lab patient split has 211/27/26 unique train/validation/test patients; the
prescription split has 302/35/40. Neither corpus has cross-split patient IDs,
and the evaluators reject patient/split or source-ID mismatches rather than
silently joining them.

### Dataset-linked extraction regressions

The lab parser was evaluated against all 394 synthetic report text pairs
(development/regression data; not an independent test because the extractor
was developed against this corpus). Counts are exact; field accuracies are
conditional on a matched test name:

| input text | test-name TP / labeled | exact value / matched | unit / matched | printed interval / matched | abnormal status / matched |
|---|---:|---:|---:|---:|---:|
| ground-truth text | 1,238/1,238 | 1,238/1,238 | 1,238/1,238 | 1,238/1,238 | 1,238/1,238 |
| simulated OCR text | 1,208/1,238 | 1,178/1,208 | 1,169/1,208 | 1,161/1,208 | 1,181/1,208 |

There were 30 unmatched labels on simulated-OCR text. No critical-result
recall can be computed because labels only distinguish N/H/L.

The prescription parser was evaluated against unchanged patient-grouped
assignments; there was no training. Investigation of train/validation misses
found 267 strict `generic_key` misses. Of these, 36 were `Dashmoolarishta`
already extracted under a different source `generic_key` (`dashmoola`); the
other 231 were missing catalog forms: Yogaraj/Simhanada guggulu (59),
Sarpagandha vati (40), Avipattikar churna (38), Gudmar churna (30),
Sitopaladi churna (29), Neem capsule (20), and Dicyclomine (15). The parser
catalog was extended for those source-attested forms. A separate train/
validation source-name comparison showed that the parser found the ingredient
but emitted only the short ingredient name for Ashwagandha churna (44),
Triphala churna (58), and Salbutamol inhaler (50); exact formulation aliases
were added and the overlapping short-name match is suppressed, avoiding
duplicate findings. Existing source names are returned, not replaced with a
guessed generic.

Both the historical exact-`generic_key` metric and a separate exact
source-formulation metric are retained. Source-name matching case-folds,
removes punctuation, strips a terminal dose/unit from the label's `drug`
field, and otherwise requires an exact name. For each metric, precision is
TP/predicted extractions, recall is TP/labeled rows, and micro-F1 is
`2*TP/(predicted extractions + labeled rows)`. The existing `generic_key`
metric requires an exact normalized key match and therefore undercounts
formulation names whose labeled key is different. Test results, measured
after the parser change was fixed, are:

| text | metric | before TP / predicted / labeled | before P / R / F1 | after TP / predicted / labeled | after P / R / F1 |
|---|---|---:|---:|---:|---:|
| Ground truth | exact source name | 50 / 77 / 111 | 0.649 / 0.450 / 0.532 | 110 / 110 / 111 | 1.000 / 0.991 / 0.996 |
| Simulated OCR | exact source name | 47 / 74 / 111 | 0.635 / 0.423 / 0.508 | 101 / 102 / 111 | 0.990 / 0.910 / 0.948 |
| Ground truth | strict `generic_key` | 77 / 77 / 111 | 1.000 / 0.694 / 0.819 | 78 / 110 / 111 | 0.709 / 0.703 / 0.706 |
| Simulated OCR | strict `generic_key` | 74 / 74 / 111 | 1.000 / 0.667 / 0.800 | 75 / 102 / 111 | 0.735 / 0.676 / 0.704 |

The source-name metric improves on validation as well: ground-truth text
changes from 60/70 precision and 60/98 recall (F1 0.714) to 97/97 (1.000)
and 97/98 (0.990), F1 0.995; simulated-OCR text changes from 53/63 (0.841)
and 53/98 (0.541), F1 0.658, to 88/88 (1.000) and 88/98 (0.898), F1
0.946. Test data were not used to select the additions. The strict `generic_key` precision after the change reflects the mismatch between
formulation names now extracted and labels' generic keys; it should not be
interpreted as evidence that those source-attested formulation extractions
are clinically incorrect. On held-out ground-truth text, the one remaining
source-name miss is an unmatched labeled row; on simulated-OCR text, ten
source-name labels remain unmatched (Amlodipine 2, Atorvastatin 1,
Metformin 1, Neem capsule 3, Salbutamol inhaler 1, Sarpagandha vati 1,
Sitopaladi churna 1). These text results do not establish OCR accuracy.

The unchanged test split has 40 patients, 55 documents, and 111 labels.
Results do not score duration, route, token spans, report generation, or image
OCR. This is a synthetic-text regression and not a blinded estimate. The
pre-change and post-change artifacts are
`evaluation_results/prescription_extraction/prescription_extraction_before_parser_change.json`
and `evaluation_results/prescription_extraction/prescription_extraction_improved.json`.
Reproduce the current result from `backend/` with:

```bash
PYTHONPATH=. ../.venv/bin/python -m training.prescription_extraction_eval \
  --output ../evaluation_results/prescription_extraction/prescription_extraction_improved.json
```

### Laboratory mismatch investigation

The lab parser was not changed in this pass. On simulated-OCR text, field
mismatches by existing split were:

| split | test names TP / labeled | value exact / matched | unit exact / matched | printed interval exact / matched |
|---|---:|---:|---:|---:|
| train | 954/977 | 928/954 | 920/954 | 919/954 |
| validation | 125/131 | 123/125 | 122/125 | 122/125 |
| test | 129/130 | 127/129 | 127/129 | 120/129 |

The single held-out name miss came from OCR text `Fasting B1ood Sugar`.
Value/unit errors include OCR substitutions that leave an unusable token,
such as `109.2 rng/dL` and `9l.7 mg/dL`; the parser does not infer a corrected
value or unit. Of the nine held-out interval mismatches, examples include
`(4.0-S.6)`, `(70-l40)`, and `(2.6-6.O)`. These are character confusions in
the simulated OCR. When an interval is not parsed, output marks a configured
baseline or unavailable interval and carries ambiguity; it does not present
the configured baseline as a printed document interval. No lab values,
attribution, or deterministic safety behavior were modified. Per-field
examples and source IDs are in
`evaluation_results/lab_extraction/lab_extraction_final_prescription_review.json`.

### Rendered raster / scanned-PDF results

`lab_scan_eval_macos.json` uses 42 test-split source reports rendered with
Menlo as synthetic ground truth: 24 good, 12 fair, and 6 poor. CER/WER are
the mean of per-document edit-distance rates after removing rule separator
lines. The file-format tests also use explicit hand-written reference strings;
the 42-report run uses the existing dataset's synthetic `ground_truth_text`,
not a human-adjudicated real-world scan corpus. Field denominators below are matched extracted findings; test-name
recall uses all 130 labeled test results.

| channel | mean CER / mean WER, good (24 reports) | fair (12) | poor (6) | test-name TP / 130 | exact value / matched | unit / matched | printed interval / matched |
|---|---:|---:|---:|---:|---:|---:|---:|
| PNG image OCR | 0.0052 / 0.0320 | 0.0096 / 0.0521 | 0.0993 / 0.4223 | 121/130 | 112/121 | 108/121 | 87/121 |
| Scanned PDF OCR | 0.0063 / 0.0392 | 0.0102 / 0.0556 | 0.1265 / 0.4472 | 123/130 | 116/123 | 108/123 | 83/123 |
| Embedded-text PDF | 0 / 0 | 0 / 0 | 0 / 0 | 130/130 | 130/130 | 130/130 | 130/130 |

CER = character edit distance divided by reference characters after
normalizing whitespace and excluding rule-only separator lines. WER uses
word edit distance divided by reference word count. Each table value is a
mean over the indicated reports, not pooled character/word counts. Exact
per-field numerators and denominators, abnormal-status errors, and ambiguity
counts are saved in `evaluation_results/lab_scan_eval_macos.json`. The
embedded-text PDF channel is a parser control, not OCR.

Tesseract was version 5.5.3; only English and orientation data (`eng`, `osd`)
were installed, so Hindi OCR remains untested. Playwright was version 1.64.0
with bundled Chromium 156. Exact macOS setup and test commands:

```bash
brew install tesseract
./.venv/bin/python -m pip install playwright
./.venv/bin/python -m playwright install chromium
cd backend
../.venv/bin/python -m pytest -q -rs
PYTHONPATH=. ../.venv/bin/python -m training.lab_scan_eval --split test \
  --output ../evaluation_results/lab_scan_eval_macos.json
PYTHONPATH=. ../.venv/bin/python -m training.prescription_extraction_eval \
  --output ../evaluation_results/prescription_extraction/prescription_extraction_improved.json
PYTHONPATH=. ../.venv/bin/python -m training.adaptive.evaluate
```

No real patient data, real scans, clinical benefit, or OCR performance on
real-world layouts is claimed.

### Final validation

Final full-suite pass/fail/skip totals, frontend syntax checks, Python
compilation, diff validation, and checkpoint integrity are recorded after the
commands completed:

| Check | Result |
|---|---|
| Backend tests, including Playwright and Tesseract cases | 242 passed, 0 failed, 0 skipped |
| Python compile (`compileall app training tests scripts`) | Passed |
| Frontend external JavaScript syntax (`node --check frontend/*.js`) | Passed |
| `git diff --check` | Passed |
| Adaptive-ranker checkpoint integrity | Passed; checkpoint and manifest SHA-256 values unchanged |

One non-failing Starlette/httpx deprecation warning remains. The browser test
setup had not entered the username field despite requiring username/password;
the test now enters both, and its “not a clear result” assertion is
case-insensitive to match the rendered wording. No application behavior was
changed for those test fixes.
