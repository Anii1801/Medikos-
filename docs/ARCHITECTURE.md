# MediKiosk architecture

```text
Patient kiosk / doctor console
              |
          REST / JSON
              v
FastAPI main.py
  |-- HistoryTakingAgent -> ontology policy -> red-flag rules
  |-- OCR and extraction -> document timeline/interactions
  |-- summary builder -> optional fact-preserving LLM rewording
  |-- consent/auth/SQLite
  `-- FHIR bundle -> mock ABDM adapter
```

## Safety boundaries

- `ontology.py` is the authoritative question and emergency-rule policy.
- `history_agent.py` validates any adapter proposal against the policy
  question. Adapters cannot change question identity, type, options, or
  red-flag disposition.
- Stateful sessions use `/api/interview/sessions` and persist in SQLite;
  `/api/interview/next` remains a stateless compatibility endpoint.
- `summary.py` labels patient-reported information and missing information;
  `llm.py` is disabled without an API key and is instructed to use only
  supplied facts.
- A doctor must review and approve the draft record.

## Data flow

1. A patient authenticates or starts a guest session.
2. Consent is recorded before submission.
3. Answers are kept as structured fields and are never inferred when absent.
4. Uploaded bytes are processed in memory; extracted text and entities are
   stored, not the original image bytes.
5. Red flags are calculated independently from summary wording.
6. Submission creates a draft FHIR document and a mock ABDM reference.
7. Guest documents are deleted after submission; the doctor record remains.

## Model configuration

`HistoryTakingAgent` accepts an `LLMAdapter` implementation. The default
`DevelopmentAdapter` is local and deterministic. The intended “JEV” model
identifier, provider, licence, and access method remain unresolved; production
configuration must resolve those facts before enabling a network adapter.
