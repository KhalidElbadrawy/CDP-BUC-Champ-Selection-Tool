"""Version 2 validation suite. Run:  .venv/bin/python -m pytest -q"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import json
import os
import re

import pytest
from fastapi.testclient import TestClient

from app import ai, config, db, imports, scoring, security, workflow
from app.seed import ANSWERS, UNSAFE, cv_bytes


@pytest.fixture(scope="module", autouse=True)
def fresh(tmp_path_factory):
    d = tmp_path_factory.mktemp("cdp2")
    os.environ.update(CDP_DB=str(d / "t.sqlite3"), CDP_UPLOAD_DIR=str(d / "up"), CDP_AI_MODE="demo")
    os.environ.pop("CDP_LEAD_PASSWORD", None)
    os.environ.pop("CDP_ENV", None)
    config.reload_settings()
    from app import seed
    asyncio.run(seed.seed())
    yield


@pytest.fixture
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def login(c):
    r = c.post("/login", data={"password": "demo", "next": "/"}, follow_redirects=False)
    assert r.status_code == 303


def csrf(c):
    basis = c.cookies.get(security.LEAD_COOKIE) or c.cookies.get(security.CAND_COOKIE) or ""
    return hmac.new(config.settings.secret_key.encode(), ("csrf:" + basis).encode(), hashlib.sha256).hexdigest()


def by_name(name, iid=1):
    return workflow.cand(db.q1("SELECT id FROM candidates WHERE name=? AND initiative_id=?", (name, iid))["id"])


def fresh_candidate(name, tier="high", answers=None):
    iid = workflow.create_initiative(f"Test {name}")
    workflow.import_records(iid, [dict(name=name, entity="Test Entity", email=f"{name.split()[0].lower()}@t.gov", consent=True,
                                       row_number=2, platform="ERP", workflow="Requisitions")])
    c = by_name(name, iid)
    workflow.upload_cv(c, f"{name}.docx", cv_bytes(name, tier, "ERP"))
    asyncio.run(workflow.screen(c["id"]))
    return workflow.cand(c["id"])


# ---------------------------------------------------------------- scoring rules (unchanged from v1)
def test_weights_and_points():
    assert sum(c["weight"] for c in scoring.CRITERIA) == 100
    assert scoring.weighted_points(4, 20) == 16
    bad = copy.deepcopy(scoring.DEFAULT_CONFIG); bad["weights"]["judgment"] = 9
    assert scoring.validate_config(bad)


@pytest.mark.parametrize("crit", ["empathy", "reliability", "judgment"])
def test_minimums(crit):
    final = {k: {"rating": 5} for k in scoring.CRITERION_KEYS}
    final[crit] = {"rating": 2}
    r = scoring.score(final, scoring.DEFAULT_CONFIG)
    assert r["overall_score"] >= 70 and r["outcome"] == scoring.OUTCOME_NOT_YET


def test_partial_scores_not_fabricated():
    final = {k: {"rating": 4} for k in scoring.CRITERION_KEYS}
    final["curiosity"] = {"rating": None}
    r = scoring.score(final, scoring.DEFAULT_CONFIG)
    assert r["overall_score"] is None and "85 assessed points" in r["score_text"]


# ---------------------------------------------------------------- survey import
def test_import_mapping_for_microsoft_forms_export():
    header = ["ID", "Email", "Name", "Nominee name", "Nominee work email", "Entity", "Line manager name", "Line manager email",
              "Has the nominee agreed to AI screening of their CV?"]
    m = imports.guess_mapping(header)
    assert m["name"] == "Nominee name" and m["email"] == "Nominee work email"
    assert m["nominator_name"] == "Name" and m["nominator_email"] == "Email"
    assert m["manager_email"] == "Line manager email" and m["manager_name"] == "Line manager name"


def test_import_requires_name_and_entity_and_flags_consent():
    header, rows = ["Nominee name", "Entity", "Consent"], [["A Person", "X", "Yes"], ["", "X", "Yes"], ["B Person", "X", "No"]]
    recs, problems = imports.apply_mapping(header, rows, {"name": "Nominee name", "entity": "Entity", "consent": "Consent"})
    assert [r["consent"] for r in recs] == [True, False] and any("no nominee name" in p for p in problems)
    with pytest.raises(imports.ImportErrorMsg):
        imports.apply_mapping(header, rows, {"name": "Nominee name"})


def test_duplicates_skipped_and_no_consent_not_screened():
    assert db.q1("SELECT COUNT(*) n FROM candidates WHERE initiative_id=1 AND name='Aisha Rahman'")["n"] == 1
    fadi = by_name("Fadi Tawil")
    assert fadi["status"] == "No Consent" and fadi["fit_final"] is None
    workflow.upload_cv(fadi, "Fadi.docx", cv_bytes("Fadi Tawil", "high", "ERP"))
    assert asyncio.run(workflow.screen(fadi["id"])) is None          # never screened without consent


def test_cv_files_match_by_name():
    m = workflow.match_files(1, ["Aisha_Rahman_CV.pdf", "cv-omar-haddad.docx", "random.pdf"])
    assert m["Aisha_Rahman_CV.pdf"] == by_name("Aisha Rahman")["id"]
    assert m["cv-omar-haddad.docx"] == by_name("Omar Haddad")["id"]
    assert m["random.pdf"] is None


# ---------------------------------------------------------------- CV fit
def test_fit_categories_and_shortlist():
    cats = {r["fit_final"] for r in db.q("SELECT fit_final FROM candidates WHERE initiative_id=1 AND fit_final IS NOT NULL")}
    assert cats == set(scoring.FIT_CATEGORIES)
    for r in db.q("SELECT status, fit_final FROM candidates WHERE initiative_id=1 AND fit_final IS NOT NULL"):
        if r["status"] in ("Shortlisted", "Not Shortlisted"):
            assert (r["status"] == "Shortlisted") == (r["fit_final"] in scoring.FIT_PROGRESS)
    assert workflow.latest_screen(by_name("Aisha Rahman")["id"])["mode"] == "demo"


def test_override_needs_reason_and_is_blocked_after_invite():
    c = fresh_candidate("Over Ride", tier="low")
    assert c["status"] == "Not Shortlisted"
    with pytest.raises(workflow.WorkflowError):
        workflow.override_fit(c, "High Fit", "")
    workflow.override_fit(c, "Moderate Fit", "Strong nomination evidence")
    c = workflow.cand(c["id"])
    assert c["status"] == "Shortlisted" and c["fit_ai"] == "Low Fit" and c["fit_final"] == "Moderate Fit"
    workflow.invite(c)
    with pytest.raises(workflow.WorkflowError):
        workflow.override_fit(workflow.cand(c["id"]), "Low Fit", "changed mind")


def test_not_shortlisted_cannot_get_link():
    with pytest.raises(workflow.WorkflowError):
        workflow.invite(by_name("Dana Khoury"))


# ---------------------------------------------------------------- access control
def test_lead_pages_require_sign_in(client):
    for path in ("/", "/i/1", f"/c/{by_name('Aisha Rahman')['id']}", "/settings", "/audit", "/export.csv"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/login")
    assert client.post("/login", data={"password": "wrong"}).status_code == 401


def test_candidate_link_scoped_expiring_and_revocable(client):
    c = fresh_candidate("Link Person")
    first = workflow.invite(c).rsplit("/", 1)[1]
    second = workflow.invite(workflow.cand(c["id"])).rsplit("/", 1)[1]
    assert client.get(f"/a/{first}").status_code == 401            # replaced
    r = client.get(f"/a/{second}")
    assert r.status_code == 200 and "Link Person" in r.text and "Aisha" not in r.text
    assert client.get("/", follow_redirects=False).status_code == 303   # candidate cannot open lead pages
    raw = security.issue_link(c["id"], days=-1)
    assert client.get(f"/a/{raw}").status_code == 401              # expired


def test_csrf_required(client):
    login(client)
    c = by_name("Mariam Saleh")
    assert client.post(f"/c/{c['id']}/decide", data={"csrf": "x", "decision": "approved", "rationale": "r"}).status_code == 403
    assert workflow.cand(c["id"])["status"] == "Assessed"


# ---------------------------------------------------------------- assessment
def test_blinded_passes(monkeypatch):
    calls = []

    async def fake(system, prompt, schema):
        calls.append(prompt)
        if schema is ai.PASS_SCHEMA:
            return {"criteria": {k: {"rating": 4, "reasoning": f"SECRET-{len(calls)}"} for k in scoring.CRITERION_KEYS}}
        return {"criteria": {k: {"final_rating": 4, "resolution": "agreed", "justification": "j"} for k in scoring.CRITERION_KEYS}, "summary": ""}
    monkeypatch.setattr(config.settings, "ai_mode", "live")
    monkeypatch.setattr(ai, "_call_claude", fake)
    snap = {"platform": "", "workflow": "", "sources": [{"id": "Q", "label": "l", "criterion": "empathy", "text": "EVIDENCE"}]}
    a = asyncio.run(ai.assessment_pass(snap, "A")); b = asyncio.run(ai.assessment_pass(snap, "B"))
    assert calls[0] == calls[1] and "SECRET-1" not in calls[1]
    asyncio.run(ai.moderate(snap, a, b))
    assert "SECRET-1" in calls[2] and "SECRET-2" in calls[2]


def test_seeded_outcomes():
    assert by_name("Aisha Rahman")["outcome"] == scoring.OUTCOME_MEETS
    assert by_name("Layla Nasser")["outcome"] == scoring.OUTCOME_NOT_YET
    assert by_name("Yousef Karim")["status"] == "Follow-up Requested"
    assert workflow.open_clarifications(by_name("Yousef Karim")["id"])[0]["kind"] == "remediation"
    assert by_name("Khalid Mansour")["outcome"] == scoring.OUTCOME_EVIDENCE


def test_follow_up_then_reassessment():
    c = by_name("Yousef Karim")
    cl = workflow.open_clarifications(c["id"])
    workflow.respond_clarifications(c, {q["id"]: ANSWERS["judgment"] for q in cl})
    asyncio.run(workflow.run_assessment(c["id"]))
    assert workflow.cand(c["id"])["outcome"] == scoring.OUTCOME_MEETS


def test_ai_failure_keeps_answers(monkeypatch):
    c = fresh_candidate("Fail Case")
    workflow.invite(c); workflow.confirm_consent(workflow.cand(c["id"]))
    workflow.save_answers(workflow.cand(c["id"]), ANSWERS, "text")
    workflow.submit_answers(workflow.cand(c["id"]))

    async def boom(*a, **k):
        raise ai.AIError("timeout")
    monkeypatch.setattr(ai, "assessment_pass", boom)
    asyncio.run(workflow.run_assessment(c["id"]))
    c = workflow.cand(c["id"])
    assert c["status"] == "Assessing" and "saved" in c["last_error"] and json.loads(c["answers_json"])["judgment"]
    monkeypatch.undo()
    asyncio.run(workflow.run_jobs())
    assert workflow.cand(c["id"])["status"] == "Assessed"


def test_offline_answers_assessed(client):
    login(client)
    c = fresh_candidate("Offline Person")
    data = {"csrf": csrf(client), **{f"a_{k}": v for k, v in ANSWERS.items()}}
    client.post(f"/c/{c['id']}/offline", data=data)
    c = workflow.cand(c["id"])
    assert c["assessment_mode"] == "offline" and c["outcome"] == scoring.OUTCOME_MEETS


def test_candidate_journey_over_http(client):
    c = fresh_candidate("Web Person")
    raw = workflow.invite(c).rsplit("/", 1)[1]
    client.get(f"/a/{raw}")
    client.post("/assess/consent", data={"csrf": csrf(client), "consent": "yes"})
    client.post("/assess/save", data={"csrf": csrf(client), "action": "submit", **{f"a_{k}": v for k, v in ANSWERS.items()}})
    assert workflow.cand(c["id"])["status"] == "Assessed"
    assert "Thank you" in client.get("/assess").text


# ---------------------------------------------------------------- decisions, dashboard, steps
def test_decision_rules():
    with pytest.raises(workflow.WorkflowError):
        workflow.decide(by_name("Hassan Ali"), "approved", "r")          # not assessed
    with pytest.raises(workflow.WorkflowError):
        workflow.decide(by_name("Huda Saeed"), "approved", "")          # rationale required
    workflow.decide(by_name("Huda Saeed"), "approved", "Strong evidence.")
    assert by_name("Huda Saeed")["status"] == "Approved"


def test_dashboard_counts_and_filters():
    d = workflow.dashboard(1)
    assert d["champions"] == db.q1("SELECT COUNT(*) n FROM candidates WHERE initiative_id=1 AND status!='Withdrawn'")["n"]
    assert d["approved"] == db.q1("SELECT COUNT(*) n FROM candidates WHERE initiative_id=1 AND status='Approved'")["n"]
    assert sum(d["by_cat"].values()) == d["champions"]
    hi = workflow.dashboard(1, category="High Fit")
    assert all(r["fit_final"] == "High Fit" for r in hi["rows"])
    ent = db.q1("SELECT entity_id FROM candidates WHERE name='Aisha Rahman'")["entity_id"]
    assert all(r["entity_id"] == ent for r in workflow.dashboard(entity=ent)["rows"])


def test_step_tracker():
    iid = workflow.create_initiative("Step Test")
    steps = workflow.step_progress(iid)
    assert len(steps) == 9 and steps[0]["current"] and not steps[0]["completed_at"]
    workflow.set_step(iid, 1, True)
    steps = workflow.step_progress(iid)
    assert steps[0]["completed_at"] and steps[1]["current"]
    workflow.set_step(iid, 1, False)
    assert workflow.step_progress(iid)[0]["current"]


def test_production_lock(client, monkeypatch):
    from app import production
    monkeypatch.setenv("CDP_ENV", "production")
    assert client.get("/login").status_code == 503
    assert security.lead_password() == ""                             # no demo password in production
    monkeypatch.setenv("CDP_SECRET_KEY", "x" * 40)
    monkeypatch.setattr(config.settings, "ai_mode", "live")
    monkeypatch.setattr(config.settings, "lead_password", "a-long-password")
    monkeypatch.setattr(config.settings, "base_url", "https://cdp.example.gov")
    assert production.setup_problems() == []


def test_unsafe_answer_triggers_remediation_not_score():
    c = fresh_candidate("Unsafe Person")
    workflow.invite(c); workflow.confirm_consent(workflow.cand(c["id"]))
    workflow.save_answers(workflow.cand(c["id"]), UNSAFE, "text")
    workflow.submit_answers(workflow.cand(c["id"]))
    r = asyncio.run(workflow.run_assessment(c["id"]))
    assert r["outcome"] == scoring.OUTCOME_REMEDIATION and workflow.cand(c["id"])["status"] == "Follow-up Requested"
