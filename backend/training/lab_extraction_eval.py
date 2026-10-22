"""Field-level benchmark of the laboratory-report extractor against labelled ground truth.

    cd backend && PYTHONPATH=. python -m training.lab_extraction_eval [--label NAME]

Ground truth: 02_ocr_handwriting/lab_result_entities.csv, joined (report_id == doc_id) to the source text in
synthetic_documents_ocr_pairs.csv. Both the clean ground-truth text and the simulated-OCR text are evaluated.
These are SYNTHETIC, uniformly formatted reports: the numbers measure parsing of this layout, not real-world
scan robustness (see the rendered-image test for OCR-in-the-loop on known text).
Fields scored separately: test name, value, unit, printed reference interval, abnormal status vs the printed flag.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from app import ocr
from app.datasets import DATASET_ROOT

DIR = DATASET_ROOT / "02_ocr_handwriting"
OUT = Path(__file__).resolve().parents[2] / "evaluation_results" / "lab_extraction"
ALIASES = {"haemoglobin": "hemoglobin", "fastingglucose": "fastingbloodsugar", "postprandialglucose": "postprandialbloodsugar"}


def canon(name: str) -> str:
    k = re.sub(r"[^a-z0-9]", "", name.lower())
    return ALIASES.get(k, k)


def norm_unit(u: str) -> str:
    return re.sub(r"\s+", "", (u or "").replace("µ", "u").replace("μ", "u")).lower().replace("^", "")


def load() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    with (DIR / "lab_result_entities.csv").open(encoding="utf-8-sig", newline="") as fh:
        labels = defaultdict(list)
        for r in csv.DictReader(fh):
            labels[r["report_id"]].append(r)
    with (DIR / "synthetic_documents_ocr_pairs.csv").open(encoding="utf-8-sig", newline="") as fh:
        docs = {r["doc_id"]: r for r in csv.DictReader(fh) if r["doc_type"] == "Lab report"}
    missing = set(labels) - set(docs)
    if missing:
        raise ValueError(f"{len(missing)} labelled reports have no source document")
    patient_splits: dict[str, set[str]] = defaultdict(set)
    for rid, group in labels.items():
        doc = docs[rid]
        if any(row["patient_id"] != doc["patient_id"] or row["split"] != doc["split"] for row in group):
            raise ValueError(f"patient/split mismatch for report {rid}")
        patient_splits[doc["patient_id"]].add(doc["split"])
    overlaps = [patient_id for patient_id, splits in patient_splits.items() if len(splits) > 1]
    if overlaps:
        raise ValueError(f"{len(overlaps)} lab patients appear in multiple splits")
    return labels, docs


def _ref_of(item: dict) -> tuple[float, float] | None:
    if item.get("ref_low") is not None and item.get("ref_high") is not None and item.get("reference_source") == "document":
        return float(item["ref_low"]), float(item["ref_high"])
    if item.get("reference_source") == "document":
        m = re.match(r"([\d.]+)[–-]([\d.]+)", item.get("ref", ""))
        return (float(m.group(1)), float(m.group(2))) if m else None
    return None


def _status_of(item: dict) -> str:
    f = item.get("flag")
    return {"normal": "N", "high": "H", "critical": "H", "low": "L"}.get(f, "?")


def evaluate(field: str, extractor: Callable[[str], dict], splits=("train", "valid", "test"),
             text_override: dict[str, str] | None = None) -> dict[str, Any]:
    labels, docs = load()
    tp = fp = fn = 0
    value_ok = unit_ok = ref_ok = flag_ok = n_matched = 0
    printed_flag_ok = 0
    wrong_abnormal_when_printed_normal = missed_abnormal = n_abnormal = n_normal = 0
    ambiguous = 0
    per_test: dict[str, Counter] = defaultdict(Counter)
    errors: list[dict[str, Any]] = []
    reports = 0
    for rid, gold in sorted(labels.items()):
        if gold[0]["split"] not in splits or (text_override is not None and rid not in text_override):
            continue
        reports += 1
        got = extractor(text_override[rid] if text_override is not None else docs[rid][field])
        by_test = defaultdict(list)
        for item in got["labs"]:
            by_test[canon(item["test"])].append(item)
        gold_keys = set()
        for g in gold:
            k = canon(g["test"]); gold_keys.add(k)
            cand = by_test.get(k, [])
            if not cand:
                fn += 1; per_test[g["test"]]["missed"] += 1
                errors.append({"report": rid, "test": g["test"], "error": "test not extracted"})
                continue
            tp += 1; n_matched += 1
            it = cand[0]
            per_test[g["test"]]["found"] += 1
            v_ok = abs(float(it["value"]) - float(g["value"])) < 1e-6
            u_ok = norm_unit(it["unit"]) == norm_unit(g["unit"])
            ref = _ref_of(it)
            r_ok = ref is not None and abs(ref[0] - float(g["ref_low"])) < 1e-6 and abs(ref[1] - float(g["ref_high"])) < 1e-6
            printed = it.get("printed_flag")
            value_ok += v_ok; unit_ok += u_ok; ref_ok += r_ok
            printed_flag_ok += printed == g["flag"]
            ours = _status_of(it)
            f_ok = ours == g["flag"]
            flag_ok += f_ok
            if g["flag"] == "N":
                n_normal += 1; wrong_abnormal_when_printed_normal += ours in ("H", "L")
            else:
                n_abnormal += 1; missed_abnormal += ours in ("N",)
            ambiguous += it.get("interpretation") == "unable_to_interpret" or bool(it.get("ambiguity"))
            for ok, what in ((v_ok, "value"), (u_ok, "unit"), (r_ok, "reference interval"), (f_ok, "abnormal status")):
                if not ok:
                    per_test[g["test"]][f"wrong_{what}"] += 1
                    if len(errors) < 400:
                        errors.append({"report": rid, "test": g["test"], "error": f"{what} wrong", "gold": {"value": g["value"], "unit": g["unit"],
                                       "ref": [g["ref_low"], g["ref_high"]], "flag": g["flag"]},
                                       "got": {"value": it["value"], "unit": it["unit"], "ref": it.get("ref"), "flag": it.get("flag"),
                                               "printed_flag": printed, "reference_source": it.get("reference_source")}})
        for k, items in by_test.items():
            if k not in gold_keys:
                fp += len(items); errors.append({"report": rid, "test": items[0]["test"], "error": "extra test (not in labels)"})
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    def ratio(a, b): return round(a / b, 4) if b else None
    return {
        "text_field": field, "reports": reports, "labelled_results": tp + fn, "matched": n_matched,
        "test_name_precision": round(pr, 4), "test_name_recall": round(rc, 4),
        "test_name_f1": round(2 * pr * rc / (pr + rc), 4) if pr + rc else 0.0, "false_positive_extractions": fp,
        "exact_value_accuracy": ratio(value_ok, n_matched), "unit_accuracy": ratio(unit_ok, n_matched),
        "printed_reference_interval_accuracy": ratio(ref_ok, n_matched),
        "printed_flag_capture_accuracy": ratio(printed_flag_ok, n_matched),
        "abnormal_status_accuracy_vs_printed_flag": ratio(flag_ok, n_matched),
        "abnormal_recall": ratio(n_abnormal - missed_abnormal, n_abnormal) if n_abnormal else None,
        "false_abnormal_rate_on_printed_normal": ratio(wrong_abnormal_when_printed_normal, n_normal),
        "ambiguous_extraction_rate": ratio(ambiguous, n_matched),
        "counts": {
            "test_name": {"true_positive": tp, "false_positive": fp, "false_negative": fn,
                          "predicted": tp + fp, "labelled": tp + fn},
            "exact_value": {"correct": value_ok, "denominator": n_matched},
            "unit": {"correct": unit_ok, "denominator": n_matched},
            "printed_reference_interval": {"correct": ref_ok, "denominator": n_matched},
            "printed_flag_capture": {"correct": printed_flag_ok, "denominator": n_matched},
            "abnormal_status_vs_printed_flag": {"correct": flag_ok, "denominator": n_matched},
            "abnormal_recall": {"correct": n_abnormal - missed_abnormal, "denominator": n_abnormal},
            "false_abnormal_on_printed_normal": {
                "false_abnormal": wrong_abnormal_when_printed_normal, "denominator": n_normal,
            },
            "ambiguous_extraction": {"count": ambiguous, "denominator": n_matched},
        },
        "critical_result_recall": None,
        "critical_result_note": "the labels contain only N/H/L; there are no 'critical' labels, so critical-result recall cannot be computed",
        "per_test": {k: dict(v) for k, v in sorted(per_test.items())},
        "error_examples": errors[:60],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="current")
    ap.add_argument("--splits", default="train,valid,test")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    res = {f: evaluate(f, ocr.extract, tuple(a.splits.split(","))) for f in ("ground_truth_text", "simulated_ocr_text")}
    (OUT / f"lab_extraction_{a.label}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    for f, r in res.items():
        print(f, {k: v for k, v in r.items() if k not in ("per_test", "error_examples", "critical_result_note")})


if __name__ == "__main__":
    main()
