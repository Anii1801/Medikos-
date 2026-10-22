# Safety and privacy

MediKiosk is clinical decision support. It must not diagnose, prescribe, or
tell a patient to ignore warning signs. Emergency messages and triage rules
are informational signals for prioritisation and require clinician review.

## Controls implemented

- explicit consent is required for history capture; ABDM sharing is not an
  operational integration and is not offered as a consent purpose;
- patient and doctor APIs are role-protected;
- batch uploads validate file type and size, isolate per-file failures, and
  report extraction status rather than treating partial failures as success;
- originals are retained in the document store for patient access and copied
  into an encounter-scoped snapshot for clinical review; guest working copies
  are deleted after submission, while snapshots follow the record lifecycle;
- document originals are served only through authenticated owner or
  encounter-authorized download routes, not from a public filesystem path;
- DPDP-style erasure deletes document originals, encounter snapshots, and
  extracted evidence for the account;
- patient-reported facts are kept distinct from generated organisation;
- FHIR resources are marked preliminary and the doctor approves the record;
- DPDP-style erasure is available at `/api/me/data`;
- ABDM defaults to a mock adapter and refuses unconfigured live mode.
- RedFlagEngine keeps deterministic warnings independent from classifier output;
  rule failure fails safe to emergency human review.

## Deployment requirements

Before real data: HTTPS, secret management, encryption at rest, backups and a
defined retention period for encounter snapshots, audit logs, rate limiting, OTP/RBAC, access reviews, vendor
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
