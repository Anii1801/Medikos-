from evaluation.framework import error_analysis, paired_comparison, safe_red_flag_comparison


def test_paired_statistics_and_confidence_intervals_are_reproducible():
    result = paired_comparison([0.5, 0.6, 0.7], [0.6, 0.6, 0.8])
    assert result["n"] == 3
    assert result["difference_proposed_minus_baseline"]["ci95_low"] <= result["difference_proposed_minus_baseline"]["estimate"]
    assert result["paired_permutation_p"] is not None


def test_error_analysis_identifies_safety_relevant_categories():
    report = error_analysis([{"id": "x", "language": "hi", "reference": "no fever for 2 days",
                              "hypothesis": "fever for 3 days", "expected_entities": {"fever"},
                              "predicted_entities": set()}])
    assert "negation" in report["counts"]
    assert "number_or_duration" in report["counts"]
    assert "omission" in report["counts"]


def test_red_flag_model_cannot_remove_rule_warning():
    result = safe_red_flag_comparison([True, False], [False, False], [True, False])
    assert result["safety_preserving_combination"]["counts"]["fn"] == 0
    assert result["override_policy"].startswith("model cannot suppress")
