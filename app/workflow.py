"""Version 2 workflow: initiatives, step tracker, survey import, CV fit screening, assessment links,
AI assessment, reports and approvals. All business rules are enforced here, on the server."""
from __future__ import annotations

import asyncio
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import ai, config, db, extraction, invite_email, mailer, production, scoring, security

STATUSES = [
    "No Consent", "Awaiting CV", "CV Unreadable", "CV Uploaded", "Shortlisted", "Not Shortlisted",
    "Invited", "In Assessment", "Assessing", "Follow-up Requested", "Assessed",
    "Approved", "Not Approved", "Withdrawn",
]
INVITABLE = {"Shortlisted", "Invited", "In Assessment", "Follow-up Requested"}
EDITABLE_ANSWERS = {"Invited", "In Assessment"}

# The step tracker. Steps are an order, not dates; the Change Lead marks each one complete.
STEPS = [
    (1, "Collect nominations", "Run the nomination survey in your survey tool (for example Microsoft Forms)."),
    (2, "Import survey results", "Upload the survey export and check the matched columns."),
    (3, "Upload CVs", "Bulk upload the nominees' CVs (PDF or DOCX)."),
    (4, "AI fit rating", "Run the AI CV screening: High, Moderate, Low or Doesn't Fit."),
    (5, "Review shortlist", "Check the shortlist and override any fit category with a reason."),
    (6, "Send assessment links", "Press Invite to email each shortlisted nominee their personal link, or download the mail-merge list."),
    (7, "Assessments completed", "Nominees complete the LAUNCH WINDOW assessment; the AI assesses their evidence."),
    (8, "Review reports", "Read each candidate's assessment report."),
    (9, "Approve champions", "Approve or decline each assessed candidate with a short rationale."),
]


class WorkflowError(Exception):
    """A business rule prevented the action. The message is safe to show."""


# ------------------------------------------------------------------ basics
def cand(cid: int) -> dict | None:
    return db.q1("SELECT c.*, e.name AS entity_name, i.name AS initiative_name FROM candidates c "
                 "LEFT JOIN entities e ON e.id=c.entity_id JOIN initiatives i ON i.id=c.initiative_id WHERE c.id=?", (cid,))


def set_status(cid: int, status: str, actor: str = "system", **detail) -> None:
    assert status in STATUSES, status
    db.ex("UPDATE candidates SET status=?, status_changed_at=?, updated_at=? WHERE id=?", (status, db.now(), db.now(), cid))
    db.audit("status." + status, actor=actor, candidate_id=cid, **detail)


def _active(c: dict) -> None:
    if c["status"] == "Withdrawn":
        raise WorkflowError("This candidate has been withdrawn.")


def new_ref() -> str:
    return "CH-" + secrets.token_hex(3).upper()


# ------------------------------------------------------------------ initiatives & steps
def create_initiative(name: str, platform: str = "", description: str = "") -> int:
    name = (name or "").strip()
    if not name:
        raise WorkflowError("Give the initiative a name, for example 'ERP Release 3'.")
    iid = db.ex("INSERT INTO initiatives(name, platform, description, created_at) VALUES (?,?,?,?)",
                (name[:120], (platform or "").strip()[:120], (description or "").strip()[:1000], db.now()))
    for no, _, _ in STEPS:
        db.ex("INSERT INTO initiative_steps(initiative_id, step_no) VALUES (?,?)", (iid, no))
    db.audit("initiative.created", actor="lead", initiative_id=iid, name=name)
    return iid


def set_step(iid: int, step_no: int, complete: bool) -> None:
    if step_no not in {s[0] for s in STEPS}:
        raise WorkflowError("Unknown step.")
    db.ex("UPDATE initiative_steps SET completed_at=? WHERE initiative_id=? AND step_no=?",
          (db.now() if complete else None, iid, step_no))
    db.audit("step.completed" if complete else "step.reopened", actor="lead", initiative_id=iid, step=step_no)


def step_progress(iid: int) -> list[dict]:
    rows = db.q("SELECT status, fit_final, decision, (SELECT COUNT(*) FROM documents d WHERE d.candidate_id=c.id AND d.superseded=0) AS docs "
                "FROM candidates c WHERE initiative_id=? AND status!='Withdrawn'", (iid,))
    total = len(rows)
    consented = [r for r in rows if r["status"] != "No Consent"]
    with_cv = sum(1 for r in consented if r["docs"])
    screened = sum(1 for r in consented if r["fit_final"])
    shortlisted = sum(1 for r in rows if r["fit_final"] in scoring.FIT_PROGRESS)
    invited = sum(1 for r in rows if r["status"] in ("Invited", "In Assessment", "Assessing", "Follow-up Requested", "Assessed", "Approved", "Not Approved"))
    assessed = sum(1 for r in rows if r["status"] in ("Assessed", "Approved", "Not Approved"))
    decided = sum(1 for r in rows if r["decision"])
    counts = {1: f"{total} nominations imported" if total else "",
              2: f"{total} nominees" if total else "",
              3: f"{with_cv} of {len(consented)} CVs uploaded",
              4: f"{screened} of {len(consented)} screened",
              5: f"{shortlisted} shortlisted",
              6: f"{invited} of {shortlisted} invited",
              7: f"{assessed} of {invited} assessed",
              8: f"{assessed} reports ready",
              9: f"{decided} of {assessed} decided"}
    done = {r["step_no"]: r["completed_at"] for r in db.q("SELECT * FROM initiative_steps WHERE initiative_id=?", (iid,))}
    out, current_found = [], False
    for no, title, hint in STEPS:
        item = {"no": no, "title": title, "hint": hint, "progress": counts[no], "completed_at": done.get(no), "current": False}
        if not item["completed_at"] and not current_found:
            item["current"], current_found = True, True
        out.append(item)
    return out


