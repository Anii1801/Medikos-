"""Evaluate the learned ranker and compare questioning policies on HELD-OUT interviews.

    cd backend && PYTHONPATH=. python -m training.adaptive.evaluate

Protocols (all patient/interview-grouped, all synthetic data):
  * official_test : checkpoint trained on the 240 train interviews, evaluated on the 30 untouched test interviews
  * grouped_cv    : 5-fold, complaint-stratified, interview-grouped out-of-fold predictions over all 300 interviews
  * loco          : leave-one-complaint-out (does the model generalise to a complaint it never saw? when does it defer?)
Confidence intervals are 95% percentile intervals from a cluster bootstrap over interviews (B=2000, fixed seed).
"""
from __future__ import annotations

import collections
import csv
import json
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from app.adaptive.features import featurize
from app.adaptive.ranker import LearnedSlotRanker
from app.adaptive.schema import STOP, TARGET_CLASSES
from .data import Interview, load_interviews, pre_answer_examples, split_interviews
from .model import fit_weights, predict_next, runtime_ranker
from .simulator import BUDGETS, CONFIG, POLICY_NAMES, replay
from .train import examples_for

BACKEND = Path(__file__).resolve().parents[2]
OUT = BACKEND.parent / "evaluation_results" / "adaptive"
B = 2000
SEED = 20261020


# ----------------------------------------------------------------------------- statistics
def _ci(samples: np.ndarray) -> list[float]:
    return [round(float(np.percentile(samples, 2.5)), 4), round(float(np.percentile(samples, 97.5)), 4)]


def boot_mean(values: Sequence[float]) -> dict[str, Any]:
    v = np.asarray(values, float)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(v), (B, len(v)))
    return {"mean": round(float(v.mean()), 4), "ci95": _ci(v[idx].mean(1)), "n": len(v)}


def boot_diff(a: Sequence[float], b: Sequence[float]) -> dict[str, Any]:
    """Paired difference a-b over the SAME interviews."""
    d = np.asarray(a, float) - np.asarray(b, float)
    return boot_mean(d)


def boot_ratio(num: Sequence[float], den: Sequence[float]) -> dict[str, Any]:
    num, den = np.asarray(num, float), np.asarray(den, float)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(num), (B, len(num)))
    return {"value": round(float(num.sum() / den.sum()), 4), "ci95": _ci(num[idx].sum(1) / den[idx].sum(1)),
            "interviews": len(num), "examples": int(den.sum())}


# ----------------------------------------------------------------------------- next-slot evaluation
def _topk(ranker, e, k: int) -> bool:
    return e.target in [c for c, _ in predict_next(ranker, e)[:k]]


def next_slot_metrics(ranker, ivs: Sequence[Interview], baselines_from: Sequence[Interview]) -> dict[str, Any]:
    """Top-1/top-3 of the learned model vs two non-learning baselines, per view/complaint/script."""
    train_ex = [e for iv in baselines_from for e in pre_answer_examples(iv, "recorded")]
    majority = collections.Counter(e.target for e in train_ex).most_common(1)[0][0]
    template: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    for e in train_ex:
        template[(e.complaint, tuple(e.state["asked"]))][e.target] += 1

    def template_pred(e):
        c = template.get((e.complaint, tuple(e.state["asked"])))
        return c.most_common(1)[0][0] if c else majority

    out: dict[str, Any] = {}
    for view in ("recorded", "app_label"):
        per_iv = []
        rows = []
        for iv in ivs:
            exs = pre_answer_examples(iv, view)
            hit1 = [predict_next(ranker, e)[0][0] == e.target for e in exs]
            hit3 = [_topk(ranker, e, 3) for e in exs]
            maj = [majority == e.target for e in exs]
            tmp = [template_pred(e) == e.target for e in exs]
            per_iv.append((iv, sum(hit1), sum(hit3), sum(maj), sum(tmp), len(exs)))
            for e, h in zip(exs, hit1):
                if not h:
                    rows.append({"interview_id": e.interview_id, "complaint": e.complaint, "view": view, "asked": e.state["asked"],
                                 "target": e.target, "predicted": predict_next(ranker, e)[0][0], "cc_text": e.state["cc_text"]})
        n = [p[5] for p in per_iv]
        out[view] = {
            "top1": boot_ratio([p[1] for p in per_iv], n), "top3": boot_ratio([p[2] for p in per_iv], n),
            "baseline_majority_class_top1": boot_ratio([p[3] for p in per_iv], n),
            "baseline_template_lookup_with_oracle_complaint_top1": boot_ratio([p[4] for p in per_iv], n),
            "errors": rows,
            "by_complaint_top1": {c: round(sum(p[1] for p in per_iv if p[0].complaint == c) / max(1, sum(p[5] for p in per_iv if p[0].complaint == c)), 4)
                                  for c in sorted({p[0].complaint for p in per_iv})},
            "by_script_top1": {s: round(sum(p[1] for p in per_iv if p[0].script == s) / max(1, sum(p[5] for p in per_iv if p[0].script == s)), 4)
                               for s in sorted({p[0].script for p in per_iv})},
        }
    return out


