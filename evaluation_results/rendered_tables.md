<!--ADAPTIVE-->

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

### A2b. Four-way next-question choice comparison (untouched official test)

| selector | top-1 | NDCG@1 | NDCG@3 |
|---|---|---|---|
| ontology_rule_selection | 0.162 [0.160, 0.164] | 0.162 [0.160, 0.164] | 0.162 [0.160, 0.164] |
| logistic_regression_recorded_wording | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| oracle_template_lookup | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| logistic_regression_app_labels | 0.997 [0.992, 1.000] | 0.997 [0.992, 1.000] | 0.999 [0.997, 1.000] |

Oracle lookup is trained only on training-split complaint/state templates. Single-choice ontology/oracle policies have no meaningful ranking beyond top-1; their NDCG@3 equals NDCG@1. Scores measure agreement with recorded template choices, not clinical benefit.

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

| policy | required-slot coverage | mandatory safety-question coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | duplicate-question rate | questions outside dataset schema |
|---|---|---|---|---|---|---|---|
| fixed_template | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.4 | 0.00 | 0.000 | 0.00 |
| ontology_v0_frozen | 0.766 [0.746, 0.789] | 1.000 [1.000, 1.000] | 0.067 [0.000, 0.167] | 13.5 | 0.33 | 0.025 | 3.30 |
| ontology_v1_current | 0.974 [0.962, 0.987] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 15.1 | 0.33 | 0.022 | 3.30 |
| safety_layer_uniform | 0.974 [0.962, 0.987] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 15.1 | 0.33 | 0.022 | 3.30 |
| learned_ranker | 0.974 [0.962, 0.987] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 15.1 | 0.33 | 0.022 | 3.30 |
| learned_ranker_recorded | 0.974 [0.962, 0.987] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 15.1 | 0.33 | 0.022 | 3.30 |

**Budget: 12 questions max**

| policy | required-slot coverage | mandatory safety-question coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | duplicate-question rate | questions outside dataset schema |
|---|---|---|---|---|---|---|---|
| fixed_template | 0.972 [0.959, 0.985] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.0 | 0.00 | 0.000 | 0.00 |
| ontology_v0_frozen | 0.761 [0.745, 0.778] | 1.000 [1.000, 1.000] | 0.067 [0.000, 0.167] | 12.0 | 0.33 | 0.028 | 1.87 |
| ontology_v1_current | 0.886 [0.866, 0.906] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.0 | 0.33 | 0.028 | 1.30 |
| safety_layer_uniform | 0.974 [0.962, 0.987] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.0 | 0.33 | 0.028 | 0.20 |
| learned_ranker | 0.974 [0.962, 0.987] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.0 | 0.33 | 0.028 | 0.20 |
| learned_ranker_recorded | 0.974 [0.962, 0.987] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.0 | 0.33 | 0.028 | 0.20 |

**Budget: 10 questions max**

| policy | required-slot coverage | mandatory safety-question coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | duplicate-question rate | questions outside dataset schema |
|---|---|---|---|---|---|---|---|
| fixed_template | 0.810 [0.799, 0.821] | 1.000 [1.000, 1.000] | 0.367 [0.200, 0.533] | 10.0 | 0.00 | 0.000 | 0.00 |
| ontology_v0_frozen | 0.645 [0.627, 0.663] | 1.000 [1.000, 1.000] | 0.100 [0.000, 0.233] | 10.0 | 0.33 | 0.033 | 1.30 |
| ontology_v1_current | 0.724 [0.706, 0.742] | 1.000 [1.000, 1.000] | 0.933 [0.833, 1.000] | 10.0 | 0.33 | 0.033 | 1.30 |
| safety_layer_uniform | 0.828 [0.815, 0.844] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 10.0 | 0.33 | 0.033 | 0.00 |
| learned_ranker | 0.828 [0.815, 0.844] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 10.0 | 0.33 | 0.033 | 0.00 |
| learned_ranker_recorded | 0.828 [0.815, 0.844] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 10.0 | 0.33 | 0.033 | 0.00 |

**Budget: 8 questions max**

| policy | required-slot coverage | mandatory safety-question coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | duplicate-question rate | questions outside dataset schema |
|---|---|---|---|---|---|---|---|
| fixed_template | 0.648 [0.639, 0.656] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 8.0 | 0.00 | 0.000 | 0.00 |
| ontology_v0_frozen | 0.483 [0.467, 0.500] | 0.989 [0.967, 1.000] | 1.000 [1.000, 1.000] | 8.0 | 0.33 | 0.042 | 1.30 |
| ontology_v1_current | 0.562 [0.545, 0.578] | 0.989 [0.967, 1.000] | 1.000 [1.000, 1.000] | 8.0 | 0.33 | 0.042 | 1.30 |
| safety_layer_uniform | 0.666 [0.654, 0.681] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 8.0 | 0.33 | 0.042 | 0.00 |
| learned_ranker | 0.666 [0.654, 0.681] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 8.0 | 0.33 | 0.042 | 0.00 |
| learned_ranker_recorded | 0.666 [0.654, 0.681] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 8.0 | 0.33 | 0.042 | 0.00 |

