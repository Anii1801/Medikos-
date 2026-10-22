import json
from pathlib import Path

import pytest

from training.manifest import DatasetError, assert_no_leakage, duplicate_fingerprints, split_by_group
from training.adaptive.data import load_interviews, split_interviews
from training.adaptive.evaluate import _ndcg_at_k, question_choice_comparison
from app.adaptive.ranker import LearnedSlotRanker


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


def test_single_relevant_target_ndcg_discount_and_cutoff():
    ranked = [("wrong-a", 0.5), ("target", 0.3), ("wrong-b", 0.2)]
    assert _ndcg_at_k(ranked, "target", 1) == 0
    assert _ndcg_at_k(ranked, "target", 3) == pytest.approx(1 / 1.5849625007)
    assert _ndcg_at_k(ranked, "missing", 3) == 0


def test_held_out_question_choice_comparison_includes_policy_views_and_oracle():
    splits = split_interviews(load_interviews())
    metrics = question_choice_comparison(LearnedSlotRanker.load(), splits["test"], splits["train"])
    policies = metrics["official_test"]
    assert set(policies) == {
        "ontology_rule_selection", "logistic_regression_recorded_wording",
        "logistic_regression_app_labels", "oracle_template_lookup",
    }
    assert all({"top1", "ndcg_at_1", "ndcg_at_3"} <= set(value) for value in policies.values())
    assert policies["oracle_template_lookup"]["top1"]["value"] == 1.0
    assert "not clinical benefit" in metrics["note"]
