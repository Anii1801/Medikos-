# TF-IDF symptom text classifier (experimental)

This model maps a short symptom-description text to a label in the bundled Symptom2Disease-derived dataset. It is a non-clinical benchmark only, not a diagnostic tool or clinical decision-support model.

The upstream Kaggle license/terms are unresolved. Keep this checkpoint and its results local until terms are reviewed. Data splits are dataset-provided; normalized full-text SHA-256 groups were checked for cross-split exact duplicate leakage. No patient/source group identifiers exist in this dataset.

See `evaluation_results/clinical_text_classification/evaluation.json` for search, held-out metrics, class-level scores, data fingerprint, and limitations. This checkpoint is not loaded by the application.
