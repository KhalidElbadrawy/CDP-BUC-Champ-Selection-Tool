"""Passwordless, role-scoped access links.

* Raw tokens are only ever emailed; the database stores a SHA-256 hash.
* Every token is scoped to one role and (where relevant) one entity or one application.
* Tokens expire and can be revoked. Opening a link that was emailed to an address is the
  proof of email ownership required before any private information is shown.
* The browser keeps the raw token in an HttpOnly, SameSite=Lax cookie; every request is
  re-validated on the server. State-changing forms also carry an HMAC CSRF token.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from app import config, db

COOKIE = "cdp_access"
ROLES = ("lead", "focal", "sponsor", "nominee", "manager")


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class Principal:
    token_id: int
    role: str
    email: str
    entity_id: int | None
    application_id: int | None

    @property
    def is_lead(self) -> bool:
        return self.role == "lead"


def issue_token(role: str, email: str, *, entity_id: int | None = None,
                application_id: int | None = None, days: int | None = None) -> str:
    if role not in ROLES:
        raise ValueError(role)
    if role in ("focal", "sponsor") and entity_id is None:
        raise ValueError("Entity roles must be scoped to an entity")
    if role in ("nominee", "manager") and application_id is None:
        raise ValueError("Individual links must be scoped to an application")
    if days is None:
        from app.scoring import current_config
        days = int(current_config()[1]["link_expiry_days"].get(role, 14))
    raw = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()
    db.ex("INSERT INTO tokens(token_hash, role, email, entity_id, application_id, expires_at, created_at) VALUES (?,?,?,?,?,?,?)",
          (_hash(raw), role, email.lower(), entity_id, application_id, expires, db.now()))
    return raw


def link_for(raw: str) -> str:
    return f"{config.settings.base_url}/a/{raw}"


class LinkError(Exception):
    def __init__(self, reason: str):
        self.reason = reason  # expired | revoked | invalid | withdrawn


def resolve(raw: str | None) -> Principal:
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
    return Principal(row["id"], row["role"], row["email"], row["entity_id"], row["application_id"])


def revoke(token_id: int) -> None:
    db.ex("UPDATE tokens SET revoked_at=? WHERE id=? AND revoked_at IS NULL", (db.now(), token_id))


def revoke_for_application(application_id: int, role: str | None = None) -> None:
    sql = "UPDATE tokens SET revoked_at=? WHERE application_id=? AND revoked_at IS NULL"
    args: list = [db.now(), application_id]
    if role:
        sql += " AND role=?"
        args.append(role)
    db.ex(sql, args)


def current(request: Request) -> Principal:
    try:
        return resolve(request.cookies.get(COOKIE))
    except LinkError as e:
        raise HTTPException(status_code=401, detail=e.reason)


def require(request: Request, *roles: str) -> Principal:
    p = current(request)
    if roles and p.role not in roles:
        raise HTTPException(status_code=403, detail="This link does not permit that action.")
    return p


def csrf_token(request: Request) -> str:
    raw = request.cookies.get(COOKIE, "")
    return hmac.new(config.settings.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()


def check_csrf(request: Request, submitted: str | None) -> None:
    if not submitted or not hmac.compare_digest(submitted, csrf_token(request)):
        raise HTTPException(status_code=403, detail="Form expired. Please reload the page and try again.")


# ------------------------------------------------------------- record-level checks
def can_view_application(p: Principal, app: dict) -> bool:
    if p.role == "lead":
        return True
    if p.role in ("focal", "sponsor"):
        return app["entity_id"] == p.entity_id
    if p.role in ("nominee", "manager"):
        return app["id"] == p.application_id
    return False


def can_view_private_evidence(p: Principal, app: dict) -> bool:
    """CVs and detailed evidence: nominee + authorised central users + explicit grants."""
    if p.role == "lead":
        return True
    if p.role == "nominee" and p.application_id == app["id"]:
        return True
    grant = db.q1("SELECT 1 FROM access_grants WHERE application_id=? AND grantee_email=? AND revoked_at IS NULL",
                  (app["id"], p.email))
    return bool(grant) and can_view_application(p, app)


def assert_application(p: Principal, app: dict | None) -> dict:
    if not app or not can_view_application(p, app):
        # 404, not 403: do not reveal whether the record exists.
        raise HTTPException(status_code=404, detail="Record not found for this link.")
    return app
