"""Verify the ACTUAL configuration against the deployment prerequisites. Exit code 1 if any BLOCKER fails.

    cd backend && PYTHONPATH=. python scripts/check_deployment_readiness.py [--json]

PASS means "this specific check passed", never "safe for real patients". Items that software cannot verify
(clinician sign-off, penetration test, legal review) are reported as MANUAL and always block until a person records them
in docs/CLINICAL_SIGNOFF.json.
"""
import json
import os
import stat
import sys
from pathlib import Path

from app import db, security
from app.redflag_engine import rules_manifest

ROOT = Path(__file__).resolve().parents[2]
SIGNOFF = ROOT / "docs" / "CLINICAL_SIGNOFF.json"


def checks():
    db.init()          # same schema bootstrap the app performs at startup
    out = []
    def add(id_, ok, detail, blocker=True, manual=False):
        out.append({"id": id_, "status": "MANUAL" if manual and not ok else "PASS" if ok else "FAIL", "blocker": blocker, "detail": detail})

    for p in security.production_problems():
        add("config:" + p.split()[0].lower(), False, p)
    if not security.production_problems():
        add("config:production", True, "doctor password, CORS origins and rate limiting configured")
    add("env:production_flag", security.is_production(), "MEDIKIOSK_ENV=production" if security.is_production() else "MEDIKIOSK_ENV is not 'production': startup enforcement is off")
    dbp = Path(db.DB_PATH)
    if dbp.exists():
        mode = stat.S_IMODE(dbp.stat().st_mode)
        add("db:file_permissions", not (mode & 0o077), f"{dbp.name} mode {oct(mode)} (must not be group/world accessible)")
    else:
        add("db:exists", True, "database not created yet", blocker=False)
    add("encryption_at_rest", os.environ.get("MEDIKIOSK_DISK_ENCRYPTION_CONFIRMED") == "yes",
        "NOT implemented in the application. Use an encrypted volume/disk and set MEDIKIOSK_DISK_ENCRYPTION_CONFIRMED=yes only after verifying it", manual=True)
    add("tls_termination", os.environ.get("MEDIKIOSK_TLS_CONFIRMED") == "yes",
        "TLS is terminated by a reverse proxy, not the app; set MEDIKIOSK_TLS_CONFIRMED=yes after verifying HTTPS-only access", manual=True)
    with db.tx() as c:
        has_audit = c.execute("SELECT name FROM sqlite_master WHERE name='audit_log'").fetchone() is not None
    add("audit_log_table", has_audit, "audit_log table present (metadata-only events)")
    add("rate_limiting", os.environ.get("MEDIKIOSK_RATE_LIMIT", "on").lower() != "off", "in-process limiter; a gateway limiter is needed for multi-worker deployments", blocker=False)
    unreviewed = [r["rule_id"] for r in rules_manifest() if r.get("review_status") != "approved"]
    signed = SIGNOFF.exists() and json.loads(SIGNOFF.read_text()).get("red_flag_rules_signed_off") is True
    add("clinician_signoff:red_flag_rules", signed, f"{len(unreviewed)} rule(s) not marked approved; record local clinician sign-off in docs/CLINICAL_SIGNOFF.json", manual=True)
    add("clinician_signoff:escalation_messages", SIGNOFF.exists() and json.loads(SIGNOFF.read_text()).get("escalation_messages_signed_off") is True,
        "every escalation message must be reviewed by a clinician", manual=True)
    add("security_review", SIGNOFF.exists() and json.loads(SIGNOFF.read_text()).get("security_review_done") is True, "independent security review / penetration test", manual=True)
    add("retention_policy", SIGNOFF.exists() and json.loads(SIGNOFF.read_text()).get("retention_policy_approved") is True, "data retention and erasure policy approved", manual=True)
    return out


if __name__ == "__main__":
    res = checks()
    if "--json" in sys.argv:
        print(json.dumps(res, indent=2))
    else:
        for r in res:
            print(f"[{r['status']:6}] {r['id']:40} {r['detail']}")
    blocked = [r for r in res if r["blocker"] and r["status"] != "PASS"]
    print(f"\n{len(blocked)} blocking item(s) remaining" if blocked else "\nno blocking items (this is NOT a clinical safety clearance)")
    sys.exit(1 if blocked else 0)
