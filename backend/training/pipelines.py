from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .manifest import DatasetError, DatasetSpec, assert_no_leakage, load_rows, split_by_group, validate_rows


PIPELINES = {
    "history_taking": {"dataset": "local_history_interview", "model": "deterministic-policy-or-configured-llm-adapter"},
    "clinical_extraction": {"dataset": "local_ocr_entities", "model": "regex-baseline; trainable NER pending licensed corpus"},
    "red_flag": {"dataset": "local_red_flag_cases", "model": "deterministic-RedFlagEngine; classifier pending provenance"},
    "ocr": {"dataset": "local_ocr_pairs", "model": "Tesseract baseline; handwriting model pending access"},
    "asr": {"dataset": "local_asr_text", "model": "browser/Web Speech baseline; audio corpus pending access"},
    "summarization": {"dataset": "local_summary_pairs", "model": "deterministic summary; generative model pending licensed data"},
}


def prepare_pipeline(root: Path, spec: DatasetSpec, output: Path, seed: int = 42) -> dict[str, Any]:
    rows = load_rows(root, spec)
    validation = validate_rows(spec, rows)
    if not validation["valid"]:
        raise DatasetError(json.dumps(validation))
    if not spec.group_key:
        raise DatasetError(f"{spec.dataset_id}: group_key is required for leakage-safe training")
    splits = split_by_group(rows, spec.group_key, seed=seed)
    assert_no_leakage(splits, spec.group_key, list(spec.schema))
    output.mkdir(parents=True, exist_ok=True)
    for name, split_rows in splits.items():
        (output / f"{spec.dataset_id}.{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in split_rows), encoding="utf-8"
        )
    return {"dataset_id": spec.dataset_id, "seed": seed, "validation": validation,
            "split_counts": {name: len(rows) for name, rows in splits.items()}}


def smoke_train(task: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    start = time.perf_counter()
    if task not in PIPELINES:
        raise DatasetError(f"Unknown task pipeline: {task}")
    if not rows:
        raise DatasetError(f"{task}: no rows available for CPU smoke test")
    target = "red_flag" if task == "red_flag" else None
    labels = [str(row.get(target, "")) for row in rows] if target else []
    majority = max(set(labels), key=labels.count) if labels else "not-applicable"
    elapsed = time.perf_counter() - start
    return {
        "task": task,
        "model": PIPELINES[task]["model"],
        "trained": False,
        "smoke_only": True,
        "rows_seen": len(rows),
        "majority_label": majority,
        "trainable_parameters": 0,
        "training_seconds": round(elapsed, 6),
        "gpu_memory_mb": 0,
        "inference_latency_ms": None,
        "metrics": {},
        "note": "Infrastructure smoke test only; no checkpoint or clinical performance claim.",
    }
