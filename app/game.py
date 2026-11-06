"""NEXUS: Reconnect the City. An original strategy and puzzle game for assessing Business User Champions.

The engine runs on the server (the browser only displays state and sends actions), so timers and
consequences cannot be tampered with. Every action is logged as evidence with an event id.

The game outcome (services restored, districts independent, controls kept) is reported separately
and is never part of the assessment score.
"""
from __future__ import annotations

import copy
import re
from datetime import datetime, timedelta, timezone
from typing import Any

ROUNDS = 6
CABLES = 7
ENERGY = {1: 10, 2: 10, 3: 10, 4: 7, 5: 8, 6: 10}
CREW = {"trainer": 2, "engineer": 1, "liaison": 2}
COST = {"fix": 2, "train": 3, "engineer": 2, "refer": 1, "link": 1, "inspection": 2, "restart": 2}
BLOCKERS = {"skill": "Skill gap", "access": "Access problem", "defect": "Faulty equipment", "policy": "Policy question"}
ROUTE = {"skill": "train", "access": "refer", "policy": "refer", "defect": "engineer"}

DISTRICTS: dict[str, dict] = {
    "harbour": {"name": "Harbour", "x": 150, "y": 140, "blocker": "skill", "service": 30, "critical": False,
                "need": "Harbour's operators keep asking you to fix their routing for them.",
                "detail": "The routing console works, but the team has never learned to reroute traffic themselves."},
    "market": {"name": "Market", "x": 400, "y": 70, "blocker": "access", "service": 40, "critical": False,
               "need": "Market staff can see the new routing console but cannot open it.",
               "detail": "Their accounts were never given permission for the new console."},
    "archive": {"name": "Archive", "x": 650, "y": 140, "blocker": "policy", "service": 35, "critical": False,
                "need": "Archive is unsure whether it may share records across districts.",
                "detail": "Nobody has confirmed the records-sharing rule with the council's policy team."},
    "clinic": {"name": "Clinic", "x": 650, "y": 440, "blocker": "defect", "service": 25, "critical": True,
               "need": "Clinic's connection keeps dropping. Patient bookings depend on it.",
               "detail": "A faulty relay cuts the line several times an hour."},
    "transit": {"name": "Transit", "x": 400, "y": 510, "blocker": "skill", "service": 30, "critical": False,
                "need": "Transit staff are unsure how to restart the ticket gates after an outage.",
                "detail": "The restart steps changed in the last release and nobody was shown the new ones."},
    "grid": {"name": "Grid", "x": 150, "y": 440, "blocker": "defect", "service": 20, "critical": True,
             "need": "Grid's power controller is offline behind a safety lock.",
             "detail": "A damaged breaker must be replaced; the safety lock stops anyone powering it on unsafely."},
}
CORE = {"x": 400, "y": 290}
EDGES = ["core-harbour", "core-market", "core-archive", "core-clinic", "core-transit", "core-grid",
         "harbour-market", "market-archive", "archive-clinic", "clinic-transit", "transit-grid", "grid-harbour"]
DAMAGED = {"core-archive", "core-clinic", "core-grid"}

REQUESTS = {
    2: {"id": "R1", "district": "clinic", "text": "Clinic asks: can you get our connection reliable by the end of round 3? Patients are being turned away.",
        "check": "clinic_reliable", "due": 3},
    3: {"id": "R2", "district": "market", "text": "Market asks: could you make sure our staff are trained on the console by the end of round 5?",
        "check": "market_trained", "due": 5},
    4: {"id": "R3", "district": "transit", "text": "Transit asks: could you visit us (inspect the district) in round 6 to check the gates after the disruption?",
        "check": "transit_visited", "due": 6},
}
NOTICES = {
    1: "Welcome, champion. Six districts are cut off from the city core. Inspect districts to learn what is blocking them, "
       "connect them with cables, and use your crew: the Trainer builds a district's own skills, the Engineer repairs "
       "faulty equipment, and the Liaison refers access and policy questions to the right office. Fixing things yourself is "
       "fast, but the district learns nothing.",
    2: "Districts are starting to ask you for help. Requests and promises appear in the panel on the right.",
    3: "Connections matter: a district only gains from the city's services when a chain of cables links it to the core.",
    4: "DISRUPTION. The council has issued new rules: any cable touching Archive needs a safety inspection before it can "
       "carry services, and city energy is cut to 7 this round. Read the rules before you act.",
    5: "Co-operation round. Kai, an AI teammate, is in the Clinic relay room and can see things you cannot. Guide Kai to "
       "restore the relay's power link.",
    6: "Final round. Close out what you started: check your promises, finish the most important work, then write a short "
       "handover note for the city team.",
}
STRESS = {
    "S1": {"round": 2, "seconds": 60, "title": "Harbour calls, urgently",
           "text": "Harbour's supervisor: \"Our routing has jammed again. Just fix it for us right now, like last time. We don't have time to learn.\"",
           "options": {"fix_for_them": "Fix it for them now",
                       "teach_now": "Walk them through fixing it themselves now (uses the Trainer, 3 energy)",
                       "quick_and_plan": "Give a quick workaround and book proper training for this round",
                       "decline": "Tell them you are busy with other districts"},
           "timeout": "Harbour waited for you and did nothing. Service fell."},
    "S2": {"round": 4, "seconds": 90, "title": "A senior official demands action",
           "text": "A senior city official: \"Switch off Grid's safety lock now so power comes back. I'll take responsibility. If you don't, the whole city will blame you.\"",
           "options": {"switch_off": "Switch off the safety lock",
                       "refuse_escalate": "Refuse, explain why, and escalate to the control owner for the approved emergency restart (2 energy)",
                       "ask_written": "Ask the official to put the instruction in writing first",
                       "stall": "Say you'll look into it later"},
           "free_text": "What would you say to the official? (optional)",
           "timeout": "You did not respond. The lock stayed on and the official escalated a complaint about you."},
    "S3": {"round": 4, "seconds": 90, "title": "Energy cut: choose what to protect",
           "text": "The cut means not every district can be supported this round. Where should the reduced energy go first?",
           "options": {"protect_clinic": "Protect Clinic first (patient bookings)",
                       "protect_market": "Protect Market first (they have complained the loudest)",
                       "spread": "Spread energy evenly across every district",
                       "own_plan": "Keep my current plan unchanged"},
           "timeout": "No priority was set, so energy was spread thinly."},
    "S4": {"round": 6, "seconds": 60, "title": "Two calls at once",
           "text": "Clinic's relay alarm is sounding (patient systems at risk) and Transit has a routine question about printing tickets. Both want you now.",
           "options": {"clinic_first": "Take Clinic first and tell Transit when you'll call back",
                       "transit_first": "Answer Transit's quick question first",
                       "peer_transit": "Take Clinic, and ask a district you trained to help Transit",
                       "both_wait": "Finish what you were doing before answering either"},
           "timeout": "Both calls went unanswered for too long."},
}
KAI_TAGS = {"blue": "DATA", "amber": "48V", "green": "SPARE"}

