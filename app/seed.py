"""Fictional demonstration data. Run:  python -m app.seed   (resets the local database).

Every record is fictional. Assessments are produced by running the real workflow with the
DEMO assessor, so they are stored with mode="demo" and shown as SIMULATED.
"""
from __future__ import annotations

import asyncio
import io
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import docx

from app import config, db, workflow
from app.main import startup

ENTITIES = [
    ("MDS", "Ministry of Digital Services", "وزارة الخدمات الرقمية", 3, "HR self-service, e-procurement, document management"),
    ("DMA", "Department of Municipal Affairs", "دائرة الشؤون البلدية", 3, "case management, e-procurement"),
    ("HSA", "Health Services Authority", "هيئة الخدمات الصحية", 4, "HR self-service, finance, case management"),
    ("EDC", "Education Council", "مجلس التعليم", 2, "document management, HR self-service"),
    ("TRA", "Transport Regulatory Authority", "هيئة تنظيم النقل", 2, "service portal, e-procurement"),
    ("PFD", "Public Finance Department", "دائرة المالية العامة", 3, "finance, e-procurement"),
]

STRONG = {
    "credibility": ("When our team moved leave requests to the HR self-service platform, several colleagues kept emailing paper "
                    "forms. Colleagues started coming to me for help, so I showed them the new steps at their desks and coached two "
                    "of them to demonstrate it to others. I collected feedback after two weeks and adopted their suggestions into a "
                    "one-page guide. We measured the paper forms received: they reduced from about forty a month to five, and the team "
                    "reported fewer errors in leave balances. Three colleagues started using the platform without help."),
    "empathy_0": "I understand — twelve years is a long time and change can feel frustrating. Let's look at it together, step by step. "
                 "The new platform removes the retyping you do at month end. Does that make sense so far?",
    "empathy_1": "Don't worry, you haven't broken anything — nothing is broken. The message means one required field is empty. "
                 "Let me show you where it is. Which part of the form were you on?",
    "empathy_2": "I'd rather we do it together so you feel confident. Try it while I watch, and we'll write short notes in your own "
                 "words so you can repeat it next time.",
    "reliability": ("A colleague could not submit purchase requisitions for a week because of an approval routing error. I logged a "
                    "ticket with the service desk, recorded the details in our team tracker, and confirmed the impact with the finance "
                    "owner. When the fix was delayed I sent an update to the affected users and explained the approved interim route. "
                    "I followed up every two days, escalated to the platform owner when the ticket passed its target date, and checked "
                    "back with the colleague after the fix to confirm it worked before the ticket was closed."),
    "curiosity": ("When the expense approval process changed last quarter, I read the release notes and the guidance, then practised in "
                  "the training sandbox. I wrote down each question I could not answer and asked the process owner, which showed my "
                  "assumption about delegation limits was wrong. I compared the new steps with the old checklist, tested two example "
                  "claims, and verified my understanding by walking a colleague through it and checking the result with finance."),
    "workflow_purpose": "Purchase requisitions let a department request goods; procurement and finance rely on accurate cost codes and approvals to commit budget.",
    "workflow_steps": "Create the requisition, choose the catalogue item, add the cost centre, attach the quote, submit for approval, and track each approval step until a purchase order is raised.",
    "workflow_exceptions": "Common exceptions are a rejected requisition because of a wrong cost code, a missing attachment, an approver on leave, or a supplier validation error.",
    "workflow_stop_refer": "I stop and refer when it is an access problem (access request to the administrator), a system error or defect (service desk ticket), or a policy question such as splitting orders (procurement policy owner).",
    "judgment": ("I would politely decline and explain why I cannot bypass the control: the approval control protects public funds and "
                 "the user's own accountability. I would check whether this is a skill gap, an access problem or a defect. If access is "
                 "missing we raise an access request; if it is a defect I log it with the service desk; if the deadline is critical I "
                 "escalate to the control owner for the approved route, such as a delegated approver. I record what happened and protect "
                 "any personal information in the request."),
}


def cv_bytes(name: str, role: str, platform: str) -> bytes:
    d = docx.Document()
    d.add_heading(name, 0)
    d.add_paragraph(f"{role}")
    d.add_paragraph(f"Experience: eight years in government administration, working daily on the {platform} platform and e-procurement.")
    d.add_paragraph("Supported colleagues during the platform rollout and coached new joiners on approved procedures.")
    d.add_paragraph("Logged and followed up service desk tickets for access and defect issues; recorded actions in the team tracker.")
    d.add_paragraph("Completed platform training and practised new releases in the sandbox before go-live.")
    d.add_paragraph("Date of birth: 01/01/1990")  # removed before assessment (personal characteristic)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def backdate(app_id: int, days: int) -> None:
    ts = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
    db.ex("UPDATE applications SET status_changed_at=?, created_at=? WHERE id=?", (ts, ts, app_id))


