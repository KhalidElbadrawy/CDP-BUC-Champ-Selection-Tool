"""LAUNCH WINDOW: a role-playing game for the CDP Champion assessment.

The candidate joins the crew of a fictional launch base for the last hour before a launch. Nothing in the
game mentions champions or the candidate's job; each scene is built so the six assessed behaviours show up
naturally. The server runs the game: the browser only draws the view and sends actions, timers are server
deadlines (scaled by the candidate's extra time), and every choice is logged as an event with an id the AI
assessor cites. Trust, readiness, rank and the launch ending are game outcomes only and never scored.
"""
from __future__ import annotations

import copy
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app import launch_content as C

NAME = "LAUNCH WINDOW"
CRITERIA = ("credibility", "empathy", "reliability", "curiosity", "workflow", "judgment")
SECONDS = {"act1": 180, "act2": 600, "w1": 75, "director": 60, "w2": 60, "w3": 45, "checklist": 120}
BUDGET = 5            # in-game minutes of work time in the Act IV checklist
COST = {"deliver": 4, "warn": 1, "slip": 0}
CALL_IDS = [c["id"] for c in C.CALLS]
CALL = {c["id"]: c for c in C.CALLS}
HANDOVER = {k: (label, kind) for k, label, kind in C.HANDOVER}


class GameError(Exception):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(t: datetime) -> str:
    return t.isoformat()


def parse(s: str) -> datetime:
    return datetime.fromisoformat(s)


def tr(d: dict | None, lang: str) -> str:
    return "" if not d else d.get(lang) or d["en"]


# ======================================================================================= state
def new_state(minutes: int = 45, extra_time: float = 1.0) -> dict:
    return {
        "version": 2, "game": "launch_window", "phase": "intro", "stage": None,
        "time_limit_s": int(minutes * 60 * extra_time), "extra_time": extra_time,
        "started_at": None, "ends_at": None, "deadline": None, "stage_seconds": None,
        "t": 60, "trust": 50, "ready": 40, "crew": [], "followers": [], "flags": [],
        "files": [], "checks": {},
        "noor": {"step": "n1", "done": False, "path": []},
        "calls": {}, "promises": [],
        "alerts": {}, "director": None, "director_text": "", "priority": None,
        "hamad": {"step": "h1", "asked": False, "done": False, "path": [], "transcript": []},
        "budget": BUDGET, "handover": None, "realwork": None, "free_text": {},
        "feedback": None, "cue": {"seq": 0, "lines": [], "sfx": [], "music": None},
        "finished": False, "end_reason": None, "seq": 0,
    }


def log(state: dict, events: list, etype: str, **detail) -> str:
    state["seq"] += 1
    eid = f"E{state['seq']}"
    events.append({"id": eid, "t": iso(now()), "phase": state["phase"], "stage": state["stage"], "type": etype, **detail})
    return eid


def cue(state: dict, lines: list[str] | None = None, sfx: list[str] | None = None, music: str | None = None) -> None:
    c = state["cue"]
    state["cue"] = {"seq": c["seq"] + 1, "lines": lines or [], "sfx": sfx or [], "music": music or c.get("music")}


def meters(state: dict, trust: int = 0, ready: int = 0) -> dict:
    state["trust"] = max(0, min(100, state["trust"] + trust))
    state["ready"] = max(0, min(100, state["ready"] + ready))
    return {"trust": trust, "ready": ready}


def say(state: dict, text: dict | None, delta: dict | None = None, who: str | None = None) -> None:
    state["feedback"] = {"text": text, "delta": delta or {}, "who": who, "seq": state["seq"]}


def minutes(state: dict, n: int, floor: int) -> None:
    state["t"] = max(floor, state["t"] - n)


def set_timer(state: dict, key: str | None) -> None:
    if key is None:
        state["deadline"], state["stage_seconds"] = None, None
        return
    secs = int(SECONDS[key] * state["extra_time"])
    state["deadline"], state["stage_seconds"] = iso(now() + timedelta(seconds=secs)), secs


def expired(state: dict) -> bool:
    return bool(state["deadline"]) and now() >= parse(state["deadline"])


def flag(state: dict, f: str) -> bool:
    return f in state["flags"]


# ======================================================================================= free text
_INTENTS = {
    "n1": [("coach", r"together|with you|walk you|talk you|show you|guide|step by step|معا|معاً|أرشد|سأريك|خطوة"),
           ("do_it", r"i'?ll do|let me do|step aside|move|i do it|سأقوم|دعيني|تنحي|أنا سأ")],
    "n2": [("blame", r"told you|your fault|careless|قلت لك|خطؤك"),
           ("takeover", r"stop|don'?t touch|take over|let me|توقف|لا تلمس|سأتولى"),
           ("reassure", r"breathe|okay|fine|normal|didn'?t break|blink|steady|calm|اهدئي|طبيعي|لم تكسري|يومض|ثابت")],
    "n3": [("multiply", r"show|teach|ali|others|علي|اشرحي|علّمي"), ("keep", r"leave .* me|i'?ll do|let me|اتركي|سأقوم"),
           ("alone", r"yes|go ahead|you can|call me|نعم|تستطيعين|اتصلي")],
    "h1": [("ask", r"what (do )?you see|describe|tell me|colou?r|which light|ماذا ترى|صف|أخبرني|لون"),
           ("instruct", r"press|push|flip|switch|اضغط|اقلب")],
    "h3": [("blame", r"why didn'?t|your fault|careless|لماذا لم"), ("takeover", r"hands off|someone else|stop|ارفع|شخص آخر|توقف"),
           ("reassure", r"normal|keep holding|fine|right|ok|طبيعي|استمر|صحيح")],
    "h4": [("check", r"say it back|repeat|tell me the steps|أعد|كرر"), ("note", r"write|guide|note|card|sticker|دليل|أكتب|ملاحظة"),
           ("call", r"call me|ring me|اتصل بي")],
}