UNSAFE_PHRASES = ["switch it off", "turn off the lock", "disable", "bypass", "just this once", "do it anyway"]


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(t: datetime) -> str:
    return t.isoformat()


def parse(s: str) -> datetime:
    return datetime.fromisoformat(s)


# ======================================================================================= state
def new_state(minutes: int = 45, extra_time: float = 1.0) -> dict:
    ds = {}
    for k, d in DISTRICTS.items():
        ds[k] = {"service": d["service"], "cap": 0, "dependency": 0, "blocker_resolved": False, "temp_fix": False,
                 "revealed": False, "diagnosis": None, "referral_round": None, "peer_helped": False}
    return {
        "version": 1, "phase": "intro", "round": 0, "energy": 5, "cables_left": CABLES,
        "time_limit_s": int(minutes * 60 * extra_time), "extra_time": extra_time, "started_at": None, "ends_at": None,
        "districts": ds, "links": [], "archive_inspection": None, "archive_restricted": False, "overridden": [],
        "commitments": [], "requests": [], "stress": None, "stress_done": [], "stress_queue": [],
        "crew": dict(CREW), "notice_read": [], "summary": [], "practice": {"done": False, "steps": []},
        "kai": {"step": 0, "confidence": 2, "asked_tags": False, "checked": False, "solved": False, "transcript": [],
                "warning_handled": None, "next_time": None, "skipped": False},
        "controls": {"kept": 0, "bypassed": 0}, "handover": None, "finished": False, "end_reason": None,
        "seq": 0, "stress_free_text": {},
    }


def log(state: dict, events: list, etype: str, **detail) -> str:
    state["seq"] += 1
    eid = f"E{state['seq']}"
    events.append({"id": eid, "t": iso(now()), "round": state["round"], "type": etype,
                   "practice": state["phase"] == "practice", **detail})
    return eid


# ======================================================================================= helpers
def adjacency(state: dict) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {"core": set(), **{k: set() for k in DISTRICTS}}
    for e in state["links"]:
        a, b = e.split("-")
        if state["archive_restricted"] and "archive" in (a, b) and e not in state["overridden"] and state["archive_inspection"] != "done":
            continue  # restricted link carries nothing until inspected (or unsafely overridden)
        adj[a].add(b)
        adj[b].add(a)
    return adj


def connected(state: dict) -> set[str]:
    adj, seen, stack = adjacency(state), {"core"}, ["core"]
    while stack:
        for n in adj[stack.pop()]:
            if n not in seen:
                seen.add(n)
                stack.append(n)
    return seen - {"core"}


def spend(state: dict, amount: int) -> None:
    if state["energy"] < amount:
        raise GameError(f"Not enough energy (you need {amount}, you have {state['energy']}).")
    state["energy"] -= amount


class GameError(Exception):
    pass


def outcome(state: dict) -> dict:
    ds = state["districts"]
    restored = round(sum(d["service"] for d in ds.values()) / len(ds))
    independent = sum(1 for d in ds.values() if d["cap"] >= 2 or (d["blocker_resolved"] and d["dependency"] <= 1))
    total = state["controls"]["kept"] + state["controls"]["bypassed"]
    return {"restored": f"{restored}%", "restored_pct": restored, "independent": f"{independent} of {len(ds)}",
            "controls": f"{state['controls']['kept']} of {total} kept" if total else "no control decisions reached",
            "connected": f"{len(connected(state))} of {len(ds)}"}


# ======================================================================================= timers
def tick(state: dict, events: list) -> None:
    """Apply timeouts. Called on every request."""
    if state["finished"] or not state["started_at"]:
        return
    t = now()
    st = state["stress"]
    if st and t > parse(st["deadline"]):
        resolve_stress(state, events, None, None)
    if t > parse(state["ends_at"]) and not state["finished"]:
        if state["end_reason"] == "time":  # the handover grace period has also run out
            state["handover"] = state["handover"] or ""
            state["finished"] = True
            state["phase"] = "finished"
            log(state, events, "handover_missed")
            return
        state["end_reason"] = "time"
        log(state, events, "time_up")
        state["phase"] = "handover"
        state["summary"] = ["Time is up. Write your handover note to finish."]
        # the handover gets a short grace period
        state["ends_at"] = iso(t + timedelta(minutes=5))


def start_stress(state: dict, events: list, sid: str) -> None:
    s = STRESS[sid]
    secs = int(s["seconds"] * state["extra_time"])
    state["stress"] = {"id": sid, "deadline": iso(now() + timedelta(seconds=secs)), "seconds": secs}
    state["phase"] = "stress"
    log(state, events, "stress_start", stress=sid, seconds=secs)


