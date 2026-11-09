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
        workflow.decide(by_name("Sara Ibrahim"), "approved", "r")        # not assessed
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


def test_clear_initiative_data(client):
    login(client)
    iid = workflow.create_initiative("Clear Me")
    workflow.import_records(iid, [dict(name="Gone Person", entity="Temp Entity Z", email="gone@t.gov", consent=True, row_number=2)])
    c = by_name("Gone Person", iid)
    workflow.upload_cv(c, "Gone.docx", cv_bytes("Gone Person", "high", "ERP"))
    path = db.q1("SELECT stored_path FROM documents WHERE candidate_id=?", (c["id"],))["stored_path"]
    workflow.set_step(iid, 1, True)
    r = client.post(f"/i/{iid}/clear", data={"csrf": csrf(client), "confirm_name": "wrong", "scope": "data"})
    assert "Nothing was deleted" in r.text and workflow.cand(c["id"])
    client.post(f"/i/{iid}/clear", data={"csrf": csrf(client), "confirm_name": "Clear Me", "scope": "data"})
    assert workflow.cand(c["id"]) is None and not os.path.exists(path)
    assert not db.q("SELECT 1 FROM audit WHERE candidate_id=?", (c["id"],))
    assert not db.q1("SELECT 1 FROM entities WHERE name='Temp Entity Z'")
    assert db.q1("SELECT 1 FROM initiatives WHERE id=?", (iid,)) and not workflow.step_progress(iid)[0]["completed_at"]
    assert by_name("Aisha Rahman")                                      # other initiatives untouched
    client.post(f"/i/{iid}/clear", data={"csrf": csrf(client), "confirm_name": "Clear Me", "scope": "initiative"})
    assert not db.q1("SELECT 1 FROM initiatives WHERE id=?", (iid,))


# ---------------------------------------------------------------- NEXUS game
from app import game  # noqa: E402

from app.seed import GOOD_PLAY  # noqa: E402


def game_candidate(name, extra=1.0):
    c = fresh_candidate(name)
    workflow.invite(c)
    workflow.confirm_consent(workflow.cand(c["id"]))
    if extra != 1.0:
        workflow.set_extra_time(workflow.cand(c["id"]), extra)
    workflow.game_start(workflow.cand(c["id"]))
    return workflow.cand(c["id"])


def play(c, moves):
    v = None
    for a, p in moves:
        v = workflow.game_action(workflow.cand(c["id"]), a, p)
        assert not v.get("error"), (a, v.get("error"))
    return v


def test_full_game_assessed_with_event_evidence():
    c = game_candidate("Game Good")
    v = play(c, GOOD_PLAY)
    assert v["finished"] and v["outcome"]["connected"] == "6 of 6"
    assert workflow.cand(c["id"])["status"] == "Assessing"
    r = asyncio.run(workflow.run_assessment(c["id"]))
    assert r["outcome"] == scoring.OUTCOME_MEETS
    snap = json.loads(db.q1("SELECT snapshot_json FROM evidence_versions WHERE candidate_id=? ORDER BY version DESC", (c["id"],))["snapshot_json"])
    text = "\n".join(s["text"] for s in snap["sources"])
    assert re.search(r"\bE\d+\b", text)                                  # evidence cites game events
    assert "services restored" not in text and "restored_pct" not in text  # game outcome kept out of the evidence
    assert db.q1("SELECT outcome_json FROM game_sessions WHERE candidate_id=?", (c["id"],))["outcome_json"]


def test_switching_off_safety_lock_needs_remediation():
    c = game_candidate("Game Unsafe")
    moves = [m for m in GOOD_PLAY if not (m[0] == "stress_choice" and m[1].get("choice") == "refuse_escalate")]
    i = moves.index(("stress_choice", {"choice": "protect_clinic"}))
    moves.insert(i, ("stress_choice", {"choice": "switch_off"}))
    play(c, moves)
    r = asyncio.run(workflow.run_assessment(c["id"]))
    assert r["outcome"] == scoring.OUTCOME_REMEDIATION
    assert workflow.open_clarifications(c["id"])[0]["kind"] == "remediation"


def test_hidden_information_and_practice_not_assessed():
    c = game_candidate("Game Hidden")
    v = workflow.game_action(c, "start_practice", {})
    assert v["districts"]["clinic"]["detail"] is None                   # blockers hidden until inspected
    v = workflow.game_action(workflow.cand(c["id"]), "fix", {"district": "harbour"})
    v = workflow.game_action(workflow.cand(c["id"]), "finish_practice", {})
    state, events = workflow.game_load(c["id"])
    assert any(e["practice"] for e in events) and state["districts"]["harbour"]["dependency"] == 0
    assert not any("fixed Harbour personally" in l for l in game.evidence(state, events)["lines"]["credibility"])


def test_stress_timer_enforced_on_server():
    c = game_candidate("Game Timer", extra=1.5)
    play(c, GOOD_PLAY[:GOOD_PLAY.index(("read_brief", {}), 2) + 1])     # into round 2: stress S1 starts
    state, events = workflow.game_load(c["id"])
    assert state["phase"] == "stress" and state["stress"]["seconds"] == 90  # 60s x 1.5 extra time
    state["stress"]["deadline"] = "2000-01-01T00:00:00+00:00"           # time has run out
    workflow.game_save(c["id"], state, events)
    v = workflow.game_action(workflow.cand(c["id"]), "poll", {})
    _, events = workflow.game_load(c["id"])
    assert v["phase"] == "playing" and any(e["type"] == "stress_timeout" for e in events)
    v = workflow.game_action(workflow.cand(c["id"]), "stress_choice", {"choice": "fix_for_them"})
    assert v.get("error")                                               # a late answer is not accepted