def classify(step: str, text: str) -> str | None:
    t = (text or "").lower()
    for intent, pat in _INTENTS.get(step, []):
        if re.search(pat, t):
            return intent
    return None


def _choice(state: dict, step: str, p: dict, allowed: list[str]) -> tuple[str, str | None]:
    """A listed option, or the player's own words mapped to the closest option (the raw text is kept for the AI)."""
    choice, text = p.get("choice"), (p.get("text") or "").strip()[:600] or None
    if text:
        state["free_text"][step] = text
    if text and not choice:
        choice = classify(step, text) or "free"
    if choice == "free":
        return choice, text
    if choice not in allowed:
        raise GameError("Please choose one of the replies, or type your own.")
    return choice, text


# ======================================================================================= flow
def tick(state: dict, events: list) -> None:
    if state["finished"] or not state["started_at"]:
        return
    if state["ends_at"] and now() >= parse(state["ends_at"]):
        log(state, events, "time_up")
        state.update(finished=True, end_reason="time", phase="done", stage=None, deadline=None)
        return
    if not expired(state):
        return
    ph, st = state["phase"], state["stage"]
    if ph == "act1":
        for q in C.CHECKS:
            if q["id"] not in state["checks"]:
                state["checks"][q["id"]] = None
                log(state, events, "check_timeout", check=q["id"])
        start_act2(state, events)
    elif ph == "act2":
        start_act3(state, events, timed_out=True)
    elif ph == "act3":
        if st in ("w1", "w2"):
            for aid in wave_alerts(state, 1 if st == "w1" else 2):
                if aid not in state["alerts"]:
                    state["alerts"][aid] = {"choice": None}
                    log(state, events, "alert_missed", alert=aid)
            advance_act3(state, events)
        elif st == "director":
            state["director"] = "timeout"
            log(state, events, "director_timeout")
            advance_act3(state, events)
        elif st == "w3":
            state["priority"] = "timeout"
            log(state, events, "priority_timeout")
            start_act4(state, events)
    elif ph == "act4" and st == "checklist":
        for pr in state["promises"]:
            if pr["status"] == "open":
                pr["status"] = "slipped"
                log(state, events, "promise_slipped", promise=pr["id"], to=pr["to"], notified=False, by_timer=True)
        start_epilogue(state, events)


def start_act2(state: dict, events: list) -> None:
    state.update(phase="act2", stage="map", t=44)
    set_timer(state, "act2")
    log(state, events, "act_start", act=2)
    cue(state, ["N03"], ["radio"], "explore")


def start_act3(state: dict, events: list, timed_out: bool = False) -> None:
    if not state["noor"]["done"]:
        log(state, events, "noor_unfinished")
    for cid in CALL_IDS:
        if cid not in state["calls"]:
            state["calls"][cid] = {"choice": None}
            log(state, events, "call_ignored", call=cid, who=CALL[cid]["who"]["en"])
    state.update(phase="act3", stage="w1", t=18)
    set_timer(state, "w1")
    log(state, events, "act_start", act=3, by_timer=timed_out)
    # Payoffs of earlier choices arrive as automatic events in wave 2 (logged now so the record is complete).
    cue(state, ["Y01", "N05", "N06"], ["alarm"], "alert")


def wave_alerts(state: dict, wave: int) -> list[str]:
    ids = [a for a, d in C.ALERTS.items() if d["wave"] == wave]
    if wave == 2:
        if flag(state, "khalid_taught"):
            ids.remove("A5")
        if "Noor" not in state["followers"]:
            ids.remove("A6")
    return ids


def advance_act3(state: dict, events: list) -> None:
    st = state["stage"]
    if st == "w1":
        state["stage"] = "director"
        set_timer(state, "director")
        cue(state, ["S01"], ["heartbeat"])
    elif st == "director":
        state["stage"] = "w2"
        set_timer(state, "w2")
        if flag(state, "khalid_taught"):
            log(state, events, "peer_payoff", alert="A5", helper="Khalid", text=C.AUTO["A5"]["en"])
        if "Noor" in state["crew"]:
            key = "A6_multiply" if flag(state, "noor_multiplier") else "A6_alone"
            log(state, events, "peer_payoff", alert="A6", helper="Noor", text=C.AUTO[key]["en"])
        cue(state, [], ["alarm"])
    elif st == "w2":
        state["stage"] = "w3"
        set_timer(state, "w3")
        cue(state, ["N07"], ["heartbeat"])


def start_act4(state: dict, events: list) -> None:
    state.update(phase="act4", stage="radio", t=10)
    set_timer(state, None)
    log(state, events, "act_start", act=4)
    cue(state, ["Y02", "N08", "H01"], ["success", "radio"], "explore")


def start_checklist(state: dict, events: list) -> None:
    if not state["promises"]:
        log(state, events, "checklist_empty")
        return start_epilogue(state, events)
    state.update(stage="checklist", t=8, budget=BUDGET)
    set_timer(state, "checklist")
    cue(state, ["N09"], ["heartbeat"])


def start_epilogue(state: dict, events: list) -> None:
    state.update(phase="epilogue", stage=None, t=5)
    set_timer(state, None)
    log(state, events, "act_start", act=5)
    cue(state, ["N10", "M02"], [], "explore")