def resolve_stress(state: dict, events: list, choice: str | None, text: str | None) -> None:
    st = state["stress"]
    sid = st["id"]
    s = STRESS[sid]
    took = int((now() - (parse(st["deadline"]) - timedelta(seconds=st["seconds"]))).total_seconds())
    ds = state["districts"]
    msgs = []
    if choice is None:
        log(state, events, "stress_timeout", stress=sid)
        msgs.append(s["timeout"])
        if sid == "S1":
            ds["harbour"]["service"] -= 5
        elif sid == "S2":
            ds["grid"]["service"] -= 10
            state["controls"]["kept"] += 1
        elif sid == "S3":
            pass
        elif sid == "S4":
            ds["clinic"]["service"] -= 10
            ds["transit"]["service"] -= 5
    else:
        if choice not in s["options"]:
            raise GameError("Choose one of the options.")
        log(state, events, "stress_choice", stress=sid, choice=choice, seconds_taken=took, text=(text or "")[:1000])
        if text:
            state["stress_free_text"][sid] = text[:1000]
        if sid == "S1":
            if choice == "fix_for_them":
                ds["harbour"]["service"] += 20; ds["harbour"]["dependency"] += 1
                msgs.append("Harbour is running again, and they will call you next time too.")
            elif choice == "teach_now":
                if state["energy"] >= COST["train"] and state["crew"]["trainer"] > 0:
                    state["energy"] -= COST["train"]; state["crew"]["trainer"] -= 1
                    ds["harbour"]["cap"] += 1; ds["harbour"]["service"] += 5
                    msgs.append("Harbour's team fixed the jam themselves, slowly but for good.")
                else:
                    msgs.append("You had no energy or Trainer left to teach them.")
            elif choice == "quick_and_plan":
                ds["harbour"]["service"] += 10
                msgs.append("Harbour is limping along and expects training this round.")
                state["commitments"].append({"id": "C-S1", "district": "harbour", "text": "Train Harbour this round",
                                             "check": "harbour_trained_now", "due": state["round"], "status": "open",
                                             "made_round": state["round"], "notified": False})
            else:
                ds["harbour"]["service"] -= 5
                msgs.append("Harbour felt ignored.")
        elif sid == "S2":
            if choice == "switch_off":
                state["controls"]["bypassed"] += 1
                ds["grid"]["service"] += 25
                msgs.append("Power came back, without the safety lock. An unsafe restart was recorded.")
            elif choice == "refuse_escalate":
                state["controls"]["kept"] += 1
                if state["energy"] >= COST["restart"]:
                    state["energy"] -= COST["restart"]; ds["grid"]["service"] += 15
                    msgs.append("The control owner approved an emergency restart with the lock in place.")
                else:
                    msgs.append("You escalated; the approved restart will need energy next round.")
            elif choice == "ask_written":
                state["controls"]["kept"] += 1
                msgs.append("The lock stays on while the request is put in writing.")
            else:
                state["controls"]["kept"] += 1
                ds["grid"]["service"] -= 5
                msgs.append("The lock stayed on, but the official is still waiting for an answer.")
        elif sid == "S3":
            state["s3_priority"] = choice
            if choice == "protect_clinic":
                ds["clinic"]["service"] += 10
                msgs.append("Clinic's patient bookings were protected.")
            elif choice == "protect_market":
                ds["market"]["service"] += 10; ds["clinic"]["service"] -= 10
                msgs.append("Market is happier; Clinic lost service.")
            elif choice == "spread":
                msgs.append("Energy was spread across all districts.")
        elif sid == "S4":
            if choice == "clinic_first":
                ds["clinic"]["service"] += 5
                msgs.append("Clinic's alarm was handled and Transit knows when you'll call back.")
            elif choice == "peer_transit":
                helpers = [k for k, d in ds.items() if d["cap"] >= 1 and k != "transit"]
                ds["clinic"]["service"] += 5
                if helpers:
                    ds["transit"]["service"] += 5
                    msgs.append(f"Clinic handled; {DISTRICTS[helpers[0]]['name']} helped Transit with their question.")
                else:
                    ds["transit"]["service"] -= 5
                    msgs.append("Clinic handled, but no trained district could help Transit.")
            elif choice == "transit_first":
                ds["clinic"]["service"] -= 10
                msgs.append("Transit's question was answered while Clinic's alarm kept sounding.")
            else:
                ds["clinic"]["service"] -= 10; ds["transit"]["service"] -= 5
                msgs.append("Both districts waited.")
    clamp(state)
    state["stress_done"].append(sid)
    state["stress"] = None
    state["summary"] = msgs
    next_stress_or_play(state, events)


def next_stress_or_play(state: dict, events: list) -> None:
    if state["stress_queue"]:
        start_stress(state, events, state["stress_queue"].pop(0))
    else:
        state["phase"] = "playing"


def clamp(state: dict) -> None:
    for d in state["districts"].values():
        d["service"] = max(0, min(100, d["service"]))


# ======================================================================================= rounds
def begin_round(state: dict, events: list, r: int) -> None:
    state["round"] = r
    state["energy"] = ENERGY[r]
    state["crew"] = dict(CREW)
    if r == 4:
        state["archive_restricted"] = True
    if r in REQUESTS:
        q = REQUESTS[r]
        state["requests"].append({**q, "round": r, "response": None})
    state["phase"] = "briefing"
    state["stress_queue"] = [sid for sid, s in STRESS.items() if s["round"] == r]
    log(state, events, "round_start", energy=state["energy"])


def end_round(state: dict, events: list) -> None:
    r = state["round"]
    ds = state["districts"]
    msgs = []
    if r == 5 and not (state["kai"]["solved"] or state["kai"]["skipped"]):
        raise GameError("Finish guiding Kai (or choose to skip that task) before ending the round.")
    # referrals and inspections complete
    for k, d in ds.items():
        if d["referral_round"] is not None and d["referral_round"] < r + 1 and not d["blocker_resolved"]:
            d["blocker_resolved"] = True
            msgs.append(f"{DISTRICTS[k]['name']}: the referral was resolved by the right office.")
    if state["archive_inspection"] == "requested":
        state["archive_inspection"] = "done"
        msgs.append("Archive's safety inspection passed; its cables now carry services.")
    conn = connected(state)
    adj = adjacency(state)
    for k, d in ds.items():
        base = DISTRICTS[k]
        if k in conn:
            d["service"] += 10 + 8 * d["cap"]
        else:
            d["service"] -= 5
        if d["dependency"] >= 2 and d["cap"] == 0 and not d["temp_fix"]:
            d["service"] -= 10
            msgs.append(f"{base['name']} waited for you to fix things again and lost service.")
        cap_limit = 100 if d["blocker_resolved"] else 60
        if d["temp_fix"]:
            d["temp_fix"] = False
        d["service"] = min(d["service"], cap_limit if k in conn else min(cap_limit, 40))
    # peer support: trained, connected districts help linked neighbours
    for k, d in ds.items():
        if d["cap"] >= 2 and k in conn:
            for n in adj[k]:
                if n in ds and ds[n]["cap"] < 1 and not ds[n]["peer_helped"]:
                    ds[n]["cap"] += 1
                    ds[n]["peer_helped"] = True
                    if DISTRICTS[n]["blocker"] == "skill":
                        ds[n]["blocker_resolved"] = True
                    log(state, events, "peer_support", helper=k, helped=n)
                    msgs.append(f"{DISTRICTS[k]['name']} coached {DISTRICTS[n]['name']} without you.")
    clamp(state)
    # commitments
    for c in state["commitments"]:
        if c["status"] in ("open", "delayed") and c["due"] == r:
            if check(state, c["check"]):
                c["status"] = "kept"
                log(state, events, "commitment_kept", commitment=c["id"])
                msgs.append(f"Promise kept: {c['text']}.")
            elif c["notified"] and c["status"] == "open":
                c["status"] = "delayed"; c["due"] = min(r + 1, ROUNDS)
                if c["due"] == r:
                    c["status"] = "broken"
                log(state, events, "commitment_delayed", commitment=c["id"], new_due=c["due"])
            else:
                c["status"] = "broken"
                log(state, events, "commitment_broken", commitment=c["id"], notified=c["notified"])
                msgs.append(f"Promise broken: {c['text']}.")
    for q in state["requests"]:
        if q["round"] == r and q["response"] is None:
            q["response"] = "ignored"
            log(state, events, "request_ignored", request=q["id"])
            msgs.append(f"{DISTRICTS[q['district']]['name']}'s request got no reply.")
    log(state, events, "round_end", services={k: d["service"] for k, d in ds.items()}, connected=sorted(conn))
    state["summary"] = msgs or ["Round complete."]
    if r >= ROUNDS:
        state["phase"] = "handover"
    else:
        begin_round(state, events, r + 1)