# ------------------------------------------------------------------ import
def entity_id(name: str) -> int:
    clean = re.sub(r"\s+", " ", name).strip()
    row = db.q1("SELECT id FROM entities WHERE lower(name)=lower(?)", (clean,))
    return row["id"] if row else db.ex("INSERT INTO entities(name) VALUES (?)", (clean,))


def import_records(iid: int, records: list[dict]) -> dict:
    created = duplicates = no_consent = 0
    notes = []
    for r in records:
        eid = entity_id(r["entity"])
        dup = None
        if r.get("email"):
            dup = db.q1("SELECT id FROM candidates WHERE initiative_id=? AND lower(email)=?", (iid, r["email"]))
        if not dup:
            dup = db.q1("SELECT id FROM candidates WHERE initiative_id=? AND lower(name)=lower(?) AND entity_id=?", (iid, r["name"], eid))
        if dup:
            duplicates += 1
            notes.append(f"Row {r['row_number']}: {r['name']} is already in this initiative (duplicate nomination recorded).")
            db.audit("import.duplicate", actor="lead", candidate_id=dup["id"], initiative_id=iid, row=r["row_number"])
            continue
        status = "Awaiting CV" if r["consent"] else "No Consent"
        no_consent += 0 if r["consent"] else 1
        ts = db.now()
        cid = db.ex("INSERT INTO candidates(ref, initiative_id, entity_id, name, email, department, platform, workflow, route, "
                    "nominator_name, nominator_email, reason, manager_name, manager_email, consent_screening, source_row_json, "
                    "status, status_changed_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (new_ref(), iid, eid, r["name"], r.get("email") or None, r.get("department"), r.get("platform"), r.get("workflow"),
                     r.get("route"), r.get("nominator_name"), r.get("nominator_email"), r.get("reason"), r.get("manager_name"),
                     r.get("manager_email"), 1 if r["consent"] else 0, json.dumps(r.get("source_row", {})), status, ts, ts, ts))
        created += 1
        db.audit("import.created", actor="lead", candidate_id=cid, initiative_id=iid)
    if no_consent:
        notes.append(f"{no_consent} nominee(s) have no recorded consent to AI screening; they will not be screened.")
    return {"created": created, "duplicates": duplicates, "no_consent": no_consent, "notes": notes}


def record_consent(c: dict, actor: str = "lead") -> None:
    """The Change Lead records consent obtained outside the survey (e.g. by email)."""
    _active(c)
    if c["status"] != "No Consent":
        return
    db.ex("UPDATE candidates SET consent_screening=1 WHERE id=?", (c["id"],))
    has_cv = db.q1("SELECT 1 FROM documents WHERE candidate_id=? AND superseded=0 AND extract_status='ok'", (c["id"],))
    set_status(c["id"], "CV Uploaded" if has_cv else "Awaiting CV", actor, reason="consent recorded")


# ------------------------------------------------------------------ CVs
def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z؀-ۿ]+", text.lower()) if len(t) >= 2}


IGNORE_TOKENS = {"cv", "resume", "final", "updated", "copy", "new", "version", "al", "el", "bin", "bint", "ibn", "abu",
                 "the", "of", "mr", "mrs", "ms", "dr", "eng", "profile", "doc", "pdf", "docx"}


def _name_tokens(text: str) -> set[str]:
    return {t for t in _tokens(text) if t not in IGNORE_TOKENS and not t.isdigit()}


def match_scores(iid: int, filenames: list[str]) -> dict[str, dict]:
    """For each file: a confident match (auto-assigned) and/or a best-guess suggestion for the Change Lead to confirm.

    A file matches a nominee when at least two parts of their name (or their email name) appear in the file name,
    or every meaningful part of a one-word name does, and no other nominee scores as high."""
    people = db.q("SELECT id, name, email FROM candidates WHERE initiative_id=? AND status!='Withdrawn'", (iid,))
    out = {}
    for fn in filenames:
        ft = _name_tokens(Path(fn).stem)
        scored = []
        for p in people:
            nt = _name_tokens(p["name"]) | _name_tokens((p["email"] or "").split("@")[0].replace(".", " "))
            hits = len(nt & ft)
            full = bool(_name_tokens(p["name"])) and _name_tokens(p["name"]) <= ft
            if hits:
                scored.append((hits + (1 if full else 0), full, p["id"]))
        scored.sort(reverse=True)
        best = scored[0] if scored else None
        unique = best and (len(scored) == 1 or scored[1][0] < best[0])
        confident = bool(best and unique and (best[0] >= 2 or best[1]))
        out[fn] = {"match": best[2] if confident else None,
                   "suggest": best[2] if best and unique else None}
    return out


