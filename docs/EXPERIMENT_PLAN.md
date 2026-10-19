# Reproducible experiment plan

## Evaluation tracks

1. **Dialogue policy:** question duplication/loop rate, completion rate,
   turns-to-completion, slot coverage, and red-flag recall on held-out
   interview cases.
2. **OCR and extraction:** character error rate where transcripts exist,
   date/document-type accuracy, medication/lab entity precision, recall and
   F1, stratified by printed/handwritten and language.
3. **Summary:** clinician-rated factuality, completeness, unsupported-claim
   rate, and time-to-review. Compare deterministic output with optional
   rewording.
4. **Triage safety:** sensitivity and false-negative rate for emergency cases;
   deterministic rules remain the release gate.
5. **ASR and language:** word error rate and slot accuracy by language,
   code-mix, noise level, device and accent.

## Protocol

- Split by patient, never by turn or document.
- Freeze dataset manifests and record configuration, code revision, seed,
  runtime, model identifier and hardware.
- Report confidence intervals and missing/unknown/declined fields separately.
- Treat emergency false negatives as a blocking safety finding.
- Obtain clinician and ethics review before using real patient data.

## Reproducible commands

```powershell
cd backend
python -m pytest -q
```

The current repository provides deterministic runtime tests and EDA endpoints.
Training a clinical model is intentionally not claimed until the required
licensed corpora and labels are available and a versioned training command is
added.