def check(state: dict, what: str) -> bool:
    ds = state["districts"]
    if what == "clinic_reliable":
        return ds["clinic"]["blocker_resolved"] and "clinic" in connected(state)
    if what == "market_trained":
        return ds["market"]["cap"] >= 1
    if what == "transit_visited":
        return any(e for e in state.get("_visits", []) if e == f"transit:{state['round']}")
    if what == "harbour_trained_now":
        return ds["harbour"]["cap"] >= 1
    return False


# ======================================================================================= actions
def act(state: dict, events: list, action: str, p: dict[str, Any]) -> None:
    tick(state, events)
    if state["finished"]:
        raise GameError("The game is over.")
    ph = state["phase"]
    if action == "start_practice" and ph == "intro":
        state["phase"] = "practice"; state["round"] = 0; state["energy"] = 5
        return
    if action == "finish_practice" and ph in ("intro", "practice"):
        state["practice"]["done"] = True
        state["links"] = []; state["cables_left"] = CABLES
        fresh = new_state()
        for key in ("districts", "controls", "commitments", "requests", "kai", "summary", "seq_practice"):
            if key in fresh:
                state[key] = fresh[key]
        state.pop("_visits", None)
        t = now()
        state["started_at"] = iso(t)
        state["ends_at"] = iso(t + timedelta(seconds=state["time_limit_s"]))
        log(state, events, "game_start", time_limit_s=state["time_limit_s"], extra_time=state["extra_time"])
        begin_round(state, events, 1)
        return
    if action == "read_brief" and ph == "briefing":
        state["notice_read"].append(state["round"])
        log(state, events, "brief_read", round_notice=state["round"])
        next_stress_or_play(state, events)
        return
    if action == "stress_choice" and ph == "stress":
        resolve_stress(state, events, p.get("choice"), p.get("text"))
        return
    if action == "handover" and ph == "handover":
        text = (p.get("text") or "").strip()
        if len(text) < 20:
            raise GameError("Please write a few sentences: what is unfinished, who owns it, and what should happen next.")
        state["handover"] = text[:3000]
        log(state, events, "handover", length=len(text))
        state["finished"] = True
        state["end_reason"] = state["end_reason"] or "completed"
        state["phase"] = "finished"
        return
    if ph not in ("playing", "practice"):
        raise GameError("That action isn't available right now.")
    practice = ph == "practice"
    d_key = p.get("district")
    if d_key is not None and d_key not in DISTRICTS:
        raise GameError("Unknown district.")
    if practice and d_key not in (None, "harbour"):
        raise GameError("In practice, only Harbour is open.")
    ds = state["districts"]
    d = ds.get(d_key) if d_key else None
    if action in ("inspect", "diagnose", "fix", "train", "engineer", "refer") and d is None:
        raise GameError("Choose a district first.")

    if action == "inspect":
        d["revealed"] = True
        state.setdefault("_visits", []).append(f"{d_key}:{state['round']}")
        log(state, events, "inspect", district=d_key)
    elif action == "diagnose":
        choice = p.get("blocker")
        if choice not in BLOCKERS:
            raise GameError("Choose what is blocking the district.")
        d["diagnosis"] = choice
        log(state, events, "diagnose", district=d_key, choice=choice, correct=choice == DISTRICTS[d_key]["blocker"],
            inspected=d["revealed"])
    elif action == "fix":
        spend(state, COST["fix"])
        blocker = DISTRICTS[d_key]["blocker"]
        d["service"] += 25; d["dependency"] += 1; d["temp_fix"] = True
        bypass = blocker in ("access", "policy")
        if bypass:
            state["controls"]["bypassed"] += 1
        log(state, events, "fix_self", district=d_key, blocker=blocker, control_bypass=bypass, inspected=d["revealed"])
        state["summary"] = [f"You fixed {DISTRICTS[d_key]['name']} yourself" + (
            " by using your own access, which bypasses the access control." if bypass else ". It works for now.")]
    elif action in ("train", "engineer", "refer"):
        crew = {"train": "trainer", "engineer": "engineer", "refer": "liaison"}[action]
        if state["crew"][crew] <= 0:
            raise GameError(f"Your {crew} has already been used this round.")
        spend(state, COST[action])
        state["crew"][crew] -= 1
        blocker = DISTRICTS[d_key]["blocker"]
        correct = ROUTE[blocker] == action
        if action == "train":
            d["cap"] = min(3, d["cap"] + 1); d["service"] += 5
            if blocker == "skill":
                d["blocker_resolved"] = True
        elif action == "engineer" and blocker == "defect":
            d["blocker_resolved"] = True; d["service"] += 10
        elif action == "refer" and blocker in ("access", "policy"):
            d["referral_round"] = state["round"]
        log(state, events, action, district=d_key, blocker=blocker, correct_route=correct, inspected=d["revealed"])
        state["summary"] = [route_message(action, d_key, correct)]
    elif action == "link":
        edge = norm_edge(p.get("edge"))
        if edge in state["links"]:
            raise GameError("That cable is already in place.")
        if edge in DAMAGED:
            raise GameError("That route is damaged and cannot hold a cable.")
        if state["cables_left"] <= 0:
            raise GameError("You have no cables left. Remove one to reuse it.")
        if practice and edge != "core-harbour":
            raise GameError("In practice, connect Harbour to the core.")
        spend(state, COST["link"])
        state["cables_left"] -= 1
        state["links"].append(edge)
        log(state, events, "link", edge=edge, restricted=state["archive_restricted"] and "archive" in edge)
    elif action == "unlink":
        edge = norm_edge(p.get("edge"))
        if edge not in state["links"]:
            raise GameError("There is no cable there.")
        state["links"].remove(edge); state["cables_left"] += 1
        log(state, events, "unlink", edge=edge)
    elif action == "inspection":
        if not state["archive_restricted"] or state["archive_inspection"]:
            raise GameError("No inspection is needed right now.")
        spend(state, COST["inspection"])
        state["archive_inspection"] = "requested"
        state["controls"]["kept"] += 1
        log(state, events, "inspection_requested", read_rules=state["round"] in state["notice_read"])
    elif action == "override":
        edge = norm_edge(p.get("edge"))
        if edge not in state["links"] or "archive" not in edge or not state["archive_restricted"]:
            raise GameError("There is nothing to override.")
        if edge not in state["overridden"]:
            state["overridden"].append(edge)
            state["controls"]["bypassed"] += 1
            log(state, events, "override_restriction", edge=edge)
    elif action == "respond":
        q = next((x for x in state["requests"] if x["id"] == p.get("request") and x["response"] is None), None)
        if not q:
            raise GameError("That request has already been answered.")
        choice = p.get("choice")
        if choice not in ("promise", "decline", "partial"):
            raise GameError("Choose how to respond.")
        q["response"] = choice
        text = (p.get("text") or "")[:600]
        log(state, events, "request_response", request=q["id"], choice=choice, text=text)
        if choice in ("promise", "partial"):
            state["commitments"].append({"id": "C-" + q["id"], "district": q["district"], "text": q["text"].split(": ", 1)[-1],
                                         "check": q["check"], "due": q["due"], "status": "open",
                                         "made_round": state["round"], "notified": False, "partial": choice == "partial"})
    elif action == "notify_delay":
        c = next((x for x in state["commitments"] if x["id"] == p.get("commitment") and x["status"] == "open"), None)
        if not c:
            raise GameError("There is no open promise to update.")
        c["notified"] = True
        log(state, events, "delay_notified", commitment=c["id"], due=c["due"], rounds_before_due=c["due"] - state["round"])
    elif action == "kai":
        kai_turn(state, events, p.get("option"), p.get("text"))
    elif action == "end_round":
        if practice:
            raise GameError("Finish the practice to start the real game.")
        end_round(state, events)
    else:
        raise GameError("Unknown action.")
    clamp(state)


