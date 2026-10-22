# MediKiosk architecture

```text
Patient kiosk / doctor console
              | REST / JSON
              v
           FastAPI
   +----------+------------------------+
   |                                   |
   v                                   v
HistoryTakingAgent                Document ingestion
   |                               PDF text: pypdf
   +-- structural questions        raster OCR: Tesseract*
   +-- mandatory safety questions  deterministic fact extraction
   +-- learned slot ranker*        source/page/confidence provenance
   +-- ontology fallback                 |
   |                                     v
   +--------------------------> Encounter evidence snapshot
                                         |
                                         v
                                  Deterministic summary
                                         |
                                         v
                                  RedFlagEngine rules
                                         |
                                         v
                                  Clinician review/approval

Consent/auth + SQLite protect patient data; FHIR export feeds mock ABDM.
* Optional: learned ranker is off by default; OCR needs a local Tesseract binary.
```

## Safety boundaries

- `ontology.py` is the authoritative question and emergency-rule policy.
- `history_agent.py` validates any adapter proposal against the policy
  question. Adapters cannot change question identity, type, options, or
  red-flag disposition.
- Stateful sessions use `/api/interview/sessions` and persist in SQLite;
  `/api/interview/next` remains a stateless compatibility endpoint.
- `summary.py` labels patient-reported information, extracted document
  evidence, and missing information. No trained report-generation model is
  integrated; `llm.py` is a separate optional adapter, not a fine-tuned model.
- The adaptive ranker can order eligible questions only after structural and
  mandatory safety questions. It cannot remove required questions and falls
  back to the ontology policy; the learned policy remains opt-in.
- A doctor must review and approve the draft record.

## Data flow

1. A patient authenticates or starts a guest session.
2. Consent is recorded before submission.
3. Answers are kept as structured fields and are never inferred when absent.
4. Batch PDF/image/text uploads are validated and processed per file.
   Originals, extracted text, structured facts, and processing status are
   stored under the patient account.
5. Submission snapshots each document and its extracted facts into the
   encounter. The submission report is then built from those persisted
   encounter snapshots, not temporary upload variables.
6. The deterministic red-flag engine runs independently of OCR, the adaptive
   ranker, and report wording. A failed screen is represented as unavailable,
   never as a clear result.
7. Report sections, red flags, and a draft FHIR bundle are stored on the
   encounter. Guest working documents are deleted only after the snapshots
   have been saved. Patients and doctors read the same encounter evidence;
   doctors can retrieve the retained original document.

## Model configuration

`HistoryTakingAgent` accepts an `LLMAdapter` implementation. The default
`DevelopmentAdapter` is local and deterministic. The intended “JEV” model
identifier, provider, licence, and access method remain unresolved; production
configuration must resolve those facts before enabling a network adapter.