def make_folds(ivs: Sequence[Interview], k: int = 5) -> list[list[Interview]]:
    folds: list[list[Interview]] = [[] for _ in range(k)]
    for i, iv in enumerate(sorted(ivs, key=lambda x: (x.complaint, x.interview_id))):   # complaint-stratified round robin
        folds[i % k].append(iv)
    return folds


def train_runtime(ivs: Sequence[Interview], C: float, seed: int = 42) -> LearnedSlotRanker:
    return runtime_ranker(fit_weights(examples_for(ivs), C, seed), "cv-fold")


# ----------------------------------------------------------------------------- generalisation to unseen complaints
def loco(ivs: Sequence[Interview], C: float) -> dict[str, Any]:
    """Train without one complaint; ask whether the model defers (fallback) and how often it would have been right."""
    res: dict[str, Any] = {}
    for c in sorted({i.complaint for i in ivs}):
        held = [i for i in ivs if i.complaint == c]
        model = train_runtime([i for i in ivs if i.complaint != c], C)
        cells = collections.Counter()
        for view in ("recorded", "app_label"):
            for iv in held:
                for e in pre_answer_examples(iv, view):
                    cands = [s for s in TARGET_CLASSES if s != STOP and s not in e.state["asked"]]
                    if not cands:
                        continue
                    rr = model.rank(e.state, cands)
                    correct = predict_next(model, e)[0][0] == e.target
                    cells[("deferred" if rr.fallback_reason else "used", "right" if correct else "wrong")] += 1
        total = sum(cells.values())
        used = cells[("used", "right")] + cells[("used", "wrong")]
        res[c] = {"n_interviews": len(held), "states": total, "deferred_to_reviewed_policy": round((total - used) / total, 4),
                  "top1_when_model_used": round(cells[("used", "right")] / used, 4) if used else None,
                  "wrong_but_used_without_deferring": cells[("used", "wrong")],
                  "top1_overall": round((cells[("used", "right")] + cells[("deferred", "right")]) / total, 4)}
    return res


# ----------------------------------------------------------------------------- policy replay
def _canonical_order(questions: list[str]) -> list[str]:
    from app.adaptive.schema import canonical_slots_for
    out: list[str] = []
    for q in questions:
        for s in ((q,) if q in TARGET_CLASSES or q == "cc" else canonical_slots_for(q)):
            if s != "cc" and s not in out:
                out.append(s)
    return out


def run_replays(ivs: Sequence[Interview], ranker_for: Callable[[Interview], LearnedSlotRanker], tag: str) -> list[dict[str, Any]]:
    rows = []
    for iv in ivs:
        rk = ranker_for(iv)
        for pol in POLICY_NAMES:
            for budget in BUDGETS:
                rows.append({**replay(iv, pol, budget, rk), "protocol": tag})
    return rows