def test_overall_clock_ends_game():
    c = game_candidate("Game Clock")
    play(c, GOOD_PLAY[:3])
    state, events = workflow.game_load(c["id"])
    state["ends_at"] = "2000-01-01T00:00:00+00:00"
    workflow.game_save(c["id"], state, events)
    v = workflow.game_action(workflow.cand(c["id"]), "poll", {})
    assert v["phase"] == "handover"
    v = play(c, [("handover", {"text": "Nothing finished yet; Harbour needs training, owned by the Trainer team."})])
    assert v["finished"] and workflow.cand(c["id"])["status"] == "Assessing"


def test_cannot_switch_to_written_after_starting_game(client):
    c = game_candidate("Game Switch")
    raw = workflow.invite(workflow.cand(c["id"])).rsplit("/", 1)[1]
    client.get(f"/a/{raw}")
    r = client.post("/assess/mode", data={"csrf": csrf(client), "mode": "text"})
    assert "already started the game" in r.text
    assert client.post("/play/api", json={"action": "poll"}, headers={"x-csrf": "bad"}).status_code == 403
    r = client.post("/play/api", json={"action": "poll"}, headers={"x-csrf": csrf(client)})
    assert r.status_code == 200 and r.json()["phase"] == "intro"
    workflow.game_reset(workflow.cand(c["id"]))
    assert workflow.game_load(c["id"])[0] is None


def test_cv_matching_handles_real_file_names():
    iid = workflow.create_initiative("Match Test")
    workflow.import_records(iid, [
        dict(name="Ahmed Mohamed Al Mansoori", entity="E", email="ahmed.mansoori@x.gov", consent=True, row_number=2),
        dict(name="Fatima Hassan Al Zaabi", entity="E", email="f.alzaabi@x.gov", consent=True, row_number=3),
        dict(name="Ahmed Saeed", entity="E", email="ahmed.saeed@x.gov", consent=True, row_number=4)])
    r = workflow.match_scores(iid, ["Ahmed_Mansoori_CV_final.pdf", "CV - Fatima Al Zaabi.docx", "Ahmed CV.pdf", "resume.pdf"])
    ids = {c["name"]: c["id"] for c in db.q("SELECT id, name FROM candidates WHERE initiative_id=?", (iid,))}
    assert r["Ahmed_Mansoori_CV_final.pdf"]["match"] == ids["Ahmed Mohamed Al Mansoori"]
    assert r["CV - Fatima Al Zaabi.docx"]["match"] == ids["Fatima Hassan Al Zaabi"]
    assert r["Ahmed CV.pdf"]["match"] is None and r["Ahmed CV.pdf"]["suggest"] is None   # two Ahmeds: ask the Change Lead
    assert r["resume.pdf"]["match"] is None


def test_bulk_consent_and_screening_blockers(client):
    login(client)
    iid = workflow.create_initiative("Consent Test")
    workflow.import_records(iid, [dict(name="No Consent One", entity="E", consent=False, row_number=2),
                                  dict(name="No Consent Two", entity="E", consent=False, row_number=3)])
    assert workflow.screening_blockers(iid)["no_consent"] == 2
    assert "Why nothing is ready" in client.get(f"/i/{iid}").text
    r = client.post(f"/i/{iid}/consent-all", data={"csrf": csrf(client)})
    assert "Tick the box" in r.text and workflow.screening_blockers(iid)["no_consent"] == 2
    client.post(f"/i/{iid}/consent-all", data={"csrf": csrf(client), "confirm": "yes"})
    b = workflow.screening_blockers(iid)
    assert b["no_consent"] == 0 and b["awaiting_cv"] == 2


def test_live_call_uses_structured_outputs(monkeypatch):
    """Live AI calls go to the Messages API in-process with structured outputs (no forced tool use)."""
    seen = {}

    class Block:
        type = "text"
        text = '{"fit_category": "High Fit"}'

    class Resp:
        content = [Block()]
        stop_reason = "end_turn"

    class Messages:
        async def create(self, **kw):
            seen.update(kw)
            return Resp()

    class Client:
        messages = Messages()
    monkeypatch.setattr(ai, "_anthropic", lambda: Client())
    out = asyncio.run(ai._call_claude("sys", "prompt", ai.PASS_SCHEMA))
    assert out == {"fit_category": "High Fit"}
    assert "tool_choice" not in seen and "tools" not in seen
    fmt = seen["output_config"]["format"]
    assert fmt["type"] == "json_schema"

    def walk(node):  # every object forbids extra keys and requires all its properties; no type lists remain
        if isinstance(node, dict):
            assert not isinstance(node.get("type"), list)
            if node.get("type") == "object":
                assert node["additionalProperties"] is False and set(node["required"]) == set(node.get("properties", {}))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(fmt["schema"])


def test_completed_steps_lock_their_actions(client):
    login(client)
    iid = workflow.create_initiative("Lock Test")
    workflow.set_step(iid, 2, True)
    page = client.get(f"/i/{iid}").text
    assert 'class="card locked"' in page and "Step 2 completed" in page
    r = client.post(f"/i/{iid}/import", data={"csrf": csrf(client)}, files={"file": ("n.csv", b"Nominee name,Entity\nA B,E\n")})
    assert "Step 2 is marked complete" in r.text
    client.post(f"/i/{iid}/step/2", data={"csrf": csrf(client), "complete": "0"})
    r = client.post(f"/i/{iid}/import", data={"csrf": csrf(client)}, files={"file": ("n.csv", b"Nominee name,Entity\nA B,E\n")})
    assert "Check the survey columns" in r.text