def match_files(iid: int, filenames: list[str]) -> dict[str, int | None]:
    return {fn: r["match"] for fn, r in match_scores(iid, filenames).items()}


def record_consent_all(iid: int) -> int:
    rows = db.q("SELECT id FROM candidates WHERE initiative_id=? AND status='No Consent'", (iid,))
    for r in rows:
        record_consent(cand(r["id"]))
    db.audit("consent.bulk", actor="lead", initiative_id=iid, count=len(rows))
    return len(rows)


def screening_blockers(iid: int) -> dict:
    rows = db.q("SELECT status FROM candidates WHERE initiative_id=? AND status!='Withdrawn'", (iid,))
    count = lambda *st: sum(1 for r in rows if r["status"] in st)
    return {"total": len(rows), "no_consent": count("No Consent"), "awaiting_cv": count("Awaiting CV"),
            "unreadable": count("CV Unreadable"), "ready": count("CV Uploaded"),
            "screened": len(rows) - count("No Consent", "Awaiting CV", "CV Unreadable", "CV Uploaded")}


def upload_cv(c: dict, filename: str, data: bytes) -> dict:
    _active(c)
    res = extraction.extract(filename, data)
    stored = None
    if res.status in ("ok", "unreadable"):
        folder = Path(config.settings.upload_dir) / str(c["id"])
        folder.mkdir(parents=True, exist_ok=True)
        stored = str(folder / f"{secrets.token_hex(8)}{Path(filename).suffix.lower()}")
        Path(stored).write_bytes(data)
    db.ex("UPDATE documents SET superseded=1 WHERE candidate_id=?", (c["id"],))
    did = db.ex("INSERT INTO documents(candidate_id, filename, stored_path, mime, size, sha256, extract_status, extract_error, extracted_text, uploaded_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (c["id"], Path(filename).name[:200], stored, extraction.ALLOWED.get(Path(filename).suffix.lower()), len(data),
                 extraction.sha256(data), res.status, res.error, res.text, db.now()))
    db.audit("cv.uploaded", actor="lead", candidate_id=c["id"], status=res.status)
    if c["status"] in ("Awaiting CV", "CV Unreadable", "CV Uploaded"):
        set_status(c["id"], "CV Uploaded" if res.status == "ok" else "CV Unreadable", "lead")
    return {"document_id": did, "status": res.status, "error": res.error}


def latest_document(cid: int) -> dict | None:
    return db.q1("SELECT id, filename, extract_status, extract_error, uploaded_at, size FROM documents "
                 "WHERE candidate_id=? AND superseded=0 ORDER BY id DESC LIMIT 1", (cid,))


# ------------------------------------------------------------------ CV fit screening
async def screen(cid: int) -> dict | None:
    c = cand(cid)
    if not c or c["status"] == "Withdrawn" or not c["consent_screening"]:
        return None
    doc = db.q1("SELECT * FROM documents WHERE candidate_id=? AND superseded=0 AND extract_status='ok' ORDER BY id DESC LIMIT 1", (cid,))
    if not doc:
        return None
    try:
        mode, result = await ai.cv_screen(extraction.redact(doc["extracted_text"], [c["name"]]), c["platform"] or "", c["workflow"] or "")
    except Exception as e:
        db.ex("UPDATE candidates SET last_error=? WHERE id=?", (f"AI screening could not run ({e}). The CV is saved; try again.", cid))
        db.audit("screen.failed", candidate_id=cid, error=str(e))
        return None
    db.ex("INSERT INTO cv_screenings(candidate_id, document_id, mode, result_json, created_at) VALUES (?,?,?,?,?)",
          (cid, doc["id"], mode, json.dumps(result), db.now()))
    cat = result["fit_category"]
    db.ex("UPDATE candidates SET fit_ai=?, fit_final=?, fit_override_reason=NULL, last_error=NULL WHERE id=?", (cat, cat, cid))
    db.audit("screen.complete", candidate_id=cid, fit=cat, mode=mode)
    if c["status"] in ("CV Uploaded", "Shortlisted", "Not Shortlisted"):
        set_status(cid, "Shortlisted" if cat in scoring.FIT_PROGRESS else "Not Shortlisted")
    return result


async def screen_many(cids: list[int]) -> int:
    results = await asyncio.gather(*(screen(i) for i in cids))
    return sum(1 for r in results if r)


def latest_screen(cid: int) -> dict | None:
    row = db.q1("SELECT * FROM cv_screenings WHERE candidate_id=? ORDER BY id DESC LIMIT 1", (cid,))
    if row:
        row["result"] = json.loads(row["result_json"])
    return row


