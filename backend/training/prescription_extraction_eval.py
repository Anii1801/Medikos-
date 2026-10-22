"""Evaluate prescription parsing on existing, source-linked synthetic text pairs.

Run from ``backend``:
    PYTHONPATH=. ../.venv/bin/python -m training.prescription_extraction_eval

This is text extraction evaluation, not OCR or end-to-end report evaluation.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app import ocr
from app.datasets import DATASET_ROOT

DATA_DIR = DATASET_ROOT / "02_ocr_handwriting"
OUT = Path(__file__).resolve().parents[2] / "evaluation_results" / "prescription_extraction"
SPLITS = ("train", "valid", "test")
DOSE_RE = re.compile(
    r"(\d+(?:\.\d+)?\s*(?:mg|mcg|μg|µg|ug|g|ml|tab(?:lets?)?|cap(?:sules?)?|iu|units?))\s*$",
    re.IGNORECASE,
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _value_key(value: str | None) -> str:
    return re.sub(r"\s+", "", (value or "").casefold().replace("μ", "u").replace("µ", "u"))


def _dose_from_label(value: str) -> str | None:
    match = DOSE_RE.search(value.strip())
    return match.group(1) if match else None


def _source_name_key(value: str) -> str:
    name = DOSE_RE.sub("", value.strip()).strip()
    return _name_key(name)


def evaluate(text_field: str, splits: tuple[str, ...] = SPLITS) -> dict[str, Any]:
    labels = _read_csv(DATA_DIR / "prescription_entities.csv")
    docs = {
        row["doc_id"]: row for row in _read_csv(DATA_DIR / "synthetic_documents_ocr_pairs.csv")
        if row["doc_type"] == "Prescription"
    }
    by_doc: dict[str, list[dict[str, str]]] = defaultdict(list)
    for label in labels:
        by_doc[label["rx_id"]].append(label)

    missing_ids = set(by_doc) - set(docs)
    if missing_ids:
        raise ValueError(f"{len(missing_ids)} prescription labels have no source text document")
    mismatches = [
        label for label in labels
        if label["patient_id"] != docs[label["rx_id"]]["patient_id"]
        or label["split"] != docs[label["rx_id"]]["split"]
    ]
    if mismatches:
        raise ValueError(f"{len(mismatches)} prescription labels disagree with source patient/split")
    patient_splits: dict[str, set[str]] = defaultdict(set)
    for doc in docs.values():
        patient_splits[doc["patient_id"]].add(doc["split"])
    overlaps = [patient_id for patient_id, doc_splits in patient_splits.items() if len(doc_splits) > 1]
    if overlaps:
        raise ValueError(f"{len(overlaps)} prescription patients appear in multiple splits")
    if text_field not in ("ground_truth_text", "simulated_ocr_text"):
        raise ValueError(f"Unsupported source text field: {text_field}")

    metrics: dict[str, Counter[str]] = {split: Counter() for split in splits}
    missed_source_names: dict[str, Counter[str]] = {split: Counter() for split in splits}
    for doc_id, source_labels in sorted(by_doc.items()):
        doc = docs[doc_id]
        split = doc["split"]
        if split not in metrics:
            continue
        extracted = ocr.extract(doc[text_field])["medications"]
        generic_available = set(range(len(extracted)))
        source_name_available = set(range(len(extracted)))
        counts = metrics[split]
        counts["documents"] += 1
        counts["gold_entities"] += len(source_labels)
        counts["predicted_entities"] += len(extracted)
        for label in source_labels:
            key = _name_key(label["generic_key"])
            match_index = next(
                (index for index in sorted(generic_available)
                 if _name_key(extracted[index].get("name", "")) == key),
                None,
            )
            if match_index is not None:
                generic_available.remove(match_index)
                found = extracted[match_index]
                counts["exact_generic_key_matches"] += 1
                expected_dose = _dose_from_label(label["drug"])
                if expected_dose:
                    counts["dose_comparable"] += 1
                    counts["dose_exact"] += _value_key(found.get("dose")) == _value_key(expected_dose)
                if label["dose_schedule"]:
                    counts["schedule_comparable"] += 1
                    counts["schedule_exact"] += (
                        _value_key(found.get("frequency")) == _value_key(label["dose_schedule"])
                    )

            source_key = _source_name_key(label["drug"])
            source_match = next(
                (index for index in sorted(source_name_available)
                 if _name_key(extracted[index].get("source_name") or extracted[index].get("name", ""))
                 == source_key),
                None,
            )
            if source_match is None:
                missed_source_names[split][label["drug"]] += 1
            else:
                source_name_available.remove(source_match)
                counts["exact_source_name_matches"] += 1
        counts["unmatched_predictions"] += len(generic_available)

    results: dict[str, Any] = {}
    for split, counts in metrics.items():
        tp = counts["exact_generic_key_matches"]
        pred = counts["predicted_entities"]
        gold = counts["gold_entities"]
        results[split] = {
            **dict(counts),
            "generic_key_precision": round(tp / pred, 4) if pred else None,
            "generic_key_recall": round(tp / gold, 4) if gold else None,
            "generic_key_f1": (
                round(2 * tp / (pred + gold), 4) if pred + gold else None
            ),
            "source_name_true_positives": counts["exact_source_name_matches"],
            "source_name_precision": (
                round(counts["exact_source_name_matches"] / pred, 4) if pred else None
            ),
            "source_name_recall": (
                round(counts["exact_source_name_matches"] / gold, 4) if gold else None
            ),
            "source_name_f1": (
                round(2 * counts["exact_source_name_matches"] / (pred + gold), 4)
                if pred + gold else None
            ),
            "exact_dose_accuracy_on_name_matches": (
                round(counts["dose_exact"] / counts["dose_comparable"], 4)
                if counts["dose_comparable"] else None
            ),
            "exact_schedule_accuracy_on_name_matches": (
                round(counts["schedule_exact"] / counts["schedule_comparable"], 4)
                if counts["schedule_comparable"] else None
            ),
        }
    return {
        "text_field": text_field,
        "split_method": "existing patient-grouped train/valid/test assignments; unchanged",
        "split_integrity": {
            "patients_per_split": {
                split: len({doc["patient_id"] for doc in docs.values() if doc["split"] == split})
                for split in SPLITS
            },
            "cross_split_patient_ids": len(overlaps),
        },
        "normalization": {
            "name": "case-fold and remove non-alphanumeric characters; exact generic_key match",
            "source_name": (
                "case-fold and remove non-alphanumeric characters after stripping a terminal "
                "dose/unit from the labeled drug field; exact source-formulation name match"
            ),
            "dose": "case-fold, remove whitespace, normalize Greek mu to u",
            "schedule": "case-fold, remove whitespace; otherwise exact",
        },
        "source_name_misses": {
            split: dict(sorted(missed_source_names[split].items()))
            for split in splits
        },
        "limitations": [
            "Synthetic text pairs; no source images, so this is not OCR evaluation.",
            "No token spans are supplied; exact generic-key matching is a strict name proxy.",
            "Dose accuracy excludes unmatched names and labels without a terminal strength/unit pattern.",
            "Duration, route, and report-generation fidelity are not scored by this evaluator.",
            "The extractor has been developed on this corpus; results are descriptive regression results, not a blinded estimate.",
        ],
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT / "prescription_extraction_current.json")
    args = parser.parse_args()
    report = {
        field: evaluate(field)
        for field in ("ground_truth_text", "simulated_ocr_text")
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({field: result["results"] for field, result in report.items()}, indent=2))


if __name__ == "__main__":
    main()