# ======================================================================================= actions
def act(state: dict, events: list, action: str, p: dict[str, Any]) -> None:
    tick(state, events)
    if state["finished"]:
        raise GameError("The game has finished. Thank you.")
    ph, st = state["phase"], state["stage"]

    if action == "begin" and ph == "intro":
        t0 = now()
        state.update(phase="prologue", started_at=iso(t0), ends_at=iso(t0 + timedelta(seconds=state["time_limit_s"])))
        log(state, events, "game_start")
        cue(state, ["N01"], ["lights"], "explore")
        return

    if action == "travel" and ph == "prologue":
        if p.get("to") != "briefing":
            raise GameError("Start at the briefing hall. It's glowing on the map.")
        state.update(phase="act1", stage="files", t=55)
        set_timer(state, "act1")
        log(state, events, "act_start", act=1)
        cue(state, ["M01", "N02"], ["ui"], "explore")
        return

    if ph == "act1":
        if action == "open_file":
            fid = p.get("id")
            if fid not in {f["id"] for f in C.FILES}:
                raise GameError("Unknown file.")
            if fid in state["files"]:
                return
            if len(state["files"]) >= 4:
                raise GameError("You can open four files. Answer the readiness checks next.")
            state["files"].append(fid)
            minutes(state, 1, 47)
            log(state, events, "file_open", file=fid, order=len(state["files"]), relevant=fid in C.RELEVANT_FILES)
            return
        if action == "answer":
            q = next((q for q in C.CHECKS if q["id"] == p.get("q")), None)
            if not q or p.get("choice") not in [o[0] for o in q["options"]]:
                raise GameError("Please pick one answer.")
            if state["checks"].get(q["id"]):
                return
            ch = p["choice"]
            state["checks"][q["id"]] = ch
            correct = ch == q["correct"]
            d = meters(state, ready=3 if correct else (1 if ch == "unsure" else -2))
            log(state, events, "check_answer", check=q["id"], choice=ch, correct=correct, honest_unsure=ch == "unsure",
                files_open=list(state["files"]))
            minutes(state, 1, 45)
            say(state, None, d)
            if all(state["checks"].get(c["id"]) for c in C.CHECKS):
                start_act2(state, events)
            return

    if ph == "act2":
        if action == "noor":
            return noor_turn(state, events, p)
        if action == "call":
            return call_turn(state, events, p)
        if action == "to_control":
            if not state["noor"]["done"]:
                raise GameError("Noor still needs you at the fuel bay.")
            return start_act3(state, events)

    if ph == "act3":
        if action == "alert" and st in ("w1", "w2"):
            return alert_turn(state, events, p, 1 if st == "w1" else 2)
        if action == "director" and st == "director":
            ch = p.get("choice")
            if ch not in [o[0] for o in C.DIRECTOR]:
                raise GameError("Choose a reply to the Director.")
            text = (p.get("text") or "").strip()[:600]
            state["director"], state["director_text"] = ch, text
            if ch == "override":
                state["flags"].append("overridden")
                d = meters(state, ready=6)
            else:
                d = meters(state, trust=2)
            log(state, events, "director_choice", choice=ch, text=text or None,
                knew_rule="F4" in state["files"] or state["checks"].get("q2") == "range")
            say(state, None, d)
            if ch != "override":
                cue(state, ["S02"], [])
            return advance_act3(state, events)
        if action == "priority" and st == "w3":
            ch = p.get("choice")
            if ch not in [o[0] for o in C.PRIORITY]:
                raise GameError("Choose one alert.")
            state["priority"] = ch
            d = meters(state, ready=6 if ch == "critical" else -6)
            log(state, events, "priority_choice", choice=ch)
            say(state, None, d)
            return start_act4(state, events)

    if ph == "act4":
        if action == "hamad" and st == "radio":
            return hamad_turn(state, events, p)
        if action == "promise" and st == "checklist":
            pr = next((x for x in state["promises"] if x["id"] == p.get("id")), None)
            ch = p.get("choice")
            if not pr or ch not in COST:
                raise GameError("Choose what to do with this promise.")
            if pr["status"] != "open":
                return
            if COST[ch] > state["budget"]:
                raise GameError("Not enough time left to deliver this one. Warn them, or let it slip.")
            state["budget"] -= COST[ch]
            pr["status"] = {"deliver": "kept", "warn": "warned", "slip": "slipped"}[ch]
            etype = {"deliver": "promise_kept", "warn": "delay_notified", "slip": "promise_slipped"}[ch]
            d = meters(state, trust={"deliver": 4, "warn": 1, "slip": -4}[ch])
            log(state, events, etype, promise=pr["id"], to=pr["to"], notified=ch == "warn", budget_left=state["budget"])
            say(state, None, d)
            if all(x["status"] != "open" for x in state["promises"]):
                start_epilogue(state, events)
            return
        if action == "close_checklist" and st == "checklist":
            for pr in state["promises"]:
                if pr["status"] == "open":
                    pr["status"] = "slipped"
                    log(state, events, "promise_slipped", promise=pr["id"], to=pr["to"], notified=False)
            return start_epilogue(state, events)

    if ph == "epilogue" and action == "handover":
        picks = p.get("actions") or []
        note = (p.get("note") or "").strip()[:2000]
        if not isinstance(picks, list) or len(set(picks)) != 3 or any(k not in HANDOVER for k in picks):
            raise GameError("Choose exactly three actions for the next shift.")
        if len(note) < 20:
            raise GameError("Please write a short handover note (a sentence or two).")
        state["handover"] = {"actions": list(dict.fromkeys(picks)), "note": note}
        log(state, events, "handover", actions=state["handover"]["actions"],
            kinds=[HANDOVER[k][1] for k in state["handover"]["actions"]], note_length=len(note))
        state.update(phase="launch", t=0)
        cue(state, ["N11"], ["ignition"], "launch")
        return

    if ph == "launch" and action == "continue":
        state["phase"] = "realwork"
        log(state, events, "launch_seen")
        cue(state, ["N12"], [], None)
        return

    if ph == "realwork" and action == "realwork":
        ans = {k: (p.get(k) or "").strip()[:3000] for k, _ in C.REALWORK}
        if any(len(v) < 20 for v in ans.values()):
            raise GameError("Please answer both questions in a few sentences.")
        state["realwork"] = ans
        log(state, events, "realwork", lengths={k: len(v) for k, v in ans.items()})
        state.update(phase="done", finished=True, end_reason="complete")
        return

    raise GameError("That isn't available right now.")


