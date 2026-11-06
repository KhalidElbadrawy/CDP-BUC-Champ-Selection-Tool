"""FastAPI application: routes for all six screen types. Permissions are enforced here, server-side."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import ai, config, db, emails, production, scoring, security, workflow
from app.i18n import translator
from app.security import COOKIE, LinkError, Principal
from app.workflow import WorkflowError

HERE = Path(__file__).parent


@asynccontextmanager
async def lifespan(_app):
    startup()
    for problem in production.setup_problems():
        logging.getLogger("cdp").error("SETUP INCOMPLETE: %s", problem)
    task = asyncio.create_task(production.scheduler_loop())
    yield
    task.cancel()


app = FastAPI(title="CDP Champion Nomination Tool", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.filters["fromjson"] = lambda s: json.loads(s) if s else {}


def startup() -> None:
    db.init_db()
    scoring.current_config()
    emails.seed_templates()
    if not db.q1("SELECT 1 FROM rounds"):
        db.ex("INSERT INTO rounds(name, status, opens_on, created_at) VALUES (?,?,?,?)",
              ("Round 1", "open", date.today().isoformat(), db.now()))


def demo_launcher_enabled() -> bool:
    if production.is_production():
        return False  # never on a public server
    return os.environ.get("CDP_DEMO_LAUNCHER", "1") == "1" and config.settings.email_mode == "demo"


@app.middleware("http")
async def production_lock(request: Request, call_next):
    """On a public server, show only a setup checklist until every required setting is in place."""
    problems = production.setup_problems()
    if problems and not request.url.path.startswith("/static"):
        items = "".join(f"<li>{p}</li>" for p in problems)
        html = ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>Setup incomplete</title><link rel='stylesheet' href='/static/style.css'></head><body><main class='wrap'>"
                "<div class='card' style='margin-top:24px'><h1>Setup incomplete</h1><p>The CDP Champion tool is locked until these "
                f"settings are added in the hosting service's Environment settings:</p><ul>{items}</ul>"
                "<p class='muted'>After saving the settings, the service restarts and this page disappears.</p></div></main></body></html>")
        return HTMLResponse(html, status_code=503)
    return await call_next(request)


# ------------------------------------------------------------------ rendering helpers
def principal_or_none(request: Request) -> Principal | None:
    try:
        return security.resolve(request.cookies.get(COOKIE))
    except LinkError:
        return None


def render(request: Request, name: str, status_code: int = 200, **ctx) -> HTMLResponse:
    lang = request.cookies.get("lang", "en")
    ctx.setdefault("principal", principal_or_none(request))
    base = dict(
        _=translator(lang), lang=lang, dir="rtl" if lang == "ar" else "ltr",
        csrf=security.csrf_token(request), ai_mode=config.settings.ai_mode, email_mode=config.settings.email_mode,
        msg=request.query_params.get("msg"), err=request.query_params.get("err"),
        demo_launcher=demo_launcher_enabled(), scoring=scoring, today=date.today().isoformat(),
    )
    base.update(ctx)
    return templates.TemplateResponse(request, name, base, status_code=status_code)


def back(url: str, msg: str | None = None, err: str | None = None) -> RedirectResponse:
    sep = "&" if "?" in url else "?"
    if msg:
        url += f"{sep}msg={quote(msg)}"
    elif err:
        url += f"{sep}err={quote(err)}"
    return RedirectResponse(url, status_code=303)


async def form_data(request: Request) -> dict:
    form = await request.form()
    data = {k: v for k, v in form.multi_items() if not hasattr(v, "filename")}
    if request.cookies.get(COOKIE):
        security.check_csrf(request, data.get("csrf"))
    return data


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        reason = {"expired": "This link has expired.", "revoked": "This link has been revoked."}.get(exc.detail, "This link is not valid.")
        return render(request, "notice.html", 401, title="Link problem", body=reason, show_request=True, principal=None)
    return render(request, "notice.html", exc.status_code, title="Not available", body=str(exc.detail), show_request=False)


def app_for(p: Principal, app_id: int) -> dict:
    return security.assert_application(p, workflow.get_app(app_id))


def enrich(apps: list[dict]) -> list[dict]:
    for a in apps:
        a["next"] = workflow.next_action(a)
    return apps


# ------------------------------------------------------------------ public & access
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return render(request, "home.html")


@app.get("/lang/{code}")
def set_lang(code: str, request: Request):
    resp = RedirectResponse(request.headers.get("referer") or "/", status_code=303)
    resp.set_cookie("lang", "ar" if code == "ar" else "en", max_age=365 * 86400, samesite="lax")
    return resp


@app.get("/a/{token}")
def open_link(token: str, request: Request):
    try:
        p = security.resolve(token)
    except LinkError as e:
        raise HTTPException(401, e.reason)
    dest = {"lead": "/lead", "focal": "/entity", "sponsor": "/sponsor", "nominee": "/me", "manager": "/manager"}[p.role]
    resp = RedirectResponse(dest, status_code=303)
    resp.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=config.settings.base_url.startswith("https"), max_age=60 * 86400)
    db.audit("link.opened", actor_role=p.role, actor_email=p.email, application_id=p.application_id, entity_id=p.entity_id)
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(COOKIE)
    return resp


@app.get("/access", response_class=HTMLResponse)
def access_form(request: Request):
    return render(request, "access.html")


@app.post("/access", response_class=HTMLResponse)
async def access_request(request: Request):
    form = await request.form()
    email = (form.get("email") or "").strip().lower()
    issued = request_fresh_links(email) if email else []
    # Always the same response: never reveal whether an address is known.
    return render(request, "notice.html", title="Check your email",
                  body="If this address is linked to the CDP Champion programme, a fresh access link has been emailed to it.",
                  demo_links=issued if demo_launcher_enabled() else None)


def request_fresh_links(email: str) -> list[str]:
    links: list[str] = []

    def issue(role, **scope):
        raw = security.issue_token(role, email, **scope)
        res = emails.send("access_link", email, {"link": security.link_for(raw), "expires": workflow._expires(role)},
                          application=workflow.get_app(scope["application_id"]) if scope.get("application_id") else None,
                          entity_id=scope.get("entity_id"), triggered_by="self-service")
        if res["status"] != "suppressed":
            links.append(security.link_for(raw))

    if email == config.settings.lead_email:
        issue("lead")
    for c in db.q("SELECT * FROM contacts WHERE lower(email)=? AND active=1", (email,)):
        issue(c["role"], entity_id=c["entity_id"])
    for a in db.q("SELECT id FROM applications WHERE lower(nominee_email)=?", (email,)):
        issue("nominee", application_id=a["id"])
    for a in db.q("SELECT id FROM applications WHERE lower(manager_email)=? AND status IN ('Awaiting Manager Commitment','Awaiting Day-90 Review')", (email,)):
        issue("manager", application_id=a["id"])
    db.audit("access.requested", actor_email=email, issued=len(links))
    return links


@app.get("/n/{slug}", response_class=HTMLResponse)
def nomination_form(slug: str, request: Request):
    ent = db.q1("SELECT * FROM entities WHERE slug=?", (slug,))
    if not ent:
        raise HTTPException(404, "This nomination link is not valid.")
    rnd = db.q1("SELECT * FROM rounds WHERE status='open' ORDER BY id DESC LIMIT 1")
    return render(request, "nominate.html", entity=ent, round=rnd, form={})


@app.post("/n/{slug}", response_class=HTMLResponse)
async def nomination_submit(slug: str, request: Request):
    ent = db.q1("SELECT * FROM entities WHERE slug=?", (slug,))
    if not ent:
        raise HTTPException(404, "This nomination link is not valid.")
    form = {k: (v or "").strip() for k, v in (await request.form()).items() if isinstance(v, str)}
    required = ["nominee_name", "nominee_email", "route", "department", "platform", "workflow", "reason", "manager_name", "manager_email"]
    if form.get("route") in ("peer", "manager"):
        required += ["nominator_name", "nominator_email", "nominator_relationship"]
    missing = [k for k in required if not form.get(k)]
    if missing or "@" not in form.get("nominee_email", ""):
        rnd = db.q1("SELECT * FROM rounds WHERE status='open' ORDER BY id DESC LIMIT 1")
        return render(request, "nominate.html", 422, entity=ent, round=rnd, form=form,
                      error="Please complete all required fields: " + ", ".join(m.replace("_", " ") for m in missing))
    try:
        application, duplicate = workflow.create_nomination(ent, form)
    except WorkflowError as e:
        return render(request, "notice.html", 409, title="Nomination not recorded", body=str(e))
    demo_link = None
    if demo_launcher_enabled() and not duplicate:
        last = db.q1("SELECT body FROM emails WHERE application_id=? ORDER BY id DESC LIMIT 1", (application["id"],))
        demo_link = next((l for l in (last["body"] if last else "").split() if "/a/" in l), None)
    # Identical message for new and duplicate nominations: no existing data is exposed.
    return render(request, "notice.html", title="Thank you",
                  body="The nomination has been received. The nominee will receive an email asking for their consent "
                       "before anything further happens.", demo_links=[demo_link] if demo_link else None)


# ------------------------------------------------------------------ nominee
def nominee(request: Request) -> tuple[Principal, dict]:
    p = security.require(request, "nominee")
    return p, app_for(p, p.application_id)


@app.get("/me", response_class=HTMLResponse)
def me(request: Request):
    p, a = nominee(request)
    asmt = workflow.latest_assessment(a["id"])
    communicated = a["status"] in ("Awaiting Manager Commitment", "Awaiting Sponsor Decision", "Not Selected",
                                   "Provisionally Appointed", "Onboarding", "Awaiting Day-90 Review", "Confirmed") \
        or a["outcome_communicated_at"]
    return render(request, "nominee.html", a=a, answers=json.loads(a["answers_json"] or "{}"),
                  extracted=json.loads(a["extracted_json"] or "{}"), doc=workflow.latest_document(a["id"]),
                  screen=workflow.latest_screen(a["id"]), clarifications=workflow.open_clarifications(a["id"]),
                  asmt=asmt if communicated else None, next=workflow.next_action(a),
                  onboarding=db.q1("SELECT * FROM onboarding WHERE application_id=?", (a["id"],)),
                  review=db.q1("SELECT * FROM day90_reviews WHERE application_id=?", (a["id"],)),
                  sim=ai.simulation_prompts(), statuses=workflow.STATUSES)


@app.post("/me/consent")
async def me_consent(request: Request):
    p, a = nominee(request)
    f = await form_data(request)
    try:
        workflow.record_consent(a, f.get("consent") == "yes", p.email)
    except WorkflowError as e:
        return back("/me", err=str(e))
    return back("/me", msg="Thank you. Your response has been recorded.")


def _application_payload(f: dict) -> dict:
    answers = {k[2:]: v for k, v in f.items() if k.startswith("a_")}
    extracted = {k[2:]: v for k, v in f.items() if k.startswith("x_")}
    payload = {"answers": answers, "availability": f.get("availability")}
    if extracted:
        payload["extracted"] = extracted
    try:
        payload["proposed_hours"] = float(f["proposed_hours"]) if f.get("proposed_hours") else None
    except ValueError:
        payload["proposed_hours"] = None
    return payload


@app.post("/me/save")
async def me_save(request: Request, background: BackgroundTasks):
    p, a = nominee(request)
    f = await form_data(request)
    try:
        workflow.save_application(a, _application_payload(f))
        if f.get("action") == "submit":
            workflow.submit_application(workflow.get_app(a["id"]))
            background.add_task(workflow.run_assessment, a["id"])
            return back("/me", msg="Application submitted. Automated assessment has started.")
    except WorkflowError as e:
        return back("/me", err=str(e))
    return back("/me", msg="Saved. You can return at any time using your link.")


@app.post("/me/cv")
async def me_cv(request: Request):
    p, a = nominee(request)
    form = await request.form()
    security.check_csrf(request, form.get("csrf"))
    up = form.get("cv")
    if not up or not getattr(up, "filename", ""):
        return back("/me", err="Choose a PDF or DOCX file to upload.")
    data = await up.read()
    try:
        res = await workflow.upload_cv(a, up.filename, data)
    except WorkflowError as e:
        return back("/me", err=str(e))
    if res["status"] != "ok":
        return back("/me", err=res["error"])
    if res.get("error"):
        return back("/me", err=res["error"])
    return back("/me#extracted", msg="CV uploaded. Please review the extracted information and correct anything that is wrong.")


@app.post("/me/clarify")
async def me_clarify(request: Request, background: BackgroundTasks):
    p, a = nominee(request)
    f = await form_data(request)
    responses = {int(k[3:]): v for k, v in f.items() if k.startswith("cl_")}
    try:
        workflow.respond_clarifications(a, responses)
    except WorkflowError as e:
        return back("/me", err=str(e))
    background.add_task(workflow.run_assessment, a["id"])
    return back("/me", msg="Thank you. Your responses were submitted and automated reassessment has started.")


@app.post("/me/willing")
async def me_willing(request: Request):
    p, a = nominee(request)
    f = await form_data(request)
    try:
        workflow.candidate_willingness(a, f.get("willing") == "yes", p.email)
    except WorkflowError as e:
        return back("/me", err=str(e))
    return back("/me", msg="Thank you, recorded.")


@app.post("/me/accept")
async def me_accept(request: Request):
    p, a = nominee(request)
    f = await form_data(request)
    if f.get("accept") == "yes" and not f.get("charter_read"):
        return back("/me", err="Please confirm you have read the role charter.")
    try:
        workflow.accept_role(a, f.get("accept") == "yes", p.email)
    except WorkflowError as e:
        return back("/me", err=str(e))
    return back("/me", msg="Thank you, your response is recorded.")


@app.post("/me/day90")
async def me_day90(request: Request):
    p, a = nominee(request)
    f = await form_data(request)
    try:
        workflow.day90_input(a, "nominee", f, p.email)
    except WorkflowError as e:
        return back("/me", err=str(e))
    return back("/me", msg="Day-90 review input submitted.")


@app.post("/me/withdraw")
async def me_withdraw(request: Request):
    p, a = nominee(request)
    f = await form_data(request)
    workflow.withdraw(a, f.get("reason") or "Withdrawn by nominee", "nominee", p.email)
    return back("/me", msg="Your withdrawal has been recorded. No further assessment or reminders will take place.")


@app.post("/me/reconsider")
async def me_reconsider(request: Request):
    p, a = nominee(request)
    f = await form_data(request)
    text = (f.get("text") or "").strip()
    if not text:
        return back("/me", err="Please explain what should be corrected or reconsidered.")
    db.ex("UPDATE applications SET reconsideration_request=? WHERE id=?", (text, a["id"]))
    db.audit("reconsideration.requested", actor_role="nominee", actor_email=p.email, application_id=a["id"])
    return back("/me", msg="Your request has been sent to the CDP Change Lead.")


@app.get("/doc/{doc_id}")
def download_doc(doc_id: int, request: Request):
    p = security.current(request)
    d = db.q1("SELECT * FROM documents WHERE id=?", (doc_id,))
    a = workflow.get_app(d["application_id"]) if d else None
    if not d or not a or not security.can_view_private_evidence(p, a) or not d["stored_path"]:
        raise HTTPException(404, "Document not available for this link.")
    db.audit("document.viewed", actor_role=p.role, actor_email=p.email, application_id=a["id"], document_id=doc_id)
    return FileResponse(d["stored_path"], filename=d["filename"], media_type=d["mime"] or "application/octet-stream")


# ------------------------------------------------------------------ manager
@app.get("/manager", response_class=HTMLResponse)
def manager_view(request: Request):
    p = security.require(request, "manager")
    a = app_for(p, p.application_id)
    return render(request, "manager.html", a=a,
                  mc=db.q1("SELECT * FROM manager_commitments WHERE application_id=?", (a["id"],)),
                  review=db.q1("SELECT * FROM day90_reviews WHERE application_id=?", (a["id"],)),
                  next=workflow.next_action(a))


@app.post("/manager/commit")
async def manager_commit(request: Request):
    p = security.require(request, "manager")
    a = app_for(p, p.application_id)
    f = await form_data(request)
    try:
        workflow.manager_commit(a, f, p.email)
    except (WorkflowError, ValueError) as e:
        return back("/manager", err=str(e))
    return back("/manager", msg="Thank you. Your commitment has been recorded.")


@app.post("/manager/day90")
async def manager_day90(request: Request):
    p = security.require(request, "manager")
    a = app_for(p, p.application_id)
    f = await form_data(request)
    try:
        workflow.day90_input(a, "manager", f, p.email)
    except WorkflowError as e:
        return back("/manager", err=str(e))
    return back("/manager", msg="Day-90 review input submitted.")


# ------------------------------------------------------------------ sponsor
@app.get("/sponsor", response_class=HTMLResponse)
def sponsor_view(request: Request):
    p = security.require(request, "sponsor")
    ent = db.q1("SELECT * FROM entities WHERE id=?", (p.entity_id,))
    pending = enrich(db.q("SELECT a.*, e.name_en AS entity_name FROM applications a JOIN entities e ON e.id=a.entity_id "
                          "WHERE a.entity_id=? AND a.status IN ('Awaiting Sponsor Decision','Awaiting Day-90 Review') ORDER BY a.id", (p.entity_id,)))
    for a in pending:
        a["asmt"] = workflow.latest_assessment(a["id"])
        a["reqs"] = workflow.appointment_requirements(a)
        a["mc"] = db.q1("SELECT * FROM manager_commitments WHERE application_id=?", (a["id"],))
        a["review"] = db.q1("SELECT * FROM day90_reviews WHERE application_id=?", (a["id"],))
        a["ob"] = db.q1("SELECT * FROM onboarding WHERE application_id=?", (a["id"],))
    decisions = db.q("SELECT d.*, a.nominee_name, a.ref FROM sponsor_decisions d JOIN applications a ON a.id=d.application_id "
                     "WHERE a.entity_id=? ORDER BY d.id DESC LIMIT 20", (p.entity_id,))
    return render(request, "sponsor.html", entity=ent, pending=pending, decisions=decisions, coverage=entity_coverage(ent))


@app.post("/sponsor/{app_id}/decide")
async def sponsor_decide(app_id: int, request: Request):
    p = security.require(request, "sponsor")
    a = app_for(p, app_id)
    f = await form_data(request)
    try:
        workflow.sponsor_decide(a, f, p.email)
    except WorkflowError as e:
        return back("/sponsor", err=str(e))
    return back("/sponsor", msg="Decision recorded.")


@app.post("/sponsor/{app_id}/day90")
async def sponsor_day90(app_id: int, request: Request):
    p = security.require(request, "sponsor")
    a = app_for(p, app_id)
    f = await form_data(request)
    try:
        workflow.day90_decide(a, f, p.email)
    except WorkflowError as e:
        return back("/sponsor", err=str(e))
    return back("/sponsor", msg="Day-90 outcome recorded.")


# ------------------------------------------------------------------ coverage
def entity_coverage(ent: dict) -> dict:
    appointed = db.q("SELECT platform FROM applications WHERE entity_id=? AND status IN ('Provisionally Appointed','Onboarding','Awaiting Day-90 Review','Confirmed')", (ent["id"],))
    covered = {(r["platform"] or "").strip().lower() for r in appointed}
    priorities = [x.strip() for x in (ent["priority_platforms"] or "").split(",") if x.strip()]
    gaps = [pl for pl in priorities if pl.lower() not in covered]
    return {"appointed": len(appointed), "target": ent["target"], "priorities": priorities, "gaps": gaps,
            "pct": round(100 * len(appointed) / ent["target"]) if ent["target"] else 0}


def entity_rows() -> list[dict]:
    rows = []
    for ent in db.q("SELECT * FROM entities ORDER BY name_en"):
        apps = db.q("SELECT status, outcome FROM applications WHERE entity_id=?", (ent["id"],))
        cov = entity_coverage(ent)
        rows.append({**ent, "coverage": cov, "nominations": len(apps),
                     "submitted": sum(1 for a in apps if a["status"] not in ("Nominated", "Awaiting Consent", "Application in Progress", "Withdrawn")),
                     "assessed": sum(1 for a in apps if a["outcome"]),
                     "meets": sum(1 for a in apps if a["outcome"] == scoring.OUTCOME_MEETS),
                     "withdrawn": sum(1 for a in apps if a["status"] == "Withdrawn")})
    return rows


# ------------------------------------------------------------------ entity focal point
@app.get("/entity", response_class=HTMLResponse)
def entity_view(request: Request):
    p = security.require(request, "focal")
    ent = db.q1("SELECT * FROM entities WHERE id=?", (p.entity_id,))
    apps = enrich(db.q("SELECT a.*, e.name_en AS entity_name FROM applications a JOIN entities e ON e.id=a.entity_id WHERE a.entity_id=? ORDER BY a.created_at DESC", (p.entity_id,)))
    for a in apps:
        a["reminder_template"] = emails.REMINDER_FOR_STATUS.get(a["status"])
        a["block"] = emails.reminder_block_reason(a, a["reminder_template"][0]) if a["reminder_template"] else None
    history = db.q("SELECT m.created_at, m.template, m.status, m.error, m.is_reminder, m.triggered_by, a.nominee_name FROM emails m "
                   "LEFT JOIN applications a ON a.id=m.application_id WHERE m.entity_id=? ORDER BY m.id DESC LIMIT 40", (p.entity_id,))
    return render(request, "entity.html", entity=ent, apps=apps, history=history, coverage=entity_coverage(ent),
                  nomination_link=f"{config.settings.base_url}/n/{ent['slug']}")


@app.post("/entity/remind/{app_id}")
async def entity_remind(app_id: int, request: Request):
    p = security.require(request, "focal")
    a = app_for(p, app_id)
    await form_data(request)
    res = send_reminder(a, f"focal:{p.email}")
    if res["status"] in ("sent", "demo-logged"):
        return back("/entity", msg=f"Reminder sent to {a['nominee_name'] if res.get('to') == 'nominee' else 'the responsible person'}.")
    return back("/entity", err=f"Reminder not sent: {res.get('error') or res['status']}")


def send_reminder(a: dict, triggered_by: str) -> dict:
    spec = emails.REMINDER_FOR_STATUS.get(a["status"])
    if not spec or a["withdrawn_at"]:
        return {"status": "suppressed", "error": "No approved reminder applies at this stage."}
    template, to = spec
    if to == "manager":
        res = workflow.send_manager_link(a, is_reminder=True, triggered_by=triggered_by)
    else:
        res = workflow.send_nominee_link(a, template, is_reminder=True, triggered_by=triggered_by,
                                         due=workflow.next_action(a)["due"] or "")
    if res["status"] in ("sent", "demo-logged") and a["status"] == "Nominated":
        workflow.set_status(a["id"], "Awaiting Consent", triggered_by)
    res["to"] = to
    return res


@app.post("/entity/announce")
async def entity_announce(request: Request):
    p = security.require(request, "focal")
    f = await form_data(request)
    ent = db.q1("SELECT * FROM entities WHERE id=?", (p.entity_id,))
    recipients = [e.strip().lower() for e in (f.get("recipients") or "").replace(";", ",").replace("\n", ",").split(",") if "@" in e]
    if not recipients or len(recipients) > 500:
        return back("/entity", err="Enter between 1 and 500 email addresses.")
    for r in recipients:
        emails.send("announcement", r, {"entity": ent["name_en"], "link": f"{config.settings.base_url}/n/{ent['slug']}"},
                    entity_id=ent["id"], triggered_by=f"focal:{p.email}")
    return back("/entity", msg=f"Role announcement sent to {len(recipients)} recipient(s).")


def register_csv(apps: list[dict]) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Reference", "Entity", "Nominee", "Email", "Department", "Platform", "Workflow", "Route", "Status",
                "Assessment outcome", "Next action", "Responsible", "Due", "Nominated on"])
    for a in enrich(apps):
        w.writerow([a["ref"], a["entity_name"], a["nominee_name"], a["nominee_email"], a["department"], a["platform"],
                    a["workflow"], a["route"], a["status"], a["outcome"] or "", a["next"]["action"], a["next"]["owner"],
                    a["next"]["due"] or "", a["created_at"][:10]])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=cdp-nomination-register.csv"})


@app.get("/entity/export.csv")
def entity_export(request: Request):
    p = security.require(request, "focal")
    db.audit("export.entity", actor_role="focal", actor_email=p.email, entity_id=p.entity_id)
    return register_csv(db.q("SELECT a.*, e.name_en AS entity_name FROM applications a JOIN entities e ON e.id=a.entity_id WHERE a.entity_id=? ORDER BY a.id", (p.entity_id,)))


# ------------------------------------------------------------------ CDP Change Lead
def lead(request: Request) -> Principal:
    return security.require(request, "lead")


@app.get("/lead", response_class=HTMLResponse)
def lead_dashboard(request: Request):
    lead(request)
    fe, fs = request.query_params.get("entity"), request.query_params.get("status")
    sql = "SELECT a.*, e.name_en AS entity_name FROM applications a JOIN entities e ON e.id=a.entity_id WHERE 1=1"
    args: list = []
    if fe:
        sql += " AND a.entity_id=?"; args.append(int(fe))
    if fs:
        sql += " AND a.status=?"; args.append(fs)
    apps = enrich(db.q(sql + " ORDER BY a.updated_at DESC", args))
    all_apps = enrich(db.q("SELECT a.*, e.name_en AS entity_name FROM applications a JOIN entities e ON e.id=a.entity_id"))
    by_status = {s: sum(1 for a in all_apps if a["status"] == s) for s in workflow.STATUSES}
    by_route = {r: sum(1 for a in all_apps if a["route"] == r) for r in ("self", "peer", "manager")}
    by_outcome: dict[str, int] = {}
    for a in all_apps:
        if a["outcome"]:
            by_outcome[a["outcome"]] = by_outcome.get(a["outcome"], 0) + 1
    outstanding = sorted([a for a in all_apps if a["next"]["owner_role"] in ("nominee", "manager", "sponsor", "lead", "focal")],
                         key=lambda a: a["next"]["due"] or "9999")
    soon = (date.today() + timedelta(days=30)).isoformat()
    day90 = db.q("SELECT a.id, a.ref, a.nominee_name, e.name_en AS entity_name, o.day90_date FROM onboarding o JOIN applications a ON a.id=o.application_id "
                 "JOIN entities e ON e.id=a.entity_id WHERE a.status IN ('Onboarding','Awaiting Day-90 Review') AND o.day90_date IS NOT NULL AND o.day90_date<=? ORDER BY o.day90_date", (soon,))
    dup = db.q("SELECT application_id, COUNT(*) n FROM nomination_events GROUP BY application_id HAVING n>1")
    evidence = []
    for a in all_apps:
        asmt = workflow.latest_assessment(a["id"])
        if asmt and asmt["result"]:
            evidence.append(6 - sum(1 for c in asmt["result"]["criteria"] if c["rating"] is None))
    reconsider = [a for a in all_apps if a["reconsideration_request"]]
    return render(request, "lead.html", apps=apps, entities=entity_rows(), by_status=by_status, by_route=by_route,
                  by_outcome=by_outcome, outstanding=outstanding[:60], overdue=[a for a in all_apps if a["next"]["overdue"]],
                  day90=day90, duplicates={d["application_id"]: d["n"] for d in dup}, total=len(all_apps),
                  evidence_avg=(sum(evidence) / len(evidence)) if evidence else None, reconsider=reconsider,
                  statuses=workflow.STATUSES, fe=fe, fs=fs, failures=[a for a in all_apps if a["last_error"]])


@app.get("/lead/app/{app_id}", response_class=HTMLResponse)
def lead_app(app_id: int, request: Request):
    p = lead(request)
    a = app_for(p, app_id)
    db.audit("evidence.viewed", actor_role="lead", actor_email=p.email, application_id=app_id)
    return render(request, "lead_app.html", **application_detail(a))


def application_detail(a: dict) -> dict:
    asmts = db.q("SELECT * FROM assessments WHERE application_id=? ORDER BY id DESC", (a["id"],))
    for s in asmts:
        for k in ("pass_a_json", "pass_b_json", "moderation_json", "result_json"):
            s[k[:-5]] = json.loads(s[k]) if s[k] else None
    return dict(
        a=a, next=workflow.next_action(a), answers=json.loads(a["answers_json"] or "{}"),
        extracted=json.loads(a["extracted_json"] or "{}"), doc=workflow.latest_document(a["id"]),
        screen=workflow.latest_screen(a["id"]), assessments=asmts,
        clarifications=db.q("SELECT * FROM clarifications WHERE application_id=? ORDER BY id", (a["id"],)),
        mc=db.q1("SELECT * FROM manager_commitments WHERE application_id=?", (a["id"],)),
        decisions=db.q("SELECT * FROM sponsor_decisions WHERE application_id=? ORDER BY id", (a["id"],)),
        ob=db.q1("SELECT * FROM onboarding WHERE application_id=?", (a["id"],)),
        review=db.q1("SELECT * FROM day90_reviews WHERE application_id=?", (a["id"],)),
        reqs=workflow.appointment_requirements(a), checklist_items=workflow.ONBOARDING_CHECKLIST,
        mails=db.q("SELECT * FROM emails WHERE application_id=? ORDER BY id DESC", (a["id"],)),
        audit=db.q("SELECT * FROM audit WHERE application_id=? ORDER BY id DESC LIMIT 200", (a["id"],)),
        tokens=db.q("SELECT id, role, email, expires_at, revoked_at, created_at, last_used_at FROM tokens WHERE application_id=? ORDER BY id DESC", (a["id"],)),
        grants=db.q("SELECT * FROM access_grants WHERE application_id=? ORDER BY id DESC", (a["id"],)),
        events=db.q("SELECT * FROM nomination_events WHERE application_id=? ORDER BY id", (a["id"],)),
        versions=db.q("SELECT version, created_at FROM evidence_versions WHERE application_id=? ORDER BY version", (a["id"],)),
    )


@app.get("/lead/app/{app_id}/report", response_class=HTMLResponse)
def lead_report(app_id: int, request: Request):
    p = lead(request)
    a = app_for(p, app_id)
    return render(request, "report.html", **application_detail(a))


@app.post("/lead/app/{app_id}/{action}")
async def lead_app_action(app_id: int, action: str, request: Request, background: BackgroundTasks):
    p = lead(request)
    a = app_for(p, app_id)
    f = await form_data(request)
    url = f"/lead/app/{app_id}"
    try:
        if action == "retry":
            if a["status"] != "Submitted":
                raise WorkflowError("Only submitted applications awaiting assessment can be retried.")
            background.add_task(workflow.run_assessment, app_id)
            return back(url, msg="Automated assessment restarted.")
        if action == "communicate":
            workflow.communicate_outcome(a, p.email)
        elif action == "onboarding":
            workflow.update_onboarding(a, f, p.email)
        elif action == "remind":
            res = send_reminder(a, f"lead:{p.email}")
            if res["status"] not in ("sent", "demo-logged"):
                raise WorkflowError(f"Reminder not sent: {res.get('error') or res['status']}")
        elif action == "withdraw":
            workflow.withdraw(a, f.get("reason") or "Withdrawn by CDP Change Lead", "lead", p.email)
        elif action == "reopen":
            if not a["reconsideration_request"] or a["status"] not in ("Assessment Complete", "Not Selected"):
                raise WorkflowError("Reopening requires a reconsideration request on a completed assessment.")
            db.ex("UPDATE applications SET clarification_rounds=0, reconsideration_request=NULL WHERE id=?", (app_id,))
            workflow.set_status(app_id, "Application in Progress", "lead", reason="reconsideration accepted")
            workflow.send_nominee_link(workflow.get_app(app_id), "application_link", triggered_by="lead")
        elif action == "grant":
            email = (f.get("email") or "").strip().lower()
            if "@" not in email:
                raise WorkflowError("Enter the email of the person to grant access.")
            db.ex("INSERT INTO access_grants(application_id, grantee_email, granted_by, reason, created_at) VALUES (?,?,?,?,?)",
                  (app_id, email, p.email, f.get("reason"), db.now()))
            db.audit("access.granted", actor_role="lead", actor_email=p.email, application_id=app_id, grantee=email)
        elif action == "revoke-grant":
            db.ex("UPDATE access_grants SET revoked_at=? WHERE id=? AND application_id=?", (db.now(), int(f["grant_id"]), app_id))
            db.audit("access.grant_revoked", actor_role="lead", actor_email=p.email, application_id=app_id)
        elif action == "revoke-token":
            tok = db.q1("SELECT id FROM tokens WHERE id=? AND application_id=?", (int(f["token_id"]), app_id))
            if tok:
                security.revoke(tok["id"])
                db.audit("link.revoked", actor_role="lead", actor_email=p.email, application_id=app_id, token_id=tok["id"])
        elif action == "delete-docs":
            workflow.delete_documents(app_id, p.email, reason=f.get("reason") or "Deletion requested")
        else:
            raise HTTPException(404, "Unknown action")
    except WorkflowError as e:
        return back(url, err=str(e))
    return back(url, msg="Done.")


@app.get("/lead/export.csv")
def lead_export(request: Request):
    p = lead(request)
    db.audit("export.central", actor_role="lead", actor_email=p.email)
    return register_csv(db.q("SELECT a.*, e.name_en AS entity_name FROM applications a JOIN entities e ON e.id=a.entity_id ORDER BY e.name_en, a.id"))


@app.get("/lead/settings", response_class=HTMLResponse)
def lead_settings(request: Request):
    lead(request)
    version, cfg = scoring.current_config()
    history = db.q("SELECT version, note, created_by, created_at FROM config_versions ORDER BY version DESC")
    return render(request, "settings.html", cfg=cfg, version=version, history=history,
                  rounds=db.q("SELECT * FROM rounds ORDER BY id DESC"), ai_reason=config.settings.ai_mode_reason)


@app.post("/lead/settings")
async def lead_settings_save(request: Request):
    p = lead(request)
    f = await form_data(request)
    _, cfg = scoring.current_config()
    try:
        cfg["weights"] = {k: float(f[f"w_{k}"]) for k in scoring.CRITERION_KEYS}
        cfg["overall_threshold"] = float(f["overall_threshold"])
        cfg["minimums"] = {k: int(f[f"min_{k}"]) for k in scoring.CRITERION_KEYS if f.get(f"min_{k}")}
        cfg["max_clarification_rounds"] = int(f["max_clarification_rounds"])
        cfg["reminders"] = {"min_hours_between": float(f["min_hours_between"]), "max_per_stage": int(f["max_per_stage"])}
        cfg["retention_days"] = int(f["retention_days"])
        for role in cfg["link_expiry_days"]:
            cfg["link_expiry_days"][role] = int(f.get(f"exp_{role}") or cfg["link_expiry_days"][role])
        version = scoring.save_config(cfg, note=f.get("note") or "Settings updated", by=p.email)
    except (ValueError, KeyError) as e:
        return back("/lead/settings", err=f"Settings not saved: {e}")
    return back("/lead/settings", msg=f"Saved as configuration version {version}. New assessments will use it.")


@app.post("/lead/rounds")
async def lead_rounds(request: Request):
    p = lead(request)
    f = await form_data(request)
    if f.get("action") == "open":
        db.ex("UPDATE rounds SET status='closed' WHERE status='open'")
        rid = db.ex("INSERT INTO rounds(name, status, opens_on, closes_on, created_at) VALUES (?,?,?,?,?)",
                    (f.get("name") or "New round", "open", date.today().isoformat(), f.get("closes_on"), db.now()))
        db.audit("round.opened", actor_role="lead", actor_email=p.email, round_id=rid)
    elif f.get("action") == "close":
        db.ex("UPDATE rounds SET status='closed' WHERE id=?", (int(f["round_id"]),))
        db.audit("round.closed", actor_role="lead", actor_email=p.email, round_id=f["round_id"])
    return back("/lead/settings", msg="Nomination round updated.")


@app.get("/lead/entities", response_class=HTMLResponse)
def lead_entities(request: Request):
    lead(request)
    ents = db.q("SELECT * FROM entities ORDER BY name_en")
    for e in ents:
        e["contacts"] = db.q("SELECT * FROM contacts WHERE entity_id=? ORDER BY role, name", (e["id"],))
    return render(request, "entities.html", entities=ents, base_url=config.settings.base_url)


@app.post("/lead/entities")
async def lead_entities_save(request: Request):
    p = lead(request)
    f = await form_data(request)
    act = f.get("action")
    try:
        if act == "add":
            code = f["code"].strip().upper()
            slug = code.lower() + "-" + os.urandom(3).hex()
            eid = db.ex("INSERT INTO entities(code, name_en, name_ar, slug, target, priority_platforms) VALUES (?,?,?,?,?,?)",
                        (code, f["name_en"].strip(), f.get("name_ar"), slug, int(f.get("target") or 2), f.get("priority_platforms", "")))
            db.audit("entity.added", actor_role="lead", actor_email=p.email, entity_id=eid)
        elif act == "update":
            eid = int(f["entity_id"])
            db.ex("UPDATE entities SET target=?, priority_platforms=?, workflows=?, user_groups=?, locations=?, capacity_needs=?, coverage_notes=? WHERE id=?",
                  (int(f.get("target") or 0), f.get("priority_platforms"), f.get("workflows"), f.get("user_groups"),
                   f.get("locations"), f.get("capacity_needs"), f.get("coverage_notes"), eid))
            db.audit("coverage.updated", actor_role="lead", actor_email=p.email, entity_id=eid)
        elif act == "add_contact":
            if f["role"] not in ("focal", "sponsor"):
                raise ValueError("role")
            db.ex("INSERT INTO contacts(entity_id, role, name, email) VALUES (?,?,?,?)",
                  (int(f["entity_id"]), f["role"], f["name"].strip(), f["email"].strip().lower()))
            db.audit("contact.assigned", actor_role="lead", actor_email=p.email, entity_id=int(f["entity_id"]), role=f["role"], email=f["email"])
        elif act == "deactivate_contact":
            c = db.q1("SELECT * FROM contacts WHERE id=?", (int(f["contact_id"]),))
            db.ex("UPDATE contacts SET active=0 WHERE id=?", (c["id"],))
            db.ex("UPDATE tokens SET revoked_at=? WHERE entity_id=? AND lower(email)=? AND role=? AND revoked_at IS NULL",
                  (db.now(), c["entity_id"], c["email"], c["role"]))
            db.audit("contact.removed", actor_role="lead", actor_email=p.email, entity_id=c["entity_id"], email=c["email"])
        elif act == "send_link":
            c = db.q1("SELECT * FROM contacts WHERE id=? AND active=1", (int(f["contact_id"]),))
            raw = security.issue_token(c["role"], c["email"], entity_id=c["entity_id"])
            emails.send("access_link", c["email"], {"link": security.link_for(raw), "expires": workflow._expires(c["role"])},
                        entity_id=c["entity_id"], triggered_by=f"lead:{p.email}")
    except (KeyError, ValueError, TypeError) as e:
        return back("/lead/entities", err=f"Not saved: {e}")
    return back("/lead/entities", msg="Saved.")


@app.get("/lead/templates", response_class=HTMLResponse)
def lead_templates(request: Request):
    lead(request)
    rows = db.q("SELECT * FROM email_templates ORDER BY key")
    sample = {"nominee_name": "Sample Nominee", "entity": "Sample Entity", "ref": "CDP-SAMPLE", "manager_name": "Sample Manager",
              "recipient_name": "Sample Recipient", "link": f"{config.settings.base_url}/a/…", "expires": "2026-12-31", "due": "2026-12-01"}
    for r in rows:
        r["preview_subject"], r["preview_body"] = emails.render(r["key"], sample)
    return render(request, "templates.html", rows=rows, version=scoring.current_config())


@app.post("/lead/templates")
async def lead_templates_save(request: Request):
    p = lead(request)
    f = await form_data(request)
    key = f["key"]
    if not db.q1("SELECT 1 FROM email_templates WHERE key=?", (key,)):
        return back("/lead/templates", err="Unknown template")
    if "{link}" not in f["body_en"] and key not in ("withdrawal",):
        return back("/lead/templates", err="The template body must contain the {link} placeholder.")
    db.ex("UPDATE email_templates SET subject_en=?, body_en=?, focal_may_send=?, updated_at=? WHERE key=?",
          (f["subject_en"], f["body_en"], 1 if f.get("focal_may_send") else 0, db.now(), key))
    db.audit("template.updated", actor_role="lead", actor_email=p.email, template=key)
    return back("/lead/templates", msg=f"Template '{key}' saved.")


@app.get("/lead/outbox", response_class=HTMLResponse)
def lead_outbox(request: Request):
    lead(request)
    return render(request, "outbox.html", mails=db.q("SELECT m.*, a.ref FROM emails m LEFT JOIN applications a ON a.id=m.application_id ORDER BY m.id DESC LIMIT 300"))


@app.get("/lead/audit", response_class=HTMLResponse)
def lead_audit(request: Request):
    lead(request)
    return render(request, "audit.html", rows=db.q("SELECT * FROM audit ORDER BY id DESC LIMIT 500"))


@app.post("/lead/jobs")
async def lead_jobs(request: Request):
    p = lead(request)
    await form_data(request)
    summary = await run_jobs(f"lead:{p.email}")
    return back("/lead", msg=summary)


async def run_jobs(triggered_by: str = "scheduler") -> str:
    """Scheduled jobs: retry failed assessments, send due automatic reminders, apply retention."""
    retried = 0
    for a in db.q("SELECT id FROM applications WHERE status='Submitted' AND withdrawn_at IS NULL"):
        try:
            await workflow.run_assessment(a["id"])
            retried += 1
        except Exception as e:  # one bad record must not stop the batch
            db.audit("jobs.assessment_error", application_id=a["id"], error=str(e))
    reminded = 0
    for a in db.q("SELECT a.*, e.name_en AS entity_name FROM applications a JOIN entities e ON e.id=a.entity_id WHERE a.withdrawn_at IS NULL"):
        nxt = workflow.next_action(a)
        if a["status"] in emails.REMINDER_FOR_STATUS and nxt["due"] and nxt["due"] <= date.today().isoformat():
            res = send_reminder(a, triggered_by)
            reminded += res["status"] in ("sent", "demo-logged")
    purged = workflow.purge_expired(triggered_by)
    return f"Jobs complete: {retried} assessment(s) run, {reminded} reminder(s) sent, {purged} record(s) past retention cleared."


# ------------------------------------------------------------------ demo launcher
@app.get("/demo", response_class=HTMLResponse)
def demo(request: Request):
    if not demo_launcher_enabled():
        raise HTTPException(404, "Not available")
    ents = db.q("SELECT * FROM entities ORDER BY name_en")
    for e in ents:
        e["contacts"] = db.q("SELECT * FROM contacts WHERE entity_id=? AND active=1", (e["id"],))
    apps = db.q("SELECT a.id, a.ref, a.nominee_name, a.status, a.manager_name, e.name_en AS entity_name FROM applications a JOIN entities e ON e.id=a.entity_id ORDER BY e.name_en, a.id")
    return render(request, "demo.html", entities=ents, apps=apps)


@app.get("/demo/enter")
def demo_enter(request: Request, role: str, id: int = 0):
    if not demo_launcher_enabled():
        raise HTTPException(404, "Not available")
    if role == "lead":
        raw = security.issue_token("lead", config.settings.lead_email)
    elif role in ("focal", "sponsor"):
        c = db.q1("SELECT * FROM contacts WHERE id=? AND role=?", (id, role))
        raw = security.issue_token(role, c["email"], entity_id=c["entity_id"])
    elif role in ("nominee", "manager"):
        a = workflow.get_app(id)
        raw = security.issue_token(role, a["nominee_email"] if role == "nominee" else a["manager_email"], application_id=id)
    else:
        raise HTTPException(404, "Unknown role")
    return RedirectResponse(f"/a/{raw}", status_code=303)
