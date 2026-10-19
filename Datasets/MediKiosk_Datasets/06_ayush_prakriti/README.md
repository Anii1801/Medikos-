# 06_ayush_prakriti

AYUSH mode.
- dashavidha_pariksha_with_context.csv - Prakriti, Vikriti, Sara, Samhanana, Pramana, Satmya, Sattva, Agni, Koshtha, Nidana + age/sex/state/complaint
- ayush_value_distribution.csv
Synthetic; has not been checked by an Ayurvedic physician. For real Prakriti data see Prakriti200 (IEEE DataPort) and the Mendeley cohorts in EXTERNAL_SOURCES.csv.

All CSVs are UTF-8 with BOM (open directly in Excel). `split` = patient-level train/valid/test (400/50/50 patients; no patient appears in two splits).

| File | Rows | Description |
|---|---|---|
| dashavidha_pariksha_with_context.csv | 356 | Dashavidha Pariksha (Prakriti, Vikriti, Sara, Samhanana, Pramana, Satmya, Sattva, Agni, Koshtha...) + demographics + chief complaint |
| ayush_value_distribution.csv | 22 | Value counts for Prakriti, Vikriti, Agni, Koshtha |