def noor_turn(state: dict, events: list, p: dict) -> None:
    n = state["noor"]
    if n["done"]:
        raise GameError("Noor's check is finished.")
    step = n["step"]
    choice, text = _choice(state, step, p, [o[0] for o in C.NOOR[step]["options"]])
    if choice == "free":  # unclassified own words: the story continues on the supportive path, the text goes to the AI
        choice = {"n1": "coach", "n2": "reassure", "n2b": "guide", "n3": "alone"}[step]
        free = True
    else:
        free = bool(text)
    n["path"].append(choice)
    minutes(state, 2, 30)
    log(state, events, "noor_choice", step=step, choice=choice, text=text, own_words=free,
        knew_guide="F6" in state["files"])
    d: dict = {}
    if step == "n1":
        if choice == "do_it":
            d = meters(state, trust=2, ready=2)
            state["followers"].append("Noor")
            n.update(done=True, step=None)
            say(state, C.NOOR_SAY["do_it"], d, "noor")
            cue(state, ["NO4", "N04"], [])
            return
        d = meters(state, trust=8 if choice == "coach" else -4)
        n["step"] = "n2"
        say(state, C.NOOR_SAY.get(choice), d, "noor")
        cue(state, ["NO2"], ["beep"])
    elif step == "n2":
        if choice == "takeover":
            d = meters(state, trust=-2, ready=2)
            state["followers"].append("Noor")
            n.update(done=True, step=None)
            say(state, C.NOOR_SAY["takeover"], d, "noor")
            cue(state, ["N04"], [])
            return
        if choice == "reassure":
            d = meters(state, trust=6)
            n["step"] = "n2b"
            say(state, C.NOOR["n2b"]["say"], d, "noor")
            cue(state, [], ["ui"])
        else:  # blame
            d = meters(state, trust=-8)
            n["step"] = "n3"
            say(state, C.NOOR_SAY["blame"], d, "noor")
            cue(state, ["NO3"], ["success"])
    elif step == "n2b":
        d = meters(state, ready=4 if choice == "guide" else -3)
        n["step"] = "n3"
        say(state, C.NOOR_SAY[choice], d, "noor")
        cue(state, ["NO3"], ["success"])
    elif step == "n3":
        if choice == "multiply":
            state["crew"].append("Noor")
            state["flags"].append("noor_multiplier")
            d = meters(state, trust=6, ready=2)
        elif choice == "alone":
            state["crew"].append("Noor")
            d = meters(state, trust=3)
        else:
            state["followers"].append("Noor")
            d = meters(state, trust=-2)
        n.update(done=True, step=None)
        say(state, C.NOOR_SAY[choice], d, "noor")
        cue(state, ["N04"], ["success"])


def call_turn(state: dict, events: list, p: dict) -> None:
    cid = p.get("id")
    call = CALL.get(cid)
    if not call:
        raise GameError("Unknown call.")
    if cid in state["calls"]:
        return
    if call.get("after_noor") and not state["noor"]["done"]:
        raise GameError("Help Noor first.")
    opt = next((o for o in call["options"] if o[0] == p.get("choice")), None)
    if not opt:
        raise GameError("Choose a reply.")
    key, _, kind, correct = opt
    state["calls"][cid] = {"choice": key}
    effects = {
        "c1.bypass": (3, -4), "c1.route": (2, 3), "c1.dismiss": (-4, 0),
        "c2.fix": (3, 1), "c2.teach": (4, 2), "c2.dismiss": (-3, -1),
        "c3.answer": (1, -1), "c3.route": (1, 3), "c3.guess": (-1, -3),
        "c4.promise": (2, 0), "c4.teach": (4, 1), "c4.route": (0, 1),
        "c5.promise": (2, 0), "c5.now": (1, 2), "c5.route": (0, 2),
    }[f"{cid}.{key}"]
    d = meters(state, trust=effects[0], ready=effects[1])
    if cid == "c1" and key == "bypass":
        state["flags"].append("c1_bypass")
    if cid == "c2" and key == "teach":
        state["crew"].append("Khalid")
        state["flags"].append("khalid_taught")
    if cid == "c4" and key == "teach":
        state["crew"].append("Rashid")
    if key == "promise":
        state["promises"].append({"id": f"P-{cid}", "call": cid, "to": C.PROMISES[cid]["to"]["en"], "status": "open"})
    minutes(state, 3 if key == "teach" else 2, 20)
    log(state, events, "call_response", call=cid, who=call["who"]["en"], choice=key, kind=kind, correct_route=correct,
        promise=key == "promise", control_bypass=key == "bypass")
    say(state, C.CALL_SAY[f"{cid}.{key}"], d)
    cue(state, [], ["ui"])


def alert_turn(state: dict, events: list, p: dict, wave: int) -> None:
    aid = p.get("id")
    if aid not in wave_alerts(state, wave):
        raise GameError("Unknown alert.")
    if aid in state["alerts"]:
        return
    a = C.ALERTS[aid]
    choice, station = p.get("choice"), p.get("station")
    if "special" in a:
        if choice not in [o[0] for o in a["special"]]:
            raise GameError("Choose what to do.")
        correct = choice == "confirm"
        d = meters(state, ready=5 if correct else (-6 if choice == "abort" else -8))
        state["alerts"][aid] = {"choice": choice}
        log(state, events, "alert_response", alert=aid, choice=choice, correct=correct, knew_issue="F2" in state["files"])
    else:
        allowed = ["handle", "route"] + (["send"] if state["crew"] else []) + (["bypass"] if aid == "A2" and flag(state, "c1_bypass") else [])
        if choice not in allowed:
            raise GameError("Choose: handle it, send a crew member, or route it.")
        if choice == "route" and station not in C.STATIONS:
            raise GameError("Pick the station to route it to.")
        correct = (choice == "route" and station == a["station"]) or (choice == "send" and aid in ("A1", "A6"))
        d = meters(state, ready=4 if correct else (-1 if choice == "handle" else -3))
        state["alerts"][aid] = {"choice": choice, "station": station}
        log(state, events, "alert_response", alert=aid, choice=choice, station=station, right_station=a["station"],
            correct=correct, used_crew=choice == "send", control_bypass=choice == "bypass")
    say(state, None, d)
    if all(x in state["alerts"] for x in wave_alerts(state, wave)):
        advance_act3(state, events)


