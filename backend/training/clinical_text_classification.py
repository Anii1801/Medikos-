"""Train an isolated TF-IDF disease-label text-classification benchmark.

This local, non-clinical experiment uses the existing dataset split and refuses
normalized-text leakage across splits. It must not be used for diagnosis.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, log_loss
from sklearn.model_selection import GridSearchCV, PredefinedSplit
from sklearn.pipeline import Pipeline

from app.datasets import DATASET_ROOT

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = DATASET_ROOT / "05_triage_redflag" / "symptom2disease_text.csv"
MODEL_OUT = REPO_ROOT / "backend" / "models" / "clinical_text_classifier" / "v1"
RESULTS_OUT = REPO_ROOT / "evaluation_results" / "clinical_text_classification"
C_GRID = (0.01, 0.1, 1.0, 10.0, 100.0)
CLASS_WEIGHTS = (None, "balanced")


def _normalise_text(text: str) -> str:
    return " ".join(text.casefold().split())


def _read_dataset(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"label", "text", "split"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Expected non-empty CSV with columns {sorted(required)}: {path}")
    if any(not row["label"].strip() or not row["text"].strip() for row in rows):
        raise ValueError("Dataset contains a blank label or text value.")
    if any(row["split"] not in {"train", "valid", "test"} for row in rows):
        raise ValueError("Dataset split values must be train, valid, or test.")
    return rows


def _group_hash(text: str) -> str:
    return hashlib.sha256(_normalise_text(text).encode("utf-8")).hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _assert_group_integrity(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    split_by_group: dict[str, str] = {}
    group_manifest = []
    for row in rows:
        group = _group_hash(row["text"])
        previous = split_by_group.setdefault(group, row["split"])
        if previous != row["split"]:
            raise ValueError("Normalized text duplicates occur across train/valid/test splits.")
        group_manifest.append({"text_group_sha256": group, "split": row["split"]})
    return group_manifest


def _scores(model: Pipeline, texts: list[str], labels: list[str], classes: list[str]) -> dict[str, Any]:
    probabilities = model.predict_proba(texts)
    predictions = model.predict(texts)
    report = classification_report(
        labels, predictions, labels=classes, output_dict=True, zero_division=0
    )
    class_order = list(model.named_steps["classifier"].classes_)
    ordered_probabilities = probabilities[:, [class_order.index(label) for label in classes]]
    sorted_indices = np.argsort(ordered_probabilities, axis=1)[:, ::-1]
    reciprocal_ranks = [
        1.0 / (next(index + 1 for index, candidate in enumerate(order) if classes[candidate] == label))
        for order, label in zip(sorted_indices, labels)
    ]
    return {
        "examples": len(labels),
        "accuracy": report["accuracy"],
        "macro_f1": report["macro avg"]["f1-score"],
        "weighted_f1": report["weighted avg"]["f1-score"],
        "macro_precision": report["macro avg"]["precision"],
        "macro_recall": report["macro avg"]["recall"],
        "top3_accuracy": float(np.mean([
            label in [classes[index] for index in order[:3]]
            for order, label in zip(sorted_indices, labels)
        ])),
        "mrr": float(np.mean(reciprocal_ranks)),
        "log_loss": float(log_loss(labels, ordered_probabilities, labels=classes)),
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
            "counts": confusion_matrix(labels, predictions, labels=classes).tolist(),
        },
    }


def run_experiment(
    data_path: Path = DATA_PATH,
    model_out: Path = MODEL_OUT,
    results_out: Path = RESULTS_OUT,
    seed: int = 42,
) -> dict[str, Any]:
    started = time.perf_counter()
    rows = _read_dataset(data_path)
    group_manifest = _assert_group_integrity(rows)
    splits = {
        name: [row for row in rows if row["split"] == name]
        for name in ("train", "valid", "test")
    }
    if any(not split_rows for split_rows in splits.values()):
        raise ValueError("Train, validation, and test splits must all contain rows.")

    classes = sorted({row["label"] for row in rows})
    train_classes = {row["label"] for row in splits["train"]}
    if train_classes != set(classes):
        raise ValueError("At least one class is absent from training; cannot score it fairly.")

    train_text = [row["text"] for row in splits["train"]]
    valid_text = [row["text"] for row in splits["valid"]]
    train_labels = [row["label"] for row in splits["train"]]
    valid_labels = [row["label"] for row in splits["valid"]]
    combined_text = train_text + valid_text
    combined_labels = np.asarray(train_labels + valid_labels)
    predefined_split = PredefinedSplit(
        test_fold=np.concatenate((
            np.full(len(train_text), -1, dtype=int),
            np.zeros(len(valid_text), dtype=int),
        ))
    )
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
        ("classifier", LogisticRegression(max_iter=3000, random_state=seed)),
    ])
    search = GridSearchCV(
        pipeline,
        param_grid={
            "classifier__C": list(C_GRID),
            "classifier__class_weight": list(CLASS_WEIGHTS),
        },
        scoring={"neg_log_loss": "neg_log_loss", "accuracy": "accuracy"},
        refit=False,
        cv=predefined_split,
        n_jobs=1,
        return_train_score=False,
    )
    search.fit(combined_text, combined_labels)
    trials = [
        {
            **params,
            "validation_log_loss": round(
                -float(search.cv_results_["mean_test_neg_log_loss"][index]), 6
            ),
            "validation_accuracy": round(
                float(search.cv_results_["mean_test_accuracy"][index]), 6
            ),
        }
        for index, params in enumerate(search.cv_results_["params"])
    ]
    best = min(
        trials,
        key=lambda trial: (
            trial["validation_log_loss"],
            -trial["validation_accuracy"],
            trial["classifier__C"],
            str(trial["classifier__class_weight"]),
        ),
    )

    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
        ("classifier", LogisticRegression(
            C=best["classifier__C"],
            class_weight=best["classifier__class_weight"],
            max_iter=3000,
            random_state=seed,
        )),
    ])
    model.fit(train_text, train_labels)
    model_out.mkdir(parents=True, exist_ok=True)
    model_path = model_out / "model.joblib"
    joblib.dump(model, model_path)
    loaded_model = joblib.load(model_path)

    test_text = [row["text"] for row in splits["test"]]
    test_labels = [row["label"] for row in splits["test"]]
    test_scores = _scores(loaded_model, test_text, test_labels, classes)
    majority = max(sorted(train_classes), key=lambda label: train_labels.count(label))
    majority_accuracy = float(np.mean([label == majority for label in test_labels]))
    training_log_loss = float(log_loss(
        train_labels,
        loaded_model.predict_proba(train_text)[:, [
            list(loaded_model.named_steps["classifier"].classes_).index(label)
            for label in classes
        ]],
        labels=classes,
    ))
    validation_scores = _scores(loaded_model, valid_text, valid_labels, classes)
    dataset_sha256 = hashlib.sha256(data_path.read_bytes()).hexdigest()
    duration = round(time.perf_counter() - started, 3)

    model_config = {
        "model_id": "tfidf_logistic_regression_symptom_label_benchmark",
        "task": "non-clinical text classification against dataset-provided disease labels",
        "labels": classes,
        "features": {"ngram_range": [1, 2], "min_df": 1, "sublinear_tf": True},
        "selected_hyperparameters": best,
        "seed": seed,
        "dataset_sha256": dataset_sha256,
        "license_status": "upstream Kaggle terms unresolved; local experiment only, do not redistribute pending review",
        "clinical_use": False,
    }
    model_config_path = model_out / "config.json"
    model_config_path.write_text(json.dumps(model_config, indent=2), encoding="utf-8")
    report = {
        "experiment_id": "symptom2disease_tfidf_lr_v1",
        "dataset": {
            "path": _display_path(data_path),
            "rows": len(rows),
            "classes": len(classes),
            "sha256": dataset_sha256,
        },
        "splits": {name: len(split_rows) for name, split_rows in splits.items()},
        "grouping": {
            "key": "sha256 of normalized full input text (no patient/source ID exists in the file)",
            "cross_split_duplicate_groups": 0,
        },
        "search": {
            "method": "GridSearchCV with PredefinedSplit; validation only",
            "trials": trials,
            "selected": best,
        },
        "final_fit": {
            "training_log_loss": training_log_loss,
            "validation_log_loss": validation_scores["log_loss"],
        },
        "test_used_for_selection": False,
        "test_metrics": test_scores,
        "majority_class_baseline": {
            "label": majority,
            "accuracy": majority_accuracy,
            "note": "Trained on the training split only.",
        },
        "runtime": {
            "seconds": duration,
            "python_sklearn": sklearn.__version__,
            "numpy": np.__version__,
            "device": "CPU",
        },
        "model_checkpoint": _display_path(model_path),
        "reloaded_from_disk_before_test_evaluation": True,
        "limitations": [
            "Dataset is a small, externally sourced symptom-description to disease-label benchmark; upstream license terms are unresolved.",
            "No patient/source group key is present; exact normalized-text hashes were checked for cross-split duplication.",
            "Labels are not clinician-adjudicated ground truth and results are not clinical diagnostic performance.",
            "Experimental artifact is not integrated into the MediKiosk application.",
        ],
    }
    results_out.mkdir(parents=True, exist_ok=True)
    (results_out / "search_results.json").write_text(
        json.dumps({"trials": trials, "selected": best}, indent=2), encoding="utf-8"
    )
    (results_out / "evaluation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    split_manifest = [
        {"text_group_sha256": item["text_group_sha256"], "split": item["split"]}
        for item in group_manifest
    ]
    (results_out / "split_manifest.json").write_text(
        json.dumps(split_manifest, indent=2), encoding="utf-8"
    )
    card = """# TF-IDF symptom text classifier (experimental)

