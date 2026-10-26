"""Train the next-slot ranker on TRAIN, select parameters on VALID, and evaluate on TEST.

    cd backend && PYTHONPATH=. python -m training.adaptive.train

The test split is read only for final evaluation after selection. Outputs are versioned:
    models/adaptive_ranker/v2/{weights.json, config.json, manifest.json, train_report.json, evaluation.json}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import sklearn
from scipy.sparse import vstack
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GridSearchCV, PredefinedSplit

from app.adaptive.ranker import LearnedSlotRanker
from app.adaptive.schema import REVIEW_STATUS
from .data import HIST_DIR, Interview, file_sha256, load_interviews, pre_answer_examples, split_interviews, assert_group_integrity
from .model import (
    DEFAULT_THRESHOLDS,
    feature_matrix,
    feature_vocabulary,
    fit_weights,
    predict_next,
    runtime_ranker,
    validation_log_loss,
)

BACKEND = Path(__file__).resolve().parents[2]
C_GRID = (0.01, 0.1, 1.0, 10.0, 100.0, 1000.0)
CLASS_WEIGHTS = (None, "balanced")


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=BACKEND, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def examples_for(ivs):
    """Both views of every interview: the patient's recorded wording and the app's ontology label."""
    return [e for iv in ivs for view in ("recorded", "app_label") for e in pre_answer_examples(iv, view)]


def _ranker_metrics(ranker: LearnedSlotRanker, interviews: list[Interview], view: str) -> dict:
    examples = [e for iv in interviews for e in pre_answer_examples(iv, view)]
    classes = ranker.classes
    targets = [e.target for e in examples]
    rankings = [predict_next(ranker, e) for e in examples]
    predictions = [ranking[0][0] for ranking in rankings]
    reciprocal_ranks = [
        1.0 / (next(i for i, (label, _) in enumerate(ranking, 1) if label == example.target))
        for ranking, example in zip(rankings, examples)
    ]
    report = classification_report(
        targets, predictions, labels=classes, output_dict=True, zero_division=0
    )
    return {
        "examples": len(examples),
        "accuracy": report["accuracy"],
        "macro_f1": report["macro avg"]["f1-score"],
        "weighted_f1": report["weighted avg"]["f1-score"],
        "macro_precision": report["macro avg"]["precision"],
        "macro_recall": report["macro avg"]["recall"],
        "mrr": float(np.mean(reciprocal_ranks)),
        "top3_accuracy": float(np.mean([
            example.target in [label for label, _ in ranking[:3]]
            for ranking, example in zip(rankings, examples)
        ])),
        "per_class": {
            label: {
                "support": int(report[label]["support"]),
                "precision": report[label]["precision"],
                "recall": report[label]["recall"],
                "f1": report[label]["f1-score"],
            }
            for label in classes
        },
        "confusion_matrix": {
            "labels": classes,
            "counts": confusion_matrix(targets, predictions, labels=classes).tolist(),
        },
    }


def _baseline_metrics(train_ivs: list[Interview], test_ivs: list[Interview], view: str) -> dict:
    train_examples = [
        e for iv in train_ivs for e in pre_answer_examples(iv, "recorded")
    ]
    majority = max(
        sorted({e.target for e in train_examples}),
        key=lambda label: sum(e.target == label for e in train_examples),
    )
    templates: dict[tuple[str, tuple[str, ...]], dict[str, int]] = {}
    for example in train_examples:
        key = (example.complaint, tuple(example.state["asked"]))
        counts = templates.setdefault(key, {})
        counts[example.target] = counts.get(example.target, 0) + 1

    results = {}
    for name in ("majority_class", "template_lookup_with_complaint"):
        examples = [e for iv in test_ivs for e in pre_answer_examples(iv, view)]
        predictions = []
        for example in examples:
            choices = templates.get((example.complaint, tuple(example.state["asked"])), {})
            predictions.append(
                max(sorted(choices), key=choices.get) if name != "majority_class" and choices else majority
            )
        results[name] = {
            "examples": len(examples),
            "accuracy": float(np.mean([e.target == p for e, p in zip(examples, predictions)])),
            "note": "Synthetic template-imitation baseline; not a clinical utility measure.",
        }
    return results


def train(seed: int = 42, out_dir: Path | None = None, version: str = "v2") -> dict:
    t0 = time.time()
    splits = split_interviews(load_interviews())
    integrity = assert_group_integrity(splits)
    train_ex, valid_ex = examples_for(splits["train"]), examples_for(splits["valid"])
    vocab = feature_vocabulary(train_ex)
    X = vstack((
        feature_matrix(train_ex, vocab),
        feature_matrix(valid_ex, vocab),
    ), format="csr")
    y = np.asarray([example.target for example in train_ex + valid_ex])
    predefined_split = PredefinedSplit(
        test_fold=np.concatenate((
            np.full(len(train_ex), -1, dtype=int),
            np.zeros(len(valid_ex), dtype=int),
        ))
    )
    search = GridSearchCV(
        LogisticRegression(max_iter=5000, random_state=seed),
        param_grid={"C": list(C_GRID), "class_weight": list(CLASS_WEIGHTS)},
        scoring={"neg_log_loss": "neg_log_loss", "accuracy": "accuracy"},
        refit=False,
        cv=predefined_split,
        n_jobs=1,
        return_train_score=False,
    )
    search.fit(X, y)
    trials = [
        {
            **params,
            "valid_log_loss": round(-float(search.cv_results_["mean_test_neg_log_loss"][index]), 5),
            "valid_top1": round(float(search.cv_results_["mean_test_accuracy"][index]), 4),
            "features": len(vocab),
        }
        for index, params in enumerate(search.cv_results_["params"])
    ]
    best = min(trials, key=lambda t: (
        t["valid_log_loss"], -t["valid_top1"], t["C"], str(t["class_weight"])
    ))
    weights = fit_weights(train_ex, best["C"], seed, class_weight=best["class_weight"])
    selected_ranker = runtime_ranker(weights, version)
    final_fit_losses = {
        "train_log_loss": validation_log_loss(selected_ranker, train_ex),
        "validation_log_loss": validation_log_loss(selected_ranker, valid_ex),
    }

    out = out_dir or (BACKEND / "models" / "adaptive_ranker" / version)
    out.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(weights, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    (out / "weights.json").write_bytes(raw)
    config = {"version": f"adaptive_ranker/{version}", "model_type": "multinomial_logistic_regression (sklearn fit, numpy/JSON inference)",
              "task": "next question slot given the pre-answer interview state; ranks eligible slots only",
              "target_classes": weights["classes"], "fallback_thresholds": DEFAULT_THRESHOLDS,
              "hyperparameters": {"C": best["C"], "class_weight": best["class_weight"],
                                  "min_df": 2, "ngram_range": [2, 4], "seed": seed},
              "state_features": ["char 2-4 grams of the chief-complaint wording", "script (devanagari/latin)",
                                 "set of canonical slots already asked (order-invariant)"],
              "review_status": REVIEW_STATUS,
              "data_status": "SYNTHETIC, templated interviews (14 complaints); not clinical evidence"}
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    split_manifest = {
        "seed": seed,
        "group_key": "patient_id",
        "source_split_column": "split",
        "groups": [
            {
                "patient_id_sha256": hashlib.sha256(iv.patient_id.encode("utf-8")).hexdigest(),
                "interview_id_sha256": hashlib.sha256(iv.interview_id.encode("utf-8")).hexdigest(),
                "split": iv.split,
            }
            for iv in load_interviews()
        ],
    }
    (out / "split_manifest.json").write_text(
        json.dumps(split_manifest, indent=2), encoding="utf-8"
    )
    manifest = {"weights_sha256": hashlib.sha256(raw).hexdigest(), "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "git_commit": _git_commit(), "seed": seed,
                "data": {"interview_turns.csv": file_sha256(HIST_DIR / "interview_turns.csv"),
                         "structured_histories.csv": file_sha256(HIST_DIR / "structured_histories.csv")},
                "split_integrity": integrity, "train_examples": len(train_ex), "valid_examples": len(valid_ex),
                "test_examples": sum(len(pre_answer_examples(iv, "recorded")) for iv in splits["test"]),
                "environment": {
                    "python": platform.python_version(),
                    "platform": platform.platform(),
                    "cpu_cores": os.cpu_count(),
                    "device": "CPU",
                    "sklearn": sklearn.__version__,
                    "numpy": np.__version__,
                },
                "train_seconds": round(time.time() - t0, 2),
                "command": f"cd backend && PYTHONPATH=. python -m training.adaptive.train --version {version}"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report = {
        "hyperparameter_search_on_valid": trials,
        "selected": best,
        "final_fit_losses": final_fit_losses,
        "test_split_used_for_selection": False,
    }
    (out / "train_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    model_root = BACKEND / "models"
    if out_dir is not None:
        try:
            model_id = out.relative_to(model_root).as_posix()
        except ValueError:
            model_root = out.parent
            model_id = out.name
    else:
        model_id = f"adaptive_ranker/{version}"
    loaded = LearnedSlotRanker.load(model_id, model_root)
    probe = valid_ex[0]
    assert predict_next(loaded, probe) == predict_next(runtime_ranker(weights, version), probe)

    test_ivs = splits["test"]
    original = LearnedSlotRanker.load("adaptive_ranker/v1", model_root)
    evaluation = {
        "experiment_id": f"adaptive_ranker_{version}",
        "seed": seed,
        "test_split": integrity["test"],
        "test_used_for_selection": False,
        "synthetic_data_warning": "Recorded next-question labels reproduce templated synthetic interviews; no clinical utility is established.",
        "models": {
            "original_v1": {
                view: _ranker_metrics(original, test_ivs, view)
                for view in ("recorded", "app_label")
            },
            "tuned_" + version: {
                view: _ranker_metrics(loaded, test_ivs, view)
                for view in ("recorded", "app_label")
            },
        },
        "simple_baselines": {
            view: _baseline_metrics(splits["train"], test_ivs, view)
            for view in ("recorded", "app_label")
        },
    }
    (out / "evaluation.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    model_card = f"""# Adaptive next-question ranker {version}

