# Adaptive history-taking verification

## Model identity and availability

The requested **“JEV model” is unresolved**. A repository search and external
verification performed on 2026-10-14 found no authoritative model identifier,
provider, weights, licence, or access endpoint. MediKiosk therefore does not
invent or silently substitute a JEV model.

The running implementation is:

- adapter: `deterministic-development`;
- model: no trained model;
- prompting: none;
- policy: `backend/app/ontology.py`;
- safety gate: `ontology.red_flags`;
- state and validation: `backend/app/history_agent.py`.

`HistoryTakingAgent` accepts any future adapter implementing `LLMAdapter`.
Adapter output is constrained to the clinically reviewed policy question and
validated using `QuestionResponse`; it cannot alter red-flag rules.

## MediTOD verification

The official repository is [dair-iitd/MediTOD](https://github.com/dair-iitd/MediTOD).
Its README identifies it as “MediTOD: An English Dialogue Dataset for Medical
History Taking with Comprehensive Annotations” and describes raw dialogues,
annotations, data, baseline training code, and metrics. The repository API
reported `license: null` on 2026-10-14. Its README thanks the authors of the
2022 respiratory interview dataset for making dialogue data publicly available,
but does not provide a redistributable licence for MediTOD itself.

Result: MediTOD is a candidate resource for future slot-learning/evaluation
after licence confirmation. It was **not downloaded, copied, or used for
training** in this implementation.

## Measured local results

Run from `backend`:

```powershell
python -m pytest -q
python scripts\evaluate_history_agent.py
python scripts\demo_history_agent.py
```

The tests cover state persistence, unique question selection, negation,
uncertainty, conflicting answers, adapter schema rejection, budget stopping,
and the HTTP persistence API. The evaluation script measures policy invariants
only. It is not a clinical accuracy result, and no JEV or MediTOD model result
is claimed.

## Structured state

Each persisted session records:

- answers and original answer history;
- asked question IDs;
- missing fields;
- uncertainty fields;
- conflicting fields;
- selected adapter metadata;
- conversation budget and session ID.

Answers are retained verbatim. “No”, “denies”, “unknown”, “unsure”, and
“prefer not” are classified as negative or uncertain metadata; they are not
converted into fabricated positive or negative clinical facts.

## Confidence-aware decision routing

The implemented research contribution follows the proposed architecture:

1. **Clinical information extraction** — `extract_clinical_state()` preserves
   answers, answer status, missing fields, uncertainty, and conflicts.
2. **Follow-up action selection** — the reviewed ontology selects the next
   question, prevents duplicates, and enforces the question budget.
3. **Natural-language question generation** — an optional adapter may reword
   only the policy-approved question. It cannot change its identity, type,
   options, or safety meaning.
4. **Safety validation** — deterministic red-flag rules run independently of
   confidence and adapter output.

Each response now includes a bounded confidence estimate, `decision_route`,
`safety_validated`, and `review_required`. Routes are `adaptive_follow_up`,
`complete_review`, `human_review`, or `safety_review`. Uncertainty and
conflicting answers trigger human review; red flags always trigger
`safety_review`, regardless of score. The score is a routing aid, not a
calibrated probability or clinical risk estimate.

The image-proposed JEV-plus-LLM comparison remains a hypothesis. JEV's exact
identity, weights, provider, licence, and availability remain unresolved.
MediKiosk therefore runs the deterministic policy adapter and does not claim
that a JEV model was trained, loaded, prompted, or evaluated. Future
experiments should compare this route against fixed-question and LLM-only
baselines using identical held-out cases, reporting completeness, omissions,
duplicate questions, red-flag recall, latency, cost, and clinician review
burden.