def override_fit(c: dict, category: str, reason: str) -> None:
    _active(c)
    if category not in scoring.FIT_CATEGORIES:
        raise WorkflowError("Choose a fit category.")
    if not (reason or "").strip():
        raise WorkflowError("Record a reason for changing the AI's fit category.")
    if not c["fit_ai"]:
        raise WorkflowError("Run the AI fit rating first.")
    if c["status"] not in ("Shortlisted", "Not Shortlisted"):
        raise WorkflowError("The fit category can only be changed before an assessment link is sent.")
    db.ex("UPDATE candidates SET fit_final=?, fit_override_reason=? WHERE id=?", (category, reason.strip(), c["id"]))
    db.audit("fit.override", actor="lead", candidate_id=c["id"], ai=c["fit_ai"], final=category, reason=reason.strip())
    set_status(c["id"], "Shortlisted" if category in scoring.FIT_PROGRESS else "Not Shortlisted", "lead")


# ------------------------------------------------------------------ assessment links
def can_email(c: dict) -> bool:
    return bool(c.get("email")) and "@" in c["email"]


async def email_invite(c: dict, first_lang: str = "en") -> dict:
    """Create a fresh personal link and email it to the nominee.

    The earlier link keeps working until the new one is delivered, so a failed send never locks
    anyone out. The stored copy of the email has the link shortened; the working link is not kept.
    Returns {"status": "sent" | "demo" | "failed", "error": str | None, "link": raw link (demo only)}."""
    _active(c)
    if c["status"] not in INVITABLE:
        raise WorkflowError("Only shortlisted candidates can be sent an assessment link.")
    if not can_email(c):
        raise WorkflowError("This nominee has no email address. Download the links list and send theirs yourself.")
    if not mailer.configured() and production.is_production():
        raise WorkflowError("Email sending isn't set up yet, so nothing was sent. Add the SMTP settings in the "
                            "hosting service, or download the links list and send the links yourself.")
    initiative = db.q1("SELECT name FROM initiatives WHERE id=?", (c["initiative_id"],))["name"]
    raw = security.issue_link(c["id"], keep_others=True)
    link = security.link_for(raw)
    subject, text, html = invite_email.build(c["name"], initiative, link, security.link_expiry(raw), first_lang)
    status, error = "demo", None
    if mailer.configured():
        try:
            await mailer.send(c["email"], subject, text, html)
            status = "sent"
        except mailer.MailError as e:
            status, error = "failed", str(e)
    db.ex("INSERT INTO emails(candidate_id, kind, to_addr, subject, body_text, status, error, created_at) VALUES (?,?,?,?,?,?,?,?)",
          (c["id"], "invite", c["email"], subject, text.replace(link, security.link_for("…" + raw[-4:])), status, error, db.now()))
    if status == "failed":
        security.cancel_link(raw)
        db.audit("invite.failed", actor="lead", candidate_id=c["id"], error=error)
        return {"status": status, "error": error, "link": None}
    security.keep_only_link(c["id"], raw)
    if c["status"] == "Shortlisted":
        set_status(c["id"], "Invited", "lead")
    db.audit("invite.emailed" if status == "sent" else "invite.recorded_demo", actor="lead", candidate_id=c["id"], to=c["email"])
    return {"status": status, "error": None, "link": link if status == "demo" else None}


def last_invite(cid: int) -> dict | None:
    return db.q1("SELECT * FROM emails WHERE candidate_id=? AND kind='invite' ORDER BY id DESC LIMIT 1", (cid,))


def invite(c: dict) -> str:
    _active(c)
    if c["status"] not in INVITABLE:
        raise WorkflowError("Only shortlisted candidates can be sent an assessment link.")
    raw = security.issue_link(c["id"])
    if c["status"] == "Shortlisted":
        set_status(c["id"], "Invited", "lead")
    db.audit("link.issued", actor="lead", candidate_id=c["id"])
    return security.link_for(raw)


def confirm_consent(c: dict) -> None:
    _active(c)
    if c["status"] not in ("Invited", "In Assessment"):
        return
    ver = scoring.current_config()[1]["consent_version"]
    db.ex("UPDATE candidates SET consent_assessment_at=? WHERE id=?", (db.now(), c["id"]))
    db.audit("consent.assessment", actor="candidate", candidate_id=c["id"], version=ver)
    if c["status"] == "Invited":
        set_status(c["id"], "In Assessment", "candidate")


def save_answers(c: dict, answers: dict, mode: str, actor: str = "candidate") -> None:
    _active(c)
    if actor == "candidate" and c["status"] not in EDITABLE_ANSWERS:
        raise WorkflowError("Your answers can no longer be changed.")
    if actor == "lead" and c["status"] not in INVITABLE:
        raise WorkflowError("Offline answers can only be added for shortlisted candidates who have not finished.")
    current = json.loads(c["answers_json"] or "{}")
    current.update({k: str(v)[:6000] for k, v in answers.items()})
    db.ex("UPDATE candidates SET answers_json=?, assessment_mode=?, updated_at=? WHERE id=?",
          (json.dumps(current), mode, db.now(), c["id"]))


def submit_answers(c: dict, actor: str = "candidate") -> None:
    _active(c)
    if actor == "candidate" and not c["consent_assessment_at"]:
        raise WorkflowError("Please confirm your consent first.")
    if c["status"] not in EDITABLE_ANSWERS and not (actor == "lead" and c["status"] in INVITABLE):
        raise WorkflowError("These answers have already been submitted.")
    set_status(c["id"], "Assessing", actor)
    snapshot_evidence(c["id"])


