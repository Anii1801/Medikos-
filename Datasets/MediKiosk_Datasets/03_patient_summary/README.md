# 03_patient_summary

Module C - summary generation.
- history_to_summary_synthetic.csv - dialogue/structured history -> English clinician summary + Hindi confirmation (300)
- aci_bench_dialogue_note_pairs.csv - 207 real-style doctor-patient dialogues -> full clinical notes (splits: train/valid/test1-3)
- mtsamples_notes_clean.csv - 4,966 clinical notes (CC0) for note-style and section modelling
Suggested use: pre-train/fine-tune on ACI-Bench + MTSamples, adapt on the synthetic Hindi/English set.

All CSVs are UTF-8 with BOM (open directly in Excel). `split` = patient-level train/valid/test (400/50/50 patients; no patient appears in two splits).

| File | Rows | Description |
|---|---|---|
| history_to_summary_synthetic.csv | 300 | Dialogue / structured history -> English clinician summary + Hindi patient confirmation (synthetic, templated) |
| aci_bench_dialogue_note_pairs.csv | 207 | ACI-Bench (Nature Sci Data 2023): 207 doctor-patient dialogue -> clinical note pairs with metadata |
| mtsamples_notes_clean.csv | 4966 | MTSamples medical transcription notes (CC0), nulls dropped, whitespace trimmed |
