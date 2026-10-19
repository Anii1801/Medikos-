"""Central access to the versioned MediKiosk datasets.

All optional dataset-backed features use this module so local runs, Docker
runs, and tests resolve the same project data directory.
"""
from __future__ import annotations

import csv
import logging
import os
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

DATASET_ROOT = Path(
    os.environ.get(
        "MEDIKIOSK_DATASETS",
        Path(__file__).resolve().parents[2] / "Datasets" / "MediKiosk_Datasets",
    )
)

FILES = {
    "patient_master": DATASET_ROOT / "00_patient_master" / "patient_master.csv",
    "patient_timeline": DATASET_ROOT / "00_patient_master" / "patient_timeline.csv",
    "symptom_text": DATASET_ROOT / "05_triage_redflag" / "symptom2disease_text.csv",
    "red_flag_cases": DATASET_ROOT / "05_triage_redflag" / "red_flag_labeled_cases.csv",
    "drug_interactions": DATASET_ROOT / "07_drug_safety" / "drug_interaction_reference.csv",
}


@lru_cache(maxsize=None)
def read_csv(name: str) -> tuple[dict[str, str], ...]:
    """Read a small, named dataset and return immutable cached rows."""
    path = FILES.get(name)
    if path is None:
        raise KeyError(f"Unknown dataset: {name}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return tuple(csv.DictReader(handle))
    except OSError as exc:
        log.warning("Dataset %s is unavailable at %s: %s", name, path, exc)
        return ()


def status() -> dict[str, object]:
    """Return dataset availability for diagnostics and the UI."""
    return {
        "root": str(DATASET_ROOT),
        "datasets": {
            name: {"path": str(path), "available": path.is_file()}
            for name, path in FILES.items()
        },
    }
