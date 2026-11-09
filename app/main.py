"""Version 2 web app: one Change Lead user plus personal candidate assessment links."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import ai, config, db, imports, production, scoring, security, workflow
from app.i18n import translator
from app.workflow import WorkflowError

HERE = Path(__file__).parent
log = logging.getLogger("cdp")
_tasks: set = set()  # keep references to background assessment tasks


@asynccontextmanager
async def lifespan(_app):
    startup()
    for problem in production.setup_problems():
        log.error("SETUP INCOMPLETE: %s", problem)
    task = asyncio.create_task(production.scheduler_loop())
    yield
    task.cancel()


app = FastAPI(title="CDP Champion Selection", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.filters["fromjson"] = lambda s: json.loads(s) if s else {}


def startup() -> None:
    db.init_db()
    scoring.current_config()


@app.middleware("http")
async def production_lock(request: Request, call_next):
    problems = production.setup_problems()
    if problems and not request.url.path.startswith("/static"):
        items = "".join(f"<li>{p}</li>" for p in problems)
        html = ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>Setup incomplete</title><link rel='stylesheet' href='/static/style.css'></head><body><main class='wrap'>"
                "<div class='card' style='margin-top:24px'><h1>Setup incomplete</h1><p>The tool is locked until these settings are "
                f"added in the hosting service's Environment settings:</p><ul>{items}</ul>"
                "<p class='muted'>After saving the settings, the service restarts and this page disappears.</p></div></main></body></html>")
        return HTMLResponse(html, status_code=503)
    return await call_next(request)


# ------------------------------------------------------------------ helpers
def render(request: Request, name: str, status_code: int = 200, **ctx) -> HTMLResponse:
    lang = request.cookies.get("lang", "en")
    base = dict(_=translator(lang), lang=lang, dir="rtl" if lang == "ar" else "ltr", csrf=security.csrf_token(request),
                ai_mode=config.settings.ai_mode, is_lead=security.lead_ok(request), msg=request.query_params.get("msg"),
                err=request.query_params.get("err"), scoring=scoring, wf=workflow, today=date.today().isoformat())
    base.update(ctx)
    return templates.TemplateResponse(request, name, base, status_code=status_code)


def back(url: str, msg: str | None = None, err: str | None = None) -> RedirectResponse:
    sep = "&" if "?" in url else "?"
    if msg:
        url += f"{sep}msg={quote(msg)}"
    elif err:
        url += f"{sep}err={quote(err)}"
    return RedirectResponse(url, status_code=303)


async def form(request: Request) -> dict:
    f = await request.form()
    data = {k: v for k, v in f.multi_items() if not hasattr(v, "filename")}
    security.check_csrf(request, data.get("csrf"))
    return data


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if exc.status_code == 401 and exc.detail == "login":
        return RedirectResponse(f"/login?next={quote(request.url.path)}", status_code=303)
    if exc.status_code == 401:
        body = {"expired": "This assessment link has expired.", "revoked": "This assessment link has been replaced or cancelled."}.get(
            exc.detail, "This assessment link is not valid.")
        return render(request, "notice.html", 401, title="Link problem",
                      body=body + " Please contact the CDP Change Lead for a new link.")
    return render(request, "notice.html", exc.status_code, title="Not available", body=str(exc.detail))


def lead(request: Request) -> None:
    security.require_lead(request)


def get_cand(cid: int) -> dict:
    c = workflow.cand(cid)
    if not c:
        raise HTTPException(404, "Candidate not found.")
    return c


def get_init(iid: int) -> dict:
    i = db.q1("SELECT * FROM initiatives WHERE id=?", (iid,))
    if not i:
        raise HTTPException(404, "Initiative not found.")
    return i


# ------------------------------------------------------------------ sign in
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html", demo_password=not config.settings.lead_password and not production.is_production(),
                  next=request.query_params.get("next", "/"))


@app.post("/login")
async def login(request: Request):
    f = await request.form()
    client = request.client.host if request.client else "?"
    nxt = f.get("next") or "/"
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/"
    if not security.check_password(f.get("password") or "", client):
        db.audit("login.failed", actor="unknown", client=client)
        return render(request, "login.html", 401, error="That password is not correct.", next=nxt,
                      demo_password=not config.settings.lead_password and not production.is_production())
    resp = RedirectResponse(nxt, status_code=303)
    resp.set_cookie(security.LEAD_COOKIE, security.make_session(), httponly=True, samesite="lax",
                    secure=config.settings.base_url.startswith("https"), max_age=security.SESSION_HOURS * 3600)
    db.audit("login", actor="lead")
    return resp


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(security.LEAD_COOKIE)
    return resp


@app.get("/lang/{code}")
def set_lang(code: str, request: Request):
    resp = RedirectResponse(request.headers.get("referer") or "/", status_code=303)
    resp.set_cookie("lang", "ar" if code == "ar" else "en", max_age=365 * 86400, samesite="lax")
    return resp


# ------------------------------------------------------------------ dashboard
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    lead(request)
    qp = request.query_params
    fi = int(qp["initiative"]) if qp.get("initiative", "").isdigit() else None
    fe = int(qp["entity"]) if qp.get("entity", "").isdigit() else None
    fc = qp.get("category") or None
    d = workflow.dashboard(fi, fe, fc)
    inits = db.q("SELECT * FROM initiatives ORDER BY status, id DESC")
    for i in inits:
        steps = workflow.step_progress(i["id"])
        i["done"] = sum(1 for s in steps if s["completed_at"])
        i["current"] = next((s for s in steps if s["current"]), None)
        i["count"] = db.q1("SELECT COUNT(*) n FROM candidates WHERE initiative_id=? AND status!='Withdrawn'", (i["id"],))["n"]
    return render(request, "dashboard.html", d=d, initiatives=inits, fi=fi, fe=fe, fc=fc, steps_total=len(workflow.STEPS),
                  entities=db.q("SELECT * FROM entities ORDER BY name"))


@app.get("/export.csv")
def export_all(request: Request):
    lead(request)
    qp = request.query_params
    d = workflow.dashboard(int(qp["initiative"]) if qp.get("initiative", "").isdigit() else None,
                           int(qp["entity"]) if qp.get("entity", "").isdigit() else None, qp.get("category") or None)
    return register_csv(d["rows"], "cdp-champions-register.csv")


def register_csv(rows: list[dict], filename: str) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Reference", "Initiative", "Entity", "Name", "Email", "Department", "Platform", "Workflow", "Status",
                "CV fit (AI)", "CV fit (final)", "Override reason", "Assessment outcome", "Decision", "Decision rationale"])
    for r in rows:
        w.writerow([r["ref"], r["initiative_name"], r["entity_name"], r["name"], r["email"] or "", r["department"] or "",
                    r["platform"] or "", r["workflow"] or "", r["status"], r["fit_ai"] or "", r["fit_final"] or "",
                    r["fit_override_reason"] or "", r["outcome"] or "", r["decision"] or "", r["decision_rationale"] or ""])
    db.audit("export.register", actor="lead", rows=len(rows))
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


# ------------------------------------------------------------------ initiatives
@app.post("/initiatives")
async def create_initiative(request: Request):
    lead(request)
    f = await form(request)
    try:
        iid = workflow.create_initiative(f.get("name"), f.get("platform"), f.get("description"))
    except WorkflowError as e:
        return back("/", err=str(e))
    return back(f"/i/{iid}", msg="Initiative created. Start with step 1.")


@app.get("/i/{iid}", response_class=HTMLResponse)
def initiative(iid: int, request: Request):
    lead(request)
    i = get_init(iid)
    status = request.query_params.get("status") or ""
    sql = ("SELECT c.*, e.name AS entity_name, (SELECT extract_status FROM documents d WHERE d.candidate_id=c.id AND d.superseded=0 "
           "ORDER BY d.id DESC LIMIT 1) AS cv_status FROM candidates c LEFT JOIN entities e ON e.id=c.entity_id WHERE c.initiative_id=?")
    args: list = [iid]
    if status:
        sql += " AND c.status=?"; args.append(status)
    cands = db.q(sql + " ORDER BY e.name, c.name", args)
    for c in cands:
        c["has_link"] = bool(db.q1("SELECT 1 FROM tokens WHERE candidate_id=? AND revoked_at IS NULL AND expires_at>?", (c["id"], db.now())))
    eligible = db.q1("SELECT COUNT(*) n FROM candidates WHERE initiative_id=? AND status='CV Uploaded' AND consent_screening=1", (iid,))["n"]
    shortlisted = db.q1("SELECT COUNT(*) n FROM candidates WHERE initiative_id=? AND status IN ('Shortlisted','Invited','In Assessment','Follow-up Requested')", (iid,))["n"]
    return render(request, "initiative.html", i=i, steps=workflow.step_progress(iid), cands=cands, status=status,
                  blockers=workflow.screening_blockers(iid),
                  eligible=eligible, shortlisted=shortlisted, statuses=workflow.STATUSES)


@app.post("/i/{iid}/step/{no}")
async def initiative_step(iid: int, no: int, request: Request):
    lead(request)
    get_init(iid)
    f = await form(request)
    try:
        workflow.set_step(iid, no, f.get("complete") == "1")
    except WorkflowError as e:
        return back(f"/i/{iid}", err=str(e))
    return back(f"/i/{iid}")


@app.post("/i/{iid}/edit")
async def initiative_edit(iid: int, request: Request):
    lead(request)
    get_init(iid)
    f = await form(request)
    if f.get("action") == "close":
        db.ex("UPDATE initiatives SET status=? WHERE id=?", ("closed" if f.get("closed") == "1" else "active", iid))
    else:
        db.ex("UPDATE initiatives SET name=?, platform=?, description=? WHERE id=?",
              ((f.get("name") or "").strip()[:120] or "Untitled", (f.get("platform") or "")[:120], (f.get("description") or "")[:1000], iid))
    db.audit("initiative.updated", actor="lead", initiative_id=iid)
    return back(f"/i/{iid}", msg="Initiative updated.")


@app.post("/i/{iid}/clear")
async def initiative_clear(iid: int, request: Request):
    lead(request)
    i = get_init(iid)
    f = await form(request)
    if (f.get("confirm_name") or "").strip() != i["name"]:
        return back(f"/i/{iid}", err="Nothing was deleted. Type the initiative's name exactly to confirm.")
    delete_all = f.get("scope") == "initiative"
    res = workflow.clear_initiative(iid, delete_initiative=delete_all)
    msg = f"Deleted {res['nominees']} nominee record(s) and {res['files']} CV file(s)."
    return back("/", msg=msg + " The initiative was removed.") if delete_all else back(f"/i/{iid}", msg=msg + " Steps were reset.")


@app.get("/i/{iid}/export.csv")
def initiative_export(iid: int, request: Request):
    lead(request)
    i = get_init(iid)
    return register_csv(workflow.dashboard(iid)["rows"], f"{i['name'].replace(' ', '-').lower()}-register.csv")


def step_locked(iid: int, no: int) -> RedirectResponse | None:
    """Actions belonging to a step marked complete are refused until the step is reopened."""
    row = db.q1("SELECT completed_at FROM initiative_steps WHERE initiative_id=? AND step_no=?", (iid, no))
    if row and row["completed_at"]:
        return back(f"/i/{iid}", err=f"Step {no} is marked complete. Reopen it to make changes.")
    return None


# ------------------------------------------------------------------ survey import
def _staging() -> Path:
    p = Path(config.settings.db_path).parent / "staging"
    p.mkdir(parents=True, exist_ok=True)
    return p


@app.post("/i/{iid}/import", response_class=HTMLResponse)
async def import_upload(iid: int, request: Request):
    lead(request)
    if (locked := step_locked(iid, 2)):
        return locked
    i = get_init(iid)
    f = await request.form()
    security.check_csrf(request, f.get("csrf"))
    up = f.get("file")
    if not up or not getattr(up, "filename", ""):
        return back(f"/i/{iid}", err="Choose the survey export file (Excel or CSV).")
    data = await up.read()
    try:
        header, rows = imports.read_table(up.filename, data)
    except imports.ImportErrorMsg as e:
        return back(f"/i/{iid}", err=str(e))
    key = secrets.token_hex(12)
    (_staging() / f"{key}.json").write_text(json.dumps({"filename": up.filename, "header": header, "rows": rows}))
    saved = db.q1("SELECT mapping_json FROM import_mappings WHERE id=1")
    mapping = imports.guess_mapping(header, json.loads(saved["mapping_json"]) if saved else None)
    return render(request, "import_map.html", i=i, key=key, header=header, rows=rows[:5], total=len(rows),
                  mapping=mapping, fields=imports.FIELDS, filename=up.filename)


@app.post("/i/{iid}/import/confirm")
async def import_confirm(iid: int, request: Request):
    lead(request)
    if (locked := step_locked(iid, 2)):
        return locked
    get_init(iid)
    f = await form(request)
    key = f.get("key", "")
    path = _staging() / f"{key}.json"
    if not key.isalnum() or not path.exists():
        return back(f"/i/{iid}", err="The uploaded file has expired. Please upload it again.")
    staged = json.loads(path.read_text())
    mapping = {k: f[f"map_{k}"] for k in imports.FIELD_KEYS if f.get(f"map_{k}")}
    try:
        records, problems = imports.apply_mapping(staged["header"], staged["rows"], mapping)
    except imports.ImportErrorMsg as e:
        return back(f"/i/{iid}", err=str(e))
    db.ex("INSERT OR REPLACE INTO import_mappings(id, mapping_json, updated_at) VALUES (1,?,?)", (json.dumps(mapping), db.now()))
    res = workflow.import_records(iid, records)
    path.unlink(missing_ok=True)
    db.audit("import.file", actor="lead", initiative_id=iid, filename=staged["filename"], **{k: v for k, v in res.items() if k != "notes"})
    notes = problems + res["notes"]
    msg = f"Imported {res['created']} nominee(s); {res['duplicates']} duplicate(s) skipped."
    if notes:
        msg += " Notes: " + " ".join(notes[:8]) + (" …" if len(notes) > 8 else "")
    return back(f"/i/{iid}", msg=msg)


# ------------------------------------------------------------------ CVs
@app.post("/i/{iid}/cvs", response_class=HTMLResponse)
async def cv_bulk(iid: int, request: Request):
    lead(request)
    if (locked := step_locked(iid, 3)):
        return locked
    i = get_init(iid)
    f = await request.form()
    security.check_csrf(request, f.get("csrf"))
    files = [u for u in f.getlist("files") if getattr(u, "filename", "")]
    if not files:
        return back(f"/i/{iid}", err="Choose one or more CV files (PDF or DOCX).")
    scores = workflow.match_scores(iid, [u.filename for u in files])
    done, unmatched = [], []
    for u in files:
        data = await u.read()
        cid = scores[u.filename]["match"]
        if cid:
            res = workflow.upload_cv(workflow.cand(cid), u.filename, data)
            done.append({"file": u.filename, "name": workflow.cand(cid)["name"], **res})
        else:
            key = secrets.token_hex(10)
            (_staging() / f"{key}.bin").write_bytes(data)
            unmatched.append({"file": u.filename, "key": key, "suggest": scores[u.filename]["suggest"]})
    people = db.q("SELECT id, name FROM candidates WHERE initiative_id=? AND status!='Withdrawn' ORDER BY name", (iid,))
    return render(request, "cv_results.html", i=i, done=done, unmatched=unmatched, people=people)


@app.post("/i/{iid}/cvs/assign")
async def cv_assign(iid: int, request: Request):
    lead(request)
    if (locked := step_locked(iid, 3)):
        return locked
    get_init(iid)
    f = await form(request)
    assigned = 0
    for k, v in f.items():
        if not k.startswith("assign_") or not v.isdigit():
            continue
        key = k[7:]
        path = _staging() / f"{key}.bin"
        c = workflow.cand(int(v))
        if not key.isalnum() or not path.exists() or not c or c["initiative_id"] != iid:
            continue
        workflow.upload_cv(c, f.get(f"name_{key}") or "cv.pdf", path.read_bytes())
        path.unlink(missing_ok=True)
        assigned += 1
    skipped = sum(1 for k, v in f.items() if k.startswith("assign_") and not v)
    if not assigned:
        return back(f"/i/{iid}", err="No CVs were assigned: no nominee was chosen for the files. Upload them again and pick "
                                     "the nominee for each file on the next page.")
    msg = f"{assigned} CV(s) assigned."
    if skipped:
        msg += f" {skipped} file(s) were skipped; upload them again to assign them."
    return back(f"/i/{iid}", msg=msg)


@app.post("/i/{iid}/consent-all")
async def consent_all(iid: int, request: Request):
    lead(request)
    if (locked := step_locked(iid, 4)):
        return locked
    get_init(iid)
    f = await form(request)
    if f.get("confirm") != "yes":
        return back(f"/i/{iid}", err="Tick the box to confirm these nominees agreed to AI screening.")
    n = workflow.record_consent_all(iid)
    return back(f"/i/{iid}", msg=f"Consent recorded for {n} nominee(s).")


@app.post("/i/{iid}/screen")
async def screen_all(iid: int, request: Request, background: BackgroundTasks):
    lead(request)
    if (locked := step_locked(iid, 4)):
        return locked
    get_init(iid)
    await form(request)
    ids = [r["id"] for r in db.q("SELECT id FROM candidates WHERE initiative_id=? AND status='CV Uploaded' AND consent_screening=1", (iid,))]
    if not ids:
        return back(f"/i/{iid}", err="No CVs are waiting for screening.")
    background.add_task(workflow.screen_many, ids)
    return back(f"/i/{iid}", msg=f"AI fit rating started for {len(ids)} CV(s). Refresh the page in a moment to see the results.")


# ------------------------------------------------------------------ assessment links
@app.post("/i/{iid}/links.csv")
async def links_export(iid: int, request: Request):
    lead(request)
    if (locked := step_locked(iid, 6)):
        return locked
    i = get_init(iid)
    f = await form(request)
    only_new = f.get("scope") != "all"
    rows = db.q("SELECT c.id FROM candidates c WHERE c.initiative_id=? AND c.status IN ('Shortlisted','Invited','In Assessment','Follow-up Requested')", (iid,))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Name", "Email", "Entity", "Assessment link", "Link expires"])
    n = 0
    for r in rows:
        c = workflow.cand(r["id"])
        active = db.q1("SELECT 1 FROM tokens WHERE candidate_id=? AND revoked_at IS NULL AND expires_at>?", (c["id"], db.now()))
        if only_new and active:
            continue
        link = workflow.invite(c)
        exp = db.q1("SELECT expires_at FROM tokens WHERE candidate_id=? AND revoked_at IS NULL ORDER BY id DESC LIMIT 1", (c["id"],))["expires_at"][:10]
        w.writerow([c["name"], c["email"] or "", c["entity_name"] or "", link, exp])
        n += 1
    db.audit("links.exported", actor="lead", initiative_id=iid, count=n)
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={i['name'].replace(' ', '-').lower()}-assessment-links.csv"})


# ------------------------------------------------------------------ candidate (Change Lead view)
@app.get("/c/{cid}", response_class=HTMLResponse)
def candidate(cid: int, request: Request):
    lead(request)
    c = get_cand(cid)
    return render(request, "candidate.html", **candidate_ctx(c), new_link=request.query_params.get("link"))


def candidate_ctx(c: dict) -> dict:
    asmt = workflow.latest_assessment(c["id"])
    return dict(
        c=c, doc=workflow.latest_document(c["id"]), screen=workflow.latest_screen(c["id"]), asmt=asmt,
        answers=json.loads(c["answers_json"] or "{}"), source=json.loads(c["source_row_json"] or "{}"),
        clarifications=db.q("SELECT * FROM clarifications WHERE candidate_id=? ORDER BY id", (c["id"],)),
        link=db.q1("SELECT * FROM tokens WHERE candidate_id=? AND revoked_at IS NULL ORDER BY id DESC LIMIT 1", (c["id"],)),
        audit=db.q("SELECT * FROM audit WHERE candidate_id=? ORDER BY id DESC LIMIT 150", (c["id"],)),
        game=db.q1("SELECT * FROM game_sessions WHERE candidate_id=?", (c["id"],)),
    )


@app.get("/c/{cid}/report", response_class=HTMLResponse)
def candidate_report(cid: int, request: Request):
    lead(request)
    c = get_cand(cid)
    db.audit("report.viewed", actor="lead", candidate_id=cid)
    return render(request, "report.html", **candidate_ctx(c))


@app.post("/c/{cid}/{action}")
async def candidate_action(cid: int, action: str, request: Request, background: BackgroundTasks):
    lead(request)
    c = get_cand(cid)
    url = f"/c/{cid}"
    if action == "cv":
        f = await request.form()
        security.check_csrf(request, f.get("csrf"))
        up = f.get("file")
        if not up or not getattr(up, "filename", ""):
            return back(url, err="Choose a CV file.")
        res = workflow.upload_cv(c, up.filename, await up.read())
        return back(url, msg="CV uploaded.") if res["status"] == "ok" else back(url, err=res["error"])
    f = await form(request)
    try:
        if action == "consent":
            workflow.record_consent(c)
        elif action == "screen":
            if not await workflow.screen(cid):
                raise WorkflowError(workflow.cand(cid)["last_error"] or "Screening needs consent and a readable CV.")
        elif action == "fit":
            workflow.override_fit(c, f.get("category"), f.get("reason"))
        elif action == "link":
            link = workflow.invite(c)
            return back(f"{url}?link={quote(link)}#link")
        elif action == "revoke":
            security.revoke_links(cid)
            db.audit("link.revoked", actor="lead", candidate_id=cid)
        elif action == "time":
            workflow.set_extra_time(c, float(f.get("factor") or 1))
        elif action == "offline":
            answers = {k[2:]: v for k, v in f.items() if k.startswith("a_")}
            workflow.save_answers(c, answers, "offline", actor="lead")
            workflow.submit_answers(workflow.cand(cid), actor="lead")
            background.add_task(workflow.run_assessment, cid)
            return back(url, msg="Offline answers saved. AI assessment started.")
        elif action == "reset-game":
            workflow.game_reset(c)
        elif action == "retry":
            if c["status"] != "Assessing":
                raise WorkflowError("Only an assessment that is waiting can be retried.")
            background.add_task(workflow.run_assessment, cid)
        elif action == "decide":
            workflow.decide(c, f.get("decision"), f.get("rationale"))
        elif action == "withdraw":
            workflow.withdraw(c, f.get("reason") or "Withdrawn by the Change Lead")
        elif action == "delete-docs":
            workflow.delete_documents(cid, f.get("reason") or "Deletion requested")
        else:
            raise HTTPException(404, "Unknown action")
    except (WorkflowError, ValueError) as e:
        return back(url, err=str(e))
    return back(url, msg="Saved.")


@app.get("/doc/{doc_id}")
def download_doc(doc_id: int, request: Request):
    lead(request)
    d = db.q1("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not d or not d["stored_path"] or not Path(d["stored_path"]).exists():
        raise HTTPException(404, "Document not available.")
    db.audit("document.viewed", actor="lead", candidate_id=d["candidate_id"])
    return FileResponse(d["stored_path"], filename=d["filename"], media_type=d["mime"] or "application/octet-stream")


# ------------------------------------------------------------------ settings, audit, jobs
@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    lead(request)
    version, cfg = scoring.current_config()
    return render(request, "settings.html", cfg=cfg, version=version, ai_reason=config.settings.ai_mode_reason,
                  history=db.q("SELECT version, note, created_at FROM config_versions ORDER BY version DESC"))


@app.post("/settings")
async def settings_save(request: Request):
    lead(request)
    f = await form(request)
    _, cfg = scoring.current_config()
    try:
        cfg["weights"] = {k: float(f[f"w_{k}"]) for k in scoring.CRITERION_KEYS}
        cfg["overall_threshold"] = float(f["overall_threshold"])
        cfg["minimums"] = {k: int(f[f"min_{k}"]) for k in scoring.CRITERION_KEYS if f.get(f"min_{k}")}
        cfg["max_clarification_rounds"] = int(f["max_clarification_rounds"])
        cfg["retention_days"] = int(f["retention_days"])
        cfg["link_expiry_days"] = {"candidate": int(f["link_days"])}
        cfg["game_minutes"] = int(f["game_minutes"])
        v = scoring.save_config(cfg, note=f.get("note") or "Settings updated", by="lead")
    except (ValueError, KeyError) as e:
        return back("/settings", err=f"Settings not saved: {e}")
    return back("/settings", msg=f"Saved as configuration version {v}.")


@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request):
    lead(request)
    return render(request, "audit.html", rows=db.q("SELECT a.*, c.name AS cname FROM audit a LEFT JOIN candidates c ON c.id=a.candidate_id ORDER BY a.id DESC LIMIT 500"))


@app.post("/jobs")
async def jobs(request: Request):
    lead(request)
    await form(request)
    return back("/", msg="Jobs complete: " + await run_jobs())


async def run_jobs(_by: str = "scheduler") -> str:
    return await workflow.run_jobs()


# ------------------------------------------------------------------ candidate assessment
@app.get("/a/{token}")
def open_link(token: str):
    try:
        acc = security.resolve(token)
    except security.LinkError as e:
        raise HTTPException(401, e.reason)
    resp = RedirectResponse("/assess", status_code=303)
    resp.set_cookie(security.CAND_COOKIE, token, httponly=True, samesite="lax",
                    secure=config.settings.base_url.startswith("https"), max_age=60 * 86400)
    db.audit("link.opened", actor="candidate", candidate_id=acc.candidate_id)
    return resp


def me(request: Request) -> dict:
    acc = security.require_candidate(request)
    c = workflow.cand(acc.candidate_id)
    if not c or c["status"] == "Withdrawn":
        raise HTTPException(401, "revoked")
    return c


@app.get("/assess", response_class=HTMLResponse)
def assess(request: Request):
    c = me(request)
    return render(request, "assess.html", c=c, answers=json.loads(c["answers_json"] or "{}"),
                  clarifications=workflow.open_clarifications(c["id"]))


@app.post("/assess/consent")
async def assess_consent(request: Request):
    c = me(request)
    f = await form(request)
    if f.get("consent") != "yes":
        return back("/assess", err="Please tick the consent box to continue, or contact the CDP Change Lead if you do not wish to take part.")
    workflow.confirm_consent(c)
    return back("/assess")


@app.post("/assess/save")
async def assess_save(request: Request, background: BackgroundTasks):
    c = me(request)
    f = await form(request)
    try:
        workflow.save_answers(c, {k[2:]: v for k, v in f.items() if k.startswith("a_")}, "text")
        if f.get("action") == "submit":
            workflow.submit_answers(workflow.cand(c["id"]))
            background.add_task(workflow.run_assessment, c["id"])
            return back("/assess", msg="Thank you. Your answers have been submitted.")
    except WorkflowError as e:
        return back("/assess", err=str(e))
    return back("/assess", msg="Saved. You can come back to this link at any time.")


@app.post("/assess/clarify")
async def assess_clarify(request: Request, background: BackgroundTasks):
    c = me(request)
    f = await form(request)
    try:
        workflow.respond_clarifications(c, {int(k[3:]): v for k, v in f.items() if k.startswith("cl_") and k[3:].isdigit()})
    except WorkflowError as e:
        return back("/assess", err=str(e))
    background.add_task(workflow.run_assessment, c["id"])
    return back("/assess", msg="Thank you. Your answers have been submitted.")


# ------------------------------------------------------------------ NEXUS game
@app.post("/assess/mode")
async def assess_mode(request: Request):
    c = me(request)
    f = await form(request)
    if f.get("mode") == "game":
        try:
            workflow.game_start(c)
        except WorkflowError as e:
            return back("/assess", err=str(e))
        return RedirectResponse("/play", status_code=303)
    if f.get("mode") == "text":
        state, _ = workflow.game_load(c["id"])
        if state:
            return back("/assess", err="You have already started the game. Contact the CDP Change Lead if you need the written version.")
        db.ex("UPDATE candidates SET assessment_mode='text' WHERE id=?", (c["id"],))
        db.audit("assessment.mode_text", actor="candidate", candidate_id=c["id"])
    return back("/assess")


@app.get("/play", response_class=HTMLResponse)
def play(request: Request):
    c = me(request)
    state, _ = workflow.game_load(c["id"])
    if not state or c["status"] != "In Assessment":
        return RedirectResponse("/assess", status_code=303)
    return render(request, "play.html", c=c)


@app.post("/play/api")
async def play_api(request: Request):
    c = me(request)
    security.check_csrf(request, request.headers.get("x-csrf"))
    try:
        body = await request.json()
    except Exception:
        body = {}
    action = str(body.get("action") or "poll")
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    try:
        view = workflow.game_action(c, action, params)
    except WorkflowError as e:
        return JSONResponse({"error": str(e)}, status_code=409)
    fresh = workflow.cand(c["id"])
    view["assessment_status"] = fresh["status"]
    if fresh["status"] == "Assessing" and c["status"] == "In Assessment":
        task = asyncio.create_task(workflow.run_assessment(c["id"]))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    return JSONResponse(view)
