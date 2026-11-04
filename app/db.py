"""SQLite persistence layer (swap for PostgreSQL in production; SQL is portable)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS config_versions (
  version INTEGER PRIMARY KEY AUTOINCREMENT,
  data_json TEXT NOT NULL,
  note TEXT,
  created_by TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rounds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',      -- draft | open | closed
  opens_on TEXT, closes_on TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE NOT NULL,
  name_en TEXT NOT NULL, name_ar TEXT,
  slug TEXT UNIQUE NOT NULL,                 -- entity-specific shared nomination link
  target INTEGER NOT NULL DEFAULT 2,
  priority_platforms TEXT DEFAULT '',        -- comma separated
  workflows TEXT DEFAULT '', user_groups TEXT DEFAULT '',
  locations TEXT DEFAULT '', capacity_needs TEXT DEFAULT '',
  coverage_notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS contacts (       -- centrally assigned privileged roles
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_id INTEGER REFERENCES entities(id),
  role TEXT NOT NULL,                        -- focal | sponsor
  name TEXT NOT NULL, email TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref TEXT UNIQUE NOT NULL,
  round_id INTEGER REFERENCES rounds(id),
  entity_id INTEGER NOT NULL REFERENCES entities(id),
  nominee_name TEXT NOT NULL, nominee_email TEXT NOT NULL,
  department TEXT, business_function TEXT, location TEXT,
  platform TEXT, workflow TEXT,
  route TEXT NOT NULL,                       -- self | peer | manager
  nominator_name TEXT, nominator_email TEXT, nominator_relationship TEXT,
  reason TEXT,
  manager_name TEXT, manager_email TEXT,
  status TEXT NOT NULL,
  status_changed_at TEXT NOT NULL,
  consent_at TEXT, consent_version TEXT,
  extracted_json TEXT DEFAULT '{}',          -- CV extraction, nominee-corrected
  answers_json TEXT DEFAULT '{}',
  availability TEXT, proposed_hours REAL,
  submitted_at TEXT,
  evidence_version INTEGER NOT NULL DEFAULT 0,
  clarification_rounds INTEGER NOT NULL DEFAULT 0,
  outcome TEXT,                              -- latest assessment outcome label
  outcome_communicated_at TEXT,
  candidate_willing INTEGER,                 -- continued willingness at capacity stage
  reconsideration_request TEXT,
  withdrawn_at TEXT, withdrawn_reason TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_app_entity ON applications(entity_id);
CREATE INDEX IF NOT EXISTS ix_app_email ON applications(nominee_email);
CREATE TABLE IF NOT EXISTS nomination_events (  -- every nomination received, incl. duplicates
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  application_id INTEGER REFERENCES applications(id),
  route TEXT, nominator_name TEXT, nominator_email TEXT, reason TEXT,
  duplicate INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  application_id INTEGER NOT NULL REFERENCES applications(id),
  filename TEXT NOT NULL, stored_path TEXT, mime TEXT, size INTEGER, sha256 TEXT,
  extract_status TEXT NOT NULL,              -- ok | unreadable | unsupported | deleted
  extract_error TEXT, extracted_text TEXT,
  uploaded_at TEXT NOT NULL, superseded INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS cv_screenings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  application_id INTEGER NOT NULL REFERENCES applications(id),
  document_id INTEGER REFERENCES documents(id),
  mode TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_versions (  -- immutable snapshots used for assessment
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  application_id INTEGER NOT NULL REFERENCES applications(id),
  version INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE(application_id, version)
);
CREATE TABLE IF NOT EXISTS assessments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  application_id INTEGER NOT NULL REFERENCES applications(id),
  evidence_version INTEGER NOT NULL,
  config_version INTEGER NOT NULL,
  round_no INTEGER NOT NULL,                 -- 0 = initial, 1..2 = clarification/reassessment
  mode TEXT NOT NULL,                        -- live | demo
  status TEXT NOT NULL,                      -- running | complete | failed
  pass_a_json TEXT, pass_b_json TEXT,
  moderation_json TEXT, result_json TEXT,
  error TEXT,
  created_at TEXT NOT NULL, completed_at TEXT
);
CREATE TABLE IF NOT EXISTS clarifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  application_id INTEGER NOT NULL REFERENCES applications(id),
  assessment_id INTEGER REFERENCES assessments(id),
  round_no INTEGER NOT NULL,
  criterion TEXT NOT NULL,
  kind TEXT NOT NULL,                        -- clarification | remediation
  question TEXT NOT NULL,
  response TEXT, responded_at TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS manager_commitments (
  application_id INTEGER PRIMARY KEY REFERENCES applications(id),
  manager_email TEXT,
  protected_hours REAL, workload TEXT, availability TEXT,
  access_confirmed INTEGER NOT NULL DEFAULT 0, access_actions TEXT,
  supports INTEGER NOT NULL DEFAULT 1,
  submitted_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sponsor_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  application_id INTEGER NOT NULL REFERENCES applications(id),
  sponsor_email TEXT, decision TEXT NOT NULL, rationale TEXT NOT NULL,
  coverage_need TEXT, coi_declared INTEGER NOT NULL, coi_details TEXT,
  conditions TEXT, decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS onboarding (
  application_id INTEGER PRIMARY KEY REFERENCES applications(id),
  accepted_at TEXT, charter_version TEXT,
  buddy TEXT, checklist_json TEXT DEFAULT '{}', objective TEXT,
  start_date TEXT, day90_date TEXT
);
CREATE TABLE IF NOT EXISTS day90_reviews (
  application_id INTEGER PRIMARY KEY REFERENCES applications(id),
  nominee_json TEXT, nominee_at TEXT,
  manager_json TEXT, manager_at TEXT,
  outcome TEXT, rationale TEXT, decided_by TEXT, decided_at TEXT
);
CREATE TABLE IF NOT EXISTS tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT UNIQUE NOT NULL,
  role TEXT NOT NULL,                        -- lead | focal | sponsor | nominee | manager
  email TEXT NOT NULL,
  entity_id INTEGER, application_id INTEGER,
  expires_at TEXT NOT NULL, revoked_at TEXT,
  created_at TEXT NOT NULL, last_used_at TEXT
);
CREATE TABLE IF NOT EXISTS access_grants (  -- explicit extra access to CVs/evidence
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  application_id INTEGER NOT NULL, grantee_email TEXT NOT NULL,
  granted_by TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL, revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS email_templates (
  key TEXT PRIMARY KEY,
  subject_en TEXT NOT NULL, body_en TEXT NOT NULL,
  subject_ar TEXT, body_ar TEXT,
  focal_may_send INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS emails (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  application_id INTEGER, entity_id INTEGER,
  template TEXT NOT NULL, to_email TEXT NOT NULL,
  subject TEXT NOT NULL, body TEXT NOT NULL,
  is_reminder INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,                      -- sent | demo-logged | failed | suppressed
  error TEXT, triggered_by TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL, actor_role TEXT, actor_email TEXT,
  action TEXT NOT NULL, application_id INTEGER, entity_id INTEGER,
  detail_json TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    Path(config.settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.settings.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def q(sql: str, args: tuple | list = ()) -> list[dict[str, Any]]:
    with tx() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def q1(sql: str, args: tuple | list = ()) -> dict[str, Any] | None:
    rows = q(sql, args)
    return rows[0] if rows else None


def ex(sql: str, args: tuple | list = ()) -> int:
    with tx() as c:
        cur = c.execute(sql, args)
        return cur.lastrowid


def audit(action: str, *, actor_role: str | None = None, actor_email: str | None = None,
          application_id: int | None = None, entity_id: int | None = None, **detail: Any) -> None:
    ex("INSERT INTO audit(at, actor_role, actor_email, action, application_id, entity_id, detail_json) VALUES (?,?,?,?,?,?,?)",
       (now(), actor_role, actor_email, action, application_id, entity_id, json.dumps(detail, default=str)))


def init_db() -> None:
    with tx() as c:
        c.executescript(SCHEMA)