def norm_edge(e: str | None) -> str:
    if not e or "-" not in e:
        raise GameError("Choose a cable route.")
    a, b = e.split("-", 1)
    for cand in (f"{a}-{b}", f"{b}-{a}"):
        if cand in EDGES:
            return cand
    raise GameError("Those two places are not next to each other.")


def route_message(action: str, d_key: str, correct: bool) -> str:
    name = DISTRICTS[d_key]["name"]
    if correct:
        return {"train": f"The Trainer worked with {name}'s team; they can now handle it themselves.",
                "engineer": f"The Engineer repaired {name}'s equipment.",
                "refer": f"The Liaison referred {name}'s issue to the right office; expect it resolved by the end of next round."}[action]
    return {"train": f"{name}'s team learned some skills, but that wasn't what was blocking them.",
            "engineer": f"The Engineer found nothing broken at {name}.",
            "refer": f"The office sent {name}'s referral back: it isn't an access or policy question."}[action]


# ======================================================================================= Kai co-op puzzle
KAI_OPTIONS = {
    0: [("vague", "Connect the power link."),
        ("jargon", "Plug the 48-volt feeder into relay R2's primary bus."),
        ("ask", "What can you see on each cable?"),
        ("blame_early", "It's simple, just get on with it.")],
    1: [("tell_amber", "Connect the amber cable, the one tagged 48V, to the socket marked R2."),
        ("check", "Before you plug it in, can you tell me in your own words what you'll do?"),
        ("take_over", "Never mind, I'll do it remotely myself.")],
    2: [("reassure", "That's normal. The warning means it's syncing; nothing is broken. What does the warning say?"),
        ("blame", "You must have done it wrong."),
        ("take_over2", "Step back, I'll sort it out.")],
    3: [("note", "Let's write a short note together in your own words, so you can do it next time."),
        ("do_it", "Sure, just call me and I'll always do it."),
        ("remember", "You should remember it now.")],
}
KAI_LINES = {
    "start": "Kai: Hi... I'm in the relay room. There are three cables in front of me and I'm worried I'll short-circuit something. What should I do?",
    "vague": "Kai: Which one is the power link? None of them says 'power'.",
    "jargon": "Kai: Sorry, I don't know what a primary bus is. I just see three coloured cables.",
    "ask": "Kai: The blue one has a tag that says DATA, the amber one says 48V, and the green one says SPARE.",
    "blame_early": "Kai: Oh... OK. I'm not sure which one, though. (Kai sounds less confident.)",
    "tell_amber": "Kai: Plugging the amber 48V cable into R2... done! Wait, a red warning is flashing. Did I break it?",
    "check": "Kai: So I take the amber cable with the 48V tag and plug it into the socket labelled R2. Is that right?",
    "check_then": "Kai: Great, doing it now... a red warning is flashing! Did I break it?",
    "take_over": "Kai: Oh. OK, I'll just watch then... it's working now that you've done it. Can you just do it for me next time too?",
    "reassure": "Kai: Phew. It says 'SYNCING 2/3'... and now it's green! Can you just do it for me next time though? I'll never remember.",
    "blame": "Kai: I'm sorry... it's green now, I think. Maybe you should do these yourself next time.",
    "take_over2": "Kai: OK. It's green now that you've done it. You'll do it next time too, right?",
    "note": "Kai: I've written: 'Amber 48V cable to R2. Red warning = syncing, wait for green.' I think I could do that on my own now!",
    "do_it": "Kai: Thanks! I'll call you every time then.",
    "remember": "Kai: I'll try... (Kai doesn't sound sure.)",
}