This model maps a short symptom-description text to a label in the bundled Symptom2Disease-derived dataset. It is a non-clinical benchmark only, not a diagnostic tool or clinical decision-support model.

The upstream Kaggle license/terms are unresolved. Keep this checkpoint and its results local until terms are reviewed. Data splits are dataset-provided; normalized full-text SHA-256 groups were checked for cross-split exact duplicate leakage. No patient/source group identifiers exist in this dataset.

See `evaluation_results/clinical_text_classification/evaluation.json` for search, held-out metrics, class-level scores, data fingerprint, and limitations. This checkpoint is not loaded by the application.
"""
    (model_out / "MODEL_CARD.md").write_text(card, encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--model-out", type=Path, default=MODEL_OUT)
    parser.add_argument("--results-out", type=Path, default=RESULTS_OUT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    report = run_experiment(args.data, args.model_out, args.results_out, args.seed)
    print(json.dumps({
        "checkpoint": report["model_checkpoint"],
        "split_rows": report["splits"],
        "selected": report["search"]["selected"],
        "test_accuracy": report["test_metrics"]["accuracy"],
        "test_macro_f1": report["test_metrics"]["macro_f1"],
        "test_weighted_f1": report["test_metrics"]["weighted_f1"],
        "runtime": report["runtime"],
    }, indent=2))


if __name__ == "__main__":
    main()