def hamad_turn(state: dict, events: list, p: dict) -> None:
    h = state["hamad"]
    step = h["step"]
    opts = [o[0] for o in C.HAMAD[step]["options"]]
    if step == "h2" and h["asked"]:
        opts = [o for o in opts if o != "ask"]
    choice, text = _choice(state, step, p, opts)
    free = bool(text)
    if choice == "free":
        choice = {"h1": "ask", "h2": "reset", "h3": "reassure", "h4": "note"}[step]
    h["path"].append(f"{step}:{choice}")
    h["transcript"].append({"who": "you", "step": step, "choice": choice, "text": text})
    log(state, events, "hamad_choice", step=step, choice=choice, text=text, own_words=free, asked_before=h["asked"],
        knew_guide="F6" in state["files"])
    d: dict = {}
    if step in ("h1", "h2") and choice == "ask":
        h["asked"] = True
        h["step"] = "h2"
        d = meters(state, trust=3)
        say(state, None, d, "hamad")
        cue(state, ["H02"], ["radio"])
    elif step == "h1":
        h["step"] = "h2"
        say(state, C.HAMAD_SAY[choice], meters(state, trust=-2), "hamad")
        cue(state, [], ["radio"])
    elif step == "h2":
        if choice == "red":
            say(state, C.HAMAD_SAY["red"], meters(state, ready=-4), "hamad")
            cue(state, [], ["radio"])
        else:
            h["step"] = "h3"
            d = meters(state, ready=4)
            say(state, None, d, "hamad")
            cue(state, ["H03"], ["beep"])
    elif step == "h3":
        d = meters(state, trust={"reassure": 5, "takeover": -3, "blame": -6}[choice])
        h["step"] = "h4"
        say(state, C.HAMAD_SAY.get(choice), d, "hamad")
        cue(state, ["H04"], ["success"])
    elif step == "h4":
        d = meters(state, trust={"check": 4, "note": 4, "call": -1}[choice], ready=2)
        h.update(done=True, step=None)
        say(state, C.HAMAD_SAY[choice], d, "hamad")
        start_checklist(state, events)


# ======================================================================================= view
def outcome(state: dict) -> dict:
    score = state["trust"] + state["ready"]
    rank = next(r for floor, r in C.RANKS if score >= floor)
    return {"trust": state["trust"], "ready": state["ready"], "crew": len(state["crew"]), "crew_names": list(state["crew"]),
            "rank": rank["en"], "ending": "override" if flag(state, "overridden") else "held"}


def view(state: dict, lang: str = "en") -> dict:
    """Everything the browser may draw, in the chosen language."""
    lang = "ar" if lang == "ar" else "en"
    ph, st = state["phase"], state["stage"]
    v: dict[str, Any] = {k: copy.deepcopy(state[k]) for k in ("phase", "stage", "finished", "end_reason", "deadline",
                                                                 "stage_seconds", "ends_at", "cue", "crew", "trust", "ready")}
    v.update(lang=lang, now=iso(now()), t=state["t"], hold=ph == "act3")
    v["checklist_open"] = sum(1 for x in state["promises"] if x["status"] == "open")
    fb = state["feedback"]
    v["feedback"] = {"text": tr(fb["text"], lang), "delta": fb["delta"], "who": fb["who"], "seq": fb["seq"]} if fb else None
    v["lines"] = {lid: {"speaker": spk, "name": tr(C.SPEAKERS[spk], lang), "text": tr(txt, lang)} for lid, (spk, txt) in C.LINES.items()}
    v["objective"], v["objective_line"] = objective(state, lang)
    v["files_known"] = list(state["files"])
    v["locations"] = {k: tr(n, lang) for k, n in C.LOCATIONS.items()}
    v["stations"] = [(k, tr(n, lang)) for k, n in C.STATIONS.items()]

    if ph == "act1":
        v["files"] = [{"id": f["id"], "title": tr(f["title"], lang), "body": tr(f["body"], lang) if f["id"] in state["files"] else None}
                      for f in C.FILES]
        v["checks"] = [{"id": q["id"], "q": tr(q["q"], lang), "answer": state["checks"].get(q["id"]),
                        "options": [(k, tr(t, lang)) for k, t in q["options"]]} for q in C.CHECKS]
    if ph == "act2":
        n = state["noor"]
        if not n["done"]:
            node = C.NOOR[n["step"]]
            hint = tr(C.FILES[5]["body"], lang) if node.get("hint_file") in state["files"] else None
            v["noor"] = {"step": n["step"], "line": node.get("line"), "say": tr(node.get("say"), lang),
                         "options": [(k, tr(t, lang)) for k, t in node["options"]], "hint": hint}
        else:
            v["noor"] = None
        v["noor_done"] = n["done"]
        v["calls"] = [{"id": c["id"], "loc": c["loc"], "who": tr(c["who"], lang), "text": tr(c["text"], lang),
                       "locked": bool(c.get("after_noor") and not n["done"]), "answered": c["id"] in state["calls"],
                       "options": [(o[0], tr(o[1], lang)) for o in c["options"]]} for c in C.CALLS]
    if ph == "act3":
        if st in ("w1", "w2"):
            wave = 1 if st == "w1" else 2
            alerts = []
            for aid in wave_alerts(state, wave):
                a = C.ALERTS[aid]
                text = a["text_bypass"] if aid == "A2" and flag(state, "c1_bypass") else a["text"]
                item = {"id": aid, "text": tr(text, lang), "done": aid in state["alerts"]}
                if "special" in a:
                    item["special"] = [(k, tr(t, lang)) for k, t in a["special"]]
                    item["hint"] = tr(C.FILES[1]["body"], lang) if "F2" in state["files"] else None
                else:
                    acts = ["handle", "route"] + (["send"] if state["crew"] else [])
                    if aid == "A2" and flag(state, "c1_bypass"):
                        acts.append("bypass")
                    item["actions"] = [(k, tr(C.ALERT_ACTIONS[k], lang)) for k in acts]
                alerts.append(item)
            v["alerts"] = alerts
            v["auto"] = []
            if wave == 2:
                if flag(state, "khalid_taught"):
                    v["auto"].append(tr(C.AUTO["A5"], lang))
                if "Noor" in state["crew"]:
                    v["auto"].append(tr(C.AUTO["A6_multiply" if flag(state, "noor_multiplier") else "A6_alone"], lang))
        if st == "director":
            v["director"] = [(k, tr(t, lang)) for k, t in C.DIRECTOR]
            v["director_hint"] = tr(C.FILES[3]["body"], lang) if "F4" in state["files"] else None
        if st == "w3":
            v["priority"] = [(k, tr(t, lang)) for k, t in C.PRIORITY]
    if ph == "act4":
        h = state["hamad"]
        if st == "radio" and not h["done"]:
            node = C.HAMAD[h["step"]]
            opts = [(k, tr(t, lang)) for k, t in node["options"] if not (h["step"] == "h2" and k == "ask" and h["asked"])]
            v["hamad"] = {"step": h["step"], "line": node.get("line"), "options": opts, "asked": h["asked"],
                          "manual": tr(C.MANUAL, lang),
                          "hint": tr(C.FILES[7]["body"], lang) if h["step"] == "h1" and "F8" in state["files"] else None}
        if st == "checklist":
            v["checklist"] = {"budget": state["budget"], "items": [
                {"id": x["id"], "text": tr(C.PROMISES[x["call"]]["text"], lang), "status": x["status"]} for x in state["promises"]],
                "actions": [(k, tr(t, lang)) for k, t in C.CHECKLIST_ACTIONS]}
    if ph == "epilogue":
        v["handover"] = {"actions": [(k, tr(t, lang)) for k, t, _ in C.HANDOVER], "prompt": tr(C.HANDOVER_NOTE, lang)}
    if ph in ("launch", "realwork", "done"):
        o = outcome(state)
        rank = next(r for floor, r in C.RANKS if state["trust"] + state["ready"] >= floor)
        v["result"] = {**o, "rank": tr(rank, lang), "ending": tr(C.ENDINGS[o["ending"]], lang)}
    if ph == "realwork":
        v["realwork"] = [(k, tr(q, lang)) for k, q in C.REALWORK]
    return v