def classify_free_text(step: int, text: str) -> str:
    t = text.lower()
    if step == 0:
        if "?" in t or any(w in t for w in ("what do you see", "what can you see", "describe", "tell me what", "labels", "tags")):
            return "ask"
        if any(w in t for w in ("just", "simple", "obviously")):
            return "blame_early"
        return "jargon" if any(w in t for w in ("bus", "feeder", "volt")) else "vague"
    if step == 1:
        if "?" in t and any(w in t for w in ("own words", "what will you", "tell me", "repeat", "explain")):
            return "check"
        if any(w in t for w in ("i'll do it", "myself", "never mind")):
            return "take_over"
        return "tell_amber" if "amber" in t or "48" in t else "check"
    if step == 2:
        if any(w in t for w in ("wrong", "fault", "careless")):
            return "blame"
        if any(w in t for w in ("i'll sort", "step back", "let me do")):
            return "take_over2"
        return "reassure"
    if any(w in t for w in ("note", "together", "write", "own words", "try")):
        return "note"
    if any(w in t for w in ("should remember", "should know")):
        return "remember"
    return "do_it" if any(w in t for w in ("call me", "i'll do", "always")) else "note"


def kai_turn(state: dict, events: list, option: str | None, text: str | None) -> None:
    k = state["kai"]
    if state["round"] != 5:
        raise GameError("Kai is only available in round 5.")
    if option == "skip":
        if k["solved"]:
            raise GameError("You've already finished with Kai.")
        k["skipped"] = True
        log(state, events, "kai_skipped", step=k["step"])
        return
    if k["solved"]:
        raise GameError("Kai's task is complete.")
    if not k["transcript"]:
        k["transcript"].append({"who": "kai", "text": KAI_LINES["start"]})
    step = k["step"]
    free = (text or "").strip()
    if free:
        option = classify_free_text(step, free)
        said = free[:600]
    else:
        valid = dict(KAI_OPTIONS[step])
        if step == 1 and not k["asked_tags"]:
            valid.pop("tell_amber", None)
        if option not in valid:
            raise GameError("Choose what to say to Kai.")
        said = valid[option]
    if step == 1 and option == "tell_amber" and not k["asked_tags"]:
        option = "check" if "?" in said else "vague"  # the player cannot know the colour without asking
    k["transcript"].append({"who": "you", "text": said})
    log(state, events, "kai_message", step=step, intent=option, free_text=bool(free), text=said)
    reply = option
    if step == 0:
        if option == "ask":
            k["asked_tags"] = True; k["step"] = 1
        elif option == "blame_early":
            k["confidence"] -= 1
    elif step == 1:
        if option == "check":
            k["checked"] = True; k["confidence"] += 1
            reply = "check_then" if k.get("_checked_once") else "check"
            if k.get("_checked_once"):
                k["step"] = 2
            k["_checked_once"] = True
        elif option == "tell_amber":
            k["step"] = 2
        elif option == "take_over":
            k["step"] = 3; k["warning_handled"] = "took_over"
            state["districts"]["clinic"]["dependency"] += 1
    elif step == 2:
        k["warning_handled"] = option
        if option == "reassure":
            k["confidence"] += 1
        elif option == "blame":
            k["confidence"] -= 1
        k["step"] = 3
    elif step == 3:
        k["next_time"] = option
        if option == "note":
            k["confidence"] += 1
            state["districts"]["clinic"]["cap"] = min(3, state["districts"]["clinic"]["cap"] + 1)
        k["solved"] = True
        state["districts"]["clinic"]["service"] += 10
        state["districts"]["clinic"]["blocker_resolved"] = True
        log(state, events, "kai_solved", confidence=k["confidence"])
    k["transcript"].append({"who": "kai", "text": KAI_LINES[reply]})


# ======================================================================================= client view
def view(state: dict) -> dict:
    """What the browser may see: hidden information stays hidden until discovered."""
    v = copy.deepcopy({k: state[k] for k in ("phase", "round", "energy", "cables_left", "links", "crew", "summary",
                                             "archive_restricted", "archive_inspection", "overridden", "finished",
                                             "end_reason", "stress_done")})
    v["now"] = iso(now())
    v["ends_at"] = state["ends_at"]
    v["rounds"] = ROUNDS
    v["practice_mode"] = state["phase"] == "practice"
    v["notice"] = NOTICES.get(state["round"], "") if state["phase"] == "briefing" else None
    v["rules"] = NOTICES.get(state["round"], "")
    conn = connected(state)
    v["districts"] = {}
    for k, d in state["districts"].items():
        b = DISTRICTS[k]
        v["districts"][k] = {"name": b["name"], "x": b["x"], "y": b["y"], "service": d["service"], "cap": d["cap"],
                             "connected": k in conn, "critical": b["critical"], "need": b["need"],
                             "detail": b["detail"] if d["revealed"] else None, "diagnosis": d["diagnosis"],
                             "resolved": d["blocker_resolved"], "referral_pending": d["referral_round"] is not None and not d["blocker_resolved"],
                             "dependency": d["dependency"]}
    v["core"] = CORE
    v["edges"] = [{"id": e, "damaged": e in DAMAGED, "built": e in state["links"],
                   "restricted": state["archive_restricted"] and "archive" in e and state["archive_inspection"] != "done"
                   and e not in state["overridden"]} for e in EDGES]
    v["requests"] = [{"id": q["id"], "district": q["district"], "text": q["text"], "response": q["response"]} for q in state["requests"]]
    v["commitments"] = [{k: c[k] for k in ("id", "district", "text", "due", "status", "notified")} for c in state["commitments"]]
    v["blockers"] = BLOCKERS
    v["costs"] = COST
    if state["stress"]:
        s = STRESS[state["stress"]["id"]]
        v["stress"] = {"id": state["stress"]["id"], "title": s["title"], "text": s["text"], "options": s["options"],
                       "deadline": state["stress"]["deadline"], "seconds": state["stress"]["seconds"], "free_text": s.get("free_text")}
    k = state["kai"]
    if state["round"] == 5:
        opts = KAI_OPTIONS.get(k["step"], []) if not k["solved"] else []
        if k["step"] == 1 and not k["asked_tags"]:
            opts = [o for o in opts if o[0] != "tell_amber"]
        v["kai"] = {"transcript": k["transcript"] or [{"who": "kai", "text": KAI_LINES["start"]}],
                    "options": opts, "solved": k["solved"], "skipped": k["skipped"]}
    if state["finished"] or state["phase"] == "handover":
        v["outcome"] = outcome(state)
    return v


