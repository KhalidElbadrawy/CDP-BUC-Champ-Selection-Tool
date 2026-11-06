/* NEXUS: Reconnect the City. Browser client. The server runs the game; this file only draws state and sends actions. */
(function () {
  "use strict";
  const root = document.getElementById("nexus");
  if (!root) return;
  const csrf = root.dataset.csrf;
  const $ = (id) => document.getElementById(id);
  const svgNS = "http://www.w3.org/2000/svg";
  let S = null, sel = null, selEdge = null, offset = 0, busy = false, lastStressId = null, modalKey = null;

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pos = (k) => (k === "core" ? S.core : S.districts[k]);
  const nameOf = (k) => (k === "core" ? "City core" : S.districts[k].name);

  async function api(action, params) {
    if (busy && action !== "poll") return;
    busy = action !== "poll";
    try {
      const r = await fetch("/play/api", { method: "POST", headers: { "Content-Type": "application/json", "x-csrf": csrf },
        body: JSON.stringify({ action, params: params || {} }) });
      const data = await r.json();
      if (!r.ok) { showMsg(data.error || "Something went wrong. Please try again."); return; }
      S = data;
      offset = Date.parse(S.now) - Date.now();
      showMsg(S.error || "");
      render();
    } catch (e) {
      showMsg("Connection problem. Your progress is saved; please check your connection and try again.");
    } finally { busy = false; }
  }

  function showMsg(t) { const m = $("nx-msg"); m.hidden = !t; m.textContent = t || ""; }

  // ----------------------------------------------------------------- map
  function drawMap() {
    const svg = $("nx-map");
    svg.innerHTML = "";
    for (const e of S.edges) {
      const [a, b] = e.id.split("-");
      const p = pos(a), q = pos(b);
      const line = document.createElementNS(svgNS, "line");
      line.setAttribute("x1", p.x); line.setAttribute("y1", p.y); line.setAttribute("x2", q.x); line.setAttribute("y2", q.y);
      let cls = "edge " + (e.damaged ? "damaged" : e.built ? "built" : "open");
      if (e.restricted && e.built) cls += " restricted";
      if (selEdge === e.id) line.setAttribute("stroke-width", "9");
      line.setAttribute("class", cls);
      if (!e.damaged) {
        line.setAttribute("tabindex", "0");
        line.setAttribute("role", "button");
        line.setAttribute("aria-label", (e.built ? "Cable " : "Lay a cable ") + nameOf(a) + " to " + nameOf(b));
        const go = () => edgeClick(e);
        line.addEventListener("click", go);
        line.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); go(); } });
      }
      const t = document.createElementNS(svgNS, "title"); t.textContent = e.damaged ? "Damaged route: no cable possible" : e.built ? "Cable: select to remove" : "Click to lay a cable (1 energy)";
      line.appendChild(t);
      svg.appendChild(line);
    }
    // core
    const core = document.createElementNS(svgNS, "g");
    core.innerHTML = `<polygon points="${hex(S.core.x, S.core.y, 40)}" fill="#14324a" stroke="#3fd6c6" stroke-width="3"/>
      <text x="${S.core.x}" y="${S.core.y + 5}" fill="#3fd6c6" style="font:700 14px system-ui;text-anchor:middle">CORE</text>`;
    svg.appendChild(core);
    for (const [k, d] of Object.entries(S.districts)) {
      if (S.practice_mode && k !== "harbour") continue;
      const g = document.createElementNS(svgNS, "g");
      g.setAttribute("class", "node" + (sel === k ? " sel" : ""));
      g.setAttribute("tabindex", "0");
      g.setAttribute("role", "button");
      g.setAttribute("aria-label", `${d.name}: service ${d.service} percent, ${d.connected ? "connected" : "not connected"}`);
      const C = 2 * Math.PI * 42, col = d.service < 40 ? "#ff6b5e" : d.service < 70 ? "#f2b33d" : "#5ee08a";
      const dots = [0, 1, 2].map((i) => `<circle cx="${d.x - 14 + i * 14}" cy="${d.y + 30}" r="4" fill="${i < d.cap ? "#9d8cff" : "#24405a"}"/>`).join("");
      g.innerHTML = `${d.connected ? `<circle cx="${d.x}" cy="${d.y}" r="52" fill="none" stroke="#3fd6c6" stroke-opacity=".35" stroke-width="6"/>` : ""}
        <circle class="ring-bg" cx="${d.x}" cy="${d.y}" r="42"/>
        <circle cx="${d.x}" cy="${d.y}" r="42" fill="none" stroke="${col}" stroke-width="6" stroke-dasharray="${(C * d.service) / 100} ${C}" transform="rotate(-90 ${d.x} ${d.y})"/>
        <text x="${d.x}" y="${d.y - 4}">${esc(d.name)}</text><text class="pct" x="${d.x}" y="${d.y + 14}">${d.service}%</text>${dots}
        ${d.critical ? `<circle cx="${d.x + 34}" cy="${d.y - 34}" r="10" fill="#ff6b5e"/><text x="${d.x + 34}" y="${d.y - 29}" style="font:800 13px system-ui;fill:#fff">!</text>` : ""}
        ${d.resolved ? `<text x="${d.x - 34}" y="${d.y - 28}" style="font:800 16px system-ui;fill:#5ee08a">✓</text>` : ""}`;
      const go = () => { sel = k; selEdge = null; render(); };
      g.addEventListener("click", go);
      g.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); go(); } });
      const t = document.createElementNS(svgNS, "title"); t.textContent = d.name; g.appendChild(t);
      svg.appendChild(g);
    }
  }
  function hex(x, y, r) { return [0, 1, 2, 3, 4, 5].map((i) => { const a = Math.PI / 3 * i + Math.PI / 6; return `${x + r * Math.cos(a)},${y + r * Math.sin(a)}`; }).join(" "); }

  function edgeClick(e) {
    if (S.phase !== "playing" && S.phase !== "practice") return;
    if (e.built) { selEdge = e.id; sel = null; render(); }
    else api("link", { edge: e.id });
  }

  // ----------------------------------------------------------------- panel
  function costBtn(label, action, cost, params, disabled, extra) {
    return `<button class="nx-btn ${extra || ""}" data-a="${action}" data-p='${esc(JSON.stringify(params || {}))}' ${disabled ? "disabled" : ""}>${esc(label)}${cost != null ? `<span class="cost">${cost} ⚡</span>` : ""}</button>`;
  }

  function districtPanel() {
    const box = $("nx-district");
    if (selEdge) {
      const e = S.edges.find((x) => x.id === selEdge);
      const [a, b] = selEdge.split("-");
      let h = `<h3>Cable: ${esc(nameOf(a))} – ${esc(nameOf(b))}</h3>`;
      if (e.restricted) {
        h += `<p class="nx-muted">New council rule: cables touching Archive need a safety inspection before they carry services.</p>`;
        h += `<div class="nx-actions">${costBtn("Request Archive's safety inspection (ready next round)", "inspection", S.costs.inspection, {}, S.energy < S.costs.inspection || S.archive_inspection)}
          ${costBtn("Override the rule and use the cable now", "override", null, { edge: selEdge }, false, "danger")}</div>`;
      }
      h += `<div class="nx-actions" style="margin-top:6px">${costBtn("Remove this cable (returns the cable, not the energy)", "unlink", null, { edge: selEdge })}</div>`;
      box.innerHTML = h;
      return;
    }
    if (!sel) {
      box.innerHTML = `<h3>${S.practice_mode ? "Practice" : "Select a district"}</h3><p class="nx-muted">${S.practice_mode
        ? "Try things safely: select Harbour, inspect it, diagnose the blocker, connect it to the core by clicking the dashed line, and try the crew. Nothing in practice is assessed."
        : "Click a district on the map to see its needs and act. Click a dashed line to lay a cable."}</p>
        ${S.practice_mode ? `<button class="nx-btn primary" data-a="finish_practice">I'm ready: start the real game</button>` : ""}`;
      return;
    }
    const d = S.districts[sel];
    const crewLeft = S.crew;
    const diag = Object.entries(S.blockers).map(([k, v]) => `<button class="nx-btn ${d.diagnosis === k ? "on" : ""}" data-a="diagnose" data-p='${JSON.stringify({ district: sel, blocker: k })}'>${esc(v)}</button>`).join("");
    let h = `<h3>${esc(d.name)} ${d.critical ? `<span class="tag broken">critical service</span>` : ""}</h3>
      <p>Service <b>${d.service}%</b> · Capability <b>${d.cap}/3</b> · ${d.connected ? "connected to the core" : "<b>not connected</b>"}</p>
      <p>${esc(d.need)}</p>
      <p class="nx-muted">${d.detail ? esc(d.detail) : "Inspect the district to find out what is really blocking it."}</p>
      ${d.resolved ? `<p class="tag kept">blocker resolved</p>` : d.referral_pending ? `<p class="tag open">referral in progress</p>` : ""}
      <p class="nx-muted" style="margin-top:6px">What is blocking ${esc(d.name)}?</p><div class="nx-diag">${diag}</div>
      <div class="nx-actions" style="margin-top:8px">
        ${costBtn("Inspect and ask questions", "inspect", 0, { district: sel })}
        ${costBtn("Fix it yourself (quick, temporary)", "fix", S.costs.fix, { district: sel }, S.energy < S.costs.fix)}
        ${costBtn(`Send the Trainer to build their skills (${crewLeft.trainer} left)`, "train", S.costs.train, { district: sel }, S.energy < S.costs.train || !crewLeft.trainer)}
        ${costBtn(`Send the Engineer to repair equipment (${crewLeft.engineer} left)`, "engineer", S.costs.engineer, { district: sel }, S.energy < S.costs.engineer || !crewLeft.engineer)}
        ${costBtn(`Liaison: refer to the access or policy office (${crewLeft.liaison} left)`, "refer", S.costs.refer, { district: sel }, S.energy < S.costs.refer || !crewLeft.liaison)}
        ${sel === "archive" && S.archive_restricted && !S.archive_inspection ? costBtn("Request Archive's safety inspection", "inspection", S.costs.inspection, {}, S.energy < S.costs.inspection) : ""}
      </div>`;
    if (S.practice_mode) h += `<button class="nx-btn primary" style="margin-top:10px" data-a="finish_practice">I'm ready: start the real game</button>`;
    box.innerHTML = h;
  }

  function requestsPanel() {
    const box = $("nx-requests");
    let h = "";
    const open = S.requests.filter((q) => !q.response);
    if (open.length) {
      h += `<h3>Requests</h3>`;
      for (const q of open) {
        h += `<div class="nx-req"><div>${esc(q.text)}</div>
          <label class="nx-muted" for="rq-${q.id}">Your reply (optional)</label><textarea id="rq-${q.id}"></textarea>
          <div class="nx-diag"><button class="nx-btn" data-r="${q.id}" data-c="promise">Promise to do it</button>
          <button class="nx-btn" data-r="${q.id}" data-c="partial">Promise part of it</button>
          <button class="nx-btn" data-r="${q.id}" data-c="decline">Decline and explain</button></div></div>`;
      }
    }
    if (S.commitments.length) {
      h += `<h3 style="margin-top:6px">Your promises</h3>`;
      for (const c of S.commitments) {
        h += `<div class="nx-req"><div>${esc(c.text)} <span class="nx-muted">(due end of round ${c.due})</span> <span class="tag ${c.status}">${c.status}</span>${c.notified ? ` <span class="nx-muted">delay notified</span>` : ""}</div>
          ${c.status === "open" && !c.notified ? `<button class="nx-btn" data-a="notify_delay" data-p='${JSON.stringify({ commitment: c.id })}'>Tell them it will be late</button>` : ""}</div>`;
      }
    }
    box.innerHTML = h;
  }

  function kaiPanel() {
    const box = $("nx-kai");
    if (!S.kai || S.phase !== "playing") { box.hidden = true; return; }
    box.hidden = false;
    const k = S.kai;
    let h = `<h3>Co-op: guide Kai</h3><div class="nx-kai"><div class="nx-chat" id="nx-chat">${k.transcript.map((m) => `<div class="bubble ${m.who}">${esc(m.text)}</div>`).join("")}</div>`;
    if (k.solved) h += `<p class="tag kept">Kai's task is complete</p>`;
    else if (k.skipped) h += `<p class="tag broken">You skipped this task</p>`;
    else {
      h += `<div class="nx-actions">${k.options.map(([id, text]) => `<button class="nx-btn" data-k="${id}">${esc(text)}</button>`).join("")}</div>
        <label class="nx-muted" for="kai-free">Or say it your own way</label><textarea id="kai-free"></textarea>
        <div class="nx-diag"><button class="nx-btn" id="kai-send">Send</button><button class="nx-btn" data-k="skip">Skip this task</button></div>`;
    }
    box.innerHTML = h + `</div>`;
    const chat = $("nx-chat"); if (chat) chat.scrollTop = chat.scrollHeight;
  }

  function edgesPanel() {
    $("nx-edges").innerHTML = S.edges.filter((e) => !(S.practice_mode && e.id !== "core-harbour")).map((e) => {
      const [a, b] = e.id.split("-");
      const label = `${nameOf(a)} – ${nameOf(b)}`;
      if (e.damaged) return `<div class="nx-muted">${esc(label)}: damaged</div>`;
      return `<div style="display:flex;justify-content:space-between;gap:6px;margin:3px 0"><span>${esc(label)}${e.restricted && e.built ? " (needs inspection)" : ""}</span>
        ${e.built ? `<button class="nx-btn" data-a="unlink" data-p='${JSON.stringify({ edge: e.id })}'>Remove</button>` : `<button class="nx-btn" data-a="link" data-p='${JSON.stringify({ edge: e.id })}'>Lay cable (1 ⚡)</button>`}</div>`;
    }).join("");
  }

  // ----------------------------------------------------------------- overlays
  function modal(html, cls, key) {
    const ov = $("nx-overlay"), m = $("nx-modal");
    if (key && key === modalKey && !ov.hidden) return;  // same dialog: keep what the player is typing
    modalKey = key || null;
    const keep = {};
    m.querySelectorAll("textarea").forEach((t) => { if (t.id) keep[t.id] = t.value; });
    m.className = "nx-modal " + (cls || "");
    m.innerHTML = html;
    for (const [id, v] of Object.entries(keep)) { const t = m.querySelector("#" + id); if (t) t.value = v; }
    ov.hidden = false;
    const f = m.querySelector("button, textarea"); if (f) f.focus();
  }
  function closeModal() { $("nx-overlay").hidden = true; modalKey = null; }

  function outcomeHtml(o) {
    if (!o) return "";
    return `<div class="nx-outcome"><div><b>${o.restored}</b>services restored</div><div><b>${o.independent}</b>districts independent</div>
      <div><b>${o.connected}</b>connected</div><div><b>${esc(o.controls)}</b>safety controls</div></div>
      <p class="nx-muted">This is the game result only. Your assessment looks at how you worked, not this score.</p>`;
  }

  function overlays() {
    const ph = S.phase;
    if (ph === "intro") {
      modal(`<h2 id="nx-modal-title">NEXUS: Reconnect the City</h2>
        <p>Six districts are cut off from the city core. Over six rounds you will explore the map, work out what is really blocking each district, connect them with cables, and decide how to use a small crew and limited energy.</p>
        <p>Fixing problems yourself is quick, but districts then depend on you. Building their skills costs more now, but lets them run on their own and help each other. Expect disruptions, competing requests and a few timed moments.</p>
        <p class="nx-muted">The game clock (${Math.round((Date.parse(S.ends_at || S.now) - Date.parse(S.now)) / 60000) || "about 45"} minutes) starts when the real game begins. There is no clock in practice.</p>
        <div class="nx-diag"><button class="nx-btn primary" data-a="start_practice">Try a short practice</button><button class="nx-btn" data-a="finish_practice">Skip practice and start</button></div>`);
    } else if (ph === "briefing") {
      modal(`<h2 id="nx-modal-title">Round ${S.round} of ${S.rounds}</h2><p>${esc(S.notice)}</p>${summaryHtml()}
        <button class="nx-btn primary" data-a="read_brief">Continue</button>`);
    } else if (ph === "stress" && S.stress) {
      const st = S.stress;
      modal(`<h2 id="nx-modal-title">⚠ ${esc(st.title)}</h2><div class="nx-count"><span id="nx-cd">--</span><div class="nx-countbar"><span id="nx-cdbar" style="width:100%"></span></div></div>
        <p>${esc(st.text)}</p>
        ${st.free_text ? `<label class="nx-muted" for="st-free">${esc(st.free_text)}</label><textarea id="st-free"></textarea>` : ""}
        <div class="nx-actions">${Object.entries(st.options).map(([k, v]) => `<button class="nx-btn" data-s="${k}">${esc(v)}</button>`).join("")}</div>`, "stress", "stress-" + st.id);
      lastStressId = st.id;
    } else if (ph === "handover") {
      modal(`<h2 id="nx-modal-title">Handover to the city team</h2>${summaryHtml()}${outcomeHtml(S.outcome)}
        <p>Write a short handover note: what is still unfinished, who owns each item, and what should happen next.</p>
        <label class="nx-muted" for="ho">Handover note</label><textarea id="ho" style="min-height:120px"></textarea>
        <button class="nx-btn primary" id="ho-send">Submit and finish</button>${S.error ? `<p class="nx-msg">${esc(S.error)}</p>` : ""}`, "", S.error ? null : "handover");
    } else if (ph === "finished") {
      modal(`<h2 id="nx-modal-title">Thank you</h2><p>Your game is complete and has been submitted for assessment.</p>${outcomeHtml(S.outcome)}
        <a class="nx-btn primary" href="/assess" style="text-decoration:none">Continue</a>`);
    } else closeModal();
  }
  function summaryHtml() { return S.summary && S.summary.length ? `<ul class="nx-summary">${S.summary.map((m) => `<li>${esc(m)}</li>`).join("")}</ul>` : ""; }

  // ----------------------------------------------------------------- render
  function render() {
    const typed = {};
    document.querySelectorAll(".nx-panel textarea").forEach((t) => { if (t.id && t.value) typed[t.id] = t.value; });
    const focused = document.activeElement && document.activeElement.id;
    $("nx-round").textContent = S.phase === "practice" || S.phase === "intro" ? "Practice" : `Round ${S.round} of ${S.rounds}`;
    $("nx-energy").textContent = S.energy;
    $("nx-cables").textContent = S.cables_left;
    $("nx-crew").textContent = `Trainer ${S.crew.trainer} · Engineer ${S.crew.engineer} · Liaison ${S.crew.liaison}`;
    $("nx-summary").innerHTML = S.phase === "playing" || S.phase === "practice" ? summaryHtml() : "";
    drawMap(); districtPanel(); requestsPanel(); kaiPanel(); edgesPanel();
    const end = $("nx-endround");
    end.disabled = S.phase !== "playing";
    end.textContent = S.round === 5 && S.kai && !(S.kai.solved || S.kai.skipped) ? "Guide Kai before ending the round" : S.round >= S.rounds ? "End the final round" : `End round ${S.round || ""}`;
    for (const [id, v] of Object.entries(typed)) { const t = $(id); if (t) t.value = v; }
    if (focused && $(focused) && $(focused).tagName === "TEXTAREA") $(focused).focus();
    overlays();
    updateClock();
  }

  // ----------------------------------------------------------------- clock
  function fmt(ms) { const s = Math.max(0, Math.round(ms / 1000)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; }
  function updateClock() {
    if (!S) return;
    const nowS = Date.now() + offset;
    const clock = $("nx-clock");
    if (S.ends_at && S.phase !== "finished") {
      const left = Date.parse(S.ends_at) - nowS;
      clock.textContent = "⏱ " + fmt(left);
      clock.classList.toggle("low", left < 5 * 60000);
      if (left <= 0 && !busy) api("poll");
    } else clock.textContent = S.phase === "finished" ? "Done" : "No clock in practice";
    if (S.phase === "stress" && S.stress) {
      const left = Date.parse(S.stress.deadline) - nowS;
      const cd = $("nx-cd"), bar = $("nx-cdbar");
      if (cd) cd.textContent = fmt(left);
      if (bar) bar.style.width = Math.max(0, (100 * left) / (S.stress.seconds * 1000)) + "%";
      if (left <= -500 && !busy) api("poll");
    }
  }
  setInterval(updateClock, 1000);
  setInterval(() => { if (S && S.phase !== "finished" && !busy) api("poll"); }, 20000);

  // ----------------------------------------------------------------- events
  root.addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b || b.disabled) return;
    if (b.dataset.a) {
      const p = b.dataset.p ? JSON.parse(b.dataset.p) : {};
      if (b.dataset.a === "unlink") selEdge = null;
      api(b.dataset.a, p);
    } else if (b.dataset.s) {
      const t = $("st-free");
      api("stress_choice", { choice: b.dataset.s, text: t ? t.value : "" });
    } else if (b.dataset.r) {
      const t = $("rq-" + b.dataset.r);
      api("respond", { request: b.dataset.r, choice: b.dataset.c, text: t ? t.value : "" });
    } else if (b.dataset.k) {
      api("kai", { option: b.dataset.k });
    } else if (b.id === "kai-send") {
      const t = $("kai-free");
      if (t && t.value.trim()) api("kai", { text: t.value });
    } else if (b.id === "ho-send") {
      api("handover", { text: $("ho").value });
    } else if (b.id === "nx-endround") {
      api("end_round", {});
    }
  });

  api("poll");
})();