## Intended use

Experimental imitation of recorded next-question slots from synthetic, templated MediKiosk interviews. Not a diagnostic model and not evidence of clinical utility.

## Training

- Algorithm: multinomial scikit-learn LogisticRegression; plain JSON weights for dependency-free inference.
- Data: 300 synthetic interview groups, split 240/30/30 by patient; 7,863 dialogue turns.
- Features: complaint character n-grams (2-4), script, and previously asked slots.
- Selection: validation-only search over `C={list(C_GRID)}` and `class_weight={list(CLASS_WEIGHTS)}`; selected `{best}`.
- Final evaluation: held-out test split after selection; see `evaluation.json`.
- Checkpoint integrity: SHA-256 in `manifest.json`; membership hashes in `split_manifest.json`.

## Limitations

The label is mostly a repeated template. A training-only complaint/state template lookup matches or exceeds the ranker on this test set. Clinical relevance, patient safety, fairness, and generalization have not been established. The application continues to load v1 by default; this checkpoint is not integrated.
"""
    (out / "MODEL_CARD.md").write_text(model_card, encoding="utf-8")
    return {
        "checkpoint": str(out),
        "weights_bytes": len(raw),
        **report,
        "evaluation": {
            name: {view: scores["accuracy"] for view, scores in views.items()}
            for name, views in evaluation["models"].items()
        },
        "manifest": manifest,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--version", default="v2")
    args = ap.parse_args()
    print(json.dumps(train(args.seed, version=args.version), indent=2)[:5000])


if __name__ == "__main__":
    main()
