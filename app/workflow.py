"""End-to-end nomination, assessment and appointment workflow (server-side rules)."""
from __future__ import annotations

import asyncio
import json
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app import ai, config, db, emails, extraction, scoring, security

STATUSES = [
    "Nominated", "Awaiting Consent", "Application in Progress", "Submitted", "Awaiting Evidence",
    "Automated Assessment in Progress", "Reassessment Required", "Assessment Complete",
    "Awaiting Manager Commitment", "Awaiting Sponsor Decision", "Provisionally Appointed", "Onboarding",
    "Awaiting Day-90 Review", "Confirmed", "Appointment Concluded", "Withdrawn", "Not Selected",
]
TERMINAL = {"Confirmed", "Appointment Concluded", "Withdrawn", "Not Selected"}
APPOINTED = {"Provisionally Appointed", "Onboarding", "Awaiting Day-90 Review", "Confirmed"}
ONBOARDING_CHECKLIST = ["Role charter accepted", "Buddy introduced", "Champion induction completed",
                        "Platform access verified", "Initial workflow objective agreed"]


class WorkflowError(Exception):
    """A business rule prevented the action. Message is safe to show to the user."""


# ------------------------------------------------------------------ helpers
def get_app(app_id: int) -> dict | None:
    return db.q1("SELECT a.*, e.name_en AS entity_name, e.name_ar AS entity_name_ar FROM applications a "
                 "JOIN entities e ON e.id=a.entity_id WHERE a.id=?", (app_id,))


def set_status(app_id: int, status: str, actor: str = "system", **detail) -> None:
    assert status in STATUSES, status
    db.ex("UPDATE applications SET status=?, status_changed_at=?, updated_at=? WHERE id=?",
          (status, db.now(), db.now(), app_id))
    db.audit("status." + status, actor_role=actor, application_id=app_id, **detail)


def _due(start_iso: str, days: int) -> str:
    return (datetime.fromisoformat(start_iso) + timedelta(days=days)).date().isoformat()


def contacts(entity_id: int, role: str) -> list[dict]:
    return db.q("SELECT * FROM contacts WHERE entity_id=? AND role=? AND active=1", (entity_id, role))


def _ensure_active(app: dict) -> None:
    if app["status"] == "Withdrawn" or app.get("withdrawn_at"):
        raise WorkflowError("This application has been withdrawn.")


def _expires(role: str) -> str:
    days = scoring.current_config()[1]["link_expiry_days"].get(role, 14)
    return (date.today() + timedelta(days=int(days))).isoformat()


def _ctx(app: dict, **extra) -> dict:
    return {"nominee_name": app["nominee_name"], "entity": app.get("entity_name", ""), "ref": app["ref"],
            "manager_name": app.get("manager_name") or "", **extra}


def send_nominee_link(app: dict, template: str, *, is_reminder=False, triggered_by="system", due: str = "") -> dict:
    raw = security.issue_token("nominee", app["nominee_email"], application_id=app["id"])
    res = emails.send(template, app["nominee_email"],
                      _ctx(app, link=security.link_for(raw), expires=_expires("nominee"), due=due),
                      application=app, is_reminder=is_reminder, triggered_by=triggered_by)
    _record_delivery(app["id"], res)
    res["link"] = security.link_for(raw)
    return res


def send_manager_link(app: dict, *, is_reminder=False, triggered_by="system") -> dict:
    if not app.get("manager_email"):
        raise WorkflowError("No line-manager email is recorded for this application.")
    raw = security.issue_token("manager", app["manager_email"], application_id=app["id"])
    nxt = next_action(app)
    res = emails.send("manager_request", app["manager_email"],
                      _ctx(app, link=security.link_for(raw), expires=_expires("manager"), due=nxt["due"] or ""),
                      application=app, is_reminder=is_reminder, triggered_by=triggered_by)
    _record_delivery(app["id"], res)
    res["link"] = security.link_for(raw)
    return res


def send_sponsor_links(entity_id: int, triggered_by="system") -> list[dict]:
    out = []
    ent = db.q1("SELECT * FROM entities WHERE id=?", (entity_id,))
    for s in contacts(entity_id, "sponsor"):
        raw = security.issue_token("sponsor", s["email"], entity_id=entity_id)
        res = emails.send("sponsor_request", s["email"],
                          {"entity": ent["name_en"], "link": security.link_for(raw), "expires": _expires("sponsor")},
                          entity_id=entity_id, triggered_by=triggered_by)
        res["link"] = security.link_for(raw)
        out.append(res)
    return out


def _record_delivery(app_id: int, res: dict) -> None:
    if res["status"] == "failed":
        db.ex("UPDATE applications SET last_error=? WHERE id=?",
              (f"Email delivery failed ({res['error']}). Progress is saved; resend the link when email is available.", app_id))
    elif res["status"] in ("sent", "demo-logged"):
        db.ex("UPDATE applications SET last_error=NULL WHERE id=? AND last_error LIKE 'Email delivery failed%'", (app_id,))


