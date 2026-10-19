import json
from pathlib import Path

import pytest

from training.manifest import DatasetError, assert_no_leakage, duplicate_fingerprints, split_by_group


def test_group_split_and_duplicate_guard():
    rows = [
        {"patient_id": "p1", "text": "one"},
        {"patient_id": "p2", "text": "two"},
        {"patient_id": "p3", "text": "three"},
        {"patient_id": "p4", "text": "four"},
        {"patient_id": "p5", "text": "five"},
    ]
    splits = split_by_group(rows, "patient_id", seed=7)
    assert sum(map(len, splits.values())) == len(rows)
    assert_no_leakage(splits, "patient_id", ["text"])
    assert not duplicate_fingerprints(rows, ["text"])


def test_duplicate_leakage_is_rejected():
    splits = {"train": [{"patient_id": "p1", "text": "same"}],
              "test": [{"patient_id": "p2", "text": "same"}]}
    with pytest.raises(DatasetError):
        assert_no_leakage(splits, "patient_id", ["text"])


def test_manifest_preserves_unavailable_resource_status():
    manifest = json.loads((Path(__file__).parents[1] / "training" / "configs" / "datasets.json").read_text())
    tabassum = next(item for item in manifest["datasets"] if item["dataset_id"] == "tabassum_handwritten_terms")
    assert tabassum["availability"] == "unavailable_pending_identification"
    assert tabassum["local_path"] is None
