# Document-to-summary pipeline

## Current release path

PDF, PNG, JPEG, WEBP, TIFF, and UTF-8 text uploads are accepted through the
document API. Multi-frame TIFF/WEBP input preserves page/frame numbers.
The batch endpoint accepts up to 10 files (8 MiB per file, 32 MiB total),
limits PDFs to 20 pages and images to 20 megapixels, and isolates validation
and extraction failures per file. PDF and image uploads are processed by
`backend/app/ocr.py`.

- PDF text is extracted page by page with `pdf-text` when an embedded text layer
  exists. Scanned pages attempt OCR from their embedded images; if no usable OCR
  is available, the document is marked failed for manual review and no text is
  fabricated.
- Images use the installed Tesseract executable when available. OCR word
  boxes and confidence values are retained in `entities.ocr_pages`.
- Supported upload bytes are retained in SQLite with their detected MIME type
  and SHA-256 digest. Downloads require patient ownership or access to the
  encounter snapshot; client-supplied paths and MIME types are not used.
- Each upload records `extracted`, `needs_review`, or `failed` status and an
  explanatory message when automated extraction cannot be used. Duplicate
  content is reported instead of silently adding another document.
- Submission copies each source document and extracted fact, including status,
  confidence, and source span, into encounter-scoped snapshot tables. The
  doctor-facing report is generated from those database snapshots, and guest
  working documents are deleted only after the record, report, and FHIR bundle
  have been stored. Patient and doctor APIs read the same encounter snapshots.
- Retained originals are included in account erasure. A production retention
  period and encryption-at-rest controls still need to be configured.
- Structured facts use the `clinical-facts-v1` schema. Facts include source
  offsets, page where known, bounding box where OCR provides one, confidence,
  and `reported`, `negated`, or `uncertain` status.
- Low-confidence, uncertain, negated, and ambiguous facts remain visible and
  carry `review_flags`. Missing values remain missing.
- An omitted lab unit is never filled from the configured baseline. Without a
  printed unit and interval, no comparison is made; with a printed interval,
  the report preserves it but marks the missing unit for clinician review.
  Multiple measurements are retained individually, and disagreement between
  entered and text-extracted report dates is exposed instead of silently
  resolved.

The models/components actually used by this implementation are the `pypdf`
embedded-text parser and the locally installed Tesseract executable (when
available), plus deterministic Python extraction rules. In the current test
environment Tesseract is unavailable, so the image integration test is
skipped and no OCR model result is reported. No neural document model was
trained; the pipeline is prompted/configured only through deterministic
processing, not claimed fine-tuning.

Summary sections are generated from the extracted facts and patient answers
after those facts have been reloaded from the encounter snapshot. Document
findings include source document IDs, filenames, source spans/pages, uncertainty,
and clinician-review status. Medication dose disagreements between the patient
statement and an uploaded document are presented as a conflict instead of
being resolved silently. The clinician record endpoint and review screen show
the report and evidence without dropping source metadata when a clinician
saves a review.

The optional LLM section-polishing path is not used to replace the grounded
release summary. This prevents unsupported claims from entering the clinical
record. Red-flag detection remains independent and is never suppressed by
OCR uncertainty.

## Evaluation status

No external handwriting/document model has been downloaded or trained in this
environment. No clinical accuracy result is claimed.

Verified synthetic PDF text-layer integration tests run through upload,
normalization, encounter persistence, report generation, guest cleanup, and
doctor retrieval. Real raster OCR comparison remains **blocked**: the current
macOS environment has no `tesseract` executable, and the repository contains
no source scans with human-verified ground truth. PNG/JPEG/WEBP/TIFF synthetic
OCR tests are explicitly skipped until Tesseract is available. Upload
acceptance and monkeypatched OCR tests are not counted as OCR accuracy.
Install on macOS with `brew install tesseract`; optionally add Hindi data with
`brew install tesseract-lang`, then verify with `tesseract --version` and
`tesseract --list-langs`. The software suite also covers negation, uncertainty,
conflicting medication doses, missing units, corrupted/unsupported files,
duplicate uploads, failed red-flag evaluation, and persisted evidence.

No CER, WER, or field-accuracy result is claimed for real OCR. Existing
text-level dataset measurements are synthetic/development-set checks, not
raster OCR performance. The required representative OCR comparison and
summarization comparison (factuality, omission rate, ROUGE, and BERTScore)
remain pending licensed ground-truth data. Text-overlap metrics must not be
interpreted as clinical correctness.

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
Findings` summary section. Each finding includes the test, value, reported unit
(null when absent), comparison interval, comparison state, report date, source document, source span,
explanation, uncertainty, and pending clinician-review status. A report-supplied
interval takes precedence. When a report omits an interval, the configured baseline
is considered only when a compatible unit is printed, is explicitly disclosed,
and still requires clinician confirmation; it is not treated as a diagnosis or
clearance.