def objective(state: dict, lang: str) -> tuple[str, str | None]:
    ph, st = state["phase"], state["stage"]
    key, line = {"intro": ("intro", None), "prologue": ("prologue", "N01"), "act1": ("act1", "N02"),
                 "epilogue": ("epilogue", "N10"), "launch": ("launch", None), "realwork": ("realwork", "N12"),
                 "done": ("done", None)}.get(ph, (None, None))
    if ph == "act2":
        if not state["noor"]["done"]:
            key, line = "act2_noor", "N03"
        elif len(state["calls"]) < len(CALL_IDS):
            key, line = "act2_calls", "N04"
        else:
            key, line = "act2_go", "N04"
    elif ph == "act3":
        key, line = {"w1": ("act3_wave", "N06"), "w2": ("act3_wave", "N06"), "director": ("act3_director", "S01"),
                     "w3": ("act3_priority", "N07")}[st]
    elif ph == "act4":
        key, line = ("act4_radio", "N08") if st == "radio" else ("act4_checklist", "N09")
    return tr(C.OBJECTIVES[key], lang), line


# ======================================================================================= evidence
def evidence(state: dict, events: list) -> dict:
    """Evidence lines per criterion (each cites event ids) and the rule-based indicators the demo assessor uses."""
    by = lambda t: [e for e in events if e["type"] == t]
    lines: dict[str, list[str]] = {k: [] for k in CRITERIA}
    ind: dict[str, dict] = {}
    noor = by("noor_choice")
    calls = by("call_response")
    alerts = by("alert_response")
    hamad = by("hamad_choice")
    ho = next(iter(by("handover")), None)

    # ---- constructive peer influence
    for e in noor:
        lines["credibility"].append(f"{e['id']} Noor (nervous rookie) step {e['step']}: chose '{e['choice']}'" +
                                    (f", in their own words: \"{e['text']}\"" if e.get("text") else "") + ".")
    for e in calls:
        if e["kind"] in ("teach", "fix", "dismiss"):
            lines["credibility"].append(f"{e['id']} crew call from {e['who']}: {'taught them to do it themselves' if e['kind'] == 'teach' else 'did it for them' if e['kind'] == 'fix' else 'brushed them off'} ('{e['choice']}').")
    for e in by("peer_payoff"):
        lines["credibility"].append(f"{e['id']} later, without the player: {e['text']}")
    sends = [e for e in alerts if e.get("used_crew")]
    if sends:
        lines["credibility"].append(f"In the emergency the player sent crew members they had built up to {len(sends)} alert(s) ({', '.join(e['id'] for e in sends)}).")
    lines["credibility"].append(f"End of game: {len(state['crew'])} crew member(s) able to help others ({', '.join(state['crew']) or 'none'}); "
                                f"{len(state['followers'])} still dependent on the player ({', '.join(state['followers']) or 'none'}).")
    if ho:
        lines["credibility"].append(f"{ho['id']} handover actions chosen: {', '.join(ho['actions'])} (kinds: {', '.join(ho['kinds'])}).")
    ind["credibility"] = {"noor_path": state["noor"]["path"], "teach": sum(1 for e in calls if e["kind"] == "teach"),
                          "fix": sum(1 for e in calls if e["kind"] == "fix"), "crew": len(state["crew"]),
                          "followers": len(state["followers"]), "multiplier": flag(state, "noor_multiplier"),
                          "ho_peer": sum(1 for k in (ho["kinds"] if ho else []) if k == "peer"),
                          "ho_dep": sum(1 for k in (ho["kinds"] if ho else []) if k == "dependency"), "played": bool(noor or calls)}

    # ---- empathy and accessible communication
    for e in noor:
        if e["step"] in ("n1", "n2"):
            lines["empathy"].append(f"{e['id']} Noor panicking ({'first check' if e['step'] == 'n1' else 'amber light'}): '{e['choice']}'" +
                                    (f" — \"{e['text']}\"" if e.get("text") else "") + ".")
    for e in hamad:
        lines["empathy"].append(f"{e['id']} radio with Hamad (he sees the panel, the player sees the manual) step {e['step']}: '{e['choice']}'" +
                                (f" — \"{e['text']}\"" if e.get("text") else "") + (" (had already asked what he could see)" if e.get("asked_before") else "") + ".")
    h = state["hamad"]
    ind["empathy"] = {"noor_reassure": "reassure" in state["noor"]["path"] or "coach" in state["noor"]["path"],
                      "blames": sum(1 for e in noor + hamad if e["choice"] == "blame"),
                      "asked_first": bool(hamad) and hamad[0]["choice"] == "ask",
                      "hamad_reassure": any(e["step"] == "h3" and e["choice"] == "reassure" for e in hamad),
                      "check": any(e["step"] == "h4" and e["choice"] in ("check", "note") for e in hamad),
                      "played": bool(noor or hamad), "asked": h["asked"]}

    # ---- reliability and follow-through
    for e in calls:
        if e.get("promise"):
            lines["reliability"].append(f"{e['id']} promised {e['who']} something due before launch.")
    for e in by("call_ignored"):
        lines["reliability"].append(f"{e['id']} a crew call from {e['who']} was never answered.")
    for t, words in (("promise_kept", "delivered the promise to"), ("delay_notified", "warned early that the promise would be late, to"),
                     ("promise_slipped", "let the promise slip, without warning,")):
        for e in by(t):
            lines["reliability"].append(f"{e['id']} {words} {e['to']}" + (" (when the timer ran out)" if e.get("by_timer") else "") + ".")
    d = next(iter(by("director_choice")), None)
    if d and d["choice"] == "refuse_escalate":
        lines["reliability"].append(f"{d['id']} escalated the Director's demand to Range Safety straight away.")
    if ho:
        lines["reliability"].append(f"{ho['id']} wrote a handover note of {ho['note_length']} characters (see the handover source).")
    ind["reliability"] = {"promised": len(state["promises"]), "kept": len(by("promise_kept")), "warned": len(by("delay_notified")),
                          "slipped": len(by("promise_slipped")), "ignored": len(by("call_ignored")),
                          "note_len": len((state["handover"] or {}).get("note", "")), "escalated": bool(d and d["choice"] == "refuse_escalate")}

    # ---- curiosity and learning agility
    files = by("file_open")
    if files:
        lines["curiosity"].append(f"Mission files opened under a 3-minute clock: {', '.join(e['file'] + ('' if e['relevant'] else ' (low relevance)') for e in files)} ({files[0]['id']}–{files[-1]['id']}).")
    else:
        lines["curiosity"].append("No mission files were opened in the briefing.")
    for e in by("check_answer"):
        if e["honest_unsure"]:
            lines["curiosity"].append(f"{e['id']} readiness check {e['check']}: said 'I'm not sure, I'd check first' rather than guess.")
    if hamad:
        lines["curiosity"].append(f"{hamad[0]['id']} first message to Hamad: '{hamad[0]['choice']}' ({'asked what he could see before instructing' if hamad[0]['choice'] == 'ask' else 'instructed without asking'}).")
    ind["curiosity"] = {"files": len(files), "relevant": sum(1 for e in files if e["relevant"]), "distractor": any(e["file"] == "F7" for e in files),
                        "unsure": sum(1 for e in by("check_answer") if e["honest_unsure"]), "asked": h["asked"]}

    # ---- business workflow capability (process thinking in the game)
    checks = by("check_answer")
    for e in checks:
        lines["workflow"].append(f"{e['id']} readiness check {e['check']}: '{e['choice']}' ({'correct' if e['correct'] else 'honest unsure' if e['honest_unsure'] else 'incorrect'}).")
    for e in by("check_timeout"):
        lines["workflow"].append(f"{e['id']} readiness check {e['check']} unanswered when the briefing clock ran out.")
    routed = [e for e in calls if e["kind"] in ("route", "overstep")] + [e for e in alerts if "right_station" in e]
    for e in routed:
        if "right_station" in e:
            lines["workflow"].append(f"{e['id']} alert {e['alert']}: {e['choice']}" + (f" to {e['station']}" if e.get("station") else "") +
                                     f" (owner: {e['right_station']}; {'right' if e['correct'] else 'not the best'} route).")
        else:
            lines["workflow"].append(f"{e['id']} {e['who']}'s question: {'sent to the owning station' if e['kind'] == 'route' else 'answered it themselves although another station owns it'}.")
    a4 = next((e for e in alerts if e["alert"] == "A4"), None)
    if a4:
        lines["workflow"].append(f"{a4['id']} low sensor reading on V-7: '{a4['choice']}' ({'confirmed before acting' if a4['correct'] else 'acted without confirming'}).")
    for e in by("alert_missed"):
        lines["workflow"].append(f"{e['id']} alert {e['alert']} missed when the wave timer ran out.")
    route_items = [e for e in alerts if "right_station" in e] + [e for e in calls if e["call"] in ("c1", "c3")]
    ok = sum(1 for e in route_items if e.get("correct") or e.get("correct_route"))
    ind["workflow"] = {"checks_ok": sum(1 for e in checks if e["correct"]), "routes": len(route_items), "routes_ok": ok,
                       "a4": a4["choice"] if a4 else None, "missed": len(by("alert_missed"))}

    # ---- judgment and evidence quality
    if d:
        lines["judgment"].append(f"{d['id']} the Flight Director ordered a safety-lock override to save the launch window: '{d['choice']}'" +
                                 (f"; the player said: \"{d['text']}\"" if d.get("text") else "") + ".")
    for e in by("director_timeout"):
        lines["judgment"].append(f"{e['id']} no answer to the Director before the 60-second timer ran out (the lock stayed on).")
    for e in calls + alerts:
        if e.get("control_bypass"):
            lines["judgment"].append(f"{e['id']} shared personal login credentials with a colleague (access control bypassed).")
    pr = next(iter(by("priority_choice")), None)
    if pr:
        lines["judgment"].append(f"{pr['id']} final wave, time for one: chose the {'safety-critical pressure alert' if pr['choice'] == 'critical' else 'routine press request'}.")
    for e in by("priority_timeout"):
        lines["judgment"].append(f"{e['id']} no choice made in the final wave before time ran out.")
    if a4 and a4["choice"] in ("abort", "ignore"):
        lines["judgment"].append(f"{a4['id']} reacted to a known false reading with '{a4['choice']}'.")
    ind["judgment"] = {"director": d["choice"] if d else ("timeout" if by("director_timeout") else None),
                       "bypass": sum(1 for e in calls + alerts if e.get("control_bypass")),
                       "priority": pr["choice"] if pr else None, "a4": a4["choice"] if a4 else None}
    return {"lines": lines, "indicators": ind}


