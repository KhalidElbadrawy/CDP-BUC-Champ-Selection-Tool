"""Scorecard, weighted scoring and threshold rules.

All scores and threshold checks are calculated HERE, in application code.
The AI only proposes criterion-level ratings with evidence; it never computes totals.

NOTE: weights and thresholds are PROPOSED settings that require pilot validation.
They are versioned (see programme_config) and every assessment records the version used.
"""
from __future__ import annotations

import copy
import json
from typing import Any

from app import db

CRITERIA: list[dict[str, Any]] = [
    {
        "key": "credibility", "name": "Credibility and constructive peer influence", "weight": 20,
        "evidence": "Colleagues seek help; influences others without relying on formal authority.",
        "question": "Describe a time colleagues changed a practice after your support. What did you do, and how do you know it helped?",
        "task": "text",
    },
    {
        "key": "empathy", "name": "Empathy and accessible communication", "weight": 20,
        "evidence": "Listens, checks understanding, adapts language, and avoids blame.",
        "question": "Complete a simulated exchange coaching a hesitant user through an unfamiliar approved task.",
        "task": "simulation",
    },
    {
        "key": "reliability", "name": "Reliability and follow-through", "weight": 20,
        "evidence": "Keeps commitments, records actions, and communicates delays early.",
        "question": "Describe an unresolved issue you followed through to referral or closure.",
        "task": "text",
    },
    {
        "key": "curiosity", "name": "Curiosity and learning agility", "weight": 15,
        "evidence": "Learns unfamiliar steps, asks useful questions, and revises assumptions.",
        "question": "Explain how you learned a recent process change and verified your understanding.",
        "task": "text",
    },
    {
        "key": "workflow", "name": "Business workflow capability", "weight": 15,
        "evidence": "Understands the task's purpose, main steps, exceptions, and referral points.",
        "question": "Complete a workflow simulation or structured walkthrough, explaining when to stop or refer.",
        "task": "walkthrough",
    },
    {
        "key": "judgment", "name": "Judgment and evidence quality", "weight": 10,
        "evidence": "Distinguishes skill gaps from access, defect, or policy issues and protects information.",
        "question": "A manager asks you to bypass a control so a user can finish. How do you respond?",
        "task": "text",
    },
]
CRITERION_KEYS = [c["key"] for c in CRITERIA]

RATING_SCALE = {
    1: "Submitted evidence demonstrates inadequate performance or an unsafe response (reason recorded separately).",
    2: "Evidence between inadequate and satisfactory.",
    3: "Satisfactory evidence in a relevant situation.",
    4: "Evidence between satisfactory and consistently strong.",
    5: "Repeated strong evidence and effective adaptation to different users.",
}

# Empathy simulation: scripted hesitant-user turns; the nominee writes their coaching replies.
EMPATHY_SIMULATION = [
    "I've done this on paper for twelve years. Why do I suddenly have to use the new platform?",
    "I pressed Submit and got a red error message. I think I've broken something.",
    "Can you just do it for me? I'll never remember all these steps.",
]
WORKFLOW_FIELDS = [
    ("purpose", "What is the purpose of the task, and who relies on the result?"),
    ("steps", "List the main steps a user follows on the platform."),
    ("exceptions", "What exceptions or problems commonly occur?"),
    ("stop_refer", "When would you stop and refer the user, and to whom (e.g. service desk, access administrator, policy owner)?"),
]

OUTCOME_MEETS = "Meets proposed assessment thresholds"
OUTCOME_NOT_YET = "Does not yet meet proposed assessment thresholds"
OUTCOME_EVIDENCE = "Additional evidence required"
OUTCOME_REMEDIATION = "Remediation and reassessment required"
OUTCOME_INCOMPLETE = "Incomplete—additional evidence required"

DEFAULT_CONFIG: dict[str, Any] = {
    "weights": {c["key"]: c["weight"] for c in CRITERIA},
    "overall_threshold": 70,
    "minimums": {"empathy": 3, "reliability": 3, "judgment": 3},
    "max_clarification_rounds": 2,
    "reminders": {"min_hours_between": 48, "max_per_stage": 3},
    "sla_days": {
        "Nominated": 2, "Awaiting Consent": 5, "Application in Progress": 10,
        "Submitted": 1, "Awaiting Evidence": 7, "Reassessment Required": 7,
        "Automated Assessment in Progress": 1, "Assessment Complete": 3,
        "Awaiting Manager Commitment": 5, "Awaiting Sponsor Decision": 7,
        "Provisionally Appointed": 5, "Onboarding": 21,
    },
    "link_expiry_days": {"lead": 7, "focal": 30, "sponsor": 14, "nominee": 30, "manager": 14},
    "retention_days": 365,
    "role_charter_version": "RC-1.0",
    "consent_version": "CONSENT-1.0",
    "label": "Proposed settings — require pilot validation",
}


