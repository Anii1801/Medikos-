# Safety and privacy

MediKiosk is clinical decision support. It must not diagnose, prescribe, or
tell a patient to ignore warning signs. Emergency messages and triage rules
are informational signals for prioritisation and require clinician review.

## Controls implemented

- consent is required for history capture and ABDM sharing;
- patient and doctor APIs are role-protected;
- guest documents are deleted after submission;
- uploaded image bytes are processed in memory;
- patient-reported facts are kept distinct from generated organisation;
- FHIR resources are marked preliminary and the doctor approves the record;
- DPDP-style erasure is available at `/api/me/data`;
- ABDM defaults to a mock adapter and refuses unconfigured live mode.
- RedFlagEngine keeps deterministic warnings independent from classifier output;
  rule failure fails safe to emergency human review.

## Deployment requirements

Before real data: HTTPS, secret management, encryption at rest, backups and
retention policy, audit logs, rate limiting, OTP/RBAC, access reviews, vendor
and data-processing agreements, threat modelling, clinical validation, and a
documented incident/rollback process are required.

Do not log access tokens, passwords, ABHA identifiers, raw medical documents,
or model prompts containing identifiable health information. Validate all
clinical reference tables and red-flag rules with qualified clinicians.
The current RedFlagEngine rules are explicitly marked
`provisional_pending_local_clinician_signoff`; they are not clinically approved.


## Addendum 2026-10-17
- A failed or unavailable red-flag screen is displayed as such, escalates queue priority, and is never shown as "no red flags".
- Red-flag next-step wording is provisional pending local clinician sign-off; the UI shows this per finding.
- Summaries are labelled draft/unreviewed until a clinician approves; rejected records are never labelled approved.
- Open: remove the unvalidated "ML Analysis / Probable conditions" panel; change default doctor credentials; add rate limiting, audit logging and encryption at rest before real patient data.