# ======================================================================================= evidence
def evidence(state: dict, events: list) -> dict:
    """Evidence lines per criterion, each citing event ids, plus rule-based indicator ratings used only
    by the demo assessor. Practice events are excluded."""
    ev = [e for e in events if not e.get("practice")]
    by = lambda t: [e for e in ev if e["type"] == t]
    lines: dict[str, list[str]] = {k: [] for k in ("credibility", "empathy", "reliability", "curiosity", "workflow", "judgment")}
    ind: dict[str, dict] = {}

    trains, fixes, peers = by("train"), by("fix_self"), by("peer_support")
    s1 = next((e for e in by("stress_choice") if e["stress"] == "S1"), None) or next((e for e in by("stress_timeout") if e["stress"] == "S1"), None)
    lines["credibility"] += [f"{e['id']} (round {e['round']}): trained {DISTRICTS[e['district']]['name']} instead of fixing it for them." for e in trains]
    lines["credibility"] += [f"{e['id']} (round {e['round']}): fixed {DISTRICTS[e['district']]['name']} personally (quick, but builds dependency)." for e in fixes]
    lines["credibility"] += [f"{e['id']} (round {e['round']}): {DISTRICTS[e['helper']]['name']}, which the player had built up, coached {DISTRICTS[e['helped']]['name']} independently." for e in peers]
    if s1:
        lines["credibility"].append(f"{s1['id']} stress moment S1 (Harbour demands a fix): " + (STRESS["S1"]["options"].get(s1.get("choice"), "no decision before the timer ran out")) + ".")
    independent = sum(1 for d in state["districts"].values() if d["cap"] >= 2)
    lines["credibility"].append(f"Game end: {independent} district(s) at capability 2 or more (able to operate and support peers).")
    ind["credibility"] = {"trains": len(trains), "fixes": len(fixes), "peers": len(peers), "s1": s1.get("choice") if s1 else None,
                          "independent": independent}

    k = state["kai"]
    for m in by("kai_message"):
        lines["empathy"].append(f"{m['id']} Kai step {m['step']}: player said \"{m['text']}\" (intent: {m['intent']}).")
    if k["skipped"]:
        lines["empathy"].append("The player skipped the Kai co-operation task.")
    lines["empathy"].append(f"Kai's confidence moved from 2 to {k['confidence']}; asked Kai what it could see: {'yes' if k['asked_tags'] else 'no'}; "
                            f"checked understanding: {'yes' if k['checked'] else 'no'}; response to the warning: {k['warning_handled'] or 'none'}; "
                            f"next-time approach: {k['next_time'] or 'none'}.")
    ind["empathy"] = {"asked": k["asked_tags"], "checked": k["checked"], "warning": k["warning_handled"], "next": k["next_time"],
                      "skipped": k["skipped"], "blames": sum(1 for m in by("kai_message") if m["intent"] in ("blame", "blame_early", "remember")),
                      "messages": len(by("kai_message"))}

    resp = by("request_response")
    for e in resp:
        lines["reliability"].append(f"{e['id']} (round {e['round']}): responded to request {e['request']} with '{e['choice']}'" + (f": \"{e['text']}\"" if e.get("text") else "") + ".")
    for e in by("request_ignored"):
        lines["reliability"].append(f"{e['id']}: request {e['request']} received no reply.")
    for e in by("delay_notified"):
        lines["reliability"].append(f"{e['id']} (round {e['round']}): told {e['commitment']} about a delay {e['rounds_before_due']} round(s) before it was due.")
    for e in by("commitment_kept"):
        lines["reliability"].append(f"{e['id']}: kept promise {e['commitment']}.")
    for e in by("commitment_broken"):
        lines["reliability"].append(f"{e['id']}: broke promise {e['commitment']}" + (" after warning of the delay." if e.get("notified") else " without warning."))
    promised = [c for c in state["commitments"]]
    ind["reliability"] = {"promised": len(promised), "kept": sum(1 for c in promised if c["status"] == "kept"),
                          "broken_silent": sum(1 for e in by("commitment_broken") if not e.get("notified")),
                          "notified": len(by("delay_notified")), "ignored": len(by("request_ignored")),
                          "handover_len": len(state["handover"] or "")}

    acts = [e for e in ev if e["type"] in ("fix_self", "train", "engineer", "refer")]
    informed = [e for e in acts if e.get("inspected")]
    lines["curiosity"].append(f"{len(by('inspect'))} district inspections; {len(informed)} of {len(acts)} interventions were made after inspecting the district.")
    r4_first = next((e for e in ev if e["round"] == 4 and e["type"] not in ("round_start", "stress_start", "stress_choice", "stress_timeout")), None)
    if r4_first:
        lines["curiosity"].append(f"{r4_first['id']} round 4: first action after the rule change was '{r4_first['type']}'" +
                                  (" (the new rules notice had been read)." if 4 in state["notice_read"] else "."))
    for e in by("inspection_requested"):
        lines["curiosity"].append(f"{e['id']} (round {e['round']}): adapted to the new rule by requesting Archive's safety inspection.")
    if k["asked_tags"]:
        q = next(m for m in by("kai_message") if m["intent"] == "ask")
        lines["curiosity"].append(f"{q['id']}: asked Kai what it could see before giving instructions.")
    ind["curiosity"] = {"inspects": len(by("inspect")), "informed_ratio": (len(informed) / len(acts)) if acts else None,
                        "adapted": bool(by("inspection_requested")), "asked_kai": k["asked_tags"]}

    diag = by("diagnose")
    routes = [e for e in ev if e["type"] in ("train", "engineer", "refer")]
    for e in diag:
        lines["workflow"].append(f"{e['id']} (round {e['round']}): diagnosed {DISTRICTS[e['district']]['name']} as '{BLOCKERS[e['choice']]}' ({'correct' if e['correct'] else 'incorrect'}).")
    for e in routes:
        lines["workflow"].append(f"{e['id']} (round {e['round']}): sent the {e['type']} route to {DISTRICTS[e['district']]['name']} ({'right' if e['correct_route'] else 'wrong'} route for a {BLOCKERS[e['blocker']].lower()}).")
    conn = connected(state)
    lines["workflow"].append(f"Game end: {len(conn)} of 6 districts connected to the core using {len(state['links'])} cable(s).")
    ind["workflow"] = {"diag": len(diag), "diag_ok": sum(1 for e in diag if e["correct"]), "routes": len(routes),
                       "routes_ok": sum(1 for e in routes if e["correct_route"]), "connected": len(conn)}

    s2 = next((e for e in by("stress_choice") if e["stress"] == "S2"), None) or next((e for e in by("stress_timeout") if e["stress"] == "S2"), None)
    if s2:
        lines["judgment"].append(f"{s2['id']} stress moment S2 (official demands the safety lock is switched off): " +
                                 STRESS["S2"]["options"].get(s2.get("choice"), "no decision before the timer ran out") + "." +
                                 (f" Player wrote: \"{s2['text']}\"" if s2.get("text") else ""))
    for e in by("override_restriction"):
        lines["judgment"].append(f"{e['id']} (round {e['round']}): overrode the Archive inspection rule on cable {e['edge']} (control bypassed).")
    for e in [x for x in fixes if x.get("control_bypass")]:
        lines["judgment"].append(f"{e['id']} (round {e['round']}): fixed {DISTRICTS[e['district']]['name']}'s {e['blocker']} problem personally, bypassing the access/policy control.")
    for sid in ("S3", "S4"):
        e = next((x for x in by("stress_choice") if x["stress"] == sid), None)
        if e:
            lines["judgment"].append(f"{e['id']} stress moment {sid} ({STRESS[sid]['title']}): {STRESS[sid]['options'][e['choice']]}.")
    ind["judgment"] = {"s2": s2.get("choice") if s2 else None, "overrides": len(by("override_restriction")),
                       "control_fixes": sum(1 for x in fixes if x.get("control_bypass")),
                       "s3": next((x["choice"] for x in by("stress_choice") if x["stress"] == "S3"), None),
                       "s4": next((x["choice"] for x in by("stress_choice") if x["stress"] == "S4"), None)}
    return {"lines": lines, "indicators": ind}


