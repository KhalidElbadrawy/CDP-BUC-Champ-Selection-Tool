"""SQLite persistence layer for version 2 (single Change Lead user)."""
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
  data_json TEXT NOT NULL, note TEXT, created_by TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS initiatives (          -- e.g. a platform release
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, platform TEXT, description TEXT,
  status TEXT NOT NULL DEFAULT 'active',          -- active | closed
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS initiative_steps (     -- the step tracker
  initiative_id INTEGER NOT NULL REFERENCES initiatives(id),
  step_no INTEGER NOT NULL,
  completed_at TEXT, note TEXT,
  PRIMARY KEY (initiative_id, step_no)
);
CREATE TABLE IF NOT EXISTS entities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL
);
CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref TEXT UNIQUE NOT NULL,
  initiative_id INTEGER NOT NULL REFERENCES initiatives(id),
  entity_id INTEGER REFERENCES entities(id),
  name TEXT NOT NULL, email TEXT,
  department TEXT, platform TEXT, workflow TEXT, route TEXT,
  nominator_name TEXT, nominator_email TEXT, reason TEXT,
  manager_name TEXT, manager_email TEXT,
  consent_screening INTEGER NOT NULL DEFAULT 0,   -- consent to AI screening, from the survey
  consent_assessment_at TEXT,                     -- confirmed by the nominee before phase 2
  source_row_json TEXT,
  status TEXT NOT NULL, status_changed_at TEXT NOT NULL,
  fit_ai TEXT,                                    -- AI fit category
  fit_final TEXT,                                 -- after any Change Lead override
  fit_override_reason TEXT,
  extra_time REAL NOT NULL DEFAULT 1.0,           -- reasonable adjustment for timed game
  assessment_mode TEXT,                           -- game | text | offline
  answers_json TEXT DEFAULT '{}',
  evidence_version INTEGER NOT NULL DEFAULT 0,
  clarification_rounds INTEGER NOT NULL DEFAULT 0,
  outcome TEXT,
  decision TEXT, decision_rationale TEXT, decided_at TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_cand_init ON candidates(initiative_id);
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  filename TEXT NOT NULL, stored_path TEXT, mime TEXT, size INTEGER, sha256 TEXT,
  extract_status TEXT NOT NULL, extract_error TEXT, extracted_text TEXT,
  uploaded_at TEXT NOT NULL, superseded INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS cv_screenings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  document_id INTEGER, mode TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  version INTEGER NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE(candidate_id, version)
);
CREATE TABLE IF NOT EXISTS assessments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  evidence_version INTEGER NOT NULL, config_version INTEGER NOT NULL,
  round_no INTEGER NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
  pass_a_json TEXT, pass_b_json TEXT, moderation_json TEXT, result_json TEXT,
  error TEXT, created_at TEXT NOT NULL, completed_at TEXT
);
CREATE TABLE IF NOT EXISTS clarifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  assessment_id INTEGER, round_no INTEGER NOT NULL,
  criterion TEXT NOT NULL, kind TEXT NOT NULL, question TEXT NOT NULL,
  response TEXT, responded_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS game_sessions (        -- NEXUS game (stage 2)
  candidate_id INTEGER PRIMARY KEY REFERENCES candidates(id),
  state_json TEXT, events_json TEXT DEFAULT '[]', outcome_json TEXT,
  started_at TEXT, completed_at TEXT
);
CREATE TABLE IF NOT EXISTS tokens (               -- candidate assessment links
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT UNIQUE NOT NULL,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  raw_hint TEXT,                                  -- last 4 chars, to recognise a link
  expires_at TEXT NOT NULL, revoked_at TEXT, created_at TEXT NOT NULL, last_used_at TEXT
);
CREATE TABLE IF NOT EXISTS import_mappings (
  id INTEGER PRIMARY KEY CHECK (id = 1), mapping_json TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT NOT NULL, actor TEXT, action TEXT NOT NULL,
  candidate_id INTEGER, initiative_id INTEGER, detail_json TEXT
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


def audit(action: str, *, actor: str = "system", candidate_id: int | None = None,
          initiative_id: int | None = None, **detail: Any) -> None:
    ex("INSERT INTO audit(at, actor, action, candidate_id, initiative_id, detail_json) VALUES (?,?,?,?,?,?)",
       (now(), actor, action, candidate_id, initiative_id, json.dumps(detail, default=str)))


def init_db() -> None:
    with tx() as c:
        c.executescript(SCHEMA)
