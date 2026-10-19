# Dataset and model-training infrastructure

## Verified source status

| Resource | Official source | Licence/access status | Local status |
|---|---|---|---|
| MediTOD | [dair-iitd/MediTOD](https://github.com/dair-iitd/MediTOD) | GitHub API reports no licence; author confirmation required | Loader interface only |
| MTS-Dialog | [abachaa/MTS-Dialog](https://github.com/abachaa/MTS-Dialog) | GitHub reports `Other` / `NOASSERTION`; terms required | Loader interface only |
| MedicalSum-related | [ACI-Bench](https://github.com/wyim/aci-bench), plus local MTSamples export | ACI-Bench GitHub reports no licence; local MTSamples is marked CC0 in project register but provenance should be retained | ACI-Bench partial CSV and MTSamples local export |
| Tabassum handwritten medical terms | No authoritative source identified from the supplied materials or repository search | Unverified; no download or licence claim | Interface only, unavailable |
| AI4Bharat multilingual resources | [AI4Bharat Hugging Face organisation](https://huggingface.co/ai4bharat) | Per-resource licence and speaker/privacy terms required | Interface only |

The exact machine-readable status is in
[`backend/training/configs/datasets.json`](../backend/training/configs/datasets.json).
No inaccessible resource is represented as downloaded, labelled, or trained.

## Loaders and leakage prevention

- `backend/training/manifest.py` loads CSV/JSONL resources from explicit paths.
- Required schema fields are checked before preparation.
- Splits are grouped by `patient_id`, `interview_id`, `encounter_id`, or
  `speaker_id` as declared by the manifest.
- Normalized duplicate fingerprints are checked across every split.
- Dataset schemas remain task-specific; no labels are merged without an
  explicit mapping.

Prepare a split:

```powershell
cd backend
python -m training.prepare --dataset-id local_history_interview
```

Validate every resource:

```powershell
python -m training.validate
```

## Separate task pipelines

`backend/training/configs/tasks.json` records independent pipelines for
history-taking, extraction, red flags, OCR, ASR, and summarization. Each task
declares its baseline, candidate model, LoRA/QLoRA policy, and metrics.

CPU smoke test:

```powershell
python -m training.smoke --task history_taking
python -m training.smoke --task red_flag
```

Smoke tests do not create a checkpoint or claim model performance. A future
trainer must write configuration, seed, checkpoint path, trainable parameter
count, elapsed time, GPU memory, inference latency, and task metrics to a
versioned report. LoRA/QLoRA is deliberately pending compatible weights,
tokenizer, licence, and hardware verification.