def summarise_policies(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["policy"], str(r["budget"]))].append(r)
    for budget in [str(b or "none") for b in BUDGETS]:
        table = {}
        ref = {p: sorted(by[(p, budget)], key=lambda r: r["interview_id"]) for p in POLICY_NAMES}
        for p in POLICY_NAMES:
            rs = ref[p]
            table[p] = {
                "required_slot_coverage": boot_mean([r["required_coverage"] for r in rs]),
                "interviews_with_safety_critical_omission": boot_mean([float(r["safety_critical_omitted"]) for r in rs]),
                "questions_per_interview": boot_mean([r["n_questions"] for r in rs]),
                "duplicate_questions_per_interview": boot_mean([r["duplicate_questions"] for r in rs]),
                "questions_outside_dataset_schema_per_interview": boot_mean([r["non_schema_questions"] for r in rs]),
            }
        paired = {}
        for a, b in (("learned_ranker", "fixed_template"), ("learned_ranker", "ontology_v1_current"),
                     ("learned_ranker", "safety_layer_uniform"), ("ontology_v1_current", "ontology_v0_frozen")):
            paired[f"{a} minus {b}"] = {
                "required_slot_coverage": boot_diff([r["required_coverage"] for r in ref[a]], [r["required_coverage"] for r in ref[b]]),
                "safety_critical_omission": boot_diff([float(r["safety_critical_omitted"]) for r in ref[a]],
                                                      [float(r["safety_critical_omitted"]) for r in ref[b]]),
                "questions": boot_diff([r["n_questions"] for r in ref[a]], [r["n_questions"] for r in ref[b]])}
        out[budget] = {"policies": table, "paired_differences": paired}
    return out


def per_slot_omission(rows: list[dict[str, Any]], budget: str) -> dict[str, Any]:
    """At the given budget: how often each required slot is never asked, per policy."""
    out: dict[str, Any] = {}
    for p in POLICY_NAMES:
        rs = [r for r in rows if r["policy"] == p and str(r["budget"]) == budget]
        c = collections.Counter(s for r in rs for s in r["missing_required"])
        out[p] = {s: round(n / len(rs), 3) for s, n in sorted(c.items(), key=lambda kv: -kv[1])}
    return out