**Budget: 6 questions max**

| policy | required-slot coverage | mandatory safety-question coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | duplicate-question rate | questions outside dataset schema |
|---|---|---|---|---|---|---|---|
| fixed_template | 0.486 [0.479, 0.492] | 0.739 [0.617, 0.850] | 1.000 [1.000, 1.000] | 6.0 | 0.00 | 0.000 | 0.00 |
| ontology_v0_frozen | 0.346 [0.325, 0.367] | 0.978 [0.933, 1.000] | 1.000 [1.000, 1.000] | 6.0 | 0.00 | 0.000 | 1.30 |
| ontology_v1_current | 0.351 [0.328, 0.376] | 0.911 [0.800, 1.000] | 1.000 [1.000, 1.000] | 6.0 | 0.00 | 0.000 | 1.30 |
| safety_layer_uniform | 0.504 [0.492, 0.518] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 6.0 | 0.33 | 0.056 | 0.00 |
| learned_ranker | 0.517 [0.506, 0.530] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 6.0 | 0.17 | 0.028 | 0.00 |
| learned_ranker_recorded | 0.517 [0.506, 0.530] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 6.0 | 0.17 | 0.028 | 0.00 |


### A5. Policy comparison — grouped CV, out-of-fold over all 300 interviews

**Budget: no limit**

| policy | required-slot coverage | mandatory safety-question coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | duplicate-question rate | questions outside dataset schema |
|---|---|---|---|---|---|---|---|
| fixed_template | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.6 | 0.00 | 0.000 | 0.00 |
| ontology_v0_frozen | 0.754 [0.746, 0.763] | 1.000 [1.000, 1.000] | 0.020 [0.007, 0.037] | 13.8 | 0.44 | 0.032 | 3.66 |
| ontology_v1_current | 0.959 [0.955, 0.964] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 15.4 | 0.44 | 0.029 | 3.66 |
| safety_layer_uniform | 0.959 [0.955, 0.964] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 15.4 | 0.44 | 0.029 | 3.66 |
| learned_ranker | 0.959 [0.955, 0.964] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 15.4 | 0.44 | 0.029 | 3.66 |
| learned_ranker_recorded | 0.959 [0.955, 0.964] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 15.4 | 0.44 | 0.029 | 3.66 |

Paired differences (same interviews; coverage / safety-omission rate / questions):

- learned_ranker minus fixed_template: coverage -0.041 [-0.045, -0.036]; safety-omission 0.000 [0.000, 0.000]; questions 2.830 [2.777, 2.880]
- learned_ranker minus ontology_v1_current: coverage 0.000 [0.000, 0.000]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- learned_ranker minus safety_layer_uniform: coverage 0.000 [0.000, 0.000]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- ontology_v1_current minus ontology_v0_frozen: coverage 0.205 [0.198, 0.211]; safety-omission -0.020 [-0.037, -0.007]; questions 1.613 [1.550, 1.680]

**Budget: 12 questions max**

| policy | required-slot coverage | mandatory safety-question coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | duplicate-question rate | questions outside dataset schema |
|---|---|---|---|---|---|---|---|
| fixed_template | 0.956 [0.952, 0.960] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.0 | 0.00 | 0.000 | 0.00 |
| ontology_v0_frozen | 0.748 [0.741, 0.754] | 1.000 [1.000, 1.000] | 0.020 [0.007, 0.037] | 12.0 | 0.44 | 0.037 | 1.96 |
| ontology_v1_current | 0.849 [0.841, 0.856] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.0 | 0.44 | 0.037 | 1.66 |
| safety_layer_uniform | 0.959 [0.955, 0.964] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.0 | 0.44 | 0.037 | 0.26 |
| learned_ranker | 0.959 [0.955, 0.964] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.0 | 0.44 | 0.037 | 0.26 |
| learned_ranker_recorded | 0.959 [0.955, 0.964] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 12.0 | 0.44 | 0.037 | 0.26 |

Paired differences (same interviews; coverage / safety-omission rate / questions):

- learned_ranker minus fixed_template: coverage 0.003 [0.002, 0.005]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- learned_ranker minus ontology_v1_current: coverage 0.111 [0.106, 0.115]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- learned_ranker minus safety_layer_uniform: coverage 0.000 [0.000, 0.000]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- ontology_v1_current minus ontology_v0_frozen: coverage 0.101 [0.096, 0.106]; safety-omission -0.020 [-0.037, -0.007]; questions 0.000 [0.000, 0.000]

**Budget: 10 questions max**

