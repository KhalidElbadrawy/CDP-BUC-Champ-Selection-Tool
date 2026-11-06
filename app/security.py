"""Version 2 access control.

* The CDP Change Lead is the only user of the tool. They sign in with a password
  (CDP_LEAD_PASSWORD) and get a signed, expiring session cookie.
* Each shortlisted candidate gets one personal assessment link. Raw tokens are shown to the
  Change Lead once; the database keeps only a SHA-256 hash. Links expire and can be revoked.
* State-changing forms carry an HMAC CSRF token.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from app import config, db

LEAD_COOKIE = "cdp_lead"
CAND_COOKIE = "cdp_candidate"
SESSION_HOURS = 12
_failed: dict[str, list[float]] = {}


def _sign(value: str) -> str:
    return hmac.new(config.settings.secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ------------------------------------------------------------------ Change Lead session
def lead_password() -> str:
    """Configured password; 'demo' is allowed only outside production (shown on the login page)."""
    from app import production
    if config.settings.lead_password:
        return config.settings.lead_password
    return "" if production.is_production() else "demo"


def check_password(submitted: str, client: str) -> bool:
    now = time.time()
    recent = [t for t in _failed.get(client, []) if now - t < 900]
    if len(recent) >= 5:
        raise HTTPException(429, "Too many attempts. Please wait 15 minutes and try again.")
    expected = lead_password()
    ok = bool(expected) and hmac.compare_digest(submitted.encode(), expected.encode())
    if not ok:
        recent.append(now)
        _failed[client] = recent
    else:
        _failed.pop(client, None)
    return ok


def make_session() -> str:
    expires = int(time.time()) + SESSION_HOURS * 3600
    payload = f"lead.{expires}.{secrets.token_hex(8)}"
    return f"{payload}.{_sign(payload)}"


def lead_ok(request: Request) -> bool:
    raw = request.cookies.get(LEAD_COOKIE, "")
    parts = raw.split(".")
    if len(parts) != 4:
        return False
    payload, sig = ".".join(parts[:3]), parts[3]
    if not hmac.compare_digest(sig, _sign(payload)):
        return False
    return int(parts[1]) > time.time()


def require_lead(request: Request) -> None:
    if not lead_ok(request):
        raise HTTPException(401, "login")


# ------------------------------------------------------------------ candidate links
@dataclass
class CandidateAccess:
    token_id: int
    candidate_id: int


class LinkError(Exception):
    def __init__(self, reason: str):
        self.reason = reason  # invalid | expired | revoked


def issue_link(candidate_id: int, days: int | None = None) -> str:
    """Revokes any earlier link for the candidate and returns a fresh raw token."""
    if days is None:
        from app.scoring import current_config
        days = int(current_config()[1]["link_expiry_days"].get("candidate", 30))
    db.ex("UPDATE tokens SET revoked_at=? WHERE candidate_id=? AND revoked_at IS NULL", (db.now(), candidate_id))
    raw = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()
    db.ex("INSERT INTO tokens(token_hash, candidate_id, raw_hint, expires_at, created_at) VALUES (?,?,?,?,?)",
          (_hash(raw), candidate_id, raw[-4:], expires, db.now()))
    return raw


def link_for(raw: str) -> str:
    return f"{config.settings.base_url}/a/{raw}"


def resolve(raw: str | None) -> CandidateAccess:
    if not raw:
        raise LinkError("invalid")
    row = db.q1("SELECT * FROM tokens WHERE token_hash=?", (_hash(raw),))
    if not row:
        raise LinkError("invalid")
    if row["revoked_at"]:
        raise LinkError("revoked")
    if row["expires_at"] < db.now():
        raise LinkError("expired")
    db.ex("UPDATE tokens SET last_used_at=? WHERE id=?", (db.now(), row["id"]))
    return CandidateAccess(row["id"], row["candidate_id"])


def require_candidate(request: Request) -> CandidateAccess:
    try:
        return resolve(request.cookies.get(CAND_COOKIE))
    except LinkError as e:
        raise HTTPException(401, e.reason)


def revoke_links(candidate_id: int) -> None:
    db.ex("UPDATE tokens SET revoked_at=? WHERE candidate_id=? AND revoked_at IS NULL", (db.now(), candidate_id))


# ------------------------------------------------------------------ CSRF
def csrf_token(request: Request) -> str:
    basis = request.cookies.get(LEAD_COOKIE) or request.cookies.get(CAND_COOKIE) or ""
    return _sign("csrf:" + basis)


def check_csrf(request: Request, submitted: str | None) -> None:
    if not submitted or not hmac.compare_digest(submitted, csrf_token(request)):
        raise HTTPException(403, "This form has expired. Please reload the page and try again.")
