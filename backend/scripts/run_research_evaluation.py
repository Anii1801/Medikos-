"""Run the reproducible MediKiosk research evaluation registry.

The command reports measured local software/dataset audits and explicitly
records comparisons that require unavailable licensed models or test data.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.redflag_engine import RedFlagEngine
from evaluation.framework import EXPERIMENTS, pending_experiment, safe_red_flag_comparison, write_report


def red_flags(root: Path) -> dict:
    path = root / "Datasets" / "MediKiosk_Datasets" / "05_triage_redflag" / "red_flag_labeled_cases.csv"
    if not path.exists():
        return pending_experiment(EXPERIMENTS[-1], f"held-out dataset not found: {path}")
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    engine = RedFlagEngine()
    actual, rules = [], []
    for row in rows:
        case = {"symptoms": {"cc": row["chief_complaint"], "duration": row["duration"],
                             "severity": row["severity_1_10"], "assoc": row["associated_symptoms"]},
                "patient_description": row["red_flag_reason"]}
        actual.append(row["red_flag"].lower() == "true")
        rules.append(engine.evaluate(case).urgency in ("EMERGENCY", "URGENT"))
    result = safe_red_flag_comparison(rules, [False] * len(rows), actual)
    return {"experiment_id": "redflag_rules_vs_model", "status": "measured_software_audit",
            "dataset": str(path), "dataset_disclaimer": "bundled synthetic/demo; not clinical validation",
            "sample_size": len(rows), "results": result, "confidence_intervals": "not computed for aggregate audit",
            "model_status": "pending: no provenance/licence-verified trained classifier configured"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("evaluation_results/research_evaluation.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    results = [red_flags(root)]
    results.extend(pending_experiment(spec, "requires paired held-out annotations and/or a verified model/checkpoint") for spec in EXPERIMENTS[:-1])
    write_report(args.output, results, {
        "seed": 42,
        "paired_comparisons": True,
        "confidence_interval": "paired bootstrap 95%; permutation p-values when paired vectors exist",
        "literature_window": "2022-01-01 through 2026-10-14",
        "clinical_validation": False,
    })
    error_path = args.output.with_name("error_analysis.json")
    error_path.write_text(json.dumps({
        "status": "pending",
        "reason": "No permissioned paired system outputs with source annotations are bundled.",
        "required_categories": ["omission", "unsupported_claim", "negation", "number_or_duration",
                                "code_switch", "poor_ocr", "model_outage", "false_negative", "false_positive"],
        "method": "stratify held-out paired outputs by language, task, entity type and error category; retain row identifiers and source evidence",
    }, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "experiments": len(results),
                      "error_analysis": str(error_path),
                      "measured": sum(x["status"] == "measured_software_audit" for x in results),
                      "pending": sum(x["status"] == "pending" for x in results)}, indent=2))


if __name__ == "__main__":
    main()
