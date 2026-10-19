# 00_patient_master

Links every module through `patient_id` (P0001-P0500).
- patient_master.csv - one row per patient + counts of linked records, triage, Prakriti, consent, split
- patient_timeline.csv - visits / prescriptions / lab reports sorted by date
- patient_master.jsonl - nested record per patient (demographics, consent, history, AYUSH, prescriptions, labs, alerts)
- fhir_bundles/ - 300 synthetic FHIR R4-style bundles (patients with an interview). NOT validated against ABDM profiles.
Use for: clinician queue / dashboard, timeline view, end-to-end demo, ABDM export tests.
Note: only 300 of 500 patients have an interview; 356 have an AYUSH record.

All CSVs are UTF-8 with BOM (open directly in Excel). `split` = patient-level train/valid/test (400/50/50 patients; no patient appears in two splits).

| File | Rows | Description |
|---|---|---|
| patient_master.csv | 500 | One row per patient: demographics, consent, language, counts of linked records, triage, Prakriti, patient-level split |
| patient_timeline.csv | 1392 | Chronological events per patient: visits, prescriptions, lab reports (for the doctor timeline view) |
| patient_master.jsonl | 500 | Nested record per patient joining every module (one JSON per line) - for dashboard / end-to-end demo |
| fhir_bundles/*.json | 300 | Synthetic FHIR R4-style Bundles (Patient, Consent, Condition, Allergy, MedicationStatement, Observation); NOT validated against ABDM profiles |