def by_group(rows, key: str, budget: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for p in POLICY_NAMES:
        g = collections.defaultdict(list)
        for r in rows:
            if r["policy"] == p and str(r["budget"]) == budget:
                g[r[key]].append(r)
        out[p] = {k: {"n": len(v), "coverage": round(float(np.mean([x["required_coverage"] for x in v])), 4),
                      "safety_omission_rate": round(float(np.mean([x["safety_critical_omitted"] for x in v])), 4),
                      "questions": round(float(np.mean([x["n_questions"] for x in v])), 2)} for k, v in sorted(g.items())}
    return out


def ordering_agreement(rows: list[dict[str, Any]], budget: str = "none") -> dict[str, Any]:
    """Does the learned policy ask in a demonstrably different order from the baselines?"""
    idx = {(r["interview_id"], r["policy"]): r for r in rows if str(r["budget"]) == budget}
    ids = sorted({k[0] for k in idx})
    def same(a, b):
        return float(np.mean([_canonical_order(idx[(i, a)]["questions"]) == _canonical_order(idx[(i, b)]["questions"]) for i in ids]))
    return {"learned_same_slot_order_as_fixed_template": round(same("learned_ranker", "fixed_template"), 4),
            "learned_same_slot_order_as_ontology_v1": round(same("learned_ranker", "ontology_v1_current"), 4),
            "learned_same_slot_order_as_safety_layer_uniform": round(same("learned_ranker", "safety_layer_uniform"), 4),
            "interviews": len(ids), "budget": budget,
            "note": "projection onto canonical dataset slots; 'same' means identical order of first-covering slots"}


def language_robustness(ivs: Sequence[Interview], ranker_for) -> dict[str, Any]:
    """'Other' complaints are typed free text. Compare the ranker given English text vs the patient's own wording
    (mostly Hindi): same question order? any deferral to the reviewed policy?"""
    from app.adaptive.schema import COMPLAINT_TO_ONTOLOGY_CC
    other = [iv for iv in ivs if COMPLAINT_TO_ONTOLOGY_CC[iv.complaint] == "Other"]
    g = collections.defaultdict(list)
    for iv in other:
        a = replay(iv, "learned_ranker", None, ranker_for(iv), "app")
        b = replay(iv, "learned_ranker", None, ranker_for(iv), "recorded")
        g[iv.script].append((a["questions"] == b["questions"], b["required_coverage"],
                             sum(x == "fallback" for x in b["selection_bases"]) / max(1, b["n_questions"])))
    return {s: {"n": len(v), "same_question_order_as_english_text": round(float(np.mean([x[0] for x in v])), 4),
                "coverage_with_patient_wording": round(float(np.mean([x[1] for x in v])), 4),
                "fallback_share_with_patient_wording": round(float(np.mean([x[2] for x in v])), 4)} for s, v in sorted(g.items())}


# ----------------------------------------------------------------------------- driver
def write_csv(path: Path, rows: list[dict[str, Any]], keep=lambda r: True):
    cols = ["protocol", "interview_id", "complaint", "script", "policy", "budget", "n_questions", "required_coverage",
            "safety_critical_omitted", "missing_required", "missing_safety_critical", "duplicate_questions",
            "non_schema_questions", "questions"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            if keep(r):
                w.writerow([";".join(r[c]) if isinstance(r[c], list) else r[c] for c in cols])


def run_evaluation(out: Path = OUT) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    ivs = load_interviews()
    splits = split_interviews(ivs)
    cfg = json.loads((BACKEND / "models" / "adaptive_ranker" / "v1" / "config.json").read_text())
    C = cfg["hyperparameters"]["C"]
    checkpoint = LearnedSlotRanker.load()

    # 1. official, untouched test split: the checkpoint trained on train only
    test_next = next_slot_metrics(checkpoint, splits["test"], splits["train"])
    test_rows = run_replays(splits["test"], lambda iv: checkpoint, "official_test_30")

    # 2. grouped CV over all 300: out-of-fold rankers (hyper-parameter C fixed from the validation search, not re-tuned)
    folds = make_folds(ivs, 5)
    fold_model: dict[str, LearnedSlotRanker] = {}
    cv_next_parts = []
    for k, held in enumerate(folds):
        train_ivs = [i for j, f in enumerate(folds) if j != k for i in f]
        m = train_runtime(train_ivs, C)
        for iv in held:
            fold_model[iv.interview_id] = m
        cv_next_parts.append((m, held, train_ivs))
    cv_next = {"recorded": None, "app_label": None}
    pooled = {v: {"c1": [], "c3": [], "n": [], "maj": [], "tmp": [], "errors": [], "iv": []} for v in cv_next}
    for m, held, train_ivs in cv_next_parts:
        part = next_slot_metrics(m, held, train_ivs)
        for v in pooled:
            pooled[v]["errors"] += part[v]["errors"]
    # recompute pooled ratios exactly from per-interview counts
    rows_cv = {}
    for v in ("recorded", "app_label"):
        c1, c3, n, maj, tmp = [], [], [], [], []
        by_c, by_s = collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0])
        for m, held, train_ivs in cv_next_parts:
            tr = [e for iv in train_ivs for e in pre_answer_examples(iv, "recorded")]
            majority = collections.Counter(e.target for e in tr).most_common(1)[0][0]
            tmpl: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
            for e in tr:
                tmpl[(e.complaint, tuple(e.state["asked"]))][e.target] += 1
            for iv in held:
                exs = pre_answer_examples(iv, v)
                h1 = sum(predict_next(m, e)[0][0] == e.target for e in exs)
                c1.append(h1); c3.append(sum(_topk(m, e, 3) for e in exs)); n.append(len(exs))
                maj.append(sum(majority == e.target for e in exs))
                tmp.append(sum((tmpl.get((e.complaint, tuple(e.state["asked"])), collections.Counter({majority: 1})).most_common(1)[0][0]) == e.target for e in exs))
                by_c[iv.complaint][0] += h1; by_c[iv.complaint][1] += len(exs)
                by_s[iv.script][0] += h1; by_s[iv.script][1] += len(exs)
        rows_cv[v] = {"top1": boot_ratio(c1, n), "top3": boot_ratio(c3, n),
                      "baseline_majority_class_top1": boot_ratio(maj, n),
                      "baseline_template_lookup_with_oracle_complaint_top1": boot_ratio(tmp, n),
                      "by_complaint_top1": {k: round(a / b, 4) for k, (a, b) in sorted(by_c.items())},
                      "by_script_top1": {k: round(a / b, 4) for k, (a, b) in sorted(by_s.items())},
                      "errors": pooled[v]["errors"]}
    cv_rows = run_replays(ivs, lambda iv: fold_model[iv.interview_id], "grouped_cv_300_oof")

    result = {
        "protocol_notes": {"data": "SYNTHETIC templated interviews, 14 complaints; no claim of clinical performance",
                           "bootstrap": f"cluster bootstrap over interviews, B={B}, seed={SEED}, 95% percentile CI",
                           "official_test": "30 interviews, never used for model/threshold selection",
                           "grouped_cv": "5 folds, complaint-stratified; each interview/patient appears in exactly one fold",
                           "C": C, "required_slots": "provisional, derived from training-split template; see config/required_slots.json"},
        "next_slot": {"official_test": {v: {k: x for k, x in d.items() if k != "errors"} for v, d in test_next.items()},
                      "grouped_cv": {v: {k: x for k, x in d.items() if k != "errors"} for v, d in rows_cv.items()}},
        "loco_unseen_complaint": loco(ivs, C),
        "policy_comparison": {
            "official_test_30": {"summary": summarise_policies(test_rows),
                                 "per_slot_omission_full_budget": per_slot_omission(test_rows, "none"),
                                 "ordering_agreement": ordering_agreement(test_rows)},
            "grouped_cv_300": {"summary": summarise_policies(cv_rows),
                               "per_slot_omission_full_budget": per_slot_omission(cv_rows, "none"),
                               "by_complaint_full_budget": by_group(cv_rows, "complaint", "none"),
                               "by_complaint_budget_8": by_group(cv_rows, "complaint", "8"),
                               "by_script_full_budget": by_group(cv_rows, "script", "none"),
                               "ordering_agreement": ordering_agreement(cv_rows),
                               "language_robustness_other_complaints": language_robustness(ivs, lambda iv: fold_model[iv.interview_id])}},
    }
    (out / "adaptive_evaluation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "error_analysis.json").write_text(json.dumps({
        "next_slot_errors_official_test": {v: d["errors"][:40] for v, d in test_next.items()},
        "next_slot_errors_grouped_cv": {v: d["errors"][:40] for v, d in rows_cv.items()},
        "next_slot_error_counts": {"official_test": {v: len(d["errors"]) for v, d in test_next.items()},
                                   "grouped_cv": {v: len(d["errors"]) for v, d in rows_cv.items()}}}, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(out / "per_case_policy_outputs_test30.csv", test_rows)
    write_csv(out / "per_case_policy_outputs_cv300.csv", cv_rows, keep=lambda r: r["budget"] in ("none", 8))
    return result


if __name__ == "__main__":
    from .audit import run_audit
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "label_quality_audit.json").write_text(json.dumps(run_audit(), indent=2, ensure_ascii=False), encoding="utf-8")
    res = run_evaluation()
    print(json.dumps({"next_slot_official_test": {v: {k: d[k] for k in ("top1", "top3", "baseline_majority_class_top1")}
                                                   for v, d in res["next_slot"]["official_test"].items()}}, indent=2))
