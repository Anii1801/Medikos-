"""Evaluate ASR text pairs by language.

This accepts the repository's text-only smoke data or a JSONL audio evaluation
manifest. Text-only rows are explicitly reported as not acoustic evaluation.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.asr_metrics import evaluate


def rows(path: Path):
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


parser = argparse.ArgumentParser()
parser.add_argument("--pairs", type=Path, required=True)
args = parser.parse_args()
if not args.pairs.exists():
    raise SystemExit(f"Evaluation file not found: {args.pairs}; no ASR results were produced.")
print(json.dumps({"by_language": evaluate(rows(args.pairs)),
                  "warning": "Do not claim English, Hindi, or Hinglish clinical support from loading alone."},
                 ensure_ascii=False, indent=2))
