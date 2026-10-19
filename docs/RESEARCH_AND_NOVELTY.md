# Research positioning and novelty

MediKiosk is an engineering prototype for Indian outpatient pre-consultation,
not a validated diagnostic system. Its useful integration points are:

- low-burden adaptive intake with English/Hindi UI and code-mixed text support;
- deterministic red-flag rules kept separate from language generation;
- OCR plus structured extraction for reports and prescriptions;
- source-aware summaries, missing-field visibility, and doctor approval;
- optional AYUSH intake fields without presenting them as diagnosis;
- FHIR-compatible packaging and an explicit mock/live ABDM boundary.

## Claims that require evidence

The repository currently does not establish clinical sensitivity, specificity,
calibration, language parity, OCR accuracy on handwriting, or outcome benefit.
The EDA endpoints are audit aids, not proof of model performance. Any paper or
deployment claim must report patient-level splits, external validation,
missingness, subgroup performance, confidence intervals, and clinician review.

## Unresolved JEV reference

No exact “JEV model” identifier was found in the project materials. The
implementation therefore uses a configurable adapter and deterministic
development policy rather than inventing a model name or licence.
