"""Render docs/EVALUATION_RESULTS.md tables from the saved result JSONs (no hand-copied numbers).

    cd backend && PYTHONPATH=. python -m training.render_reports
"""
import json
from pathlib import Path

R = Path(__file__).resolve().parents[2] / "evaluation_results"
J = lambda p: json.loads((R / p).read_text(encoding="utf-8"))


def ci(x, k="mean"):
    v = x.get(k, x.get("value"))
    return f"{v:.3f} [{x['ci95'][0]:.3f}, {x['ci95'][1]:.3f}]"


def pct(x): return "n/a" if x is None else f"{100 * x:.1f}%"


def adaptive() -> str:
    r = J("adaptive/adaptive_evaluation.json"); a = J("adaptive/label_quality_audit.json")
    L = ["### A1. Label-quality audit (run before training)", "",
         f"- {a['interviews']} interviews / {a['turns']:,} turns; **{a['distinct_question_orderings']} distinct question orderings** (differing only by whether `rad` is asked).",
         f"- Best guess of the next recorded question from the asked-set alone: **{a['next_slot_determinism']['accuracy_of_best_guess_from_asked_set_only']:.1%}**; from asked-sequence + complaint: **{a['next_slot_determinism']['accuracy_of_best_guess_from_asked_sequence_plus_complaint']:.1%}**.",
         f"- Question text variants per slot: {set(a['ai_question_text_variants_per_slot'].values())} (one Hindi, one English). Triage priority = deterministic function of severity: {a['triage_is_function_of_severity']['match']}/{a['triage_is_function_of_severity']['of']}.",
         f"- {a['answer_entropy']['pairs_with_a_single_constant_answer']} of {a['answer_entropy']['complaint_slot_pairs']} (complaint, slot) pairs have a single constant answer.",
         f"- Conclusion: {a['conclusion']}", "", "### A2. Next-slot prediction (recorded next question)", "",
         "| protocol | view | learned top-1 | top-3 | NDCG@1 | NDCG@3 | majority-class top-1 | template lookup (oracle complaint) top-1 |", "|---|---|---|---|---|---|---|---|"]
    for proto in ("official_test", "grouped_cv"):
        for v, d in r["next_slot"][proto].items():
            L.append(f"| {proto} | {v} | {ci(d['top1'])} | {ci(d['top3'])} | {ci(d['ndcg_at_1'])} | {ci(d['ndcg_at_3'])} | {d['baseline_majority_class_top1']['value']:.3f} | {d['baseline_template_lookup_with_oracle_complaint_top1']['value']:.3f} |")
    L += ["", "### A2b. Four-way next-question choice comparison (untouched official test)", "",
          "| selector | top-1 | NDCG@1 | NDCG@3 |", "|---|---|---|---|"]
    for selector, metrics in r["question_choice_comparison"]["official_test"].items():
        L.append(f"| {selector} | {ci(metrics['top1'])} | {ci(metrics['ndcg_at_1'])} | {ci(metrics['ndcg_at_3'])} |")
    L += ["", r["question_choice_comparison"]["note"]]
    L += ["", "### A3. Unseen-complaint generalisation (leave-one-complaint-out)", "",
          "| held-out complaint | states | deferred to reviewed policy | top-1 when model used | wrong but used | top-1 overall |", "|---|---:|---:|---:|---:|---:|"]
    for c, d in r["loco_unseen_complaint"].items():
        L.append(f"| {c} | {d['states']} | {pct(d['deferred_to_reviewed_policy'])} | {pct(d['top1_when_model_used'])} | {d['wrong_but_used_without_deferring']} | {pct(d['top1_overall'])} |")
    for proto, title in (("official_test_30", "A4. Policy comparison — official test split (30 interviews)"), ("grouped_cv_300", "A5. Policy comparison — grouped CV, out-of-fold over all 300 interviews")):
        L += ["", f"### {title}", ""]
        for b in ("none", "12", "10", "8", "6"):
            s = r["policy_comparison"][proto]["summary"][b]["policies"]
            L += [f"**Budget: {'no limit' if b == 'none' else b + ' questions max'}**", "", "| policy | required-slot coverage | mandatory safety-question coverage | interviews with a safety-critical omission | questions | duplicate-slot questions | duplicate-question rate | questions outside dataset schema |", "|---|---|---|---|---|---|---|---|"]
            for p, m in s.items():
                L.append(f"| {p} | {ci(m['required_slot_coverage'])} | {ci(m['mandatory_safety_question_coverage'])} | {ci(m['interviews_with_safety_critical_omission'])} | {m['questions_per_interview']['mean']:.1f} | {m['duplicate_questions_per_interview']['mean']:.2f} | {m['duplicate_question_rate']:.3f} | {m['questions_outside_dataset_schema_per_interview']['mean']:.2f} |")
            L.append("")
            if proto == "grouped_cv_300":
                L += ["Paired differences (same interviews; coverage / safety-omission rate / questions):", ""]
                for k, v in r["policy_comparison"][proto]["summary"][b]["paired_differences"].items():
                    L.append(f"- {k}: coverage {ci(v['required_slot_coverage'])}; safety-omission {ci(v['safety_critical_omission'])}; questions {ci(v['questions'])}")
                L.append("")
    pc = r["policy_comparison"]["grouped_cv_300"]
    L += ["### A6. Required slots never asked at full budget (share of interviews)", "", "| policy | slots (share of interviews missing them) |", "|---|---|"]
    for p, d in pc["per_slot_omission_full_budget"].items():
        L.append(f"| {p} | {', '.join(f'{s}: {v:.0%}' for s, v in d.items()) or 'none'} |")
    o = pc["ordering_agreement"]
    L += ["", f"### A7. Does the learned policy ask in a different order?", "",
          f"Identical canonical-slot order to fixed template: **{o['learned_same_slot_order_as_fixed_template']:.1%}**; to ontology v1: **{o['learned_same_slot_order_as_ontology_v1']:.1%}**; to the uniform-ranker safety-layer ablation: **{o['learned_same_slot_order_as_safety_layer_uniform']:.1%}** ({o['interviews']} interviews).", "",
          "Language robustness for typed 'Other' complaints (English text vs patient's own wording):", "", f"`{json.dumps(pc['language_robustness_other_complaints'], ensure_ascii=False)}`"]
    return "\n".join(L)


