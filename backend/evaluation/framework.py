"""Common evaluation primitives and experiment registry.

The framework deliberately separates measured software results from clinical
validation. Every comparison consumes paired, held-out rows when available;
missing data produces a pending result rather than a fabricated score.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def paired_bootstrap(values: list[float], seed: int = 42, samples: int = 2000) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "estimate": None, "ci95_low": None, "ci95_high": None}
    rng = random.Random(seed)
    estimates = []
    for _ in range(samples):
        draw = [values[rng.randrange(len(values))] for _ in values]
        estimates.append(sum(draw) / len(draw))
    estimates.sort()
    return {"n": len(values), "estimate": sum(values) / len(values),
            "ci95_low": estimates[int(samples * 0.025)],
            "ci95_high": estimates[int(samples * 0.975) - 1]}


def paired_permutation_pvalue(differences: list[float], seed: int = 42, samples: int = 10000) -> float | None:
    if not differences:
        return None
    observed = abs(sum(differences) / len(differences))
    rng = random.Random(seed)
    exceed = 0
    for _ in range(samples):
        signed = [value if rng.getrandbits(1) else -value for value in differences]
        if abs(sum(signed) / len(signed)) >= observed:
            exceed += 1
    return (exceed + 1) / (samples + 1)


def paired_comparison(baseline: list[float], proposed: list[float], seed: int = 42) -> dict[str, Any]:
    if len(baseline) != len(proposed):
        raise ValueError("paired comparison requires equal-length baseline and proposed vectors")
    differences = [b - a for a, b in zip(baseline, proposed)]
    return {"n": len(differences), "baseline": paired_bootstrap(baseline, seed),
            "proposed": paired_bootstrap(proposed, seed),
            "difference_proposed_minus_baseline": paired_bootstrap(differences, seed),
            "paired_permutation_p": paired_permutation_pvalue(differences, seed)}


def binary_metrics(actual: list[bool], predicted: list[bool]) -> dict[str, Any]:
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted vectors must have equal length")
    tp = sum(a and p for a, p in zip(actual, predicted))
    tn = sum(not a and not p for a, p in zip(actual, predicted))
    fp = sum(not a and p for a, p in zip(actual, predicted))
    fn = sum(a and not p for a, p in zip(actual, predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    return {"n": len(actual), "counts": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
            "sensitivity_recall": recall, "specificity": specificity, "precision": precision,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "false_negative_cases": fn, "false_positive_burden": fp}


def token_error(reference: str, hypothesis: str) -> int:
    left, right = (reference or "").lower().split(), (hypothesis or "").lower().split()
    previous = list(range(len(right) + 1))
    for i, token in enumerate(left, 1):
        current = [i]
        for j, expected in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (token != expected)))
        previous = current
    return previous[-1]


def wer(reference: str, hypothesis: str) -> float:
    ref = (reference or "").split()
    return token_error(reference, hypothesis) / max(1, len(ref))


def cer(reference: str, hypothesis: str) -> float:
    ref = list(reference or "")
    # Reuse the same edit distance without language-specific tokenization.
    previous = list(range(len(ref) + 1))
    for i, char in enumerate(hypothesis or "", 1):
        current = [i]
        for j, expected in enumerate(ref, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (char != expected)))
        previous = current
    return previous[-1] / max(1, len(ref))


def clinical_entity_prf(expected: Iterable[str], predicted: Iterable[str]) -> dict[str, float]:
    gold, found = set(expected), set(predicted)
    tp = len(gold & found)
    precision = tp / len(found) if found else 0.0
    recall = tp / len(gold) if gold else 0.0
    return {"precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}


def error_categories(reference: str, hypothesis: str, expected_entities: set[str] | None = None,
                     predicted_entities: set[str] | None = None) -> list[str]:
    categories = []
    ref, hyp = (reference or "").lower(), (hypothesis or "").lower()
    if bool(re.search(r"\b(no|not|never|denies|without)\b", ref)) != bool(re.search(r"\b(no|not|never|denies|without)\b", hyp)):
        categories.append("negation")
    if re.findall(r"\d+(?:\.\d+)?", ref) != re.findall(r"\d+(?:\.\d+)?", hyp):
        categories.append("number_or_duration")
    if expected_entities is not None and predicted_entities is not None:
        if expected_entities - predicted_entities:
            categories.append("omission")
        if predicted_entities - expected_entities:
            categories.append("spurious_entity")
    if ref and not hyp:
        categories.append("empty_output")
    if ref != hyp and not categories:
        categories.append("lexical_or_order")
    return categories


def error_analysis(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    examples: dict[str, dict[str, Any]] = {}
    row_count = 0
    error_ids: set[str] = set()
    for row in rows:
        row_count += 1
        categories = error_categories(row.get("reference", ""), row.get("hypothesis", ""),
                                      set(row.get("expected_entities", [])), set(row.get("predicted_entities", [])))
        for category in categories:
            error_ids.add(str(row.get("id", row_count)))
            counts[category] += 1
            examples.setdefault(category, {k: row.get(k) for k in ("id", "language", "reference", "hypothesis")})
    return {"rows": row_count, "rows_with_errors": len(error_ids),
            "counts": dict(counts), "examples": examples}


def safe_red_flag_comparison(rule_predictions: list[bool], model_predictions: list[bool],
                             actual: list[bool]) -> dict[str, Any]:
    if not (len(rule_predictions) == len(model_predictions) == len(actual)):
        raise ValueError("red-flag vectors must have equal length")
    # A model may add a warning, but may never remove a deterministic warning.
    effective = [rule or model for rule, model in zip(rule_predictions, model_predictions)]
    return {"rules": binary_metrics(actual, rule_predictions),
            "model_observed_only": binary_metrics(actual, model_predictions),
            "safety_preserving_combination": binary_metrics(actual, effective),
            "override_policy": "model cannot suppress a triggered deterministic rule"}


EXPERIMENTS = [
    {"id": "history_fixed_vs_adaptive", "baseline": "fixed-question order",
     "proposed": "HistoryTakingAgent adaptive policy", "metrics": ["history_completeness", "slot_coverage", "omissions", "duplicate_rate", "turns", "red_flag_recall", "inference_latency"]},
    {"id": "extraction_generic_vs_clinical", "baseline": "generic extraction",
     "proposed": "configured clinical NLP baseline", "metrics": ["precision", "recall", "f1", "negation_accuracy", "uncertainty_accuracy", "inference_latency"]},
    {"id": "summary_oneshot_vs_grounded", "baseline": "one-shot generation",
     "proposed": "extraction-first grounded generation", "metrics": ["omission_rate", "hallucination_rate", "factuality", "source_link_coverage", "ROUGE", "BERTScore", "inference_latency"]},
    {"id": "ocr_baseline_vs_document_pipeline", "baseline": "raw OCR",
     "proposed": "proposed document pipeline", "metrics": ["cer", "wer", "field_accuracy", "inference_latency"]},
    {"id": "finetune_vs_peft", "baseline": "full fine-tuning",
     "proposed": "LoRA/PEFT", "metrics": ["task_metric", "model_size", "trainable_parameters", "training_time", "peak_memory", "inference_latency"]},
    {"id": "manual_vs_ai_documentation", "baseline": "manual documentation",
     "proposed": "AI draft plus clinician review", "metrics": ["documentation_time", "correction_time", "omissions", "hallucination_rate"]},
    {"id": "english_vs_hindi_hinglish", "baseline": "English",
     "proposed": "Hindi/Hinglish separately", "metrics": ["WER", "entity_accuracy", "latency"]},
    {"id": "redflag_rules_vs_model", "baseline": "deterministic rules",
     "proposed": "trained model, if verified", "metrics": ["sensitivity", "false_negatives", "false_positive_burden"]},
]


def pending_experiment(spec: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"experiment_id": spec["id"], "status": "pending", "baseline": spec["baseline"],
            "proposed": spec["proposed"], "metrics": spec["metrics"], "reason": reason,
            "sample_size": 0, "confidence_intervals": "not applicable"}


def write_report(path: Path, results: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    payload = {"framework_version": "1.0", "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "metadata": metadata, "experiments": results}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
