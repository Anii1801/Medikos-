"""Train the next-slot ranker on the TRAIN split, select C on the VALID split, save a checkpoint.

    cd backend && PYTHONPATH=. python -m training.adaptive.train

The test split is never read here. Outputs (committed; < 1 MB):
    models/adaptive_ranker/v1/{weights.json, config.json, manifest.json, train_report.json, MODEL_CARD.md}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import sklearn

from app.adaptive.ranker import LearnedSlotRanker
from app.adaptive.schema import REVIEW_STATUS
from .data import HIST_DIR, file_sha256, load_interviews, pre_answer_examples, split_interviews, assert_group_integrity
from .model import DEFAULT_THRESHOLDS, fit_weights, predict_next, runtime_ranker, validation_log_loss

BACKEND = Path(__file__).resolve().parents[2]
C_GRID = (0.1, 1.0, 10.0, 100.0)
VERSION = "v1"


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=BACKEND, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def examples_for(ivs):
    """Both views of every interview: the patient's recorded wording and the app's ontology label."""
    return [e for iv in ivs for view in ("recorded", "app_label") for e in pre_answer_examples(iv, view)]


def train(seed: int = 42, out_dir: Path | None = None) -> dict:
    t0 = time.time()
    splits = split_interviews(load_interviews())
    integrity = assert_group_integrity(splits)
    train_ex, valid_ex = examples_for(splits["train"]), examples_for(splits["valid"])
    trials = []
    for C in C_GRID:
        w = fit_weights(train_ex, C, seed)
        r = runtime_ranker(w, VERSION)
        ll = validation_log_loss(r, valid_ex)
        acc = float(np.mean([predict_next(r, e)[0][0] == e.target for e in valid_ex]))
        trials.append({"C": C, "valid_log_loss": round(ll, 5), "valid_top1": round(acc, 4), "features": len(w["vocab"])})
    best = min(trials, key=lambda t: (t["valid_log_loss"], -t["valid_top1"], t["C"]))
    weights = fit_weights(train_ex, best["C"], seed)

    out = out_dir or (BACKEND / "models" / "adaptive_ranker" / VERSION)
    out.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(weights, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    (out / "weights.json").write_bytes(raw)
    config = {"version": f"adaptive_ranker/{VERSION}", "model_type": "multinomial_logistic_regression (sklearn fit, numpy/JSON inference)",
              "task": "next question slot given the pre-answer interview state; ranks eligible slots only",
              "target_classes": weights["classes"], "fallback_thresholds": DEFAULT_THRESHOLDS,
              "hyperparameters": {"C": best["C"], "min_df": 2, "ngram_range": [2, 4], "seed": seed},
              "state_features": ["char 2-4 grams of the chief-complaint wording", "script (devanagari/latin)",
                                 "set of canonical slots already asked (order-invariant)"],
              "review_status": REVIEW_STATUS,
              "data_status": "SYNTHETIC, templated interviews (14 complaints); not clinical evidence"}
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest = {"weights_sha256": hashlib.sha256(raw).hexdigest(), "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "git_commit": _git_commit(), "seed": seed,
                "data": {"interview_turns.csv": file_sha256(HIST_DIR / "interview_turns.csv"),
                         "structured_histories.csv": file_sha256(HIST_DIR / "structured_histories.csv")},
                "split_integrity": integrity, "train_examples": len(train_ex), "valid_examples": len(valid_ex),
                "environment": {"python": platform.python_version(), "sklearn": sklearn.__version__, "numpy": np.__version__},
                "train_seconds": round(time.time() - t0, 2),
                "command": "cd backend && PYTHONPATH=. python -m training.adaptive.train"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report = {"hyperparameter_search_on_valid": trials, "selected": best, "test_split_used": False}
    (out / "train_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    loaded = LearnedSlotRanker.load(f"adaptive_ranker/{VERSION}", out.parents[1] if out_dir else None)   # prove the saved file loads
    probe = valid_ex[0]
    assert predict_next(loaded, probe) == predict_next(runtime_ranker(weights, VERSION), probe)
    return {"checkpoint": str(out), "weights_bytes": len(raw), **report, "manifest": manifest}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    print(json.dumps(train(args.seed), indent=2)[:2500])


if __name__ == "__main__":
    main()
