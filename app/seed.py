"""Fictional demonstration data for version 2. Run:  python -m app.seed   (resets the local database).

All people are fictional. AI results come from the labelled DEMO assessor (SIMULATED).
Also writes samples/nominations_sample.csv, a Microsoft Forms-style export you can import yourself.
"""
from __future__ import annotations

import asyncio
import csv
import io
import shutil
from pathlib import Path

import docx

from app import config, db, game, imports, workflow
from app.config import BASE_DIR
from app.main import startup

HEADER = ["ID", "Start time", "Completion time", "Email", "Name", "Nominee name", "Nominee work email", "Entity",
          "Department", "Platform", "Workflow", "Nomination type", "Why are you nominating them?",
          "Line manager name", "Line manager email", "Has the nominee agreed to AI screening of their CV?"]

# (name, entity, department, platform, workflow, route, consent, cv_tier)
PEOPLE = [
    ("Aisha Rahman", "Ministry of Digital Services", "Corporate Services", "ERP", "Purchase requisitions", "Self", "Yes", "high"),
    ("Omar Haddad", "Department of Municipal Affairs", "Permits", "ERP", "Supplier onboarding", "Peer", "Yes", "high"),
    ("Layla Nasser", "Health Services Authority", "Finance", "ERP", "Expense claims", "Manager", "Yes", "high"),
    ("Yousef Karim", "Education Council", "Procurement", "ERP", "Purchase requisitions", "Peer", "Yes", "moderate"),
    ("Mariam Saleh", "Public Finance Department", "Accounts Payable", "ERP", "Invoice approval", "Manager", "Yes", "high"),
    ("Khalid Mansour", "Transport Regulatory Authority", "Licensing", "ERP", "Purchase requisitions", "Self", "Yes", "high"),
    ("Hassan Ali", "Department of Municipal Affairs", "Planning", "ERP", "Budget transfers", "Peer", "Yes", "moderate"),
    ("Sara Ibrahim", "Ministry of Digital Services", "HR", "ERP", "Leave requests", "Self", "Yes", "moderate"),
    ("Noor Jaber", "Health Services Authority", "Records", "ERP", "Purchase requisitions", "Peer", "Yes", "low"),
    ("Rami Aziz", "Public Finance Department", "Treasury", "ERP", "Payments", "Manager", "Yes", "low"),
    ("Dana Khoury", "Education Council", "Facilities", "ERP", "Work orders", "Peer", "Yes", "none"),
    ("Fadi Tawil", "Transport Regulatory Authority", "Customer Service", "ERP", "Refunds", "Self", "No", "moderate"),
    ("Huda Saeed", "Ministry of Digital Services", "Legal", "ERP", "Contract approvals", "Manager", "Yes", "high"),
    ("Samir Odeh", "Health Services Authority", "Pharmacy", "ERP", "Stock requests", "Peer", "Yes", "moderate"),
]

ANSWERS = {
    "credibility": ("I would not keep fixing Harbour's routing myself. I would sit with the Harbour team, showed them how to read the "
                    "routing map, then coached one of their operators to demonstrate the fix to the others. I would collect feedback "
                    "after the next shift and adjust the guide. If Market district started using the same checklist without being "
                    "asked, and Harbour reported fewer errors, I would know the approach was spreading. I would also measured how "
                    "often Harbour still called me; that should drop."),
    "empathy_0": "I understand, it is normal to worry the first time. Let's look at it together, step by step. The power link is the one with the green tag. Does that make sense so far?",
    "empathy_1": "Don't worry, you haven't broken anything, nothing is broken. The red warning just means the link is still syncing. Which part did you do last?",
    "empathy_2": "I'd rather we do it together so you feel confident next time. Try it while I watch, and we'll write short notes in your own words that you can reuse.",
    "reliability": ("I would tell Clinic district straight away that the outage affects my promise, rather than letting it slip. I "
                    "logged the commitment in the city tracker, recorded the new risk, and sent an update to Clinic and the outage "
                    "lead explaining the delay and a new date. I escalated to the resource owner so the backup line stayed on the "
                    "priority list, followed up every day, and checked back with Clinic after the line was restored to confirm it "
                    "worked before I closed the item."),
    "curiosity": ("First I would read the council's change notice and the release notes, then practise the new rules in the training "
                  "sandbox. I would write down the questions I could not answer and asked the council's routing officer, because my "
                  "assumption about priority lanes might be wrong. I compared my old plan with the new rules, tested it on one "
                  "district first, and verified the result with the network team before rolling it out."),
    "workflow_purpose": "Ticketing lets residents pay for and validate journeys; Transit operations and the finance office rely on it for accurate fares and passenger counts.",
    "workflow_steps": "Check the outage scope, restore the card readers' network step by step, confirm payment approval with finance, validate test transactions, then reopen the gates.",
    "workflow_exceptions": "Common exceptions are a rejected payment batch, a reader with the wrong configuration, missing access rights for station staff, or an error in fare tables.",
    "workflow_stop_refer": "I stop and refer when it is an access problem (access office), a system defect or error (network engineers via the service desk), or a fare policy question (council policy team).",
    "judgment": ("I would politely decline and explain why I cannot bypass the safety lock: it protects residents and the official too. "
                 "I would check whether this is an access problem or a defect, escalate to the control owner straight away, and "
                 "offer the approved route, an emergency restart that keeps the lock in place. I would record the request and "
                 "protect any personal information in the incident log."),
}
WEAK_EMPATHY = dict(ANSWERS,
                    empathy_0="I understand it is frustrating, but the steps are obvious. Just read the guide first; it is all in there.",
                    empathy_1="That warning is your fault for skipping a step. Go back and check it again before asking me.",
                    empathy_2="I cannot do it for you. You should know this by now after the training.")
