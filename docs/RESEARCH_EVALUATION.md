# MediKiosk research evaluation framework

## Scope and evidence policy

This framework operationalises the 2022–2026 evaluation themes identified in
the literature review: early-stage clinical AI evaluation must measure real
workflow effects and safety, not only model scores; paired held-out
comparisons are preferred; reporting must identify data provenance, failures,
human review, and deployment limitations. The reporting anchor is the
DECIDE-AI early-stage clinical evaluation guideline (The Lancet Digital
Health, 2022): [publisher record](https://www.thelancet.com/journals/landig/article/PIIS2589-7500(21)00277-2/fulltext).
The framework also follows the reproducibility principles in the
[CONSORT-AI extension](https://www.nature.com/articles/s41591-020-1034-x)
and the [CLAIM checklist](https://pubs.rsna.org/doi/10.1148/radiol.2020200343);
these are included as reporting precedents, not as evidence that MediKiosk is
clinically validated. A search should be rerun before publication for papers
published after the current cutoff (2026-10-14).

The implementation is in
[`backend/evaluation/framework.py`](../backend/evaluation/framework.py).
`backend/scripts/run_research_evaluation.py` produces a JSON report and a
separate `error_analysis.json`. It uses a fixed seed, paired bootstrap 95%
intervals, and paired permutation p-values when paired vectors are available.
It refuses unequal paired vectors. It never turns unavailable models or
missing annotations into zero scores.

Run from the repository root:

```powershell
python backend/scripts/run_research_evaluation.py --output evaluation_results/research_evaluation.json
```

The red-flag result is an audit of the bundled synthetic/demo CSV, not clinical
validation. The current run has **one measured software audit** and seven
pending experiments. The generated report records the exact sample size and
disclaimer. The current local suite does not contain licensed paired outputs
for the other comparisons.

## Comparison registry

| Comparison | Primary endpoint | Held-out data/status | Current result |
|---|---|---|---|
| Fixed questions vs adaptive questions | slot coverage, omission rate, duplicate rate, turns, red-flag recall | Patient-group split and clinician slot annotations required; local dialogue is synthetic and not yet wired to both policies | **Pending** |
| Generic extraction vs clinical NLP baseline | entity precision/recall/F1, negation and conflict accuracy | Local prescription CSV is not BIO/clinical-span labelled | **Pending** |
| One-shot summary vs extraction-first grounded summary | omission, unsupported-claim/hallucination rate, source-link coverage, clinician factuality | Local summaries are synthetic; no blinded clinician labels | **Pending** |
| Baseline OCR vs document pipeline | CER, WER, field accuracy, latency | Local OCR file has no pixel images; permissioned image set required | **Pending** |
| Full fine-tuning vs LoRA/PEFT | task metric, trainable parameters, time, peak memory, latency, model size | No verified compatible checkpoint, licensed corpus, or training run | **Pending / not applicable** |
| Manual vs AI draft plus clinician review | documentation time, correction time, omissions, unsafe edits | Requires prospective or simulated workflow study and ethics/clinical review | **Pending** |
| English vs Hindi vs Hinglish | language-stratified WER and clinical-entity accuracy | Bundled ASR data has no audio and no Hinglish rows; text-pair smoke only | **Pending** |
| Deterministic red flags vs model | sensitivity, false negatives, false-positive burden, subgroup results | 300-row bundled synthetic/demo audit; no trained model | **Measured rules audit; model pending** |

## Required protocol

1. Freeze a manifest version, code revision, random seed, model/checkpoint
   identifiers, licence, hardware, and preprocessing configuration.
2. Split by patient/encounter/speaker/document as appropriate. Deduplicate
   normalized source text and keep all variants in one group. Never tune on
   the test split.
3. For paired comparisons, run both systems on exactly the same held-out
   rows. Report `n`, per-row outcomes, aggregate estimate, 95% paired bootstrap
   interval, and paired permutation p-value. Do not report p-values without
   the paired rows.
4. Report extraction micro and macro precision/recall/F1 by entity type,
   negation, uncertainty, temporal change, and conflict. Report omissions and
   unsupported claims separately from lexical overlap.
5. Report OCR/ASR CER/WER by language/document quality and clinical-entity
   transcription accuracy. Text-only simulated ASR and synthetic OCR are
   smoke tests, not acoustic or handwriting evidence.
6. For history taking, define completeness against a clinician-reviewed slot
   set before measuring adaptive versus fixed questioning. Count duplicate
   questions, unanswered required slots, turns, and red-flag recall.
7. For workflow studies, pre-register time measurement: start/stop events,
   correction time, clinician experience, and whether the clinician accepted,
   edited, or rejected each generated statement.
8. For red flags, evaluate the deterministic engine independently. A model may
   add a warning but may never suppress a validated deterministic warning.
   Analyze every false negative individually.

## Resource and runtime reporting

Each run must record trainable parameters, total parameters, checkpoint/model
size, CPU/GPU type, peak memory, training wall time, inference latency
(median and p95), batch size, and software versions. If a model is not run,
the field is `pending`, never `0` unless zero is the measured value (for
example, the deterministic smoke pipeline has zero trainable parameters).

## Error analysis

`error_analysis.json` is intentionally pending until paired source-annotated
outputs exist. Its required categories are omission, unsupported claim,
negation, number/duration, code-switching, poor OCR, provider/model outage,
red-flag false negative, and false positive. Each case should retain an
identifier, language, system outputs, expected evidence, source span, and
review disposition. Error counts must be accompanied by denominators and
stratified by language and task.

## Achieved results, pending experiments, hypotheses

| Type | Statement |
|---|---|
| Achieved | Stateful adaptive history, deterministic red-flag rules, source-linked extraction-first summaries, configurable ASR boundary, paired-statistics utilities, and safety-preserving rule/model combination are implemented and tested. |
| Achieved | The bundled red-flag audit has previously measured sensitivity 1.0, specificity 0.7508896797, precision 0.2134831461, 0 false negatives, and 70 false positives on 300 synthetic/demo rows. These are not clinical accuracy claims. |
| Pending | All model-vs-model, OCR image, acoustic ASR, Hindi/Hinglish clinical, clinician-time, fine-tuning/PEFT, and clinician-factuality experiments listed above. |
| Hypothesis | Grounded generation should reduce unsupported claims relative to one-shot generation, at the cost of possible omissions and review time. This is not a result. |
| Hypothesis | Adaptive questioning should reduce redundant turns while preserving or improving required-slot coverage. This is not a result. |
| Hypothesis | Audio and language-specific clinical terminology will change WER and entity accuracy by language and accent. This is not a result. |

No new dataset is claimed. No clinical validation, generalization, superiority,
or causal workflow benefit is claimed.