# ------------------------------------------------------------------ nomination
def new_ref() -> str:
    return "CDP-" + secrets.token_hex(3).upper()


def create_nomination(entity: dict, form: dict, actor: str = "public") -> tuple[dict, bool]:
    """Returns (application, is_duplicate). Duplicates are recorded as extra nomination events."""
    email = form["nominee_email"].strip().lower()
    route = form["route"]
    if route not in ("self", "peer", "manager"):
        raise WorkflowError("Choose a nomination route.")
    rnd = db.q1("SELECT * FROM rounds WHERE status='open' ORDER BY id DESC LIMIT 1")
    if not rnd:
        raise WorkflowError("Nominations are not currently open.")
    existing = db.q1("SELECT id FROM applications WHERE lower(nominee_email)=? AND round_id=? AND status NOT IN ('Withdrawn')",
                     (email, rnd["id"]))
    if existing:
        db.ex("INSERT INTO nomination_events(application_id, route, nominator_name, nominator_email, reason, duplicate, created_at) VALUES (?,?,?,?,?,1,?)",
              (existing["id"], route, form.get("nominator_name"), form.get("nominator_email"), form.get("reason"), db.now()))
        db.audit("nomination.duplicate", actor_role=actor, application_id=existing["id"], entity_id=entity["id"], route=route)
        return get_app(existing["id"]), True
    ts = db.now()
    app_id = db.ex(
        "INSERT INTO applications(ref, round_id, entity_id, nominee_name, nominee_email, department, business_function, location, "
        "platform, workflow, route, nominator_name, nominator_email, nominator_relationship, reason, manager_name, manager_email, "
        "status, status_changed_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (new_ref(), rnd["id"], entity["id"], form["nominee_name"].strip(), email, form.get("department"), form.get("business_function"),
         form.get("location"), form.get("platform"), form.get("workflow"), route,
         None if route == "self" else form.get("nominator_name"), None if route == "self" else form.get("nominator_email"),
         None if route == "self" else form.get("nominator_relationship"), form.get("reason"),
         form.get("manager_name"), (form.get("manager_email") or "").strip().lower() or None, "Nominated", ts, ts, ts))
    db.ex("INSERT INTO nomination_events(application_id, route, nominator_name, nominator_email, reason, created_at) VALUES (?,?,?,?,?,?)",
          (app_id, route, form.get("nominator_name"), form.get("nominator_email"), form.get("reason"), ts))
    db.audit("nomination.created", actor_role=actor, application_id=app_id, entity_id=entity["id"], route=route)
    app = get_app(app_id)
    # Every route (incl. self) receives an emailed link: opening it verifies email ownership,
    # and consent is collected before any CV is requested or assessment begins.
    res = send_nominee_link(app, "consent_request")
    if res["status"] in ("sent", "demo-logged"):
        set_status(app_id, "Awaiting Consent")
    return get_app(app_id), False


def record_consent(app: dict, give: bool, actor_email: str) -> None:
    _ensure_active(app)
    if app["status"] not in ("Nominated", "Awaiting Consent"):
        return
    if give:
        ver = scoring.current_config()[1]["consent_version"]
        db.ex("UPDATE applications SET consent_at=?, consent_version=? WHERE id=?", (db.now(), ver, app["id"]))
        db.audit("consent.given", actor_role="nominee", actor_email=actor_email, application_id=app["id"], version=ver)
        set_status(app["id"], "Application in Progress", "nominee")
    else:
        withdraw(app, "Nominee declined consent", "nominee", actor_email)


# ------------------------------------------------------------------ application
def save_application(app: dict, data: dict) -> None:
    _ensure_active(app)
    if app["status"] not in ("Application in Progress",):
        raise WorkflowError("The application can no longer be edited at this stage.")
    answers = json.loads(app["answers_json"] or "{}")
    answers.update(data.get("answers", {}))
    extracted = json.loads(app["extracted_json"] or "{}")
    if "extracted" in data:
        extracted.update(data["extracted"])
        extracted["corrected_by_nominee"] = True
    db.ex("UPDATE applications SET answers_json=?, extracted_json=?, availability=?, proposed_hours=?, updated_at=? WHERE id=?",
          (json.dumps(answers), json.dumps(extracted), data.get("availability", app["availability"]),
           data.get("proposed_hours", app["proposed_hours"]), db.now(), app["id"]))
    db.audit("application.saved", actor_role="nominee", application_id=app["id"])