def labs() -> str:
    b, a = J("lab_extraction/lab_extraction_before_fix.json"), J("lab_extraction/lab_extraction_after_fix.json")
    keys = [("test_name_recall", "test-name recall"), ("test_name_precision", "test-name precision"), ("exact_value_accuracy", "exact value"), ("unit_accuracy", "unit"),
            ("printed_reference_interval_accuracy", "printed reference interval"), ("printed_flag_capture_accuracy", "printed N/H/L flag captured"),
            ("abnormal_status_accuracy_vs_printed_flag", "abnormal status vs printed flag"), ("false_abnormal_rate_on_printed_normal", "lab-normal wrongly flagged abnormal"),
            ("ambiguous_extraction_rate", "marked ambiguous / for confirmation")]
    L = ["| metric | before: clean text | after: clean text | before: simulated-OCR text | after: simulated-OCR text |", "|---|---|---|---|---|"]
    for k, n in keys:
        L.append(f"| {n} | {pct(b['ground_truth_text'][k])} | {pct(a['ground_truth_text'][k])} | {pct(b['simulated_ocr_text'][k])} | {pct(a['simulated_ocr_text'][k])} |")
    g = a["ground_truth_text"]
    L += ["", f"394 reports / {g['labelled_results']} labelled results (all splits; the extractor was developed while looking at this data, so these are **development-set numbers**). Critical-result recall: not computable ({g['critical_result_note']}).", "",
          "**Rendered scans with known text** (42 test-split reports; synthetic rendering of one monospace layout, Tesseract with row-preserving segmentation):", "",
          "| channel | CER good / fair / poor | test-name recall | exact value | unit | printed interval | false-abnormal | ambiguous |", "|---|---|---|---|---|---|---|---|"]
    s = J("lab_extraction/lab_scan_eval.json")
    for ch in ("image_png", "scanned_pdf", "text_pdf"):
        q = s[ch]["ocr_by_scan_quality"]; e = s[ch]["extraction"]
        L.append(f"| {ch} | {' / '.join(pct(q[k]['char_error_rate_excluding_rule_lines']) for k in ('good', 'fair', 'poor'))} | {pct(e['test_name_recall'])} | {pct(e['exact_value_accuracy'])} | {pct(e['unit_accuracy'])} | {pct(e['printed_reference_interval_accuracy'])} | {pct(e['false_abnormal_rate_on_printed_normal'])} | {pct(e['ambiguous_extraction_rate'])} |")
    return "\n".join(L)


def hindi() -> str:
    b, a = J("hindi_nlp/hindi_nlp_before.json"), J("hindi_nlp/hindi_nlp_after_fix.json")
    L = ["| task | script | before | after |", "|---|---|---|---|"]
    for sc in ("devanagari", "latin"):
        L.append(f"| answer polarity accuracy | {sc} | {pct(b['polarity_of_answers'][sc]['accuracy'])} | {pct(a['polarity_of_answers'][sc]['accuracy'])} |")
        L.append(f"| negative-answer recall | {sc} | {pct(b['polarity_of_answers'][sc]['negative_recall'])} | {pct(a['polarity_of_answers'][sc]['negative_recall'])} |")
        L.append(f"| positive answers misread as negative | {sc} | {b['polarity_of_answers'][sc]['positive_answers_misread_as_negative']} | {a['polarity_of_answers'][sc]['positive_answers_misread_as_negative']} |")
        L.append(f"| duration parsed / exact days | {sc} | {pct(b['durations'][sc]['parsed_rate'])} / {pct(b['durations'][sc]['days_exact_rate'])} | {pct(a['durations'][sc]['parsed_rate'])} / {pct(a['durations'][sc]['days_exact_rate'])} |")
        L.append(f"| complaint concept recall | {sc} | {pct(b['complaint_concept_recall'][sc]['concept_recall'])} | {pct(a['complaint_concept_recall'][sc]['concept_recall'])} |")
    return "\n".join(L)


if __name__ == "__main__":
    print(json.dumps({"adaptive": adaptive(), "labs": labs(), "hindi": hindi()})[:50])
    Path(R / "rendered_tables.md").write_text("\n\n".join(["<!--ADAPTIVE-->", adaptive(), "<!--LABS-->", labs(), "<!--HINDI-->", hindi()]), encoding="utf-8")
