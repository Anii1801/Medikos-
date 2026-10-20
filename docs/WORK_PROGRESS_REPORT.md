# MediKiosk work progress report

**Report date:** 2026-10-20  
**Repository:** `Anii1801/Medikos-`  
**Scope:** Work completed in the current implementation cycle

## 1. Executive summary

MediKiosk now has a functioning deterministic baseline for adaptive history
taking, clinical fact extraction, laboratory-report processing, source-linked
summary generation, red-flag screening, and clinician review.

The implementation deliberately does not claim clinical validation or model
training. The available local datasets are primarily synthetic, demo, text-only,
or incomplete for the intended task. External datasets and model checkpoints
remain gated until their provenance, licence, access conditions, and evaluation
fitness are verified.

## 2. Adaptive history-taking

The existing ontology-driven interviewer has been exposed through the explicit
`AdaptiveHistoryTakingAgent` contract in
[`backend/app/history_agent.py`](../backend/app/history_agent.py).

Implemented behavior:

- Complaint-aware question selection using the existing 28-slot ontology.
- Mandatory safety-oriented questioning before less relevant history.
- Duplicate-question suppression while retaining the current unanswered question
  on repeated reads.
- Budget-based safe stopping.
- Negative, uncertain, reported, and conflicting answer handling.
- Red-flag routing independent of summary generation.
- Conservative confidence and human-review routing.
- Persistence and restoration of interview state.
- Per-slot state containing:
  - Answer value
  - Patient source
  - Provenance
  - Answer status
  - Attempt count
  - Last attempt index

The API now constructs and restores the adaptive agent through
[`backend/app/main.py`](../backend/app/main.py).

The underlying clinical NLP service remains a transparent `rule_v1` baseline.
It extracts clinical facts with assertion, experiencer, temporal context,
source type, source span, and verification status. It is not a trained or
calibrated model and currently supports English-oriented rule patterns.

## 3. Medical document and laboratory pipeline

The application already supported authenticated PDF/image/text document intake.
The pipeline now passes structured laboratory findings into the clinical summary.

Current flow:

```text
Upload
  -> file size validation
  -> PDF text extraction or Tesseract OCR
  -> OCR/page provenance
  -> deterministic clinical entity extraction
  -> laboratory value/unit/reference parsing
  -> abnormality comparison
  -> structured summary section
  -> clinician review
```

Laboratory findings now expose:

- Test name
- Numeric result
- Normalized unit
- Reference interval
- Below/within/above comparison state
- Explicit critical flag when present in the source text
- Report date
- Source document
- Source span/page metadata where available
- Extraction status and uncertainty
- Pending clinician-review status

Report-supplied reference intervals take precedence. When a report does not
provide an interval, the configured baseline is disclosed explicitly and the
finding remains subject to confirmation. A within-range result is not presented
as proof that a person is healthy.

The dedicated section is titled **Laboratory and Investigation Findings** and is
included in the generated summary alongside existing timeline, abnormal-value,
medication, interaction, and conflict sections.

Relevant files:

- [`backend/app/ocr.py`](../backend/app/ocr.py)
- [`backend/app/summary.py`](../backend/app/summary.py)
- [`docs/DOCUMENT_PIPELINE.md`](DOCUMENT_PIPELINE.md)

## 4. Safety and clinician review

The existing red-flag engine remains deterministic and separate from summary
text. It continues to:

- Preserve evidence and source provenance.
- Distinguish unavailable screening from a clean result.
- Avoid treating missing information as a negative finding.
- Mark findings as provisional pending clinician sign-off.
- Escalate failed screening rather than returning an empty red-flag list.

Doctor-only record access and approval remain backend-protected. Report status
changes to approved only after an explicit clinician confirmation.

## 5. Dataset audit findings

The dataset inventory was checked against files on disk rather than trusting
manifest entries alone. The detailed audit is in
[`docs/DATASET_AUDIT.md`](DATASET_AUDIT.md).

Verified local resources include:

- Patient master and timeline data.
- 7,863 history-interview turns.
- 300 structured histories.
- A 28-slot history inventory.
- 1,238 laboratory entity rows.
- 1,011 prescription entity rows.
- 892 simulated OCR text pairs.
- 300 synthetic history-to-summary pairs.
- 207 ACI-Bench dialogue/note pairs.
- 4,966 note-only MTSamples records.
- 900 simulated ASR text pairs.
- Red-flag rules and labelled demo cases.
- Optional AYUSH and drug-safety tables.