async def upload_cv(app: dict, filename: str, data: bytes) -> dict:
    _ensure_active(app)
    if not app["consent_at"]:
        raise WorkflowError("Consent is required before a CV can be uploaded.")
    if app["status"] not in ("Application in Progress", "Awaiting Evidence"):
        raise WorkflowError("A CV cannot be uploaded at this stage.")
    res = extraction.extract(filename, data)
    stored = None
    if res.status in ("ok", "unreadable"):
        folder = Path(config.settings.upload_dir) / str(app["id"])
        folder.mkdir(parents=True, exist_ok=True)
        stored = str(folder / f"{secrets.token_hex(8)}{Path(filename).suffix.lower()}")
        Path(stored).write_bytes(data)
    db.ex("UPDATE documents SET superseded=1 WHERE application_id=?", (app["id"],))
    doc_id = db.ex("INSERT INTO documents(application_id, filename, stored_path, mime, size, sha256, extract_status, extract_error, extracted_text, uploaded_at) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (app["id"], Path(filename).name[:200], stored, extraction.ALLOWED.get(Path(filename).suffix.lower()),
                    len(data), extraction.sha256(data), res.status, res.error, res.text, db.now()))
    db.audit("cv.uploaded", actor_role="nominee", application_id=app["id"], document_id=doc_id, status=res.status)
    out = {"document_id": doc_id, "status": res.status, "error": res.error}
    if res.status == "ok":
        try:
            mode, screen = await ai.cv_screen(extraction.redact(res.text, [app["nominee_name"]]),
                                              app["platform"] or "", app["workflow"] or "")
            db.ex("INSERT INTO cv_screenings(application_id, document_id, mode, result_json, created_at) VALUES (?,?,?,?,?)",
                  (app["id"], doc_id, mode, json.dumps(screen), db.now()))
            fresh = get_app(app["id"])
            extracted = json.loads(fresh["extracted_json"] or "{}")
            for k, v in screen.get("extracted", {}).items():
                extracted[k] = ", ".join(v) if isinstance(v, list) and k != "examples" else ("\n".join(v) if isinstance(v, list) else v)
            extracted["corrected_by_nominee"] = False
            db.ex("UPDATE applications SET extracted_json=? WHERE id=?", (json.dumps(extracted), app["id"]))
            db.audit("cv.screened", application_id=app["id"], mode=mode)
            out["screen"] = screen
        except ai.AIError as e:
            out["error"] = f"CV uploaded. Automated CV screening is temporarily unavailable ({e}); you can enter details manually."
            db.audit("cv.screen_failed", application_id=app["id"], error=str(e))
    return out


def latest_screen(app_id: int) -> dict | None:
    row = db.q1("SELECT * FROM cv_screenings WHERE application_id=? ORDER BY id DESC LIMIT 1", (app_id,))
    if row:
        row["result"] = json.loads(row["result_json"])
    return row


def latest_document(app_id: int) -> dict | None:
    return db.q1("SELECT id, filename, extract_status, extract_error, uploaded_at, size FROM documents WHERE application_id=? AND superseded=0 ORDER BY id DESC LIMIT 1", (app_id,))


def build_snapshot(app: dict) -> dict:
    """Evidence given to BOTH assessors: identical, redacted, source-tagged, no personal characteristics."""
    names = [app["nominee_name"]]
    answers = json.loads(app["answers_json"] or "{}")
    extracted = json.loads(app["extracted_json"] or "{}")
    sources = []
    doc = db.q1("SELECT extracted_text FROM documents WHERE application_id=? AND superseded=0 AND extract_status='ok' ORDER BY id DESC LIMIT 1", (app["id"],))
    if doc:
        sources.append({"id": "CV", "label": "Uploaded CV (claims are unverified)", "criterion": None,
                        "text": extraction.redact(doc["extracted_text"], names)[:15000]})
    if extracted:
        summary = "; ".join(f"{k}: {v}" for k, v in extracted.items() if k != "corrected_by_nominee" and v)
        if summary:
            sources.append({"id": "CV-SUMMARY", "label": "CV summary confirmed or corrected by candidate", "criterion": None,
                            "text": extraction.redact(summary, names)})
    for c in scoring.CRITERIA:
        k = c["key"]
        if c["task"] == "simulation":
            turns = [f"User: {u}\nCandidate: {answers.get(f'empathy_{i}', '').strip()}"
                     for i, u in enumerate(scoring.EMPATHY_SIMULATION)]
            text = "\n".join(turns) if any(answers.get(f"empathy_{i}") for i in range(3)) else ""
            label = "Simulated coaching exchange (performance within a digital exercise)"
        elif c["task"] == "walkthrough":
            parts = [f"Prompt: {q}\nCandidate: {answers.get('workflow_' + f, '').strip()}" for f, q in scoring.WORKFLOW_FIELDS]
            text = "\n".join(parts) if any(answers.get("workflow_" + f) for f, _ in scoring.WORKFLOW_FIELDS) else ""
            label = "Structured workflow walkthrough (performance within a digital exercise)"
        else:
            text = answers.get(k, "").strip()
            label = f"Answer to: {c['question']}"
        sources.append({"id": f"Q-{k}", "label": label, "criterion": k, "text": extraction.redact(text, names) if text else ""})
        fup = answers.get(f"followup_{k}", "").strip()
        if fup:
            sources.append({"id": f"FU-{k}", "label": "Answer to CV follow-up question", "criterion": k,
                            "text": extraction.redact(fup, names)})
    for cl in db.q("SELECT * FROM clarifications WHERE application_id=? AND response IS NOT NULL ORDER BY id", (app["id"],)):
        sources.append({"id": f"CL{cl['round_no']}-{cl['criterion']}", "criterion": cl["criterion"],
                        "label": f"{cl['kind'].title()} response (round {cl['round_no']}) to: {cl['question'][:160]}",
                        "text": extraction.redact(cl["response"], names)})
    return {"platform": app["platform"], "workflow": app["workflow"], "sources": sources}


