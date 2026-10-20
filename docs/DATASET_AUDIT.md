# Dataset audit

Audit date: 2026-10-20. The inventory was checked against files present under
`Datasets/MediKiosk_Datasets`; manifest entries alone are not treated as evidence
that an external resource is available.

| Dataset | Verified local content | Intended use | Quality and leakage risk | Recommendation |
|---|---:|---|---|---|
| `00_patient_master` | Patient CSV/JSONL and FHIR examples | Context and linkage | Synthetic/demo; patient-linked | Group-split, local smoke tests only |
| `01_history_interview` | 7,863 turns, 300 histories, 28 slots | Adaptive questioning | Synthetic/template; turn leakage risk | CPU baseline and leakage-safe evaluation |
| MediTOD sample | 3 sample dialogues | Research comparison | Not the full corpus; licence unresolved | Do not train or redistribute |
| `02_ocr_handwriting` | 1,238 lab entities, 1,011 prescription entities, 892 simulated OCR pairs | Extraction and text-level OCR | Images are not bundled; synthetic/noisy and duplicate rows | Baseline/evaluation only |
| `03_patient_summary` | 300 synthetic pairs, 207 ACI-Bench pairs, 4,966 notes | Summary experiments | Notes are not paired with dialogue; synthetic data is not evidence | Use genuine pairs only |
| `04_asr_voice` | 900 simulated text pairs | Text-level WER/CER | No audio is present | Cannot train ASR |
| `05_triage_redflag` | Rules, labelled cases, symptom tables | Rule evaluation | Synthetic/illustrative labels | Keep deterministic rules authoritative |
| `06_ayush_prakriti` | Local tabular records | Optional AYUSH module | Synthetic; not clinician validated | Isolate from general inference |
| `07_drug_safety` | Illustrative interaction tables | Warning lookup | Small and requires source validation | Not comprehensive |
| External gated resources | Not bundled | Future research | Access/licence/images/audio unresolved | No downloads performed |

All model preparation must use patient/interview-group splits and duplicate
checks. No neural checkpoint or clinical validation result was produced.
