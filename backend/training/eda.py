"""Generate privacy-safe aggregate EDA reports and plots for bundled datasets.

Run from ``backend`` with ``PYTHONPATH=. python -m training.eda``.
No record-level examples or patient identifiers are written to outputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from app.datasets import DATASET_ROOT

REPO_ROOT = Path(__file__).resolve().parents[2]
TEXT_COLUMN_NAMES = {
    "text", "dialogue", "note", "summary", "transcription", "input_dialogue",
    "ground_truth_text", "simulated_ocr_text", "reference_text", "simulated_asr_text",
    "description", "chief_complaint", "symptoms", "input_text",
}
CATEGORY_COLUMNS = {
    "split", "role", "slot", "red_flag", "triage_priority", "language",
    "doc_type", "label", "specialty", "flag", "source_type", "handwritten",
}
SOURCE_TEXT_COLUMNS = {
    "source_text", "original_text", "document_text", "raw_text", "input_text",
    "ground_truth_text",
}
START_COLUMNS = {"start", "start_char", "char_start", "begin"}
END_COLUMNS = {"end", "end_char", "char_end", "finish"}
REQUIRED_FIELDS = {
    "00_patient_master/patient_master.csv": {"patient_id", "split"},
    "00_patient_master/patient_timeline.csv": {"patient_id", "event_date", "event_type", "split"},
    "01_history_interview/interview_turns.csv": {
        "interview_id", "patient_id", "split", "role", "text", "slot",
    },
    "01_history_interview/structured_histories.csv": {
        "interview_id", "patient_id", "split", "chief_complaint",
    },
    "02_ocr_handwriting/lab_result_entities.csv": {
        "report_id", "patient_id", "split", "test", "value",
    },
    "02_ocr_handwriting/prescription_entities.csv": {
        "rx_id", "patient_id", "split", "drug", "dose_schedule",
    },
    "02_ocr_handwriting/synthetic_documents_ocr_pairs.csv": {
        "doc_id", "patient_id", "split", "ground_truth_text", "simulated_ocr_text",
    },
    "03_patient_summary/history_to_summary_synthetic.csv": {
        "interview_id", "patient_id", "input_dialogue", "summary_en",
    },
    "03_patient_summary/aci_bench_dialogue_note_pairs.csv": {
        "encounter_id", "dialogue", "note", "split",
    },
    "04_asr_voice/asr_noisy_test_set.csv": {
        "interview_id", "patient_id", "reference_text", "simulated_asr_text",
    },
    "05_triage_redflag/symptom2disease_text.csv": {"label", "text", "split"},
}


def _load_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if path.suffix.lower() == ".jsonl":
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        columns = sorted({str(key) for row in rows for key in row})
        return rows, columns
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), reader.fieldnames or []


def _missing(value: Any) -> bool:
    return value is None or not str(value).strip()


def _percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)]


def _profile(
    path: Path, relative_path: str
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, list[int]]]:
    rows, columns = _load_rows(path)
    missing_counts = {
        column: sum(_missing(row.get(column)) for row in rows)
        for column in columns
    }
    signatures = Counter(
        hashlib.sha256(
            json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        for row in rows
    )
    duplicates = sum(count - 1 for count in signatures.values() if count > 1)

    text_stats = []
    length_distributions = {}
    for column in columns:
        if column.lower() not in TEXT_COLUMN_NAMES:
            continue
        values = [str(row.get(column) or "") for row in rows if not _missing(row.get(column))]
        lengths = [len(value) for value in values]
        word_counts = [len(value.split()) for value in values]
        if values:
            length_distributions[column] = lengths
            text_stats.append({
                "column": column,
                "nonempty": len(values),
                "mean_characters": round(sum(lengths) / len(lengths), 2),
                "median_characters": _percentile(lengths, 0.5),
                "p95_characters": _percentile(lengths, 0.95),
                "max_characters": max(lengths),
                "mean_words": round(sum(word_counts) / len(word_counts), 2),
            })

    category_counts = {}
    for column in columns:
        if column.lower() not in CATEGORY_COLUMNS:
            continue
        counts = Counter(str(row.get(column) or "[missing]") for row in rows)
        if len(counts) <= 100:
            category_counts[column] = dict(sorted(counts.items()))

    normalized_columns = {column.lower() for column in columns}
    has_source_text = bool(normalized_columns & SOURCE_TEXT_COLUMNS)
    has_offsets = bool(normalized_columns & START_COLUMNS) and bool(normalized_columns & END_COLUMNS)
    has_text_label_pair = {"text", "label"}.issubset(normalized_columns)
    if has_text_label_pair:
        complete_text_label_rows = sum(
            not _missing(row.get("text")) and not _missing(row.get("label"))
            for row in rows
        )
    else:
        complete_text_label_rows = 0
    if has_source_text and has_offsets:
        source_column = next(
            column for column in columns if column.lower() in SOURCE_TEXT_COLUMNS
        )
        start_column = next(column for column in columns if column.lower() in START_COLUMNS)
        end_column = next(column for column in columns if column.lower() in END_COLUMNS)
        span_rows = sum(
            not _missing(row.get(source_column))
            and str(row.get(start_column, "")).strip().isdigit()
            and str(row.get(end_column, "")).strip().isdigit()
            and int(row[start_column]) < int(row[end_column])
            and int(row[end_column]) <= len(str(row[source_column]))
            for row in rows
        )
    else:
        span_rows = 0
    required = REQUIRED_FIELDS.get(relative_path)
    invalid_records = (
        sum(any(_missing(row.get(field)) for field in required) for row in rows)
        if required
        else None
    )
    profile = {
        "rows": len(rows),
        "columns": len(columns),
        "column_names": columns,
        "missing_cells": sum(missing_counts.values()),
        "missing_cell_share": round(
            sum(missing_counts.values()) / max(1, len(rows) * len(columns)), 6
        ),
        "missing_by_column": missing_counts,
        "exact_duplicate_rows": duplicates,
        "category_counts": category_counts,
        "text_lengths": text_stats,
        "has_source_text": has_source_text,
        "has_character_offsets": has_offsets,
        "annotation_coverage": {
            "has_text_label_pair": has_text_label_pair,
            "complete_text_label_rows": complete_text_label_rows,
            "complete_text_label_share": round(
                complete_text_label_rows / max(1, len(rows)), 6
            ) if has_text_label_pair else None,
            "source_text_and_character_span_rows": span_rows,
            "character_span_coverage": round(span_rows / max(1, len(rows)), 6),
        },
        "required_schema_fields": sorted(required) if required else None,
        "invalid_required_records": invalid_records,
    }
    summaries = [
        {"file": relative_path, "column": item["column"], **item}
        for item in text_stats
    ]
    return profile, summaries, length_distributions


def _write_plots(
    profiles: dict[str, dict[str, Any]],
    output: Path,
    text_length_distributions: dict[str, list[int]],
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "EDA plots require matplotlib; install the declared training dependencies."
        ) from exc

    output.mkdir(parents=True, exist_ok=True)
    files = [name for name in profiles if not name.startswith("_")]
    row_counts = [profiles[name]["rows"] for name in files]
    fig, ax = plt.subplots(figsize=(12, max(5, len(files) * 0.28)))
    ax.barh(files, row_counts, color="#3572A5")
    ax.set_xlabel("Records")
    ax.set_title("Dataset composition (rows per file)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(output / "dataset_composition.png", dpi=150)
    plt.close(fig)

    missing = [
        (name, profile["missing_cell_share"])
        for name, profile in profiles.items()
        if not name.startswith("_")
    ]
    missing.sort(key=lambda item: item[1], reverse=True)
    fig, ax = plt.subplots(figsize=(10, max(4, len(missing) * 0.28)))
    ax.barh([name for name, _ in missing], [share * 100 for _, share in missing], color="#D9863B")
    ax.set_xlabel("Missing cells (%)")
    ax.set_title("Missingness by dataset file")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(output / "missingness.png", dpi=150)
    plt.close(fig)

    text_items = [
        (f"{name}:{item['column']}", item["median_characters"])
        for name, profile in profiles.items()
        if not name.startswith("_")
        for item in profile["text_lengths"]
    ]
    if text_items:
        fig, ax = plt.subplots(figsize=(11, max(4, len(text_items) * 0.35)))
        ax.barh(
            [name for name, _ in text_items],
            [length for _, length in text_items],
            color="#4B8B68",
        )
        ax.set_xlabel("Median characters")
        ax.set_title("Text-length distributions (median per text field)")
        ax.invert_yaxis()
        fig.tight_layout()
        fig.savefig(output / "text_lengths.png", dpi=150)
        plt.close(fig)

    text_fields = [
        (name, column, lengths)
        for name, fields in text_length_distributions.items()
        for column, lengths in fields.items()
        if lengths
    ]
    if text_fields:
        columns = 3
        rows = math.ceil(len(text_fields) / columns)
        fig, axes = plt.subplots(
            rows, columns, figsize=(15, max(4, rows * 2.8)), squeeze=False
        )
        for ax, (name, column, lengths) in zip(axes.flat, text_fields):
            ax.hist(lengths, bins=20, color="#4B8B68", edgecolor="white")
            ax.set_title(f"{Path(name).name}: {column}", fontsize=8)
            ax.set_xlabel("Characters")
            ax.set_ylabel("Records")
        for ax in axes.flat[len(text_fields):]:
            ax.set_visible(False)
        fig.suptitle("Text-length distributions by dataset field", y=1.0)
        fig.tight_layout()
        fig.savefig(output / "text_length_distributions.png", dpi=150)
        plt.close(fig)

    class_entries = [
        (name, column, label, count)
        for name, profile in profiles.items()
        if not name.startswith("_")
        for column, counts in profile["category_counts"].items()
        if column.lower() in {"label", "red_flag", "triage_priority", "slot"}
        for label, count in counts.items()
    ]
    if class_entries:
        labels = [
            f"{Path(name).name}:{column}={label}"
            for name, column, label, _ in class_entries
        ]
        fig, ax = plt.subplots(figsize=(12, max(5, len(labels) * 0.27)))
        ax.barh(labels, [count for _, _, _, count in class_entries], color="#875A9E")
        ax.set_xlabel("Records")
        ax.set_title("Selected class / annotation frequencies")
        ax.invert_yaxis()
        fig.tight_layout()
        fig.savefig(output / "class_frequencies.png", dpi=150)
        plt.close(fig)


def run_eda(data_root: Path = DATASET_ROOT, output: Path | None = None) -> dict[str, Any]:
    output = output or REPO_ROOT / "evaluation_results" / "eda"
    csv_field_limit = csv.field_size_limit()
    csv.field_size_limit(2**31 - 1)
    profiles: dict[str, dict[str, Any]] = {}
    text_length_distributions: dict[str, dict[str, list[int]]] = {}
    try:
        for path in sorted(data_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".csv", ".jsonl"}:
                continue
            if "fhir_bundles" in path.parts:
                continue
            relative = path.relative_to(data_root).as_posix()
            profiles[relative], _, text_length_distributions[relative] = _profile(path, relative)
    finally:
        csv.field_size_limit(csv_field_limit)

    image_count = sum(
        path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".pdf"}
        for path in data_root.rglob("*")
        if path.is_file()
    )
    audio_count = sum(
        path.suffix.lower() in {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
        for path in data_root.rglob("*")
        if path.is_file()
    )
    profiles["_assets"] = {"images_and_pdfs_on_disk": image_count, "audio_on_disk": audio_count}
    profiles["_summary"] = {
        "files_profiled": len(profiles) - 1,
        "total_rows": sum(item["rows"] for item in profiles.values() if "rows" in item),
        "patient_examples_written": False,
        "invalid_required_records_by_dataset": {
            name: profile["invalid_required_records"]
            for name, profile in profiles.items()
            if profile.get("invalid_required_records") is not None
        },
        "source_span_supervision": {
            name: bool(profile["has_source_text"] and profile["has_character_offsets"])
            for name, profile in profiles.items()
            if name in {
                "02_ocr_handwriting/lab_result_entities.csv",
                "02_ocr_handwriting/prescription_entities.csv",
            }
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "dataset_eda.json").write_text(
        json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _write_plots(profiles, output, text_length_distributions)
    return profiles


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DATASET_ROOT)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "evaluation_results" / "eda")
    args = parser.parse_args()
    profiles = run_eda(args.data_root, args.output)
    print(json.dumps(profiles["_summary"], indent=2))
    print(f"Aggregate-only EDA artifacts written to {args.output}")


if __name__ == "__main__":
    main()