def submit_application(app: dict) -> None:
    _ensure_active(app)
    if not app["consent_at"]:
        raise WorkflowError("Consent is required before submission.")
    if app["status"] != "Application in Progress":
        raise WorkflowError("This application has already been submitted.")
    if not latest_document(app["id"]):
        raise WorkflowError("Please upload your CV (PDF or DOCX) before submitting.")
    if not app["availability"] or not app["proposed_hours"]:
        raise WorkflowError("Please state your availability and proposed protected hours.")
    db.ex("UPDATE applications SET submitted_at=? WHERE id=?", (db.now(), app["id"]))
    set_status(app["id"], "Submitted", "nominee")
    snapshot_evidence(app["id"])
    send_nominee_link(get_app(app["id"]), "acknowledgment")


def snapshot_evidence(app_id: int) -> int:
    app = get_app(app_id)
    version = app["evidence_version"] + 1
    db.ex("INSERT INTO evidence_versions(application_id, version, snapshot_json, created_at) VALUES (?,?,?,?)",
          (app_id, version, json.dumps(build_snapshot(app)), db.now()))
    db.ex("UPDATE applications SET evidence_version=? WHERE id=?", (version, app_id))
    db.audit("evidence.versioned", application_id=app_id, version=version)
    return version


# ------------------------------------------------------------------ automated assessment
async def run_assessment(app_id: int) -> dict | None:
    app = get_app(app_id)
    if not app or app["withdrawn_at"] or app["status"] not in ("Submitted", "Automated Assessment in Progress"):
        return None
    ev = db.q1("SELECT * FROM evidence_versions WHERE application_id=? ORDER BY version DESC LIMIT 1", (app_id,))
    snapshot = json.loads(ev["snapshot_json"])
    cfg_version, cfg = scoring.current_config()
    set_status(app_id, "Automated Assessment in Progress")
    asmt_id = db.ex("INSERT INTO assessments(application_id, evidence_version, config_version, round_no, mode, status, created_at) VALUES (?,?,?,?,?,?,?)",
                    (app_id, ev["version"], cfg_version, app["clarification_rounds"], ai.mode(), "running", db.now()))
    try:
        # Two blinded passes: separate sessions, same snapshot, neither receives the other's output.
        pass_a, pass_b = await asyncio.gather(ai.assessment_pass(snapshot, "A"), ai.assessment_pass(snapshot, "B"))
        db.ex("UPDATE assessments SET pass_a_json=?, pass_b_json=? WHERE id=?", (json.dumps(pass_a), json.dumps(pass_b), asmt_id))
        db.audit("assessment.passes_complete", application_id=app_id, assessment_id=asmt_id)
        if get_app(app_id)["withdrawn_at"]:
            db.ex("UPDATE assessments SET status='stopped', completed_at=? WHERE id=?", (db.now(), asmt_id))
            return None
        moderation = await ai.moderate(snapshot, pass_a, pass_b)
    except Exception as e:  # AIError or malformed output: never leave an assessment stuck 'running'
        db.ex("UPDATE assessments SET status='failed', error=?, completed_at=? WHERE id=?", (str(e), db.now(), asmt_id))
        db.ex("UPDATE applications SET last_error=? WHERE id=?",
              (f"Automated assessment could not run ({e}). Your submission is saved and will be retried.", app_id))
        set_status(app_id, "Submitted", detail="assessment failed")
        db.audit("assessment.failed", application_id=app_id, assessment_id=asmt_id, error=str(e))
        return None

    final = {k: {"rating": m["final_rating"], "rating_basis": m["rating_basis"], "unsafe_serious": m["unsafe_serious"]}
             for k, m in moderation["criteria"].items()}
    result = scoring.score(final, cfg)
    for k, m in moderation["criteria"].items():
        if m["differed"]:
            db.audit("moderation.difference", application_id=app_id, assessment_id=asmt_id, criterion=k,
                     pass_a=m["pass_a"], pass_b=m["pass_b"], final=m["final_rating"], resolution=m["resolution"],
                     justification=m["justification"])

    app = get_app(app_id)
    if app["withdrawn_at"]:
        db.ex("UPDATE assessments SET status='stopped', completed_at=? WHERE id=?", (db.now(), asmt_id))
        return None
    max_rounds = int(cfg["max_clarification_rounds"])
    needs = [(k, m) for k, m in moderation["criteria"].items() if m["resolution"] in ("clarification", "remediation")]
    rounds_left = app["clarification_rounds"] < max_rounds
    outcome = result["outcome"]
    if needs and not rounds_left and outcome != scoring.OUTCOME_REMEDIATION:
        outcome = scoring.OUTCOME_INCOMPLETE
    result["final_outcome"] = outcome
    result["summary"] = assessment_summary(result, moderation)
    db.ex("UPDATE assessments SET moderation_json=?, result_json=?, status='complete', completed_at=? WHERE id=?",
          (json.dumps(moderation), json.dumps(result), db.now(), asmt_id))
    db.ex("UPDATE applications SET outcome=?, last_error=NULL WHERE id=?", (outcome, app_id))
    db.audit("assessment.complete", application_id=app_id, assessment_id=asmt_id, outcome=outcome,
             score=result["score_text"], config_version=cfg_version, evidence_version=ev["version"], mode=ai.mode())

    if needs and rounds_left:
        round_no = app["clarification_rounds"] + 1
        remediation = any(m["resolution"] == "remediation" for _, m in needs)
        for k, m in needs:
            kind = "remediation" if m["resolution"] == "remediation" else "clarification"
            question = (m["remediation_exercise"] or ai.REMEDIATION_EXERCISE) if kind == "remediation" else (m["clarification_question"] or ai.CLARIFY_BANK[k])
            db.ex("INSERT INTO clarifications(application_id, assessment_id, round_no, criterion, kind, question, created_at) VALUES (?,?,?,?,?,?,?)",
                  (app_id, asmt_id, round_no, k, kind, question, db.now()))
        status = "Reassessment Required" if remediation else "Awaiting Evidence"
        set_status(app_id, status)
        app = get_app(app_id)
        send_nominee_link(app, "reassessment" if remediation else "clarification", due=next_action(app)["due"] or "")
    elif outcome == scoring.OUTCOME_MEETS:
        set_status(app_id, "Assessment Complete")
        set_status(app_id, "Awaiting Manager Commitment")
        app = get_app(app_id)
        send_nominee_link(app, "outcome_meets")
        try:
            send_manager_link(app)
        except WorkflowError as e:
            db.ex("UPDATE applications SET last_error=? WHERE id=?", (str(e), app_id))
    else:
        set_status(app_id, "Assessment Complete")
    return result