def build_snapshot(c: dict) -> dict:
    """Evidence for both assessors: identical, redacted, source-tagged."""
    names = [c["name"]]
    if c["assessment_mode"] == "game":
        from app import game
        state, events = game_load(c["id"])
        sources, indicators = game.snapshot_sources(state, events)
        for s_ in sources:
            s_["text"] = extraction.redact(s_["text"], names)
        for cl in db.q("SELECT * FROM clarifications WHERE candidate_id=? AND response IS NOT NULL ORDER BY id", (c["id"],)):
            prefix = "Remediation response" if cl["kind"] == "remediation" else "Clarification response"
            sources.append({"id": f"CL{cl['round_no']}-{cl['criterion']}", "criterion": cl["criterion"],
                            "label": f"{prefix} (round {cl['round_no']}) to: {cl['question'][:160]}",
                            "text": extraction.redact(cl["response"], names)})
        return {"platform": c["platform"], "workflow": c["workflow"], "sources": sources,
                "game_indicators": indicators, "game_outcome_excluded": True}
    answers = json.loads(c["answers_json"] or "{}")
    origin = "offline document entered by the Change Lead" if c["assessment_mode"] == "offline" else "LAUNCH WINDOW written scenarios"
    sources = []
    for cr in scoring.CRITERIA:
        k = cr["key"]
        if cr["task"] == "simulation":
            turns = [f"User: {u}\nCandidate: {answers.get(f'empathy_{i}', '').strip()}" for i, u in enumerate(scoring.EMPATHY_SIMULATION)]
            text = "\n".join(turns) if any(answers.get(f"empathy_{i}") for i in range(3)) else ""
            label = f"Coaching exchange with Noor, a nervous rookie technician ({origin}; performance within a digital exercise)"
        elif cr["task"] == "walkthrough":
            parts = [f"Prompt: {q}\nCandidate: {answers.get('workflow_' + f, '').strip()}" for f, q in scoring.WORKFLOW_FIELDS]
            text = "\n".join(parts) if any(answers.get("workflow_" + f) for f, _ in scoring.WORKFLOW_FIELDS) else ""
            label = f"Transit ticketing walkthrough ({origin}; performance within a digital exercise)"
        else:
            text = answers.get(k, "").strip()
            label = f"Response to: {cr['question']} ({origin})"
        sources.append({"id": f"Q-{k}", "label": label, "criterion": k, "text": extraction.redact(text, names) if text else ""})
    for cl in db.q("SELECT * FROM clarifications WHERE candidate_id=? AND response IS NOT NULL ORDER BY id", (c["id"],)):
        prefix = "Remediation response" if cl["kind"] == "remediation" else "Clarification response"
        sources.append({"id": f"CL{cl['round_no']}-{cl['criterion']}", "criterion": cl["criterion"],
                        "label": f"{prefix} (round {cl['round_no']}) to: {cl['question'][:160]}",
                        "text": extraction.redact(cl["response"], names)})
    return {"platform": c["platform"], "workflow": c["workflow"], "sources": sources}


def snapshot_evidence(cid: int) -> int:
    c = cand(cid)
    v = c["evidence_version"] + 1
    db.ex("INSERT INTO evidence_versions(candidate_id, version, snapshot_json, created_at) VALUES (?,?,?,?)",
          (cid, v, json.dumps(build_snapshot(c)), db.now()))
    db.ex("UPDATE candidates SET evidence_version=? WHERE id=?", (v, cid))
    return v