UNSAFE = dict(ANSWERS, judgment=("If the Director says it is that urgent I would override the lock just this once so we keep the "
                                 "launch window, then tell the team about it later in the week."))
THIN = dict(ANSWERS, curiosity="", reliability="I always keep my promises.")


# A sound playthrough of LAUNCH WINDOW used for demo data and tests.
GOOD_PLAY = [
    ("begin", {}), ("travel", {"to": "briefing"}),
    *[("open_file", {"id": f}) for f in ("F2", "F4", "F6", "F8")],
    ("answer", {"q": "q1", "choice": "confirm"}), ("answer", {"q": "q2", "choice": "range"}), ("answer", {"q": "q3", "choice": "route"}),
    ("noor", {"choice": "coach"}), ("noor", {"choice": "reassure"}), ("noor", {"choice": "guide"}), ("noor", {"choice": "multiply"}),
    ("call", {"id": "c1", "choice": "route"}), ("call", {"id": "c2", "choice": "teach"}), ("call", {"id": "c3", "choice": "route"}),
    ("call", {"id": "c4", "choice": "promise"}), ("call", {"id": "c5", "choice": "promise"}), ("to_control", {}),
    ("alert", {"id": "A1", "choice": "send"}), ("alert", {"id": "A2", "choice": "route", "station": "access"}),
    ("alert", {"id": "A3", "choice": "route", "station": "comms"}),
    ("director", {"choice": "refuse_escalate", "text": "I can't override it. Only Range Safety can release the lock; I'm calling them now."}),
    ("alert", {"id": "A4", "choice": "confirm"}), ("priority", {"choice": "critical"}),
    *[("hamad", {"choice": c}) for c in ("ask", "reset", "reassure", "check")],
    ("promise", {"id": "P-c4", "choice": "deliver"}), ("promise", {"id": "P-c5", "choice": "warn"}),
    ("handover", {"actions": ["pair", "guide", "brief"],
                  "note": "Done: valve V-7 reset and checked; Rashid's checklist returned. Not done: Yousef's valve readings are late and he knows. Owners: fuel bay for V-7, Range Safety for the lock."}),
    ("continue", {}),
    ("realwork", {"q1": "When our team moved to the new leave system I sat with a colleague, let her drive, and wrote a one-page guide she now shares with others.",
                  "q2": "Purchase approvals stall when the budget code is wrong. I check the code with finance before submitting and keep a list of the common mistakes."}),
]


def cv_bytes(name: str, tier: str, platform: str) -> bytes:
    lines = {
        "high": [f"Senior Administrative Officer", f"Eight years using the {platform} platform for requisitions and approvals.",
                 "Trained new staff on the platform and coached colleagues through the last release.",
                 "Supported colleagues at their desks during go-live; helped colleagues build quick reference guides.",
                 "Logged tickets with the service desk and followed up until resolved; kept the team tracker up to date.",
                 "Completed platform training and practised each release in the sandbox."],
        "moderate": [f"Administrative Coordinator", f"Uses the {platform} system daily for team requests.",
                     "Helped colleagues with approvals when they were unsure.", "Attended platform training in 2025."],
        "low": ["Administrative Assistant", "Manages the director's calendar and filing.", "Prepares monthly reports from the finance system."],
        "none": ["Facilities Technician", "Maintains building equipment and schedules contractors."],
    }[tier]
    d = docx.Document()
    d.add_heading(name, 0)
    for l in lines:
        d.add_paragraph(l)
    d.add_paragraph("Date of birth: 01/01/1990")  # removed before AI screening
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def write_sample_csv() -> Path:
    path = BASE_DIR / "samples" / "nominations_sample.csv"
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for n, (name, ent, dept, plat, wf, route, consent, _) in enumerate(PEOPLE, start=1):
            first = name.split()[0].lower()
            w.writerow([n, "2026-11-01 09:00", "2026-11-01 09:05", f"nominator{n}@example.gov", f"Nominator {n}", name,
                        f"{first}.{name.split()[1].lower()}@example.gov", ent, dept, plat, wf, route,
                        f"{name.split()[0]} is patient and already helps colleagues with {plat}.",
                        f"Manager of {first.title()}", f"manager.{first}@example.gov", consent])
    return path