def assessment_summary(result: dict, moderation: dict) -> str:
    agreed = sum(1 for m in moderation["criteria"].values() if m["resolution"] == "agreed")
    reeval = sum(1 for m in moderation["criteria"].values() if m["resolution"] == "re-evaluated")
    parts = [f"AI-generated assessment. Score: {result['score_text']}", f"Outcome: {result['outcome']}.",
             f"Evidence coverage: {result['evidence_coverage']}.",
             f"Moderation: {agreed} criteria agreed between passes, {reeval} re-evaluated."]
    if result["minimum_failures"]:
        names = [c["name"] for c in scoring.CRITERIA if c["key"] in result["minimum_failures"]]
        parts.append("Below minimum rating: " + "; ".join(names) + ".")
    if result["unsafe_serious"]:
        parts.append("A potentially unsafe response requires remediation and reassessment.")
    parts.append("Agreement between passes indicates scoring consistency; it does not verify CV claims.")
    return " ".join(parts)


def latest_assessment(app_id: int) -> dict | None:
    row = db.q1("SELECT * FROM assessments WHERE application_id=? ORDER BY id DESC LIMIT 1", (app_id,))
    if row:
        for k in ("pass_a_json", "pass_b_json", "moderation_json", "result_json"):
            row[k[:-5]] = json.loads(row[k]) if row[k] else None
    return row


def open_clarifications(app_id: int) -> list[dict]:
    return db.q("SELECT * FROM clarifications WHERE application_id=? AND response IS NULL ORDER BY id", (app_id,))


def respond_clarifications(app: dict, responses: dict[int, str]) -> None:
    _ensure_active(app)
    if app["status"] not in ("Awaiting Evidence", "Reassessment Required"):
        raise WorkflowError("There are no outstanding requests to answer.")
    pending = open_clarifications(app["id"])
    for cl in pending:
        text = (responses.get(cl["id"]) or "").strip()
        if not text:
            raise WorkflowError("Please answer every outstanding question before resubmitting.")
    for cl in pending:
        db.ex("UPDATE clarifications SET response=?, responded_at=? WHERE id=?", (responses[cl["id"]].strip(), db.now(), cl["id"]))
    db.ex("UPDATE applications SET clarification_rounds=clarification_rounds+1 WHERE id=?", (app["id"],))
    db.audit("clarification.responded", actor_role="nominee", application_id=app["id"], count=len(pending))
    set_status(app["id"], "Submitted", "nominee")
    snapshot_evidence(app["id"])


