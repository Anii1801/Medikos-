# Dataset register

The application resolves data through `backend/app/datasets.py`. Override the
root with `MEDIKIOSK_DATASETS`.

| Dataset key | Relative path | Runtime use |
|---|---|---|
| `patient_master` | `00_patient_master/patient_master.csv` | maintained patient source |
| `patient_timeline` | `00_patient_master/patient_timeline.csv` | timeline source |
| `symptom_text` | `05_triage_redflag/symptom2disease_text.csv` | transparent symptom fallback |
| `red_flag_cases` | `05_triage_redflag/red_flag_labeled_cases.csv` | triage inventory |
| `drug_interactions` | `07_drug_safety/drug_interaction_reference.csv` | interaction alerts |

The wider tree also contains interview, OCR, summary, ASR, AYUSH, and drug
safety exports. Their manifests and limitations are documented in
`Datasets/MediKiosk_Datasets/README.md` and `QUALITY_REPORT.md`.

## Governance

Splits are patient-keyed where supplied. External datasets retain their
original licences and must be reviewed before redistribution or training.
Synthetic/demo rows must not be presented as clinical validation evidence.
No production patient data should be added to the repository.