async def seed() -> None:
    config.settings.ai_mode = "demo"
    for p in (Path(config.settings.db_path), Path(config.settings.db_path + "-wal"), Path(config.settings.db_path + "-shm")):
        p.unlink(missing_ok=True)
    shutil.rmtree(config.settings.upload_dir, ignore_errors=True)
    startup()

    # Initiative 1: full pipeline
    iid = workflow.create_initiative("ERP Release 3", "ERP", "Champions for the ERP purchasing and finance release.")
    path = write_sample_csv()
    header, rows = imports.read_table(path.name, path.read_bytes())
    records, _ = imports.apply_mapping(header, rows, imports.guess_mapping(header))
    workflow.import_records(iid, records)
    tiers = {p[0]: p[7] for p in PEOPLE}
    files = []
    for c in db.q("SELECT id, name FROM candidates WHERE initiative_id=?", (iid,)):
        if c["name"] == "Samir Odeh":
            continue  # left without a CV
        files.append((f"{c['name'].replace(' ', '_')}_CV.docx", cv_bytes(c["name"], tiers[c["name"]], "ERP")))
    matches = workflow.match_files(iid, [f for f, _ in files])
    for fn, data in files:
        workflow.upload_cv(workflow.cand(matches[fn]), fn, data)
    await workflow.screen_many([r["id"] for r in db.q("SELECT id FROM candidates WHERE initiative_id=? AND status='CV Uploaded'", (iid,))])

    by = {r["name"]: r["id"] for r in db.q("SELECT id, name FROM candidates WHERE initiative_id=?", (iid,))}
    # Change Lead override: Noor moved up after a strong nomination reason
    workflow.override_fit(workflow.cand(by["Noor Jaber"]), "Moderate Fit", "Strong peer feedback in the nomination; CV is brief.")

    plans = {"Aisha Rahman": ANSWERS, "Omar Haddad": ANSWERS, "Layla Nasser": WEAK_EMPATHY, "Yousef Karim": UNSAFE,
             "Mariam Saleh": ANSWERS, "Khalid Mansour": THIN, "Huda Saeed": ANSWERS}
    for name, answers in plans.items():
        c = workflow.cand(by[name])
        workflow.invite(c)
        workflow.confirm_consent(workflow.cand(c["id"]))
        workflow.save_answers(workflow.cand(c["id"]), answers, "text")
        workflow.submit_answers(workflow.cand(c["id"]))
        await workflow.run_assessment(c["id"])
    for name in ("Hassan Ali", "Sara Ibrahim", "Noor Jaber"):
        workflow.invite(workflow.cand(by[name]))
    # Hassan plays the whole LAUNCH WINDOW game; Noor is part-way through Act II
    for name, moves in (("Hassan Ali", GOOD_PLAY), ("Noor Jaber", GOOD_PLAY[:12])):
        cid = by[name]
        workflow.confirm_consent(workflow.cand(cid))
        workflow.game_start(workflow.cand(cid))
        for a, p in moves:
            workflow.game_action(workflow.cand(cid), a, p)
    await workflow.run_assessment(by["Hassan Ali"])
    workflow.confirm_consent(workflow.cand(by["Sara Ibrahim"]))
    workflow.save_answers(workflow.cand(by["Sara Ibrahim"]), {"credibility": ANSWERS["credibility"]}, "text")

    workflow.decide(workflow.cand(by["Aisha Rahman"]), "approved", "Meets thresholds; strong evidence of building capability in others.")
    workflow.decide(workflow.cand(by["Omar Haddad"]), "approved", "Meets thresholds; fills the Municipal Affairs coverage gap.")
    workflow.decide(workflow.cand(by["Layla Nasser"]), "not_approved", "Below the empathy minimum; revisit after coaching.")
    for step in (1, 2, 3, 4, 5, 6):
        workflow.set_step(iid, step, True)

    # Initiative 2: just started
    iid2 = workflow.create_initiative("HR Self-Service Rollout", "HR self-service", "Leave and payroll self-service champions.")
    workflow.set_step(iid2, 1, True)
    sub = [r for r in rows if r[7] in ("Ministry of Digital Services", "Education Council")][:3]
    records2, _ = imports.apply_mapping(header, sub, imports.guess_mapping(header))
    workflow.import_records(iid2, records2)
    workflow.set_step(iid2, 2, True)

    for c in db.q("SELECT c.name, c.status, c.fit_final, c.outcome, i.name AS init FROM candidates c JOIN initiatives i ON i.id=c.initiative_id ORDER BY c.id"):
        print(f"  {c['init'][:14]:<14} {c['name']:<15} {c['status']:<20} {c['fit_final'] or '':<13} {c['outcome'] or ''}")


if __name__ == "__main__":
    asyncio.run(seed())
    print("\nDemo data loaded. Start the server, open http://localhost:8000 and sign in with the password: demo")