async def run_assessment(cid: int) -> dict | None:
    c = cand(cid)
    if not c or c["status"] != "Assessing":
        return None
    ev = db.q1("SELECT * FROM evidence_versions WHERE candidate_id=? ORDER BY version DESC LIMIT 1", (cid,))
    snapshot = json.loads(ev["snapshot_json"])
    cfg_version, cfg = scoring.current_config()
    aid = db.ex("INSERT INTO assessments(candidate_id, evidence_version, config_version, round_no, mode, status, created_at) VALUES (?,?,?,?,?,?,?)",
                (cid, ev["version"], cfg_version, c["clarification_rounds"], ai.mode(), "running", db.now()))
    try:
        pass_a, pass_b = await asyncio.gather(ai.assessment_pass(snapshot, "A"), ai.assessment_pass(snapshot, "B"))
        db.ex("UPDATE assessments SET pass_a_json=?, pass_b_json=? WHERE id=?", (json.dumps(pass_a), json.dumps(pass_b), aid))
        moderation = await ai.moderate(snapshot, pass_a, pass_b)
    except Exception as e:
        db.ex("UPDATE assessments SET status='failed', error=?, completed_at=? WHERE id=?", (str(e), db.now(), aid))
        db.ex("UPDATE candidates SET last_error=? WHERE id=?", (f"AI assessment could not run ({e}). Answers are saved and will be retried.", cid))
        db.audit("assessment.failed", candidate_id=cid, error=str(e))
        return None
    if cand(cid)["status"] != "Assessing":  # withdrawn meanwhile
        db.ex("UPDATE assessments SET status='stopped', completed_at=? WHERE id=?", (db.now(), aid))
        return None
    final = {k: {"rating": m["final_rating"], "rating_basis": m["rating_basis"], "unsafe_serious": m["unsafe_serious"]}
             for k, m in moderation["criteria"].items()}
    result = scoring.score(final, cfg)
    for k, m in moderation["criteria"].items():
        if m["differed"]:
            db.audit("moderation.difference", candidate_id=cid, criterion=k, pass_a=m["pass_a"], pass_b=m["pass_b"],
                     final=m["final_rating"], resolution=m["resolution"], justification=m["justification"])
    needs = [(k, m) for k, m in moderation["criteria"].items() if m["resolution"] in ("clarification", "remediation")]
    rounds_left = c["clarification_rounds"] < int(cfg["max_clarification_rounds"])
    outcome = result["outcome"]
    if needs and not rounds_left and outcome != scoring.OUTCOME_REMEDIATION:
        outcome = scoring.OUTCOME_INCOMPLETE
    result["final_outcome"] = outcome
    result["recommendation"] = recommendation(outcome)
    db.ex("UPDATE assessments SET moderation_json=?, result_json=?, status='complete', completed_at=? WHERE id=?",
          (json.dumps(moderation), json.dumps(result), db.now(), aid))
    db.ex("UPDATE candidates SET outcome=?, last_error=NULL WHERE id=?", (outcome, cid))
    db.audit("assessment.complete", candidate_id=cid, outcome=outcome, score=result["score_text"], mode=ai.mode(),
             config_version=cfg_version, evidence_version=ev["version"])
    if needs and rounds_left and c["assessment_mode"] != "offline":
        rn = c["clarification_rounds"] + 1
        for k, m in needs:
            kind = "remediation" if m["resolution"] == "remediation" else "clarification"
            q = (m["remediation_exercise"] or ai.REMEDIATION_EXERCISE) if kind == "remediation" else (m["clarification_question"] or ai.CLARIFY_BANK[k])
            db.ex("INSERT INTO clarifications(candidate_id, assessment_id, round_no, criterion, kind, question, created_at) VALUES (?,?,?,?,?,?,?)",
                  (cid, aid, rn, k, kind, q, db.now()))
        set_status(cid, "Follow-up Requested")
    else:
        set_status(cid, "Assessed")
    return result


def recommendation(outcome: str) -> str:
    return {
        scoring.OUTCOME_MEETS: "Recommended for approval",
        scoring.OUTCOME_NOT_YET: "Not recommended at this stage",
        scoring.OUTCOME_REMEDIATION: "Not recommended until the safety concern is resolved",
        scoring.OUTCOME_INCOMPLETE: "Evidence incomplete: decide with caution",
        scoring.OUTCOME_EVIDENCE: "Evidence incomplete: decide with caution",
    }.get(outcome, "")


def open_clarifications(cid: int) -> list[dict]:
    return db.q("SELECT * FROM clarifications WHERE candidate_id=? AND response IS NULL ORDER BY id", (cid,))


def respond_clarifications(c: dict, responses: dict[int, str]) -> None:
    _active(c)
    if c["status"] != "Follow-up Requested":
        raise WorkflowError("There are no follow-up questions to answer.")
    pending = open_clarifications(c["id"])
    if any(not (responses.get(cl["id"]) or "").strip() for cl in pending):
        raise WorkflowError("Please answer every follow-up question.")
    for cl in pending:
        db.ex("UPDATE clarifications SET response=?, responded_at=? WHERE id=?", (responses[cl["id"]].strip()[:6000], db.now(), cl["id"]))
    db.ex("UPDATE candidates SET clarification_rounds=clarification_rounds+1 WHERE id=?", (c["id"],))
    set_status(c["id"], "Assessing", "candidate")
    snapshot_evidence(c["id"])


def latest_assessment(cid: int) -> dict | None:
    row = db.q1("SELECT * FROM assessments WHERE candidate_id=? ORDER BY id DESC LIMIT 1", (cid,))
    if row:
        for k in ("pass_a_json", "pass_b_json", "moderation_json", "result_json"):
            row[k[:-5]] = json.loads(row[k]) if row[k] else None
    return row


# ------------------------------------------------------------------ decisions
def decide(c: dict, decision: str, rationale: str) -> None:
    _active(c)
    if c["status"] not in ("Assessed", "Approved", "Not Approved"):
        raise WorkflowError("A candidate can be approved only after their assessment is complete.")
    if decision not in ("approved", "not_approved"):
        raise WorkflowError("Choose Approve or Not approve.")
    if not (rationale or "").strip():
        raise WorkflowError("Record a short rationale for the decision.")
    db.ex("UPDATE candidates SET decision=?, decision_rationale=?, decided_at=? WHERE id=?",
          (decision, rationale.strip()[:2000], db.now(), c["id"]))
    db.audit("decision." + decision, actor="lead", candidate_id=c["id"], rationale=rationale.strip())
    set_status(c["id"], "Approved" if decision == "approved" else "Not Approved", "lead")


