"""Deployment hardening: audit trail, rate limiting and production-config enforcement.

What this is: baseline controls that make misuse visible and brute force expensive.
What this is NOT: a security review. Encryption at rest, TLS termination, secret management, backups and
retention are deployment responsibilities, checked (not provided) by scripts/check_deployment_readiness.py.
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict, deque
from typing import Any

from starlette.responses import JSONResponse

from . import db

DEFAULT_DOCTOR_PASS = "doctor123"


def is_production() -> bool:
    return os.environ.get("MEDIKIOSK_ENV", "development").strip().lower() == "production"


def production_problems() -> list[str]:
    """Configuration that must not reach a real-patient deployment."""
    problems = []
    if os.environ.get("DOCTOR_PASS", DEFAULT_DOCTOR_PASS) in ("", DEFAULT_DOCTOR_PASS):
        problems.append("DOCTOR_PASS is unset or the public demo default")
    if len(os.environ.get("DOCTOR_PASS", "")) < 12:
        problems.append("DOCTOR_PASS shorter than 12 characters")
    if os.environ.get("MEDIKIOSK_CORS_ORIGINS", "*").strip() in ("", "*"):
        problems.append("MEDIKIOSK_CORS_ORIGINS is '*' (list the real front-end origin)")
    if os.environ.get("MEDIKIOSK_RATE_LIMIT", "on").lower() == "off":
        problems.append("rate limiting is switched off")
    return problems


def enforce_production_config() -> None:
    if is_production() and (problems := production_problems()):
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))


# ------------------------------------------------------------------------------------------ audit trail
def audit(event: str, *, actor_id: int | None = None, role: str | None = None, target: str | None = None,
          detail: dict[str, Any] | None = None, ip: str | None = None) -> None:
    """Append one audit event. ``detail`` must carry metadata only (ids, counts, outcome): never answers, report text or names."""
    try:
        with db.tx() as c:
            c.execute("INSERT INTO audit_log(ts,event,actor_id,role,target,detail,ip) VALUES(?,?,?,?,?,?,?)",
                      (time.time(), event, actor_id, role, target, json.dumps(detail or {}, ensure_ascii=False), ip))
    except Exception:                       # auditing must never break clinical workflow; the failure itself is visible in logs
        import logging
        logging.getLogger("medikiosk.audit").exception("audit write failed for %s", event)


# ------------------------------------------------------------------------------------------ rate limiting
class RateLimitMiddleware:
    """Sliding-window limiter per client IP. Authentication endpoints get a much lower budget (credential guessing).
    In-memory and per-process: put a shared limiter (reverse proxy / gateway) in front for multi-worker deployments."""

    AUTH_PATHS = ("/api/auth/login", "/api/auth/register", "/api/auth/guest")

    def __init__(self, app, auth_per_min: int = 20, api_per_min: int = 300, enabled: bool = True):
        self.app, self.auth_limit, self.api_limit, self.enabled = app, auth_per_min, api_per_min, enabled
        self.hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self.lock = threading.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.enabled or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        ip = (scope.get("client") or ("unknown", 0))[0]
        bucket, limit = ("auth", self.auth_limit) if scope["path"] in self.AUTH_PATHS else ("api", self.api_limit)
        now = time.monotonic()
        with self.lock:
            q = self.hits[(ip, bucket)]
            while q and now - q[0] > 60:
                q.popleft()
            allowed = len(q) < limit
            if allowed:
                q.append(now)
            retry = int(60 - (now - q[0])) + 1 if q else 1
        if not allowed:
            audit("rate_limited", target=bucket, ip=ip)
            resp = JSONResponse({"detail": "Too many requests"}, status_code=429, headers={"Retry-After": str(retry)})
            return await resp(scope, receive, send)
        return await self.app(scope, receive, send)