Important limitations:

- Most bundled data is synthetic or demo data.
- The bundled ASR resource contains no audio.
- Referenced handwriting images are not bundled.
- MTSamples notes are not paired with source dialogue.
- The MediTOD material present locally is only three sample dialogues.
- External resource licences and access conditions remain unresolved for several
  candidate datasets.
- Duplicate rows and patient/interview linkage require group-aware splitting.

## 6. Training status

No neural model was trained and no checkpoint was created.

Current task baselines:

| Task | Current baseline | Status |
|---|---|---|
| Adaptive questioning | Ontology policy and `AdaptiveHistoryTakingAgent` | Integrated |
| Clinical NLP | Rule-based `ClinicalNLPService` | Integrated |
| Laboratory extraction | Deterministic parser | Integrated |
| Red flags | Deterministic `RedFlagEngine` | Integrated |
| OCR | Embedded PDF extraction/Tesseract when installed | Integrated |
| ASR | Browser/Web Speech integration | Existing baseline |
| Summary generation | Evidence-grounded deterministic template | Integrated |

Leakage-safe preparation utilities are available in
[`backend/training`](../backend/training). They validate schemas, perform
group-based splits, and reject duplicate leakage. The reproducibility guidance
is in [`docs/MODEL_TRAINING.md`](MODEL_TRAINING.md).

## 7. Tests and verification

The full backend suite was run with:

```powershell
$env:PYTHONPATH='C:\path\to\medikiosk\backend'
pytest backend/tests -q
```

Result:

```text
94 passed, 2 skipped, 1 warning
```

The skipped tests depend on Tesseract/image OCR availability. The warning is
the existing Starlette/httpx deprecation warning.

Additional focused checks covered:

- Adaptive slot provenance and attempt tracking.
- Interview persistence and restoration.
- Contradiction and uncertainty handling.
- Explicit report reference intervals.
- Missing-reference disclosure.
- Laboratory source spans and clinician-review state.
- Existing clinical report ordering and red-flag contracts.

The adaptive smoke evaluator reported:

```text
3 cases
2 duplicate-free cases
duplicate-free rate: 0.6667
1 case with expected red flags
```

This is an invariant smoke result only, not a clinical performance metric.

## 8. Files added or changed

### Added

- [`backend/tests/test_lab_findings.py`](../backend/tests/test_lab_findings.py)
- [`docs/DATASET_AUDIT.md`](DATASET_AUDIT.md)
- [`docs/MODEL_TRAINING.md`](MODEL_TRAINING.md)
- [`docs/EVALUATION_RESULTS.md`](EVALUATION_RESULTS.md)
- This report

### Changed

- [`backend/app/history_agent.py`](../backend/app/history_agent.py)
- [`backend/app/main.py`](../backend/app/main.py)
- [`backend/app/ocr.py`](../backend/app/ocr.py)
- [`backend/app/summary.py`](../backend/app/summary.py)
- [`backend/tests/test_history_agent.py`](../backend/tests/test_history_agent.py)
- [`docs/DOCUMENT_PIPELINE.md`](DOCUMENT_PIPELINE.md)

## 9. Remaining work

The following work is not yet complete because it requires additional verified
data, access, or clinical governance:

1. Reconstruct pre-answer adaptive-question training examples from interview
   turns and evaluate a learned ranker against the deterministic policy.
2. Add clinician-reviewed held-out evaluation data for adaptive questioning.
3. Obtain and verify permitted external datasets and model licences.
4. Add a real, permissioned OCR/image benchmark with source spans.
5. Add annotated laboratory extraction data for test-name, value, unit,
   reference-range, abnormality, and critical-result metrics.
6. Improve handling of report-specific units and demographic/specimen context
   only when those values are explicitly available.
7. Add frontend assertions for the new structured laboratory findings display.
8. Run deployment-level security, privacy, and clinician workflow review.
9. Resolve the existing test-environment Tesseract dependency if image OCR
   integration coverage is required.

## 10. Overall status

**Software integration:** working baseline  
**Backend regression suite:** passing  
**Laboratory findings in summary:** implemented and tested  
**Adaptive agent state/provenance:** implemented and tested  
**Neural model training:** not performed  
**Clinical validation:** not performed  
**Production readiness:** not established; clinician, privacy, regulatory, and
dataset-governance review remain required