def withdraw(c: dict, reason: str) -> None:
    if c["status"] == "Withdrawn":
        return
    security.revoke_links(c["id"])
    db.audit("withdrawn", actor="lead", candidate_id=c["id"], reason=reason)
    set_status(c["id"], "Withdrawn", "lead")


def set_extra_time(c: dict, factor: float) -> None:
    if not 1.0 <= factor <= 3.0:
        raise WorkflowError("Extra time must be between 1x and 3x.")
    db.ex("UPDATE candidates SET extra_time=? WHERE id=?", (factor, c["id"]))
    db.audit("adjustment.extra_time", actor="lead", candidate_id=c["id"], factor=factor)


# ------------------------------------------------------------------ dashboard
def dashboard(initiative_id: int | None = None, entity: int | None = None, category: str | None = None) -> dict:
    sql = ("SELECT c.*, e.name AS entity_name, i.name AS initiative_name FROM candidates c LEFT JOIN entities e ON e.id=c.entity_id "
           "JOIN initiatives i ON i.id=c.initiative_id WHERE c.status!='Withdrawn'")
    args: list = []
    if initiative_id:
        sql += " AND c.initiative_id=?"; args.append(initiative_id)
    if entity:
        sql += " AND c.entity_id=?"; args.append(entity)
    if category == "Not yet rated":
        sql += " AND c.fit_final IS NULL"
    elif category:
        sql += " AND c.fit_final=?"; args.append(category)
    rows = db.q(sql + " ORDER BY e.name, c.name", args)
    cats = scoring.FIT_CATEGORIES + ["Not yet rated"]
    by_cat = {k: 0 for k in cats}
    by_entity: dict[str, dict] = {}
    for r in rows:
        k = r["fit_final"] or "Not yet rated"
        by_cat[k] += 1
        e = by_entity.setdefault(r["entity_name"] or "—", {**{c: 0 for c in cats}, "total": 0, "approved": 0, "assessed": 0})
        e[k] += 1
        e["total"] += 1
        e["approved"] += r["status"] == "Approved"
        e["assessed"] += r["status"] in ("Assessed", "Approved", "Not Approved")
    approved_by_cat = {k: sum(1 for r in rows if r["status"] == "Approved" and (r["fit_final"] or "Not yet rated") == k) for k in cats}
    return {"rows": rows, "entities": len({r["entity_id"] for r in rows}), "champions": len(rows), "by_cat": by_cat,
            "approved": sum(1 for r in rows if r["status"] == "Approved"), "by_entity": by_entity, "approved_by_cat": approved_by_cat,
            "categories": cats}


# ------------------------------------------------------------------ jobs
async def run_jobs() -> str:
    retried = 0
    for r in db.q("SELECT id FROM candidates WHERE status='Assessing'"):
        try:
            if await run_assessment(r["id"]):
                retried += 1
        except Exception as e:
            db.audit("jobs.error", candidate_id=r["id"], error=str(e))
    rescreened = 0
    for r in db.q("SELECT id FROM candidates WHERE status='CV Uploaded' AND consent_screening=1 AND last_error IS NOT NULL"):
        rescreened += 1 if await screen(r["id"]) else 0
    purged = purge_expired()
    return f"{retried} assessment(s) completed, {rescreened} CV screening(s) retried, {purged} closed record(s) past retention cleared."


def purge_expired() -> int:
    days = int(scoring.current_config()[1]["retention_days"])
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.q("SELECT c.id FROM candidates c JOIN initiatives i ON i.id=c.initiative_id "
                "WHERE (i.status='closed' OR c.status IN ('Withdrawn','Not Approved','Not Shortlisted','No Consent')) AND c.status_changed_at < ? "
                "AND EXISTS (SELECT 1 FROM documents d WHERE d.candidate_id=c.id AND d.extract_status!='deleted')", (cutoff,))
    for r in rows:
        delete_documents(r["id"], f"Retention period of {days} days elapsed")
    return len(rows)


def delete_documents(cid: int, reason: str) -> None:
    for d in db.q("SELECT stored_path FROM documents WHERE candidate_id=? AND stored_path IS NOT NULL", (cid,)):
        Path(d["stored_path"]).unlink(missing_ok=True)
    db.ex("UPDATE documents SET stored_path=NULL, extracted_text=NULL, extract_status='deleted' WHERE candidate_id=?", (cid,))
    db.ex("UPDATE evidence_versions SET snapshot_json='{\"sources\":[],\"deleted\":true}' WHERE candidate_id=?", (cid,))
    db.audit("retention.deleted", actor="lead", candidate_id=cid, reason=reason)