# ------------------------------------------------------------------ capacity & appointment
def manager_commit(app: dict, form: dict, actor_email: str) -> None:
    _ensure_active(app)
    if app["status"] != "Awaiting Manager Commitment":
        raise WorkflowError("A manager commitment is not currently required for this application.")
    hours = float(form.get("protected_hours") or 0)
    if hours <= 0:
        raise WorkflowError("Please confirm the number of protected hours.")
    db.ex("INSERT OR REPLACE INTO manager_commitments(application_id, manager_email, protected_hours, workload, availability, access_confirmed, access_actions, supports, submitted_at) "
          "VALUES (?,?,?,?,?,?,?,?,?)",
          (app["id"], actor_email, hours, form.get("workload"), form.get("availability"),
           1 if form.get("access_confirmed") else 0, form.get("access_actions"), 1 if form.get("supports", True) else 0, db.now()))
    db.audit("manager.committed", actor_role="manager", actor_email=actor_email, application_id=app["id"],
             hours=hours, access_confirmed=bool(form.get("access_confirmed")))
    maybe_advance_to_sponsor(get_app(app["id"]))


def candidate_willingness(app: dict, willing: bool, actor_email: str) -> None:
    _ensure_active(app)
    if app["status"] != "Awaiting Manager Commitment":
        raise WorkflowError("Not required at this stage.")
    db.ex("UPDATE applications SET candidate_willing=? WHERE id=?", (1 if willing else 0, app["id"]))
    db.audit("candidate.willingness", actor_role="nominee", actor_email=actor_email, application_id=app["id"], willing=willing)
    if not willing:
        withdraw(app, "Candidate no longer willing to take part", "nominee", actor_email)
        return
    maybe_advance_to_sponsor(get_app(app["id"]))


def maybe_advance_to_sponsor(app: dict) -> bool:
    mc = db.q1("SELECT * FROM manager_commitments WHERE application_id=?", (app["id"],))
    if mc and mc["supports"] and mc["access_confirmed"] and app["candidate_willing"] == 1:
        set_status(app["id"], "Awaiting Sponsor Decision")
        send_sponsor_links(app["entity_id"])
        return True
    return False


def appointment_requirements(app: dict) -> list[dict]:
    mc = db.q1("SELECT * FROM manager_commitments WHERE application_id=?", (app["id"],))
    sd = db.q1("SELECT * FROM sponsor_decisions WHERE application_id=? AND decision='provisional' ORDER BY id DESC LIMIT 1", (app["id"],))
    return [
        {"key": "consent", "label": "Nominee consent recorded", "met": bool(app["consent_at"])},
        {"key": "assessment", "label": "Assessment meets proposed thresholds", "met": app["outcome"] == scoring.OUTCOME_MEETS},
        {"key": "capacity", "label": "Line-manager capacity commitment", "met": bool(mc and mc["supports"] and mc["protected_hours"])},
        {"key": "access", "label": "Required platform access confirmed", "met": bool(mc and mc["access_confirmed"])},
        {"key": "willing", "label": "Candidate confirms continued willingness", "met": app["candidate_willing"] == 1},
        {"key": "sponsor", "label": "Entity sponsor authorisation", "met": bool(sd)},
    ]


def sponsor_decide(app: dict, form: dict, actor_email: str) -> None:
    _ensure_active(app)
    if app["status"] != "Awaiting Sponsor Decision":
        raise WorkflowError("This application is not awaiting a sponsor decision.")
    decision = form.get("decision")
    if decision not in ("provisional", "not_selected", "defer"):
        raise WorkflowError("Choose a decision.")
    if not (form.get("rationale") or "").strip():
        raise WorkflowError("A documented rationale is required.")
    if form.get("coi_declared") not in ("none", "declared"):
        raise WorkflowError("Please complete the conflict-of-interest declaration.")
    if decision == "provisional":
        unmet = [r["label"] for r in appointment_requirements(app) if not r["met"] and r["key"] != "sponsor"]
        if unmet:
            raise WorkflowError("Provisional appointment is blocked until these are confirmed: " + "; ".join(unmet))
    db.ex("INSERT INTO sponsor_decisions(application_id, sponsor_email, decision, rationale, coverage_need, coi_declared, coi_details, conditions, decided_at) "
          "VALUES (?,?,?,?,?,?,?,?,?)",
          (app["id"], actor_email, decision, form["rationale"].strip(), form.get("coverage_need"),
           1 if form["coi_declared"] == "declared" else 0, form.get("coi_details"), form.get("conditions"), db.now()))
    db.audit("sponsor.decision", actor_role="sponsor", actor_email=actor_email, application_id=app["id"], decision=decision)
    if decision == "provisional":
        set_status(app["id"], "Provisionally Appointed", "sponsor")
        send_nominee_link(get_app(app["id"]), "provisional_appointment")
    elif decision == "not_selected":
        set_status(app["id"], "Not Selected", "sponsor")
        send_nominee_link(get_app(app["id"]), "unsuccessful")