def validate_config(cfg: dict[str, Any]) -> list[str]:
    errors = []
    weights = cfg.get("weights", {})
    if set(weights) != set(CRITERION_KEYS):
        errors.append("Weights must be defined for exactly the six scorecard criteria.")
    total = sum(float(v) for v in weights.values())
    if abs(total - 100) > 1e-9:
        errors.append(f"Weights must total 100% (currently {total:g}%).")
    if any(float(v) <= 0 for v in weights.values()):
        errors.append("Every weight must be greater than zero.")
    thr = cfg.get("overall_threshold", 0)
    if not (0 < float(thr) <= 100):
        errors.append("Overall threshold must be between 1 and 100.")
    for k, v in cfg.get("minimums", {}).items():
        if k not in CRITERION_KEYS or not (1 <= int(v) <= 5):
            errors.append(f"Invalid minimum rating for {k}.")
    if not (0 <= int(cfg.get("max_clarification_rounds", 2)) <= 5):
        errors.append("Clarification rounds must be between 0 and 5.")
    return errors


# ---------------------------------------------------------------- config store
def current_config() -> tuple[int, dict[str, Any]]:
    row = db.q1("SELECT version, data_json FROM config_versions ORDER BY version DESC LIMIT 1")
    if not row:
        version = save_config(copy.deepcopy(DEFAULT_CONFIG), note="Initial proposed settings", by="system")
        return version, copy.deepcopy(DEFAULT_CONFIG)
    return row["version"], json.loads(row["data_json"])


def get_config(version: int) -> dict[str, Any]:
    row = db.q1("SELECT data_json FROM config_versions WHERE version=?", (version,))
    return json.loads(row["data_json"]) if row else copy.deepcopy(DEFAULT_CONFIG)


def save_config(cfg: dict[str, Any], note: str, by: str) -> int:
    errors = validate_config(cfg)
    if errors:
        raise ValueError("; ".join(errors))
    version = db.ex("INSERT INTO config_versions(data_json, note, created_by, created_at) VALUES (?,?,?,?)",
                    (json.dumps(cfg), note, by, db.now()))
    db.audit("config.changed", actor_role="lead", actor_email=by, version=version, note=note)
    return version


# ---------------------------------------------------------------- scoring
def weighted_points(rating: int, weight: float) -> float:
    """Weighted points = (Rating / 5) x Criterion weight in points."""
    if not isinstance(rating, int) or not 1 <= rating <= 5:
        raise ValueError("Rating must be an integer from 1 to 5")
    return round(rating / 5 * float(weight), 2)


def _fmt(x: float) -> str:
    return f"{x:g}"


def score(final: dict[str, dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    """Compute the assessment result from moderated criterion ratings.

    `final[key]` = {"rating": int|None, "unsafe": bool, "unsafe_serious": bool, ...}
    A rating of None means "Not yet assessed" (never treated as 1).
    """
    weights = cfg["weights"]
    minimums = cfg.get("minimums", {})
    threshold = float(cfg["overall_threshold"])
    rows, earned, assessed_possible, unassessed = [], 0.0, 0.0, 0.0
    min_failures, unsafe_serious = [], []

    for c in CRITERIA:
        k = c["key"]
        w = float(weights[k])
        f = final.get(k) or {}
        rating = f.get("rating")
        row = {"key": k, "name": c["name"], "weight": w, "rating": rating,
               "rating_basis": f.get("rating_basis"), "minimum": minimums.get(k)}
        if rating is None:
            row.update(points=None, label="Not yet assessed")
            unassessed += w
        else:
            pts = weighted_points(int(rating), w)
            row.update(points=pts, label=f"{rating}/5")
            earned += pts
            assessed_possible += w
            if k in minimums and int(rating) < int(minimums[k]):
                min_failures.append(k)
        if f.get("unsafe_serious"):
            unsafe_serious.append(k)
        rows.append(row)

    earned = round(earned, 2)
    complete = unassessed == 0
    overall = earned if complete else None
    # Minimums can only be confirmed as met once each minimum criterion is assessed.
    minimums_assessed = all(final.get(k, {}).get("rating") is not None for k in minimums)
    minimums_met = minimums_assessed and not min_failures
    threshold_met = complete and earned >= threshold

    if unsafe_serious:
        outcome = OUTCOME_REMEDIATION
    elif not complete:
        outcome = OUTCOME_EVIDENCE
    elif threshold_met and minimums_met:
        outcome = OUTCOME_MEETS
    else:
        outcome = OUTCOME_NOT_YET

    if complete:
        score_text = f"{_fmt(earned)}/100"
    else:
        score_text = (f"{_fmt(earned)} points from {_fmt(assessed_possible)} assessed points; "
                      f"{_fmt(unassessed)} points remain unassessed.")
    return {
        "criteria": rows,
        "overall_score": overall,
        "earned_points": earned,
        "assessed_points": round(assessed_possible, 2),
        "unassessed_points": round(unassessed, 2),
        "complete": complete,
        "score_text": score_text,
        "threshold": threshold,
        "threshold_met": threshold_met,
        "minimum_failures": min_failures,
        "minimums_met": minimums_met,
        "unsafe_serious": unsafe_serious,
        "outcome": outcome,
        "evidence_coverage": f"{len(CRITERIA) - sum(1 for r in rows if r['rating'] is None)} of {len(CRITERIA)} criteria assessed",
    }