# ------------------------------------------------------------------ clearing an initiative's data
def clear_initiative(iid: int, delete_initiative: bool = False) -> dict:
    """Permanently delete every nominee record for an initiative: CV files, AI results, answers, game
    records, links and their audit entries. Keeps one audit line with counts only (no personal data)."""
    ids = [r["id"] for r in db.q("SELECT id FROM candidates WHERE initiative_id=?", (iid,))]
    files = 0
    for cid in ids:
        for d in db.q("SELECT stored_path FROM documents WHERE candidate_id=? AND stored_path IS NOT NULL", (cid,)):
            Path(d["stored_path"]).unlink(missing_ok=True)
            files += 1
        folder = Path(config.settings.upload_dir) / str(cid)
        if folder.exists():
            for f in folder.iterdir():
                f.unlink(missing_ok=True)
            folder.rmdir()
    with db.tx() as conn:
        for table in ("documents", "cv_screenings", "evidence_versions", "assessments", "clarifications",
                      "game_sessions", "tokens", "emails", "audit"):
            conn.executemany(f"DELETE FROM {table} WHERE candidate_id=?", [(cid,) for cid in ids])
        conn.execute("DELETE FROM candidates WHERE initiative_id=?", (iid,))
        conn.execute("DELETE FROM entities WHERE id NOT IN (SELECT DISTINCT entity_id FROM candidates WHERE entity_id IS NOT NULL)")
        if delete_initiative:
            conn.execute("DELETE FROM initiative_steps WHERE initiative_id=?", (iid,))
            conn.execute("DELETE FROM initiatives WHERE id=?", (iid,))
        else:
            conn.execute("UPDATE initiative_steps SET completed_at=NULL WHERE initiative_id=?", (iid,))
    db.audit("initiative.deleted" if delete_initiative else "initiative.cleared", actor="lead",
             initiative_id=None if delete_initiative else iid, nominees=len(ids), files=files)
    return {"nominees": len(ids), "files": files}


# ------------------------------------------------------------------ LAUNCH WINDOW game
def game_load(cid: int) -> tuple[dict | None, list]:
    row = db.q1("SELECT * FROM game_sessions WHERE candidate_id=?", (cid,))
    if not row or not row["state_json"]:
        return None, []
    return json.loads(row["state_json"]), json.loads(row["events_json"] or "[]")


def game_save(cid: int, state: dict, events: list) -> None:
    db.ex("UPDATE game_sessions SET state_json=?, events_json=? WHERE candidate_id=?",
          (json.dumps(state), json.dumps(events), cid))


def game_start(c: dict) -> dict:
    from app import game
    _active(c)
    if c["status"] != "In Assessment" or not c["consent_assessment_at"]:
        raise WorkflowError("Please confirm your consent first.")
    state, _ = game_load(c["id"])
    if state and state.get("game") == "launch_window":
        return state
    if c["assessment_mode"] == "text" and json.loads(c["answers_json"] or "{}"):
        raise WorkflowError("You have already started the written version.")
    minutes = int(scoring.current_config()[1].get("game_minutes", 45))
    state = game.new_state(minutes, float(c["extra_time"] or 1.0))
    db.ex("INSERT OR REPLACE INTO game_sessions(candidate_id, state_json, events_json, started_at) VALUES (?,?,?,?)",
          (c["id"], json.dumps(state), "[]", db.now()))
    db.ex("UPDATE candidates SET assessment_mode='game' WHERE id=?", (c["id"],))
    db.audit("game.opened", actor="candidate", candidate_id=c["id"], minutes=minutes, extra_time=c["extra_time"])
    return state


def game_action(c: dict, action: str, params: dict, lang: str = "en") -> dict:
    """Apply one action (or a timer check when action is 'poll'). Returns the browser view in the player's language."""
    from app import game
    _active(c)
    state, events = game_load(c["id"])
    if not state:
        raise WorkflowError("The game has not been started.")
    if state.get("game") != "launch_window" and c["status"] == "In Assessment":
        state = game_start(c)  # an unfinished game from the previous engine restarts in LAUNCH WINDOW
        events = []
    if c["status"] != "In Assessment":
        return game.view(state, lang)
    before = len(events)
    if action == "poll":
        game.tick(state, events)
    else:
        try:
            game.act(state, events, action, params)
        except game.GameError as e:
            game_save(c["id"], state, events)
            v = game.view(state, lang)
            v["error"] = str(e)
            return v
    game_save(c["id"], state, events)
    if state["finished"] and len(events) > before or (state["finished"] and c["status"] == "In Assessment"):
        game_finish(c["id"], state, events)
    return game.view(state, lang)


def game_finish(cid: int, state: dict, events: list) -> None:
    from app import game
    c = cand(cid)
    if c["status"] != "In Assessment":
        return
    out = game.outcome(state)
    db.ex("UPDATE game_sessions SET outcome_json=?, completed_at=? WHERE candidate_id=?", (json.dumps(out), db.now(), cid))
    db.audit("game.finished", actor="candidate", candidate_id=cid, reason=state["end_reason"], events=len(events), **out)
    set_status(cid, "Assessing", "candidate")
    snapshot_evidence(cid)


def game_reset(c: dict) -> None:
    """Change Lead only: discard an unfinished game (e.g. after a technical problem) so the candidate can restart
    or use the written version."""
    if c["status"] not in ("Invited", "In Assessment"):
        raise WorkflowError("Only an unfinished game can be reset.")
    db.ex("DELETE FROM game_sessions WHERE candidate_id=?", (c["id"],))
    db.ex("UPDATE candidates SET assessment_mode=NULL WHERE id=?", (c["id"],))
    db.audit("game.reset", actor="lead", candidate_id=c["id"])
