# Model training and reproducibility

The supported production path is currently a deterministic baseline.

| Task | Current implementation | Training status |
|---|---|---|
| Adaptive history-taking | `AdaptiveHistoryTakingAgent` and ontology policy | No neural checkpoint |
| Clinical extraction | `ClinicalNLPService` and OCR entity parser | No BIO mapping configured |
| Laboratory reports | Deterministic parser and source-linked comparison | No clinical model |
| Red flags | `RedFlagEngine` deterministic rules | No classifier for safety decisions |
| OCR | PDF extraction/Tesseract when installed | No handwriting images bundled |
| ASR | Browser/Web Speech | Bundled data is text-only |
| Summaries | Evidence-grounded deterministic template | No generative model enabled |

From the repository root:

```powershell
$env:PYTHONPATH='C:\path\to\medikiosk\backend'
python backend/training/prepare.py --dataset-id local_history_interview
python backend/scripts/evaluate_history_agent.py
pytest backend/tests -q
```

Preparation performs schema validation, group splitting, and duplicate/leakage
checks. It does not download data or claim training. External resources remain
gated in `backend/training/configs/datasets.json`.

The adaptive agent records each slot's value, status, source, provenance,
attempt count, and last attempt. A learned ranker may be added behind this
contract only after reconstructing pre-answer states and evaluating on
interview-level held-out data.
