# Document-to-summary pipeline

## Current release path

Permitted PDF and image uploads are processed by `backend/app/ocr.py`.

- PDF text is extracted page by page with `pdf-text` when an embedded text layer
  exists. Scanned PDFs are reported as `pdf-scanned-unsupported`; no text is
  fabricated.
- Images use the installed Tesseract executable when available. OCR word
  boxes and confidence values are retained in `entities.ocr_pages`.
- Original image/PDF bytes are not stored. The extracted text is stored in full
  in the document row, together with filename, date, engine, page count and
  byte-size provenance.
- Structured facts use the `clinical-facts-v1` schema. Facts include source
  offsets, page where known, bounding box where OCR provides one, confidence,
  and `reported`, `negated`, or `uncertain` status.
- Low-confidence, uncertain, negated, and ambiguous facts remain visible and
  carry `review_flags`. Missing values remain missing.

The models/components actually used by this implementation are the `pypdf`
embedded-text parser and the locally installed Tesseract executable (when
available), plus deterministic Python extraction rules. In the current test
environment Tesseract is unavailable, so the image integration test is
skipped and no OCR model result is reported. No neural document model was
trained; the pipeline is prompted/configured only through deterministic
processing, not claimed fine-tuning.

Summary sections are generated from the validated extracted facts and patient
answers. Each section exposes `source_refs`; document sections also expose
review flags. Medication dose disagreements between the patient statement and
an uploaded document are presented as a conflict instead of being resolved
silently. The clinician record endpoint and review screen show the document
facts, source page, confidence, status, and review indicators.

The optional LLM section-polishing path is not used to replace the grounded
release summary. This prevents unsupported claims from entering the clinical
record. Red-flag detection remains independent and is never suppressed by
OCR uncertainty.

## Evaluation status

No external handwriting/document model has been downloaded or trained in this
environment. No clinical accuracy result is claimed.

The required OCR comparison (CER, WER, and field-level accuracy) and
summarization comparison (factuality, omission rate, ROUGE, and BERTScore)
remain **pending** because a verified, licensed, representative evaluation
corpus and ground-truth source spans were not available locally. Text-overlap
metrics must not be interpreted as clinical correctness. The existing test
suite contains software-only cases for negation, uncertainty, conflicting
medication doses, empty/poor OCR output, and API persistence; synthetic cases
are not evidence of clinical performance.

With a permissioned JSONL image/transcript set, the reproducible OCR comparison
is run with `python backend/scripts/evaluate_document_pipeline.py --pairs
<pairs.jsonl>`. It reports baseline raw Tesseract versus the proposed
preprocessed/page-aware path. Structured field accuracy still requires
annotated field references and is intentionally not inferred from text overlap.

Before deployment, a clinician-reviewed, permissioned test set must be added
with document-level and span-level references. Report baseline and proposed
systems on the same fixed, leakage-safe split, including the number of
documents/pages and confidence intervals where feasible. Clinical review and
local regulatory/privacy approval remain required.

## Structured laboratory findings

Uploaded laboratory results are emitted in the dedicated `Laboratory and Investigation
Findings` summary section. Each finding includes the test, value, normalized unit,
comparison interval, comparison state, report date, source document, source span,
explanation, uncertainty, and pending clinician-review status. A report-supplied
interval takes precedence. When a report omits an interval, the configured baseline
is explicitly disclosed and the finding still requires clinician confirmation; it is
not treated as a diagnosis or clearance.
