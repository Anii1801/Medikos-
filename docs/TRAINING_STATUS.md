> **Superseded (2026-10-21).** One checkpoint now exists (`backend/models/adaptive_ranker/v1`, a logistic-regression slot ranker on synthetic data). See `docs/PROJECT_STATUS.md` (generated), `docs/MODEL_TRAINING.md` and `docs/EVALUATION_RESULTS.md`. The statements below predate it.

# MediKiosk training status

Generated from the infrastructure verification run on 2026-10-14.

| Pipeline | Actual model | Trained in this repository | Checkpoint | Evidence |
|---|---|---:|---|---|
| History-taking | deterministic ontology / adapter boundary | No | None | CPU smoke only |
| Clinical extraction | regex baseline | No | None | Local schema validation only |
| Red-flag | RedFlagEngine deterministic rules | No | None | 300-row demo evaluation |
| OCR | Tesseract integration baseline | No | None | Text-pair smoke only; image OCR needs Tesseract |
| ASR | browser/Web Speech and text-pair baseline | No | None | 900-row text-level resource validation |
| Summarization | deterministic summary builder | No | None | 300-row synthetic schema validation |

No LoRA/QLoRA run was performed. No GPU memory, trainable parameter count,
training time, or neural inference latency is claimed because no trainable
checkpoint was produced. CPU smoke outputs intentionally report zero
trainable parameters and no checkpoint.

## Pending gates

1. Obtain licence/access confirmation for MediTOD, MTS-Dialog, ACI-Bench, and
   each selected AI4Bharat resource.
2. Identify the authoritative Tabassum handwritten medical-term corpus and
   verify its schema, licence, image access, and patient/writer split policy.
3. Define explicit label mappings before combining any datasets.
4. Add approved de-identification, patient/conversation/speaker leakage checks,
   and clinician-reviewed validation sets.
5. Select compatible model weights and hardware before enabling LoRA/QLoRA.
6. Run task-specific evaluation with confidence intervals and subgroup
   reporting; do not treat synthetic local data as clinical evidence.