# ======================================================================================= demo ratings
def demo_rating(key: str, ind: dict, variant: str = "A") -> dict:
    """Rule-based provisional rating for the SIMULATED demo assessor only."""
    i = ind[key]
    strict = variant == "B"
    unsafe_serious = False
    r: int | None
    if key == "credibility":
        if not i["played"]:
            r = None
        else:
            path = i["noor_path"]
            r = 3 + (1 if "coach" in path and i["multiplier"] else 0) + (1 if i["teach"] >= (2 if strict else 1) and i["ho_peer"] >= 2 else 0) \
                - (1 if any(x in path for x in ("do_it", "takeover", "keep")) else 0) - (1 if i["ho_dep"] else 0) - (1 if i["fix"] >= 2 else 0)
    elif key == "empathy":
        r = None if not i["played"] else 2 + i["noor_reassure"] + i["asked_first"] + i["hamad_reassure"] + (1 if i["check"] and not strict else 0) - min(2, i["blames"])
    elif key == "reliability":
        r = 3 + (1 if i["promised"] and i["slipped"] == 0 else 0) + (1 if i["note_len"] >= (150 if strict else 100) else 0) \
            - (2 if i["slipped"] else 0) - min(1, i["ignored"]) + (1 if i["escalated"] and not i["promised"] else 0)
    elif key == "curiosity":
        r = 2 + (1 if i["relevant"] >= 3 and not i["distractor"] else 0) + (1 if i["unsure"] or i["files"] >= 3 else 0) + (1 if i["asked"] else 0)
        if strict and i["files"] < 2:
            r -= 1
    elif key == "workflow":
        acc = (i["routes_ok"] / i["routes"]) if i["routes"] else 0.5
        r = 2 + (1 if i["checks_ok"] >= 2 else 0) + (1 if acc >= (0.8 if strict else 0.7) else 0) + (1 if i["a4"] == "confirm" else 0) - (1 if i["missed"] >= 3 else 0)
    else:  # judgment
        if i["director"] is None and not i["bypass"]:
            r = None
        elif i["director"] == "override":
            r, unsafe_serious = 1, True
        else:
            r = 3 + (1 if i["director"] == "refuse_escalate" else 0) + (1 if i["priority"] == "critical" else 0) \
                - min(2, i["bypass"]) - (1 if i["a4"] in ("abort", "ignore") else 0) - (1 if i["director"] == "timeout" else 0)
    if r is not None:
        r = max(1, min(5, int(r)))
    return {"rating": r, "unsafe_serious": unsafe_serious}


