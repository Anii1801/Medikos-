# MediKiosk model and dataset selection (research notes)

Updated: 2026-10-18. This document records model candidates, the current implementation, and dataset availability. It does not claim that any model has been trained or clinically validated in this repository.

## Current implementation

- Adaptive interview: ontology-based question policy plus `HistoryTakingAgent` state, answer history, question budget, uncertainty/conflict tracking, and a validated adapter boundary. The active policy is deterministic and is **not a trained model**.
- Clinical extraction: rule-based `ClinicalNLPService`; English-only and untrained.
- Summary: extraction-first deterministic template, source references, and explicit missing/uncertain fields.
- Red flags: provisional deterministic rules. No trained risk model is bundled; no ML-derived clinical probability should be displayed.
- Voice: browser Web Speech API in the UI. This depends on browser support, permission, network, and selected language. Server-side ASR requires a configured provider and language evaluation.

## Candidate models/papers and what each can support

| Component | Candidate / paper | Why relevant | What it does NOT prove |
|---|---|---|---|
| Adaptive history / dialogue policy | Saley et al., **MediTOD**, EMNLP 2024, https://aclanthology.org/2024.emnlp-main.936/ and official repo https://github.com/dair-iitd/MediTOD | Annotated medical-history-taking dialogue with symptom slots and attributes; useful for policy/NLU benchmark and comparison | It is not an ASR dataset, and using its data does not itself produce a clinically validated interview policy |
| Multilingual dialogue summary and QA | Roy & Das, **NLP4Health**, NLP-AI4Health 2025, https://aclanthology.org/2025.nlpai4health-main.10/ | Uses `google/mt5-base` with LoRA for English summaries, structured JSON and QA in the original language; published/reproducible direction for Indian-language work | This is a summarization/QA approach, not automatically the best model for adaptive question selection; the repository currently has no trained adapter |
| Multilingual extraction/summarization | Zaid et al., Qwen-1.5B + LoRA, NLP-AI4Health 2025, https://aclanthology.org/2025.nlpai4health-main.6/ | Lightweight parameter-efficient model candidate for structured outputs under constrained compute | Requires exact task-matched evaluation, compatible hardware, license review and leakage-safe splits before adoption |
| Multilingual patient-centric tasks | MedQwen-PE, Qwen3-1.7B + QLoRA, NLP-AI4Health 2025 shared-task listing, https://aclanthology.org/events/nlpai4health-2025/ | Candidate for structured extraction, QA and summarization where its released artefacts and terms fit | Shared-task performance is not evidence of safe autonomous clinical use or guaranteed performance on this project's data |
| Clinical note factuality | Abridge engineering note on Editors, https://tech.abridge.com/blog/real-time-error-detection-and-correction | Inspires a separate detector/corrector stage and evidence-grounded note checks | Abridge's private models/weights/architecture are not included or copied here |

### Recommendation

Do **not** replace the deterministic adaptive policy with a generative model alone. Keep a transparent state/policy layer responsible for question order, duplicate prevention, missingness, stopping, and safety escalation. Benchmark a task-oriented dialogue policy against this baseline using licensed MediTOD data if available. Consider mT5-base + LoRA for multilingual summary/QA only after an evaluation baseline and hardware check. The 2025 Qwen LoRA/QLoRA approaches are alternatives to compare, not assumed winners. No clinical red-flag decision should depend solely on a text generator.

## Dataset inventory and availability

The ZIP already includes `Datasets/MediKiosk_Datasets/` and the local dataset index. Therefore no blanket dataset download was necessary to restore the project. Included tables are not all research-grade: some are synthetic, templated, derived, small samples, or only manifests for images that are absent. See `DATASET_INDEX.csv`, `EXTERNAL_SOURCES.csv`, and `QUALITY_REPORT.md` for item-level details.

| Dataset / source | Current state in project | Use / limitation |
|---|---|---|
| Project interview turns and structured histories | Included CSV/JSONL; synthetic/templated according to local quality report | Software smoke tests and internal development only; not clinical evidence |
| MediTOD | Three sample dialogues only, according to local manifest | Full dataset/release and any UMLS-dependent canonicalized annotations require verifying the official repository's terms and any access conditions; do not claim the full dataset is present |
| ACI-Bench | 207 dialogue-note pairs listed as included | Useful note-generation benchmark candidate; verify original license and dataset version before training or redistribution |
| MTSamples | 4,966 cleaned notes listed as included | The notes are not paired patient-history dialogues; do not use them as if they were dialogue-to-note pairs |
| OCR image datasets | Manifests included; source images are not bundled per local manifest | Do not report image OCR performance from text-level simulated pairs; acquire images only from their authoritative source after license/version checks |
| ASR noisy test set | 900 rows of simulated transcript noise; no audio | Can test text correction only, not real speech recognition WER |
| Red-flag labelled cases | 300 synthetic cases | Software testing and pipeline diagnostics only; not clinical validation |
| MIMIC-III / MIMIC-IV | Not bundled | Access/credentialing and data-use requirements apply; not downloaded into this project |
| NLP4Health / Qwen adapters | Model candidates, not included trained checkpoints | Verify released artifact version, licence, dependencies and task match before downloading |

### Kaggle acceptance checklist

A Kaggle dataset is not publication-ready merely because it is popular. Before including any new Kaggle dataset in a paper, record its canonical URL, owner, exact version/retrieval date, upstream source/publication, license, data dictionary, preprocessing, duplicate/leakage checks, and split policy. Prefer the original publisher or official repository when possible. The project currently has some Kaggle-derived manifests/tables but does not establish an exact reproducible Kaggle version for every item. Do not invent missing version IDs or licenses.

### Download policy

Do not download all candidate corpora blindly or put restricted/credentialed patient data into the ZIP. This working tree already contains its project dataset directory. Missing image assets and full external corpora are documented as missing; acquire them from their authoritative source only after checking the licence/access conditions and pinning an exact version. For MIMIC, complete required PhysioNet access steps rather than bypassing them. Do not commit `.env`, API keys, database files containing patient records, model weights, or large licensed corpora.

## Minimum reproducible experiments before a paper claim

1. Compare the current ontology/state policy against a fixed questionnaire on a held-out, permitted history-taking dataset.
2. Report question count, duplicate rate, relevant-question ratio, slot/attribute F1, history completeness, and omitted critical facts.
3. Compare deterministic extraction-first summary against a single-pass baseline using factuality/unsupported-claim and omission analysis; ROUGE/BERTScore are secondary.
4. Evaluate each language separately. Text-only dialogue is not an ASR benchmark; real audio is required for ASR WER/CER.
5. Evaluate red flags separately using clinician-labelled data and sensitivity/false-negative analysis. Synthetic cases are not clinical evidence.
6. Keep patient/conversation/speaker groups separated across train/validation/test, report exact versions and seeds, and publish scripts/configuration where permitted.
