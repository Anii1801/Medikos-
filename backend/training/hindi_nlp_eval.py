"""Measure clinical-NLP behaviour on the dataset's real Hindi (Devanagari) and English patient answers.

    cd backend && PYTHONPATH=. python -m training.hindi_nlp_eval [--label NAME]

Self-contained (reads the CSVs directly) so the SAME script can be run against an older checkout for before/after.
Data are SYNTHETIC and templated (a handful of phrasings per slot); scores describe those phrasings, not Hindi clinical
language in general. No audio is involved: this is text only.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
from pathlib import Path

from app.clinical_nlp import ClinicalNLPService
from app.datasets import DATASET_ROOT
from app.history_agent import classify_answer

D = DATASET_ROOT / "01_history_interview"
OUT = Path(__file__).resolve().parents[2] / "evaluation_results" / "hindi_nlp"
POLARITY_FIELDS = {"allergy": "allergy", "drug_history": "drug_history", "past_history": "past_history",
                   "family_history": "family_history", "personal_history": "personal_history",
                   "radiation": "hpi_radiation", "relieving": "hpi_relieving", "aggravating": "hpi_aggravating"}
NEGATIVE_GOLD = {"no known allergies", "none", "no similar illness", "non-smoker, no alcohol", "it does not spread",
                 "nothing helps", "nothing specific", "nothing in particular"}      # every gold value with a 'nothing / none' meaning (enumerated from the data)
EXPECTED = {"chest pain": {"chest_pain"}, "fever": {"fever"}, "cough and breathlessness": {"cough", "breathlessness"},
            "headache with dizziness": {"headache", "dizziness"}, "pain in the abdomen": {"abdominal_pain"},
            "sudden weakness on one side and slurred speech": {"focal_weakness", "speech_disturbance"}}
UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def script_of(s: str) -> str:
    return "devanagari" if any("\u0900" <= c <= "\u097F" for c in s) else "latin"


def load():
    hist = {r["interview_id"]: r for r in csv.DictReader((D / "structured_histories.csv").open(encoding="utf-8-sig", newline=""))}
    turns = list(csv.DictReader((D / "interview_turns.csv").open(encoding="utf-8-sig", newline="")))
    return hist, [t for t in turns if t["role"] == "PATIENT"]


def gold_days(text: str):
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(day|week|month|year)s?", text)
    return float(m.group(1)) * UNIT_DAYS[m.group(2)] if m else None


def pred_days(text: str):
    """Duration of a bare answer to 'how long?', through the public temporal parser."""
    from app.clinical_nlp import parse_temporal
    t = parse_temporal(text)
    return t.duration_days if t else None


def run() -> dict:
    hist, turns = load()
    svc = ClinicalNLPService()
    # A. answer polarity
    pol = collections.defaultdict(lambda: collections.Counter())
    errors = []
    for t in turns:
        f = POLARITY_FIELDS.get(t["slot"])
        if not f:
            continue
        gold = "negative" if hist[t["interview_id"]][f] in NEGATIVE_GOLD else "reported"
        pred = classify_answer(t["text"])
        sc = script_of(t["text"])
        pol[sc][(gold, pred)] += 1
        if pred != gold and len(errors) < 40:
            errors.append({"slot": t["slot"], "script": sc, "text": t["text"], "gold": gold, "predicted": pred})
    polarity = {}
    for sc, c in pol.items():
        n = sum(c.values()); ok = sum(v for (g, p), v in c.items() if g == p)
        neg_n = sum(v for (g, p), v in c.items() if g == "negative")
        neg_ok = sum(v for (g, p), v in c.items() if g == "negative" and p == "negative")
        pos_n = sum(v for (g, p), v in c.items() if g == "reported")
        false_neg = sum(v for (g, p), v in c.items() if g == "reported" and p == "negative")
        polarity[sc] = {"answers": n, "accuracy": round(ok / n, 4), "negative_recall": round(neg_ok / neg_n, 4) if neg_n else None,
                        "negative_answers": neg_n, "positive_answers_misread_as_negative": false_neg, "positive_answers": pos_n,
                        "confusion": {f"gold={g},pred={p}": v for (g, p), v in sorted(c.items())}}
    # B. durations
    dur = collections.defaultdict(lambda: collections.Counter())
    for t in turns:
        if t["slot"] != "duration":
            continue
        g = gold_days(hist[t["interview_id"]]["duration"]); p = pred_days(t["text"]); sc = script_of(t["text"])
        if g is None:      # gold like "since childhood" has no day count
            continue
        dur[sc]["n"] += 1
        dur[sc]["parsed"] += p is not None
        dur[sc]["exact_days"] += p is not None and g is not None and abs(p - g) < 0.5
    durations = {sc: {"answers": c["n"], "parsed_rate": round(c["parsed"] / c["n"], 4), "days_exact_rate": round(c["exact_days"] / c["n"], 4)} for sc, c in dur.items()}
    # C. complaint concept recall (present assertion)
    rec = collections.defaultdict(lambda: collections.Counter())
    for t in turns:
        if t["slot"] != "chief_complaint":
            continue
        comp = hist[t["interview_id"]]["chief_complaint"]
        if comp not in EXPECTED:
            continue
        got = {f.concept for f in svc.extract(t["text"], source_id="x") if f.assertion == "present"}
        sc = script_of(t["text"])
        for c in EXPECTED[comp]:
            rec[sc]["expected"] += 1
            rec[sc]["found"] += c in got
        rec[sc]["utterances"] += 1
    concepts = {sc: {"utterances": c["utterances"], "expected_concepts": c["expected"], "concept_recall": round(c["found"] / c["expected"], 4)} for sc, c in rec.items()}
    return {"polarity_of_answers": polarity, "durations": durations, "complaint_concept_recall": concepts, "polarity_errors": errors}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--label", default="current"); a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    res = run()
    (OUT / f"hindi_nlp_{a.label}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "polarity_errors"}, indent=1, ensure_ascii=False))