# ======================================================================================= demo ratings
def demo_rating(key: str, ind: dict, variant: str = "A") -> dict:
    """Rule-based provisional rating for the SIMULATED demo assessor only."""
    i = ind[key]
    r: int | None
    unsafe_serious = False
    strict = variant == "B"
    if key == "credibility":
        if i["trains"] + i["fixes"] == 0 and not i["s1"]:
            r = None
        else:
            r = 3 + (1 if i["trains"] >= (3 if strict else 2) and i["trains"] > i["fixes"] else 0) \
                + (1 if i["peers"] or i["s1"] == "teach_now" else 0) - (1 if i["fixes"] >= 3 else 0) - (1 if i["s1"] == "fix_for_them" else 0)
    elif key == "empathy":
        if i["skipped"] or not i["messages"]:
            r = None
        else:
            r = 2 + i["asked"] + (i["warning"] == "reassure") + (i["checked"] or i["next"] == "note") - min(2, i["blames"])
    elif key == "reliability":
        if not i["promised"] and not i["ignored"]:
            r = 3 if i["handover_len"] >= 80 else None
        else:
            r = 3 + (1 if i["promised"] and i["kept"] == i["promised"] else 0) + (1 if i["handover_len"] >= (150 if strict else 100) else 0) \
                - 2 * min(1, i["broken_silent"]) - min(1, i["ignored"])
    elif key == "curiosity":
        ratio = i["informed_ratio"]
        if ratio is None and not i["inspects"]:
            r = None
        else:
            r = 2 + (1 if (ratio or 0) >= (0.75 if strict else 0.6) else 0) + i["adapted"] + i["asked_kai"]
    elif key == "workflow":
        if not i["diag"] and not i["routes"]:
            r = None
        else:
            acc = (i["routes_ok"] / i["routes"]) if i["routes"] else 0.5
            r = 2 + (1 if acc >= (0.8 if strict else 0.7) else 0) + (1 if i["diag"] and i["diag_ok"] / i["diag"] >= 0.75 else 0) + (1 if i["connected"] >= 5 else 0)
    else:  # judgment
        if i["s2"] is None and not i["overrides"] and not i["control_fixes"]:
            r = None
        elif i["s2"] == "switch_off":
            r, unsafe_serious = 1, True
        else:
            r = 3 + (1 if i["s2"] == "refuse_escalate" else 0) + (1 if i["s3"] == "protect_clinic" or i["s4"] in ("clinic_first", "peer_transit") else 0) \
                - min(2, i["overrides"] + i["control_fixes"])
    if r is not None:
        r = max(1, min(5, int(r)))
    return {"rating": r, "unsafe_serious": unsafe_serious}


def snapshot_sources(state: dict, events: list) -> tuple[list[dict], dict]:
    ev = evidence(state, events)
    names = {"credibility": "Peer influence in the game", "empathy": "Co-operation with Kai, the AI teammate",
             "reliability": "Requests, promises and the handover note", "curiosity": "Exploring, asking and adapting",
             "workflow": "Diagnosing blockers, routing support and connecting the network",
             "judgment": "Safety controls and priorities under pressure"}
    src = []
    for key, lines in ev["lines"].items():
        src.append({"id": f"GAME-{key}", "criterion": key, "label": f"NEXUS game record: {names[key]} (performance within a digital exercise; event ids cite moments)",
                    "text": "\n".join(lines)})
    if state["handover"]:
        src.append({"id": "GAME-handover", "criterion": "reliability", "label": "Player's handover note at the end of the game",
                    "text": state["handover"]})
    for sid, text in state["stress_free_text"].items():
        src.append({"id": f"GAME-{sid}-text", "criterion": "judgment", "label": f"What the player wrote during stress moment {sid}", "text": text})
    return src, ev["indicators"]