def accept_role(app: dict, accept: bool, actor_email: str) -> None:
    _ensure_active(app)
    if app["status"] != "Provisionally Appointed":
        raise WorkflowError("There is no role offer to respond to.")
    if not accept:
        withdraw(app, "Declined role charter", "nominee", actor_email)
        return
    ver = scoring.current_config()[1]["role_charter_version"]
    checklist = {item: (item == "Role charter accepted") for item in ONBOARDING_CHECKLIST}
    db.ex("INSERT OR REPLACE INTO onboarding(application_id, accepted_at, charter_version, checklist_json) VALUES (?,?,?,?)",
          (app["id"], db.now(), ver, json.dumps(checklist)))
    db.audit("role.accepted", actor_role="nominee", actor_email=actor_email, application_id=app["id"], charter_version=ver)
    set_status(app["id"], "Onboarding", "nominee")
    send_nominee_link(get_app(app["id"]), "onboarding")


def update_onboarding(app: dict, form: dict, actor_email: str) -> None:
    _ensure_active(app)
    if app["status"] != "Onboarding":
        raise WorkflowError("Onboarding is not in progress.")
    ob = db.q1("SELECT * FROM onboarding WHERE application_id=?", (app["id"],))
    checklist = {item: bool(form.get(f"check_{i}")) or (item == "Role charter accepted") for i, item in enumerate(ONBOARDING_CHECKLIST)}
    start = form.get("start_date") or ob.get("start_date")
    day90 = (date.fromisoformat(start) + timedelta(days=90)).isoformat() if start else None
    db.ex("UPDATE onboarding SET buddy=?, objective=?, start_date=?, day90_date=?, checklist_json=? WHERE application_id=?",
          (form.get("buddy"), form.get("objective"), start, day90, json.dumps(checklist), app["id"]))
    db.audit("onboarding.updated", actor_role="lead", actor_email=actor_email, application_id=app["id"])
    if form.get("complete"):
        if not (form.get("buddy") and form.get("objective") and start and all(checklist.values())):
            raise WorkflowError("Assign a buddy, set the initial workflow objective and start date, and complete every checklist item first.")
        set_status(app["id"], "Awaiting Day-90 Review", "lead")


def day90_input(app: dict, who: str, form: dict, actor_email: str) -> None:
    _ensure_active(app)
    if app["status"] != "Awaiting Day-90 Review":
        raise WorkflowError("The day-90 review is not open.")
    if not db.q1("SELECT 1 FROM day90_reviews WHERE application_id=?", (app["id"],)):
        db.ex("INSERT INTO day90_reviews(application_id) VALUES (?)", (app["id"],))
    payload = json.dumps({k: form.get(k) for k in ("readiness", "contribution", "workload", "willing", "comments")})
    col = "nominee" if who == "nominee" else "manager"
    db.ex(f"UPDATE day90_reviews SET {col}_json=?, {col}_at=? WHERE application_id=?", (payload, db.now(), app["id"]))
    db.audit(f"day90.{col}_input", actor_role=who, actor_email=actor_email, application_id=app["id"])


def day90_decide(app: dict, form: dict, actor_email: str) -> None:
    _ensure_active(app)
    if app["status"] != "Awaiting Day-90 Review":
        raise WorkflowError("The day-90 review is not open.")
    rv = db.q1("SELECT * FROM day90_reviews WHERE application_id=?", (app["id"],))
    if not rv or not rv["nominee_json"] or not rv["manager_json"]:
        raise WorkflowError("Nominee and manager day-90 inputs are both required before an outcome is recorded.")
    outcome = form.get("outcome")
    if outcome not in ("confirmed", "extended", "concluded") or not (form.get("rationale") or "").strip():
        raise WorkflowError("Choose an outcome and record a rationale.")
    db.ex("UPDATE day90_reviews SET outcome=?, rationale=?, decided_by=?, decided_at=? WHERE application_id=?",
          (outcome, form["rationale"].strip(), actor_email, db.now(), app["id"]))
    db.audit("day90.decision", actor_role="sponsor", actor_email=actor_email, application_id=app["id"], outcome=outcome)
    if outcome == "confirmed":
        set_status(app["id"], "Confirmed", "sponsor")
    elif outcome == "concluded":
        set_status(app["id"], "Appointment Concluded", "sponsor")
    else:
        ob = db.q1("SELECT day90_date FROM onboarding WHERE application_id=?", (app["id"],))
        new_date = (date.fromisoformat(ob["day90_date"]) + timedelta(days=60)).isoformat() if ob and ob["day90_date"] else None
        db.ex("UPDATE onboarding SET day90_date=? WHERE application_id=?", (new_date, app["id"]))
        db.ex("UPDATE day90_reviews SET nominee_json=NULL, manager_json=NULL WHERE application_id=?", (app["id"],))
        db.audit("day90.extended", application_id=app["id"], new_review_date=new_date)


