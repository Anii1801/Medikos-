# 04_asr_voice

Voice input (Bhashini/ASR stage).
- asr_noisy_test_set.csv - 900 rows (300 phrases x quiet room / OPD corridor / crowded hall) with WER/CER
- asr_noise_summary.csv - mean WER/CER per language and noise profile
- external_audio_sources.csv - real audio corpora to download (IndicVoices, Kathbath, Svarah, Shrutilipi)
Text-level simulation only; no audio exists in the uploads.

All CSVs are UTF-8 with BOM (open directly in Excel). `split` = patient-level train/valid/test (400/50/50 patients; no patient appears in two splits).

| File | Rows | Description |
|---|---|---|
| asr_noisy_test_set.csv | 900 | Chief-complaint reference text vs simulated ASR text under 3 noise profiles (text-level simulation, no audio) |
| asr_noise_summary.csv | 6 | Mean WER/CER by language and noise profile |
| external_audio_sources.csv | 4 | Real audio corpora to fine-tune/evaluate ASR (not downloaded) |
