# 01_history_interview

Module A - conversational history taking.
- interview_turns.csv / interviews.jsonl - 300 interviews, 7,863 turns (Hindi + English, voice/touch input), slot-labelled
- structured_histories.csv - gold structured history (use as extraction target)
- slot_inventory.csv - slot names (AI turn = question slot, PATIENT turn = answer slot)
- meditod_sample_dialogs.csv - 3 real English doctor-patient dialogues with dialog-state annotations (MediTOD sample)
Caveat: only 14 distinct chief complaints; templated language. Good for pipeline tests, not for generalisation claims.

All CSVs are UTF-8 with BOM (open directly in Excel). `split` = patient-level train/valid/test (400/50/50 patients; no patient appears in two splits).

| File | Rows | Description |
|---|---|---|
| interview_turns.csv | 7863 | Turn-by-turn AI/patient history-taking dialogue (Hindi+English) with slot labels |
| structured_histories.csv | 300 | Gold structured history per interview (HPI, PMH, drug, allergy, family, personal, red flag, triage) |
| slot_inventory.csv | 28 | Slots used in interviews: AI turns carry the question slot, PATIENT turns the answer slot |
| interviews.jsonl | 300 | Nested interview: all turns + gold structured history (one JSON per line) |
| meditod_sample_dialogs.csv | 359 | MediTOD (IIT Delhi) - only 3 sample dialogues (115, 317, 407); full canonicalised set needs UMLS licence |
