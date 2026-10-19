# Quality report and limitations

- Only 14 distinct chief complaints across 300 synthetic interviews - templated, low diversity; do not use for generalisation claims.
- MediTOD file supplied has only 3 dialogues (the public sample). Full set requires UMLS licence + request form.
- prescriptions sheet has 9 exact duplicate rows (flagged in is_exact_duplicate, not removed).
- Noisy Medical Docs: hospital names are Indian but fields follow US conventions (NPI numbers); images are synthetic.
- Prescription BD: 78 brand names but only 15 generic names; Bangladeshi brands - map to Indian brands before use.
- MTSamples: 33 rows dropped for missing transcription; no patient IDs; US specialty notes.
- ASR set is text-level simulation only (Hindi + English). No real audio in any uploaded file; patients in other languages (Marathi, Tamil...) have no ASR data.
- Kaggle Training.csv: 4920 rows but only 304 unique symptom patterns across 41 diseases (heavy duplication). Deduplicated copy provided - note train/test overlap likely inflates accuracy.
- 41 of 42 Testing.csv rows exactly match a Training row.
- data.csv has 713 disease labels, 246,945 rows (not copied - use your original file).
- Symptom datasets are non-clinical benchmarks; use for prototyping only, not diagnosis.
- AYUSH records exist for 356 of 500 patients; synthetic and not validated by an Ayurvedic physician.
- Drug interaction table has only 9 pairs - illustrative; validate against a real source before use.
- All 500 patients have consent_capture=True (no negative-consent cases to test consent handling).

## Integrity checks
No orphan patient or interview IDs in any table; no patient in more than one split (400/50/50).

## Simulated OCR noise (mean CER/WER)
```
 handwritten scan_quality   n  mean_cer  mean_wer
       False         fair 223    0.0036    0.0292
       False         good 299    0.0007    0.0058
       False         poor  82    0.0088    0.0763
        True         fair 109    0.0040    0.0282
        True         good 114    0.0005    0.0038
        True         poor  65    0.0085    0.0618
```
## Simulated ASR noise
```
language        noise_profile   n  mean_wer  mean_cer
      en crowded_waiting_hall  45    0.3263    0.2348
      en         opd_corridor  45    0.0927    0.0645
      en           quiet_room  45    0.0000    0.0000
      hi crowded_waiting_hall 255    0.2041    0.1755
      hi         opd_corridor 255    0.1014    0.0915
      hi           quiet_room 255    0.0000    0.0000
```
All synthetic modules (01-04, 06, 07) are for pipeline development and demos. Real-world accuracy must be measured on consented real data.
