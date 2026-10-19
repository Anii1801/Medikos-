from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class DatasetError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    task: str
    source_url: str
    licence_status: str
    availability: str
    local_path: str | None
    format: str
    schema: dict[str, str]
    group_key: str | None
    label_schema: str
    notes: str


def load_manifest(path: Path) -> list[DatasetSpec]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [DatasetSpec(**item) for item in data["datasets"]]


def _path(root: Path, spec: DatasetSpec) -> Path:
    if not spec.local_path:
        raise DatasetError(f"{spec.dataset_id}: no local path; access steps are documented in the manifest")
    return root / spec.local_path


def load_rows(root: Path, spec: DatasetSpec) -> list[dict[str, Any]]:
    path = _path(root, spec)
    if not path.exists():
        raise DatasetError(f"{spec.dataset_id}: expected file is unavailable at {path}")
    if spec.format == "csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    if spec.format == "jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    raise DatasetError(f"{spec.dataset_id}: unsupported format {spec.format}")


def validate_rows(spec: DatasetSpec, rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    missing = []
    for index, row in enumerate(rows):
        for field in spec.schema:
            if field not in row:
                missing.append({"row": index, "field": field})
    groups = [str(row[spec.group_key]) for row in rows if spec.group_key and row.get(spec.group_key) not in (None, "")]
    return {
        "dataset_id": spec.dataset_id,
        "rows": len(rows),
        "missing_fields": missing[:50],
        "missing_field_count": len(missing),
        "group_count": len(set(groups)),
        "valid": not missing,
    }


def _normalise(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def duplicate_fingerprints(rows: Iterable[dict[str, Any]], fields: Iterable[str]) -> dict[str, list[int]]:
    seen: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        text = "\x1f".join(_normalise(row.get(field)) for field in fields)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        seen.setdefault(digest, []).append(index)
    return {digest: indexes for digest, indexes in seen.items() if len(indexes) > 1}


def split_by_group(
    rows: list[dict[str, Any]], group_key: str, seed: int = 42, ratios: tuple[float, float, float] = (0.8, 0.1, 0.1)
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get(group_key) or "")
        if not key:
            raise DatasetError(f"Cannot split without non-empty group key {group_key}")
        groups.setdefault(key, []).append(row)
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    n = len(keys)
    first = int(n * ratios[0])
    second = first + int(n * ratios[1])
    return {
        "train": [row for key in keys[:first] for row in groups[key]],
        "validation": [row for key in keys[first:second] for row in groups[key]],
        "test": [row for key in keys[second:] for row in groups[key]],
    }


def assert_no_leakage(splits: dict[str, list[dict[str, Any]]], group_key: str, fingerprint_fields: list[str]) -> None:
    group_sets = {name: {str(row.get(group_key)) for row in rows} for name, rows in splits.items()}
    names = list(group_sets)
    for left_index, left in enumerate(names):
        for right in names[left_index + 1:]:
            overlap = group_sets[left] & group_sets[right] - {""}
            if overlap:
                raise DatasetError(f"group leakage between {left} and {right}: {sorted(overlap)[:5]}")
    fingerprints: dict[str, str] = {}
    for name, rows in splits.items():
        for row in rows:
            text = "\x1f".join(_normalise(row.get(field)) for field in fingerprint_fields)
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if digest in fingerprints and fingerprints[digest] != name:
                raise DatasetError(f"duplicate leakage between {fingerprints[digest]} and {name}")
            fingerprints[digest] = name