def withdraw(app: dict, reason: str, actor: str, actor_email: str | None = None) -> None:
    if app["status"] in ("Withdrawn",):
        return
    db.ex("UPDATE applications SET withdrawn_at=?, withdrawn_reason=? WHERE id=?", (db.now(), reason, app["id"]))
    set_status(app["id"], "Withdrawn", actor, reason=reason)
    security.revoke_for_application(app["id"], "manager")
    emails.send("withdrawal", app["nominee_email"], _ctx(app), application=get_app(app["id"]), triggered_by=actor)


def communicate_outcome(app: dict, actor_email: str) -> None:
    if app["status"] != "Assessment Complete" or app["outcome"] == scoring.OUTCOME_MEETS:
        raise WorkflowError("There is no unsuccessful outcome to communicate.")
    db.ex("UPDATE applications SET outcome_communicated_at=? WHERE id=?", (db.now(), app["id"]))
    set_status(app["id"], "Not Selected", "lead")
    send_nominee_link(get_app(app["id"]), "unsuccessful", triggered_by="lead")


# ------------------------------------------------------------------ next action
def next_action(app: dict) -> dict:
    cfg = scoring.current_config()[1]
    s = app["status"]
    due = None
    if s in cfg["sla_days"]:
        due = _due(app["status_changed_at"], int(cfg["sla_days"][s]))
    sponsors = ", ".join(c["name"] for c in contacts(app["entity_id"], "sponsor")) or "Entity sponsor"
    mgr = app.get("manager_name") or "Line manager"
    nominee = app["nominee_name"]
    table = {
        "Nominated": ("Resend consent link (email not yet delivered)", "Entity focal point", "focal"),
        "Awaiting Consent": ("Give or decline consent", nominee, "nominee"),
        "Application in Progress": ("Complete and submit application", nominee, "nominee"),
        "Submitted": ("Automated assessment queued" if not app.get("last_error") else "Automated assessment retry", "Automated assessment service", "system"),
        "Automated Assessment in Progress": ("Automated assessment running", "Automated assessment service", "system"),
        "Awaiting Evidence": ("Answer clarification questions", nominee, "nominee"),
        "Reassessment Required": ("Complete remediation exercise", nominee, "nominee"),
        "Assessment Complete": ("Communicate assessment outcome", "CDP Change Lead", "lead"),
        "Awaiting Manager Commitment": ("Confirm protected time, workload and access" + ("" if app.get("candidate_willing") == 1 else "; nominee to confirm willingness"), mgr, "manager"),
        "Awaiting Sponsor Decision": ("Record provisional appointment decision", sponsors, "sponsor"),
        "Provisionally Appointed": ("Accept role charter", nominee, "nominee"),
        "Onboarding": ("Assign buddy, complete onboarding checklist", "Programme team", "lead"),
        "Awaiting Day-90 Review": ("Complete day-90 review", f"{nominee}, {mgr}, {sponsors}", "sponsor"),
    }
    if s == "Awaiting Day-90 Review":
        ob = db.q1("SELECT day90_date FROM onboarding WHERE application_id=?", (app["id"],))
        due = ob["day90_date"] if ob else None
    if s in TERMINAL:
        return {"action": "None — closed", "owner": "—", "owner_role": None, "due": None, "overdue": False}
    action, owner, role = table[s]
    overdue = bool(due and due < date.today().isoformat())
    return {"action": action, "owner": owner, "owner_role": role, "due": due, "overdue": overdue}


# ------------------------------------------------------------------ retention
def purge_expired(actor_email: str) -> int:
    days = int(scoring.current_config()[1]["retention_days"])
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    apps = db.q("SELECT id FROM applications WHERE status IN ('Withdrawn','Not Selected','Appointment Concluded') AND status_changed_at < ?", (cutoff,))
    for a in apps:
        delete_documents(a["id"], actor_email, reason=f"Retention period of {days} days elapsed")
    return len(apps)


def delete_documents(app_id: int, actor_email: str, reason: str) -> None:
    for d in db.q("SELECT * FROM documents WHERE application_id=? AND extract_status!='deleted'", (app_id,)):
        if d["stored_path"]:
            Path(d["stored_path"]).unlink(missing_ok=True)
    db.ex("UPDATE documents SET stored_path=NULL, extracted_text=NULL, extract_status='deleted' WHERE application_id=?", (app_id,))
    db.ex("UPDATE evidence_versions SET snapshot_json='{\"sources\":[],\"deleted\":true}' WHERE application_id=?", (app_id,))
    db.audit("retention.deleted", actor_role="lead", actor_email=actor_email, application_id=app_id, reason=reason)
