# Deployment readiness

Run `cd backend && PYTHONPATH=. python scripts/check_deployment_readiness.py`. It checks the **actual** environment and exits non-zero while anything blocking remains. PASS means one specific check passed, never "safe for patients".

| Control | State |
|---|---|
| Doctor-only access to `/api/eda/*` | **Fixed** (was unauthenticated; `/api/eda/ayush-analysis/{id}` returned patient answers by sequential id). Tested. |
| Audit trail (`audit_log`; `GET /api/admin/audit`, doctor only) | **Added.** Logins/failures, doctor list/view/review, erasure, rate-limit hits. Metadata only: never answers, report text or passwords. |
| Rate limiting | **Added**, in-process (20/min auth, 300/min API per IP, env-tunable). Use a gateway limiter for multi-worker deployments. |
| Production config enforcement | **Added.** `MEDIKIOSK_ENV=production` refuses to start with the demo doctor password, a short password, `*` CORS, or limiter off. |
| Encryption at rest | **Not implemented in the app.** Use an encrypted volume; confirm with `MEDIKIOSK_DISK_ENCRYPTION_CONFIRMED=yes`. |
| TLS | Reverse-proxy responsibility; confirm with `MEDIKIOSK_TLS_CONFIRMED=yes`. |
| Red-flag rules and escalation messages | **All 8 rules remain `provisional_pending_local_clinician_signoff`.** Record sign-off in `docs/CLINICAL_SIGNOFF.json` (template provided, everything `false`). |
| Security review, retention policy | Manual items; not done. |
| Session/credential hardening beyond the above (logout revocation, MFA, secret management) | Not addressed. |

Do not process real patient data until every MANUAL item has been completed by a responsible person.
