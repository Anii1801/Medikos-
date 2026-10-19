# 07_drug_safety

Drug-interaction checking.
- drug_interaction_reference.csv (9 illustrative pairs), drug_interaction_alerts.csv (84 alerts), patient_drug_lists.csv
Illustrative only - validate against a real interaction database before any clinical use.

All CSVs are UTF-8 with BOM (open directly in Excel). `split` = patient-level train/valid/test (400/50/50 patients; no patient appears in two splits).

| File | Rows | Description |
|---|---|---|
| drug_interaction_reference.csv | 9 | Small illustrative interaction table (9 pairs) |
| drug_interaction_alerts.csv | 84 | Interaction pairs found in each patient's prescriptions |
| patient_drug_lists.csv | 377 | Unique generic drugs per patient and systems (Allopathy/Ayurveda) - input for interaction checks |