async def build_case(ent: dict, name: str, email: str, *, route="self", answers=None, platform="e-procurement",
                     workflow_name="Purchase requisitions", stop_at="submitted", nominator=None, hours=6.0) -> dict:
    form = dict(nominee_name=name, nominee_email=email, route=route, department="Corporate Services",
                business_function="Operations", location="Head office", platform=platform, workflow=workflow_name,
                reason="Patient and practical; colleagues already ask for help with the platform.",
                manager_name=f"Manager of {name.split()[0]}", manager_email=f"mgr.{email}")
    if nominator:
        form.update(nominator_name=nominator[0], nominator_email=nominator[1], nominator_relationship=nominator[2])
    a, _ = workflow.create_nomination(ent, form, actor="seed")
    if stop_at == "consent":
        return a
    workflow.record_consent(workflow.get_app(a["id"]), True, email)
    await workflow.upload_cv(workflow.get_app(a["id"]), f"{name.split()[0]}_CV.docx", cv_bytes(name, "Senior Administrative Officer", platform))
    workflow.save_application(workflow.get_app(a["id"]), {"answers": answers or {}, "availability": "Tuesday and Thursday afternoons",
                                                          "proposed_hours": hours})
    if stop_at == "in_progress":
        return workflow.get_app(a["id"])
    workflow.submit_application(workflow.get_app(a["id"]))
    await workflow.run_assessment(a["id"])
    return workflow.get_app(a["id"])


