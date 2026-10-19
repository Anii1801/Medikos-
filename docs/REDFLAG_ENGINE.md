# RedFlagEngine

`backend/app/redflag_engine.py` is an independent, fail-safe warning-sign
detector. It is not a diagnostic model and must not be used to rule out disease.
It consumes structured symptoms, free-text descriptions, report findings, and
observations. Each finding returns its rule metadata, supporting evidence,
missing information, urgency, human-review status, and a safe next step.

## Rule provenance

The initial rule catalogue is based on emergency warning-sign patterns in the
WHO *Basic Emergency Care: approach to the acutely ill and injured* guidance
(2018). The local CSV also contains candidate rules, but it is repository
demonstration data rather than a validated clinical guideline.

Every rule records source, version, URL, target population, and review status.
The current status is `provisional_pending_local_clinician_signoff`. This is
intentional: no clinician sign-off was available in this coding session, so
the module must not be represented as clinically approved or deployed.

## Safety behavior

- Explicit denials are not treated as positive evidence.
- Unknown, unsure, declined, and missing fields remain missing/uncertain.
- Conflicting statements remain visible and require human review.
- A classifier is optional and secondary. A low classifier score never removes
  a deterministic finding.
- Classifier outage returns availability/error metadata while deterministic
  warnings continue.
- Rule-engine failure returns `EMERGENCY`, requires immediate human review,
  and instructs the caller to stop automated triage.
- Findings are warning signs, not definitive diagnoses.

## Classifier status and evaluation

`ClassifierAdapter` is an extension point only. The repository's existing
ML helper claims external datasets and performance figures that are not
provenance-complete for this safety module, so it is not wired as a trained
RedFlagEngine classifier. No classifier was trained in this change.

Run:

```powershell
cd backend
python scripts\evaluate_red_flags.py
```

This evaluates the deterministic engine against the bundled
`red_flag_labeled_cases.csv` and reports sensitivity/recall, specificity,
precision, F1, false negatives, false positives, and sex subgroup counts.
The file is synthetic/demo data and cannot establish clinical accuracy.
No deployment is permitted until clinician review, applicable local guidance,
licensed labels, external validation, and prospective safety assessment are
complete.