| policy | required-slot coverage | mandatory safety-question coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | duplicate-question rate | questions outside dataset schema |
|---|---|---|---|---|---|---|---|
| fixed_template | 0.797 [0.793, 0.800] | 1.000 [1.000, 1.000] | 0.573 [0.517, 0.627] | 10.0 | 0.00 | 0.000 | 0.00 |
| ontology_v0_frozen | 0.613 [0.606, 0.620] | 1.000 [1.000, 1.000] | 0.063 [0.037, 0.093] | 10.0 | 0.44 | 0.044 | 1.66 |
| ontology_v1_current | 0.689 [0.682, 0.696] | 1.000 [1.000, 1.000] | 0.980 [0.963, 0.993] | 10.0 | 0.44 | 0.044 | 1.66 |
| safety_layer_uniform | 0.820 [0.816, 0.825] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 10.0 | 0.44 | 0.044 | 0.00 |
| learned_ranker | 0.820 [0.816, 0.825] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 10.0 | 0.44 | 0.044 | 0.00 |
| learned_ranker_recorded | 0.820 [0.816, 0.825] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 10.0 | 0.44 | 0.044 | 0.00 |

Paired differences (same interviews; coverage / safety-omission rate / questions):

- learned_ranker minus fixed_template: coverage 0.023 [0.019, 0.028]; safety-omission -0.573 [-0.627, -0.517]; questions 0.000 [0.000, 0.000]
- learned_ranker minus ontology_v1_current: coverage 0.131 [0.123, 0.138]; safety-omission -0.980 [-0.993, -0.963]; questions 0.000 [0.000, 0.000]
- learned_ranker minus safety_layer_uniform: coverage 0.000 [0.000, 0.000]; safety-omission -1.000 [-1.000, -1.000]; questions 0.000 [0.000, 0.000]
- ontology_v1_current minus ontology_v0_frozen: coverage 0.076 [0.074, 0.078]; safety-omission 0.917 [0.877, 0.953]; questions 0.000 [0.000, 0.000]

**Budget: 8 questions max**

| policy | required-slot coverage | mandatory safety-question coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | duplicate-question rate | questions outside dataset schema |
|---|---|---|---|---|---|---|---|
| fixed_template | 0.637 [0.634, 0.640] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 8.0 | 0.00 | 0.000 | 0.00 |
| ontology_v0_frozen | 0.454 [0.447, 0.460] | 0.986 [0.977, 0.993] | 1.000 [1.000, 1.000] | 8.0 | 0.44 | 0.055 | 1.66 |
| ontology_v1_current | 0.541 [0.536, 0.547] | 0.986 [0.977, 0.993] | 1.000 [1.000, 1.000] | 8.0 | 0.30 | 0.037 | 1.66 |
| safety_layer_uniform | 0.661 [0.657, 0.665] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 8.0 | 0.44 | 0.055 | 0.00 |
| learned_ranker | 0.661 [0.657, 0.665] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 8.0 | 0.44 | 0.055 | 0.00 |
| learned_ranker_recorded | 0.661 [0.657, 0.665] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 8.0 | 0.44 | 0.055 | 0.00 |

Paired differences (same interviews; coverage / safety-omission rate / questions):

- learned_ranker minus fixed_template: coverage 0.023 [0.019, 0.028]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- learned_ranker minus ontology_v1_current: coverage 0.120 [0.112, 0.127]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- learned_ranker minus safety_layer_uniform: coverage 0.000 [0.000, 0.000]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]
- ontology_v1_current minus ontology_v0_frozen: coverage 0.087 [0.084, 0.091]; safety-omission 0.000 [0.000, 0.000]; questions 0.000 [0.000, 0.000]

**Budget: 6 questions max**

| policy | required-slot coverage | mandatory safety-question coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | duplicate-question rate | questions outside dataset schema |
|---|---|---|---|---|---|---|---|
| fixed_template | 0.478 [0.476, 0.480] | 0.626 [0.579, 0.674] | 1.000 [1.000, 1.000] | 6.0 | 0.00 | 0.000 | 0.00 |
| ontology_v0_frozen | 0.326 [0.319, 0.334] | 0.971 [0.953, 0.987] | 1.000 [1.000, 1.000] | 6.0 | 0.00 | 0.000 | 1.66 |
| ontology_v1_current | 0.328 [0.320, 0.336] | 0.951 [0.928, 0.972] | 1.000 [1.000, 1.000] | 6.0 | 0.00 | 0.000 | 1.66 |
| safety_layer_uniform | 0.501 [0.497, 0.505] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 6.0 | 0.44 | 0.074 | 0.00 |
| learned_ranker | 0.529 [0.526, 0.533] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 6.0 | 0.09 | 0.014 | 0.00 |
| learned_ranker_recorded | 0.529 [0.526, 0.533] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 6.0 | 0.09 | 0.014 | 0.00 |

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
| learned_ranker_recorded | rad: 53% |

### A7. Does the learned policy ask in a different order?

Identical canonical-slot order to fixed template: **22.7%**; to ontology v1: **0.0%**; to the uniform-ranker safety-layer ablation: **0.0%** (300 interviews).

Language robustness for typed 'Other' complaints (English text vs patient's own wording):

`{"devanagari": {"n": 68, "same_question_order_as_english_text": 1.0, "coverage_with_patient_wording": 0.9819, "fallback_share_with_patient_wording": 0.0}, "latin": {"n": 9, "same_question_order_as_english_text": 1.0, "coverage_with_patient_wording": 0.9744, "fallback_share_with_patient_wording": 0.0}}`

<!--LABS-->

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

<!--HINDI-->

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