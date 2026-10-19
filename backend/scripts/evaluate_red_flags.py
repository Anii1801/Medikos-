"""Dataset audit of the deterministic RedFlagEngine against the bundled labelled triage CSV.

NOT clinical validation. The CSV is synthetic/demo data. Notes on method:
  * The label's own explanation column (`red_flag_reason`) is NOT given to the engine (it would be
    label leakage; an earlier version of this script did pass it - measured effect on this engine: none).
  * Primary prediction = engine urgency EMERGENCY (the dataset's red_flag=True maps to EMERGENCY triage).
    Secondary = any finding (URGENT or EMERGENCY).
  * 95% Wilson interval is reported for sensitivity/specificity; with 19 positives it is wide.
  * Positives are only two synthetic templates (ACS, stroke): rules were not developed on a
    held-out set, and agreement here says nothing about unseen real-world phrasing.
"""
import csv, json, math, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.redflag_engine import RedFlagEngine

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "Datasets" / "MediKiosk_Datasets" / "05_triage_redflag" / "red_flag_labeled_cases.csv"
OUT = ROOT / "evaluation_results" / "redflag_dataset_audit.json"


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def metrics(c):
    tp, tn, fp, fn = c["tp"], c["tn"], c["fp"], c["fn"]
    return {"counts": dict(c), "n": tp + tn + fp + fn,
            "sensitivity": round(tp / (tp + fn), 3) if tp + fn else None, "sensitivity_95ci": wilson(tp, tp + fn),
            "specificity": round(tn / (tn + fp), 3) if tn + fp else None, "specificity_95ci": wilson(tn, tn + fp),
            "precision": round(tp / (tp + fp), 3) if tp + fp else None, "false_negatives": fn, "false_positives": fp}


def main():
    rows = list(csv.DictReader(CSV.open(encoding="utf-8-sig", newline="")))
    eng = RedFlagEngine()
    keys = ("tp", "tn", "fp", "fn")
    res = {m: {s: dict.fromkeys(keys, 0) for s in ("all", "train", "valid", "test")} for m in ("emergency_level", "any_finding")}
    misses = []
    for r in rows:
        case = {"symptoms": {"cc": r["chief_complaint"], "duration": r["duration"],
                             "severity": r["severity_1_10"], "assoc": r["associated_symptoms"]}}
        out = eng.evaluate(case)
        actual = r["red_flag"].lower() == "true"
        for mode, pred in (("emergency_level", out.urgency == "EMERGENCY"), ("any_finding", out.urgency in ("EMERGENCY", "URGENT"))):
            k = "tp" if pred and actual else "tn" if not pred and not actual else "fp" if pred else "fn"
            res[mode]["all"][k] += 1
            res[mode][r["split"]][k] += 1
            if mode == "emergency_level" and k == "fn":
                misses.append({k2: r[k2] for k2 in ("interview_id", "chief_complaint", "associated_symptoms", "severity_1_10")})
    report = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "dataset": str(CSV.relative_to(ROOT)),
              "dataset_nature": "synthetic/demo; NOT clinical validation", "positives": {"all": sum(r["red_flag"].lower() == "true" for r in rows)},
              "leakage_control": "red_flag_reason not provided to engine",
              "results": {m: {s: metrics(c) for s, c in d.items()} for m, d in res.items()},
              "emergency_level_false_negative_cases": misses}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({m: {s: {k: v for k, v in x.items() if k in ("counts", "sensitivity", "sensitivity_95ci", "specificity", "precision")}
                         for s, x in d.items()} for m, d in report["results"].items()}, indent=1))
    print("false negatives (emergency level):", len(misses), "->", OUT)


if __name__ == "__main__":
    main()
