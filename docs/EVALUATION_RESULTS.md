# Evaluation results

These are software and data-integrity results, not clinical validation.

- Existing clinical-report/API focused tests passed in the repository test run;
  the image OCR integration test is skipped when Tesseract is unavailable.
- Laboratory regression tests cover explicit report intervals, configured
  baseline disclosure, source spans, and pending clinician review.
- Dataset preparation enforces schemas, group splits, and duplicate leakage
  detection.

Adaptive next-slot accuracy, complaint/language subgroup performance, real-image
OCR CER/WER, entity F1, critical-result recall, summary factuality, and clinical
red-flag sensitivity require permissioned annotated held-out data. The bundled
synthetic and text-level resources cannot support those claims.
