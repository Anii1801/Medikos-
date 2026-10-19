# 02_ocr_handwriting

Module B - document digitisation.
- synthetic_documents_ocr_pairs.csv - 892 lab reports / prescriptions: ground truth vs simulated OCR, with CER/WER
- prescription_entities.csv, lab_result_entities.csv - entity-extraction ground truth
- noisy_docs_manifest.csv - 1,000 Kaggle noisy bill / discharge images + JSON ground truth (images stay in Noisy_Medical_Document_Images__OCR_.zip)
- handwriting_words_manifest.csv, handwriting_label_map.csv - 4,680 handwritten medicine-name images (images stay in Doctor_s_Handwritten_Prescription_BD_dataset.zip)
Image files are NOT copied (335 MB); `path_in_zip` + `source_zip` tell you where each one is.

All CSVs are UTF-8 with BOM (open directly in Excel). `split` = patient-level train/valid/test (400/50/50 patients; no patient appears in two splits).

| File | Rows | Description |
|---|---|---|
| synthetic_documents_ocr_pairs.csv | 892 | Ground-truth vs simulated-OCR text for lab reports and prescriptions (text-level simulation, not real OCR) |
| prescription_entities.csv | 1011 | Drug, dose schedule, duration per prescription line (entity-extraction ground truth) |
| lab_result_entities.csv | 1238 | Lab test, value, unit, reference range, flag per report (entity-extraction ground truth) |
| ocr_noise_summary.csv | 6 | Mean CER/WER of simulated OCR by handwritten flag and scan quality |
| noisy_docs_manifest.csv | 1000 | Kaggle Noisy Medical Document Images: 500 bills + 500 discharge summaries; JSON ground truth + image path (images NOT copied, 304 MB) |
| handwriting_words_manifest.csv | 4680 | Kaggle Prescription BD: 4,680 handwritten medicine-name word images, train/valid/test as published (images NOT copied) |
| handwriting_label_map.csv | 78 | Medicine brand -> generic mapping with image counts |
