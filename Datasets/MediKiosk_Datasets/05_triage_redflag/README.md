# 05_triage_redflag

Red-flag detection and symptom triage.
- red_flag_rules.csv (8 rules), red_flag_labeled_cases.csv (300 labelled interviews)
- symptom_binary_train_dedup.csv / symptom_binary_test.csv - Kaggle 132-symptom, 41-disease set (deduplicated)
- symptom2disease_text.csv - free-text symptoms, 24 diseases, stratified split
- symptom_severity_weights.csv, disease_knowledge.csv - severity weights, descriptions, precautions
- symptom_binary_large_SAMPLE_5000.csv - sample of the 246,945-row data.csv (full file not copied)
Prototyping only - not for diagnosis.

All CSVs are UTF-8 with BOM (open directly in Excel). `split` = patient-level train/valid/test (400/50/50 patients; no patient appears in two splits).

| File | Rows | Description |
|---|---|---|
| red_flag_rules.csv | 8 | Rule set for EMERGENCY / URGENT triage (illustrative; needs clinical validation) |
| red_flag_labeled_cases.csv | 300 | Interview-level red-flag and triage labels (300 synthetic cases; 19 EMERGENCY, 57 URGENT) |
| symptom_binary_train_dedup.csv | 304 | 132 binary symptoms -> prognosis (41 diseases), duplicates removed |
| symptom_binary_test.csv | 42 | Official Testing.csv (42 rows) |
| symptom2disease_text.csv | 1153 | Free-text symptom descriptions -> disease (24 classes), stratified split; 47 duplicate texts removed |
| symptom_severity_weights.csv | 133 | Severity weight (1-7) per symptom |
| disease_knowledge.csv | 41 | Disease description + up to 4 precautions (patient-education text; not clinical guidance) |
| symptom_binary_large_SAMPLE_5000.csv | 5000 | Random 5,000-row sample of data.csv (246,945 rows x 377 symptoms; full file not copied, 182 MB) |