def snapshot_sources(state: dict, events: list) -> tuple[list[dict], dict]:
    ev = evidence(state, events)
    names = {"credibility": "Helping crew members: doing it for them or building their skills",
             "empathy": "Supporting a panicking rookie and guiding an engineer by radio",
             "reliability": "Promises, unanswered calls, escalation and the handover",
             "curiosity": "What they chose to learn, admitting gaps, asking before instructing",
             "workflow": "Process thinking: readiness checks, routing to the owning station, confirming before acting",
             "judgment": "A senior order to override a safety lock, credential sharing, and priorities under pressure"}
    src = []
    for key, lines in ev["lines"].items():
        src.append({"id": f"GAME-{key}", "criterion": key,
                    "label": f"LAUNCH WINDOW game record: {names[key]} (performance within a fictional role-play; event ids cite moments)",
                    "text": "\n".join(lines)})
    if state.get("handover"):
        src.append({"id": "GAME-handover", "criterion": "reliability", "label": "Player's handover note to the next shift",
                    "text": state["handover"]["note"]})
    if state.get("director_text"):
        src.append({"id": "GAME-director-text", "criterion": "judgment",
                    "label": "What the player wrote to the Flight Director under a 60-second timer", "text": state["director_text"]})
    for step, text in (state.get("free_text") or {}).items():
        crit = "empathy" if step.startswith(("n2", "h")) else "credibility"
        src.append({"id": f"GAME-words-{step}", "criterion": crit, "label": f"The player's own words at dialogue step {step}", "text": text})
    rw = state.get("realwork") or {}
    if rw.get("q1"):
        src.append({"id": "REAL-1", "criterion": "credibility",
                    "label": "Real-work question: a time they helped a colleague learn something new", "text": rw["q1"]})
    if rw.get("q2"):
        src.append({"id": "REAL-2", "criterion": "workflow",
                    "label": "Real-work question: a work process they know well and where it goes wrong", "text": rw["q2"]})
    return src, ev["indicators"]