async def seed() -> None:
    config.settings.ai_mode = "demo"
    config.settings.email_mode = "demo"
    for p in (Path(config.settings.db_path), Path(config.settings.db_path + "-wal"), Path(config.settings.db_path + "-shm")):
        p.unlink(missing_ok=True)
    shutil.rmtree(config.settings.upload_dir, ignore_errors=True)
    startup()
    ents = {}
    for code, en, ar, target, plats in ENTITIES:
        eid = db.ex("INSERT INTO entities(code, name_en, name_ar, slug, target, priority_platforms, workflows, user_groups, locations, capacity_needs) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (code, en, ar, f"{code.lower()}-demo", target, plats, "Purchase requisitions, Leave requests",
                     "Administrative staff, line managers", "Head office, regional offices", "4-8 hours/month per champion"))
        dom = f"{code.lower()}.example.gov"
        db.ex("INSERT INTO contacts(entity_id, role, name, email) VALUES (?,?,?,?)", (eid, "focal", f"{code} Focal Point", f"focal@{dom}"))
        db.ex("INSERT INTO contacts(entity_id, role, name, email) VALUES (?,?,?,?)", (eid, "sponsor", f"{code} Sponsor", f"sponsor@{dom}"))
        ents[code] = db.q1("SELECT * FROM entities WHERE id=?", (eid,))

    # 1. Complete assessment meeting thresholds -> capacity confirmed -> awaiting sponsor decision.
    a1 = await build_case(ents["MDS"], "Aisha Rahman", "aisha.rahman@mds.example.gov", answers=STRONG)
    workflow.candidate_willingness(workflow.get_app(a1["id"]), True, a1["nominee_email"])
    workflow.manager_commit(workflow.get_app(a1["id"]), {"protected_hours": 6, "workload": "Two routine reports reassigned to a colleague.",
                            "availability": "Tue/Thu afternoons", "access_confirmed": "1"}, a1["manager_email"])
    # duplicate nomination of the same person (peer) - recorded, not duplicated
    workflow.create_nomination(ents["MDS"], dict(nominee_name="Aisha Rahman", nominee_email="aisha.rahman@mds.example.gov", route="peer",
                               nominator_name="Peer Colleague", nominator_email="peer@mds.example.gov", nominator_relationship="Colleague",
                               reason="She helps everyone.", platform="HR self-service", workflow="Leave requests"), actor="seed")

    # 2. Missing evidence requiring clarification.
    thin = dict(STRONG, curiosity="", reliability="I always follow up on issues.")
    await build_case(ents["DMA"], "Omar Haddad", "omar.haddad@dma.example.gov", answers=thin, platform="case management",
                     workflow_name="Permit applications")

    # 3. High overall score with a failed minimum criterion (empathy).
    weak_empathy = dict(STRONG,
                        empathy_0="I understand it is frustrating, but honestly the steps are obvious. Just read the manual first; management requires everyone to use it.",
                        empathy_1="That error is your fault for skipping a field. Go back and check it again before you ask anyone.",
                        empathy_2="I cannot do it for you. You should know this by now because the training was last month.")
    await build_case(ents["HSA"], "Layla Nasser", "layla.nasser@hsa.example.gov", answers=weak_empathy, platform="HR self-service",
                     workflow_name="Leave requests", route="manager", nominator=("Dr Samir Odeh", "samir.odeh@hsa.example.gov", "Line manager"))

    # 4. Remediation and reassessment (unsafe response).
    unsafe = dict(STRONG, judgment=("If the manager says it is urgent I would help the user finish. I could log in with my credentials "
                                    "and approve it just this once, then tell the team about it later in the week."))
    await build_case(ents["EDC"], "Yousef Karim", "yousef.karim@edc.example.gov", answers=unsafe, platform="document management",
                     workflow_name="Records filing")

    # 5. Awaiting manager commitment (overdue).
    a5 = await build_case(ents["PFD"], "Mariam Saleh", "mariam.saleh@pfd.example.gov", answers=STRONG, platform="finance",
                          workflow_name="Expense claims", route="peer", nominator=("Rami Aziz", "rami.aziz@pfd.example.gov", "Team colleague"))
    workflow.candidate_willingness(workflow.get_app(a5["id"]), True, a5["nominee_email"])
    backdate(a5["id"], 8)

    # 6. Provisional appointment awaiting day-90 review.
    a6 = await build_case(ents["TRA"], "Khalid Mansour", "khalid.mansour@tra.example.gov", answers=STRONG, platform="service portal",
                          workflow_name="Licence renewals")
    workflow.candidate_willingness(workflow.get_app(a6["id"]), True, a6["nominee_email"])
    workflow.manager_commit(workflow.get_app(a6["id"]), {"protected_hours": 8, "workload": "Counter rota adjusted on Wednesdays.",
                            "availability": "Wednesdays", "access_confirmed": "1"}, a6["manager_email"])
    workflow.sponsor_decide(workflow.get_app(a6["id"]), {"decision": "provisional", "rationale": "Meets thresholds; fills the service portal coverage gap.",
                            "coverage_need": "service portal", "coi_declared": "none"}, "sponsor@tra.example.gov")
    workflow.accept_role(workflow.get_app(a6["id"]), True, a6["nominee_email"])
    start = (date.today() - timedelta(days=80)).isoformat()
    workflow.update_onboarding(workflow.get_app(a6["id"]), {"buddy": "Hana Yusuf (champion, Licensing)", "objective": "Reduce rejected licence renewals caused by missing documents",
                               "start_date": start, **{f"check_{i}": "1" for i in range(5)}, "complete": "1"}, config.settings.lead_email)
    workflow.day90_input(workflow.get_app(a6["id"]), "nominee", {"readiness": "Mostly ready", "contribution": "Coached 14 colleagues; rejected renewals down by a third.",
                         "workload": "Sustainable", "willing": "Yes"}, a6["nominee_email"])

    # Others: awaiting consent (overdue peer nomination), in progress, withdrawn.
    a7 = await build_case(ents["DMA"], "Hassan Ali", "hassan.ali@dma.example.gov", route="peer", stop_at="consent",
                          nominator=("Dana Khoury", "dana.khoury@dma.example.gov", "Colleague"))
    backdate(a7["id"], 8)
    await build_case(ents["MDS"], "Sara Ibrahim", "sara.ibrahim@mds.example.gov", stop_at="in_progress",
                     answers={"credibility": STRONG["credibility"]}, platform="HR self-service", workflow_name="Leave requests")
    a9 = await build_case(ents["HSA"], "Noor Jaber", "noor.jaber@hsa.example.gov", stop_at="consent")
    workflow.record_consent(workflow.get_app(a9["id"]), True, a9["nominee_email"])
    workflow.withdraw(workflow.get_app(a9["id"]), "Moving to a new role", "nominee", a9["nominee_email"])

    for a in db.q("SELECT ref, nominee_name, status, outcome FROM applications ORDER BY id"):
        print(f"  {a['ref']}  {a['nominee_name']:<16} {a['status']:<30} {a['outcome'] or ''}")


if __name__ == "__main__":
    asyncio.run(seed())
    print("\nDemo data loaded. Start the server and open /demo")
