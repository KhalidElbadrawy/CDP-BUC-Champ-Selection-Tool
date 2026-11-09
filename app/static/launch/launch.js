/* LAUNCH WINDOW: browser client. The server runs the game; this file draws the view, plays the voices,
   music and sound effects, and sends the player's choices. All server text is escaped before display. */
(function () {
  "use strict";
  const root = document.getElementById("lw");
  if (!root) return;
  const csrf = root.dataset.csrf;
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = { get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } },
                  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let lang = store.get("lw-lang", root.dataset.lang === "ar" ? "ar" : "en");
  let S = null, offset = 0, busy = false, lastCue = null, lastFb = null, lastKey = "", polling = false, expiredFor = null;
  const ui = { loc: null, scene: null, seen: {}, picks: new Set(), unlocked: false, typed: {} };

  const IMG = (n) => `/static/launch/img/${n}.webp`;
  const AV = { Noor: "av_noor", Hamad: "av_hamad", Maryam: "av_maryam", Saeed: "av_saeed", Yousef: "av_yousef" };
  const LOC_POS = { comms: [22, 20], pad: [53, 13], control: [80, 41], hangar: [17, 43], briefing: [27, 78], fuel: [75, 78] };

  const T = {
    en: { trust: "Trust", ready: "Readiness", crew: "Crew", checklist: "Checklist", whatnow: "What now?", soundOn: "Sound on", soundOff: "Sound off",
      langBtn: "عربي", hold: "HOLD", tlabel: "Countdown", session: "Time left", start: "Start", testSound: "Test sound",
      headphones: "Headphones recommended. Captions are always on.", tagline: "The final hour before launch. The whole base is counting on you.",
      resume: "Resume", resumeText: "Your game is saved. Press Resume to continue.", skip: "Skip", backMap: "Back to the map", close: "Close",
      own: "Or say it in your own words…", send: "Say it", files: "Mission files", opened: (n) => `${n} of 4 opened`, filesTip: "Tap a file to open it. You can open four.",
      checks: "Readiness checks", routeTo: "Route to…", route: "Route", board: "Incident board", wave: (n) => `Wave ${n} of 3`,
      directorPrompt: "What would you say to him? (optional)", choose1: "Time for one", manual: "Your manual · Hamad can't see this", radio: "Pad radio",
      checkTitle: "Your checklist", workLeft: "Work time left", done: "Done", st: { open: "Due", kept: "Delivered", warned: "Warned early", slipped: "Slipped" },
      handTitle: "Handover to the next shift", pick3: "Choose 3 actions", noteLabel: "Handover note", handGo: "Hand over and launch",
      goControl: "Head to mission control", goWarn: "Calls you haven't answered will be left waiting.", noorBtn: "Talk to Noor", locked: "Not yet",
      liftoff: "Liftoff", rank: "Your rank", trustL: "Crew trust", readyL: "Launch readiness", crewL: "Crew who can help others",
      excluded: "These game results are just for fun. They are not part of your assessment.", cont: "Continue", realTitle: "Two questions about your real work",
      realTip: "Answer in a few sentences. Specific examples help most.", submit: "Submit", thanks: "Thank you. You're done.",
      thanksText: "Your answers are saved and the CDP Change Lead will be in touch. You can close this page.", timeUp: "Time is up. Thank you: everything you did has been saved.",
      conn: "Connection problem. Your progress is saved; please check your connection and try again.", you: "You", tapBriefing: "Briefing hall",
      noorDone: "Noor's check is finished.", here: "Here", unanswered: "Calls waiting" },
    ar: { trust: "الثقة", ready: "الجاهزية", crew: "الطاقم", checklist: "المهام", whatnow: "ماذا الآن؟", soundOn: "الصوت يعمل", soundOff: "الصوت متوقف",
      langBtn: "English", hold: "توقف", tlabel: "العد التنازلي", session: "الوقت المتبقي", start: "ابدأ", testSound: "اختبر الصوت",
      headphones: "يُفضّل استخدام السماعات. الترجمة النصية تظهر دائماً.", tagline: "الساعة الأخيرة قبل الإطلاق. القاعدة كلها تعتمد عليك.",
      resume: "متابعة", resumeText: "لُعبتك محفوظة. اضغط متابعة للاستمرار.", skip: "تخطي", backMap: "العودة إلى الخريطة", close: "إغلاق",
      own: "أو قلها بكلماتك…", send: "قلها", files: "ملفات المهمة", opened: (n) => `فُتح ${n} من 4`, filesTip: "اضغط على ملف لفتحه. يمكنك فتح أربعة.",
      checks: "أسئلة الجاهزية", routeTo: "أحِله إلى…", route: "إحالة", board: "لوحة الحوادث", wave: (n) => `الموجة ${n} من 3`,
      directorPrompt: "ماذا ستقول له؟ (اختياري)", choose1: "الوقت يكفي لواحد", manual: "دليلك · حمد لا يراه", radio: "لاسلكي المنصة",
      checkTitle: "قائمة مهامك", workLeft: "وقت العمل المتبقي", done: "تم", st: { open: "مستحق", kept: "أُنجز", warned: "نُبّه مبكراً", slipped: "فات" },
      handTitle: "التسليم للمناوبة القادمة", pick3: "اختر 3 إجراءات", noteLabel: "ملاحظة التسليم", handGo: "سلّم وابدأ الإطلاق",
      goControl: "توجّه إلى غرفة التحكم", goWarn: "النداءات التي لم تُجب عنها ستبقى منتظرة.", noorBtn: "تحدث إلى نور", locked: "ليس بعد",
      liftoff: "انطلاق", rank: "رتبتك", trustL: "ثقة الطاقم", readyL: "جاهزية الإطلاق", crewL: "أفراد قادرون على مساعدة غيرهم",
      excluded: "نتائج اللعبة للمتعة فقط، وليست جزءاً من تقييمك.", cont: "متابعة", realTitle: "سؤالان عن عملك الفعلي",
      realTip: "أجب في بضع جمل. الأمثلة المحددة هي الأكثر فائدة.", submit: "إرسال", thanks: "شكراً لك. انتهيت.",
      thanksText: "إجاباتك محفوظة، وسيتواصل معك مسؤول التغيير في المنصات الرقمية المشتركة. يمكنك إغلاق هذه الصفحة.", timeUp: "انتهى الوقت. شكراً لك: كل ما قمت به محفوظ.",
      conn: "مشكلة في الاتصال. تقدّمك محفوظ؛ تحقق من الاتصال وحاول مجدداً.", you: "أنت", tapBriefing: "قاعة الإحاطة",
      noorDone: "انتهى فحص نور.", here: "هنا", unanswered: "نداءات منتظرة" },
  };
  const t = (k) => T[lang][k];

  // ===================================================================== audio
  const A = {
    on: store.get("lw-sound", "on") === "on", music: null, musicName: null, voice: new Audio(), queue: [], playing: false, onDone: null, timer: null,
    vol: () => (A.playing ? 0.1 : 0.3),
    unlock() { if (ui.unlocked) return; ui.unlocked = true; try { const a = new Audio("/static/launch/sfx/ui.mp3"); a.volume = 0.01; a.play().catch(() => {}); } catch (e) { /* ignore */ } },
    playMusic(name) {
      if (name === A.musicName) return;
      const old = A.music;
      if (old) A.fade(old, 0, 900, () => old.pause());
      A.musicName = name; A.music = null;
      if (!name) return;
      const a = new Audio(`/static/launch/music/${name}.mp3`);
      a.loop = true; a.volume = 0; A.music = a;
      if (A.on) a.play().catch(() => {});
      A.fade(a, A.vol(), 1400);
    },
    fade(a, to, ms, done) {
      const from = a.volume, t0 = performance.now();
      const step = (now) => { const k = Math.min(1, (now - t0) / ms); a.volume = Math.max(0, Math.min(1, from + (to - from) * k)); if (k < 1) requestAnimationFrame(step); else if (done) done(); };
      requestAnimationFrame(step);
    },
    sfx(name) { if (!A.on || !name) return; const a = new Audio(`/static/launch/sfx/${name}.mp3`); a.volume = name === "ignition" ? 1 : 0.65; a.play().catch(() => {}); },
    say(ids, done) {
      A.queue.push(...ids.filter((id) => S && S.lines[id]));
      if (done) A.onDone = done;
      if (!A.playing) A.next();
      else if (!A.queue.length && done) { /* finishes with current line */ }
    },
    next() {
      clearTimeout(A.timer);
      const id = A.queue.shift();
      if (!id) {
        A.playing = false; hideCaption();
        if (A.music) A.fade(A.music, A.vol(), 600);
        const d = A.onDone; A.onDone = null; if (d) d();
        return;
      }
      A.playing = true; showCaption(id);
      if (A.music) A.fade(A.music, A.vol(), 400);
      const fallback = () => { A.timer = setTimeout(A.next, Math.max(2600, (S.lines[id].text || "").length * 60)); };
      if (!A.on) return fallback();
      A.voice.src = `/static/launch/vo/${lang}/${id}.mp3`;
      A.voice.onended = () => { A.timer = setTimeout(A.next, 350); };
      A.voice.onerror = fallback;
      A.voice.play().catch(fallback);
    },
    stop() { A.queue = []; clearTimeout(A.timer); A.voice.pause(); A.playing = false; A.onDone = null; hideCaption(); if (A.music) A.fade(A.music, A.vol(), 400); },
    toggle() {
      A.on = !A.on; store.set("lw-sound", A.on ? "on" : "off");
      if (A.on) { if (A.music) A.music.play().catch(() => {}); } else { if (A.music) A.music.pause(); A.voice.pause(); if (A.playing) A.next(); }
      drawTools();
    },
  };

  function showCaption(id) {
    const l = S && S.lines[id]; if (!l) return;
    $("lw-caption-who").textContent = l.name; $("lw-caption-text").textContent = l.text; $("lw-caption").hidden = false;
  }
  function hideCaption() { $("lw-caption").hidden = true; }

  // ===================================================================== server
  async function api(action, params) {
    if (busy && action !== "poll") return;
    if (action !== "poll") busy = true;
    try {
      const r = await fetch("/play/api", { method: "POST", headers: { "Content-Type": "application/json", "x-csrf": csrf },
        body: JSON.stringify({ action, params: params || {}, lang }) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { showError(data.error || t("conn")); return; }
      S = data; offset = Date.parse(S.now) - Date.now();
      if (S.error) showError(S.error);
      update();
    } catch (e) { showError(t("conn")); } finally { busy = false; }
  }
  const act = (action, params) => { A.sfx("ui"); return api(action, params); };

  function showError(msg) { const e = $("lw-error"); e.textContent = msg; e.hidden = false; clearTimeout(showError.t); showError.t = setTimeout(() => { e.hidden = true; }, 4500); }

  // ===================================================================== update cycle
  function update() {
    root.dir = lang === "ar" ? "rtl" : "ltr"; document.documentElement.lang = lang; document.documentElement.dir = root.dir;
    [...root.classList].filter((c) => c.startsWith("phase-")).forEach((c) => root.classList.remove(c));
    root.classList.add("phase-" + S.phase);
    root.classList.toggle("alert", S.phase === "act3"); root.classList.toggle("hold", S.phase === "act3");
    drawHud(); drawTools(); drawObjective(); handleFeedback();
    const key = JSON.stringify([S.phase, S.stage, S.lang, ui.loc, ui.scene, S.files_known, S.checklist_open, S.noor, S.calls && S.calls.map((c) => c.answered), S.alerts && S.alerts.map((a) => a.done),
      S.hamad, S.checklist, S.handover && 1, S.realwork && 1, S.finished, S.trust, S.ready, S.checks && S.checks.map((c) => c.answer)]);
    if (key !== lastKey) { lastKey = key; drawStage(); }
    handleCue();
  }

  function handleCue() {
    if (!S.cue || !ui.unlocked) return;
    if (lastCue === S.cue.seq) return;
    const first = lastCue === null; lastCue = S.cue.seq;
    if (S.cue.music !== undefined) A.playMusic(S.finished ? null : S.cue.music);
    if (!first) (S.cue.sfx || []).forEach((s, i) => setTimeout(() => A.sfx(s), i * 450));
    if (S.phase === "prologue" && !ui.seen.prologue) return openingShot();
    if (S.phase === "act3" && !ui.seen.act3 && !first) { ui.seen.act3 = true; alarmShot(); }
    if (S.phase === "launch" && !ui.seen.launch) return launchShot();
    A.stop(); A.say(S.cue.lines || []);
  }

  function handleFeedback() {
    const f = S.feedback;
    if (!f || f.seq === lastFb) return;
    const first = lastFb === null; lastFb = f.seq;
    if (first) return;
    const parts = [];
    for (const [k, v] of Object.entries(f.delta || {})) if (v) parts.push(`<span class="${v > 0 ? "up" : "down"}">${t(k)} ${v > 0 ? "+" : ""}${v}</span>`);
    if (!f.text && !parts.length) return;
    const el = $("lw-feedback");
    el.innerHTML = (f.text ? `<span>${esc(f.text)}</span>` : "") + (parts.length ? `<span class="d">${parts.join(" · ")}</span>` : "");
    el.hidden = true; void el.offsetWidth; el.hidden = false;
    for (const k of Object.keys(f.delta || {})) if (f.delta[k]) { const m = $("m-" + k); m.classList.remove("bump"); void m.offsetWidth; m.classList.add("bump"); }
  }

  // ===================================================================== HUD
  function setBg(name) {
    const el = $("lw-bg-img");
    if (el.dataset.want === name) return;
    el.dataset.want = name; el.classList.remove("on");
    const apply = () => { if (el.dataset.want !== name) return; el.style.backgroundImage = `url("${IMG(name)}")`; requestAnimationFrame(() => el.classList.add("on")); };
    if (el.style.backgroundImage) setTimeout(apply, 450); else apply();
  }
  function drawHud() {
    for (const k of ["trust", "ready"]) { const m = $("m-" + k); m.querySelector(".lbl").textContent = t(k); m.querySelector("i").style.width = S[k] + "%"; m.querySelector("b").textContent = S[k]; }
    const crew = S.crew || [];
    $("m-crew").innerHTML = `${esc(t("crew"))} <b>${crew.length}</b>` + crew.map((n) => AV[n] ? `<img src="${IMG(AV[n])}" alt="${esc(n)}">` : "").join("");
    const ck = $("m-check"); ck.innerHTML = `${esc(t("checklist"))} <b>${S.checklist_open}</b>`; ck.classList.toggle("hot", S.phase === "act4" && S.stage === "checklist");
    $("lw-t-label").textContent = t("tlabel");
  }
  function drawTools() {
    $("lw-whatnow").textContent = t("whatnow");
    const s = $("lw-sound"); s.textContent = A.on ? "🔊 " + t("soundOn") : "🔇 " + t("soundOff"); s.setAttribute("aria-pressed", String(A.on));
    $("lw-lang").textContent = t("langBtn");
  }
  function drawObjective() {
    $("lw-objective-text").textContent = S.objective || "";
    const ob = $("lw-objective"); if (drawObjective.last !== S.objective) { drawObjective.last = S.objective; ob.classList.remove("flash"); void ob.offsetWidth; ob.classList.add("flash"); }
  }

  function clockTick() {
    if (!S) return;
    const nowMs = Date.now() + offset;
    // in-game countdown: minutes from the server, seconds ticking for atmosphere
    const tb = $("lw-t");
    if (S.phase === "act3") tb.textContent = `${t("hold")} · T−18:00`;
    else if (["launch", "realwork", "done"].includes(S.phase)) tb.textContent = "T−00:00";
    else {
      if (clockTick.base !== S.t) { clockTick.base = S.t; clockTick.at = nowMs; }
      const el = Math.floor((nowMs - clockTick.at) / 1000), sec = 59 - (el % 60);
      tb.textContent = `T−${String(Math.max(0, S.t - 1)).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
    }
    // stage timer ring
    const tm = $("lw-timer");
    if (S.deadline && !S.finished) {
      const left = Math.max(0, (Date.parse(S.deadline) - nowMs) / 1000), total = S.stage_seconds || 60;
      tm.hidden = false; $("lw-timer-s").textContent = Math.ceil(left);
      $("lw-ring").style.strokeDashoffset = String(97.4 * (1 - left / total));
      tm.classList.toggle("low", left <= 10);
      if (left <= 0 && expiredFor !== S.deadline) { expiredFor = S.deadline; setTimeout(() => api("poll"), 600); }
      if (left > 0 && left <= 10 && Math.ceil(left) !== clockTick.lastBeat) { clockTick.lastBeat = Math.ceil(left); if (left <= 5) A.sfx("heartbeat"); }
    } else tm.hidden = true;
  }

  // ===================================================================== stage
  function drawStage() {
    const st = $("lw-stage");
    const ph = S.phase;
    const bg = { act1: "briefing", act3: "control" }[ph] || "pad";
    setBg(bg);
    let html = "";
    if (S.finished && ph === "done" && S.end_reason === "time") html = panelMsg(t("timeUp"), "");
    else if (ph === "intro") html = introHtml();
    else if (ph === "prologue") html = ui.seen.prologue ? mapHtml() : "";
    else if (ph === "act1") html = briefingHtml();
    else if (ph === "act2") html = ui.scene === "noor" ? noorHtml() : mapHtml() + sheetHtml();
    else if (ph === "act3") html = act3Html();
    else if (ph === "act4") html = S.stage === "checklist" ? checklistHtml() : radioHtml();
    else if (ph === "epilogue") html = handoverHtml();
    else if (ph === "launch") html = ui.seen.launchDone ? resultsHtml() : "";
    else if (ph === "realwork") html = realworkHtml();
    else if (ph === "done") html = panelMsg(t("thanks"), t("thanksText"));
    st.innerHTML = html;
    wire(st);
    typeLines(st);
  }

  const opts = (list, action, extra) => `<div class="opts">${list.map(([k, txt], i) =>
    `<button class="opt" type="button" data-act="${action}" data-choice="${esc(k)}"${extra ? ` data-extra="${esc(extra)}"` : ""}><span class="k">${String.fromCharCode(65 + i)}</span>${esc(txt)}</button>`).join("")}</div>`;
  const ownWords = (action) => `<form class="own" data-own="${action}"><input type="text" maxlength="600" placeholder="${esc(t("own"))}" aria-label="${esc(t("own"))}"><button class="btn ghost" type="submit">${esc(t("send"))}</button></form>`;
  const panelMsg = (h, p) => `<div class="title-card"><div class="inner panel rise"><h2>${esc(h)}</h2>${p ? `<p class="muted">${esc(p)}</p>` : ""}</div></div>`;
  const speaker = (key, name) => `<div class="speaker">${key ? `<img src="${IMG("av_" + key)}" alt="">` : ""}<div><b>${esc(name)}</b></div></div>`;

  function introHtml() {
    const resume = S.phase !== "intro";
    return `<div class="title-card"><div class="inner">
      <h1>LAUNCH WINDOW</h1><div class="ar-title">نافذة الإطلاق</div>
      <p class="tag">${esc(t("tagline"))}<br><span class="small">${esc(t("headphones"))}</span></p>
      <div class="row"><button class="btn" type="button" data-act="begin">${esc(resume ? t("resume") : t("start"))}</button>
      <button class="btn ghost" type="button" data-test-sound>${esc(t("testSound"))}</button></div></div></div>`;
  }

  // ---------------------------------------------------------------- map (prologue + act II)
  function mapHtml() {
    const ph = S.phase, calls = S.calls || [];
    const pins = Object.entries(LOC_POS).map(([k, [x, y]]) => {
      let cls = "", count = 0, label = S.locations[k];
      if (ph === "prologue") cls = k === "briefing" ? "goal" : "locked";
      else {
        const open = calls.filter((c) => c.loc === k && !c.answered && !c.locked).length + (k === "fuel" && !S.noor_done ? 1 : 0);
        count = open;
        if (k === "control") cls = S.noor_done ? "goal" : "locked";
        else if (k === "pad") cls = "locked";
        else if (k === "briefing") cls = "done";
        else cls = open ? "task" : (calls.some((c) => c.loc === k) ? "done" : "");
      }
      return `<button class="hot ${cls}" type="button" style="left:${x}%;top:${y}%" data-loc="${k}" ${cls === "locked" ? 'aria-disabled="true"' : ""}>
        <span class="pin"></span><span class="tag">${esc(label)}</span>${count ? `<span class="count">${count}</span>` : ""}</button>`;
    }).join("");
    return `<div class="map-wrap rise"><img src="${IMG("map")}" alt="">${pins}</div>`;
  }

  function sheetHtml() {
    if (!ui.loc) return "";
    const k = ui.loc, calls = (S.calls || []).filter((c) => c.loc === k);
    let body = "";
    if (k === "control") {
      const waiting = (S.calls || []).filter((c) => !c.answered).length;
      body = `<p>${esc(S.objective)}</p>${waiting ? `<p class="muted small">${esc(t("goWarn"))} (${waiting})</p>` : ""}<button class="btn" type="button" data-act="to_control">${esc(t("goControl"))}</button>`;
    } else {
      if (k === "fuel" && !S.noor_done) body += `<div class="callcard"><div class="who">${esc(S.lines.NO1.name)}</div><p class="small">${esc(S.lines.NO1.text)}</p><button class="btn" type="button" data-scene="noor">${esc(t("noorBtn"))}</button></div>`;
      for (const c of calls) {
        if (c.locked) continue;
        body += `<div class="callcard ${c.answered ? "done" : ""}"><div class="who">${esc(c.who)}</div><p>${esc(c.text)}</p>${c.answered ? "" : opts(c.options, "call", c.id)}</div>`;
      }
      if (!body) body = `<p class="muted">${esc(t("noorDone"))}</p>`;
    }
    return `<aside class="sheet panel" aria-label="${esc(S.locations[k])}"><button class="btn ghost close" type="button" data-close>${esc(t("close"))}</button>
      <div class="eyebrow">${esc(t("here"))}</div><h2>${esc(S.locations[k])}</h2>${body}</aside>`;
  }

  // ---------------------------------------------------------------- Act I
  function briefingHtml() {
    const n = S.files.filter((f) => f.body).length, full = n >= 4;
    const files = S.files.map((f) => f.body
      ? `<div class="file open"><span class="fid">${esc(f.id)}</span><h4>${esc(f.title)}</h4><p>${esc(f.body)}</p></div>`
      : `<button class="file ${full ? "dim" : ""}" type="button" data-act="open_file" data-id="${esc(f.id)}" ${full ? "disabled" : ""}><span class="fid">${esc(f.id)}</span><h4>${esc(f.title)}</h4></button>`).join("");
    const checks = S.checks.map((q) => `<div class="q"><p>${esc(q.q)}</p>${q.answer ? `<div class="opt" aria-pressed="true">${esc((q.options.find((o) => o[0] === q.answer) || ["", ""])[1])}</div>` : opts(q.options, "answer", q.id)}</div>`).join("");
    return `<div class="brief"><section class="panel rise"><div class="row" style="justify-content:space-between"><h2>${esc(t("files"))}</h2><span class="counter">${esc(t("opened")(n))}</span></div>
      <p class="muted small">${esc(t("filesTip"))}</p><div class="files">${files}</div></section>
      <section class="panel rise checks"><h2>${esc(t("checks"))}</h2>${checks}</section></div>`;
  }

  // ---------------------------------------------------------------- Act II: Noor
  function noorHtml() {
    const n = S.noor;
    let inner;
    if (!n) inner = `<p class="line">${esc(t("noorDone"))}</p><button class="btn" type="button" data-scene="">${esc(t("backMap"))}</button>`;
    else {
      const line = n.line ? S.lines[n.line].text : "";
      inner = `${speaker("noor", S.lines.NO1.name)}${line ? `<p class="line" data-type="${esc(n.line)}">${esc(line)}</p>` : ""}${n.say ? `<p class="say">${esc(n.say)}</p>` : ""}
        ${opts(n.options, "noor")}${n.step !== "n2b" ? ownWords("noor") : ""}${n.hint ? `<div class="hint"><b>F6</b> ${esc(n.hint)}</div>` : ""}`;
    }
    return `<div class="scene rise"><img src="${IMG("noor")}" alt=""><div class="dlg panel">${inner}</div></div>`;
  }

  // ---------------------------------------------------------------- Act III
  function act3Html() {
    if (S.stage === "director") {
      return `<div class="scene rise"><img src="${IMG("saeed")}" alt=""><div class="dlg panel">${speaker("saeed", S.lines.S01.name)}
        <p class="line" data-type="S01">${esc(S.lines.S01.text)}</p>${opts(S.director, "director")}
        <label for="dir-text" class="small" style="margin-top:12px">${esc(t("directorPrompt"))}</label><textarea id="dir-text" maxlength="600" style="min-height:64px"></textarea>
        ${S.director_hint ? `<div class="hint"><b>F4</b> ${esc(S.director_hint)}</div>` : ""}</div></div>`;
    }
    if (S.stage === "w3") {
      return `<div class="board rise"><div class="head"><h2>${esc(t("board"))}</h2><span class="counter">${esc(t("wave")(3))} · ${esc(t("choose1"))}</span></div>
        <div class="choose2">${S.priority.map(([k, txt]) => `<button class="opt" type="button" data-act="priority" data-choice="${esc(k)}">${esc(txt)}</button>`).join("")}</div></div>`;
    }
    const wave = S.stage === "w1" ? 1 : 2;
    const stations = S.stations.map(([k, n]) => `<option value="${esc(k)}">${esc(n)}</option>`).join("");
    const cards = (S.alerts || []).map((a) => {
      let acts = "";
      if (!a.done) {
        if (a.special) acts = opts(a.special, "alert", a.id) + (a.hint ? `<div class="hint"><b>F2</b> ${esc(a.hint)}</div>` : "");
        else acts = `<div class="acts">${a.actions.filter(([k]) => k !== "route").map(([k, txt]) => `<button class="opt" type="button" data-act="alert" data-extra="${esc(a.id)}" data-choice="${esc(k)}">${esc(txt)}</button>`).join("")}
          <span class="row"><select aria-label="${esc(t("routeTo"))}" data-route-for="${esc(a.id)}"><option value="">${esc(t("routeTo"))}</option>${stations}</select>
          <button class="opt" type="button" data-route="${esc(a.id)}">${esc(t("route"))}</button></span></div>`;
      }
      return `<article class="alert ${a.done ? "done" : ""}"><span class="code">${esc(a.id)}${a.done ? " · ✓" : ""}</span><p>${esc(a.text)}</p>${acts}</article>`;
    }).join("");
    const auto = (S.auto || []).map((x) => `<div class="auto">${esc(x)}</div>`).join("");
    return `<div class="board"><div class="head"><h2>${esc(t("board"))}</h2><span class="counter">${esc(t("wave")(wave))}</span></div>${auto}<div class="alerts">${cards}</div></div>`;
  }

  // ---------------------------------------------------------------- Act IV
  function radioHtml() {
    const h = S.hamad;
    if (!h) return "";
    const lights = h.step === "h4" ? '<i class="b"></i><i class="g"></i><i class="r"></i>' : '<i class="b"></i><i class="a"></i><i class="r"></i>';
    const manual = h.manual.split(/(?=\s\d\.\s)/).map((s) => s.trim().replace(/^\d\.\s*/, "")).filter(Boolean).map((s) => `<li>${esc(s)}</li>`).join("");
    const line = h.line ? `<p class="line" data-type="${esc(h.line)}">${esc(S.lines[h.line].text)}</p>` : (h.asked && h.step === "h2" ? `<p class="line">${esc(S.lines.H02.text)}</p>` : "");
    return `<div class="radio"><aside class="panel manual rise"><div class="eyebrow">${esc(t("manual"))}</div><h3>${esc((S.lang === "ar") ? "دليل لوحة الصمامات" : "Valve panel guide")}</h3><ol>${manual}</ol>
        ${h.asked ? `<div class="panel-lights" aria-hidden="true">${lights}</div>` : ""}</aside>
      <div class="scene rise"><img src="${IMG("hamad")}" alt=""><div class="dlg panel"><div class="eyebrow">${esc(t("radio"))}</div>${speaker("hamad", S.lines.H01.name)}
        ${line}${opts(h.options, "hamad")}${h.step !== "h2" ? ownWords("hamad") : ""}${h.hint ? `<div class="hint"><b>F8</b> ${esc(h.hint)}</div>` : ""}</div></div></div>`;
  }

  function checklistHtml() {
    const c = S.checklist;
    const bar = Array.from({ length: 5 }, (_, i) => `<i class="${i < 5 - c.budget ? "used" : ""}"></i>`).join("");
    const items = c.items.map((p) => `<div class="promise rise"><div class="row" style="justify-content:space-between"><b>${esc(p.text)}</b><span class="st ${p.status}">${esc(t("st")[p.status])}</span></div>
      ${p.status === "open" ? `<div class="row">${c.actions.map(([k, txt]) => `<button class="opt" type="button" data-act="promise" data-extra="${esc(p.id)}" data-choice="${esc(k)}">${esc(txt)}</button>`).join("")}</div>` : ""}</div>`).join("");
    return `<div class="checklist"><div class="panel rise"><div class="row" style="justify-content:space-between"><h2>${esc(t("checkTitle"))}</h2><span class="row small">${esc(t("workLeft"))} <span class="budget">${bar}</span></span></div></div>
      ${items}<div class="row"><button class="btn ghost" type="button" data-act="close_checklist">${esc(t("done"))}</button></div></div>`;
  }

  // ---------------------------------------------------------------- epilogue
  function handoverHtml() {
    const h = S.handover;
    const picks = h.actions.map(([k, txt]) => `<button class="opt" type="button" data-pick="${esc(k)}" aria-pressed="${ui.picks.has(k)}">${esc(txt)}</button>`).join("");
    return `<div class="epi"><div class="scene rise"><img src="${IMG("maryam")}" alt=""><div class="dlg panel">${speaker("maryam", S.lines.M02.name)}<p class="line" data-type="M02">${esc(S.lines.M02.text)}</p></div></div>
      <div class="handover panel rise"><h2>${esc(t("handTitle"))}</h2><div class="row" style="justify-content:space-between"><b>${esc(t("pick3"))}</b><span class="counter" id="pick-n">${ui.picks.size} / 3</span></div>
      <div class="picks">${picks}</div><label for="ho-note">${esc(t("noteLabel"))}</label><p class="muted small" style="margin:0 0 6px">${esc(h.prompt)}</p>
      <textarea id="ho-note" maxlength="2000">${esc(ui.typed.note || "")}</textarea><div class="row"><button class="btn" type="button" data-handover>${esc(t("handGo"))}</button></div></div></div>`;
  }

  function resultsHtml() {
    const r = S.result;
    const lineup = (r.crew_names || []).map((n, i) => `<figure style="animation-delay:${1 + i * 0.25}s">${AV[n] ? `<img src="${IMG(AV[n])}" alt="">` : `<span class="ini" aria-hidden="true">${esc(n[0])}</span>`}<figcaption>${esc(n)}</figcaption></figure>`).join("");
    return `<div class="results"><div class="eyebrow">${esc(t("liftoff"))}</div><h2>${esc(r.ending)}</h2>
      <div class="rank">${esc(t("rank"))}: ${esc(r.rank)}</div>
      <div class="stats"><div><b data-count="${r.trust}">0</b>${esc(t("trustL"))}</div><div><b data-count="${r.ready}">0</b>${esc(t("readyL"))}</div><div><b data-count="${r.crew}">0</b>${esc(t("crewL"))}</div></div>
      <div class="lineup">${lineup}</div><p class="note-excl">${esc(t("excluded"))}</p><button class="btn" type="button" data-act="continue">${esc(t("cont"))}</button></div>`;
  }

  function realworkHtml() {
    const qs = S.realwork.map(([k, q]) => `<div><label for="rw-${esc(k)}">${esc(q)}</label><textarea id="rw-${esc(k)}" maxlength="3000">${esc(ui.typed[k] || "")}</textarea></div>`).join("");
    return `<div class="handover panel rise"><div class="eyebrow">LAUNCH WINDOW · ${esc(t("done"))}</div><h2>${esc(t("realTitle"))}</h2><p class="muted small">${esc(t("realTip"))}</p>${qs}
      <div class="row"><button class="btn" type="button" data-realwork>${esc(t("submit"))}</button></div></div>`;
  }

  // ===================================================================== interaction
  function wire(st) {
    st.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", () => {
      const a = b.dataset.act, choice = b.dataset.choice, extra = b.dataset.extra;
      if (a === "begin") { A.unlock(); if (S.phase === "intro") return act("begin"); lastCue = null; root.classList.remove("cine"); return update(); }
      if (a === "open_file") { A.sfx("file"); return api("open_file", { id: b.dataset.id }); }
      if (a === "answer") return act("answer", { q: extra, choice });
      if (a === "call") return act("call", { id: extra, choice });
      if (a === "noor") return act("noor", { choice });
      if (a === "alert") return act("alert", { id: extra, choice });
      if (a === "director") return act("director", { choice, text: ($("dir-text") || {}).value || "" });
      if (a === "hamad") return act("hamad", { choice });
      if (a === "promise") return act("promise", { id: extra, choice });
      if (a === "to_control") { ui.loc = null; return act("to_control"); }
      return act(a, choice ? { choice } : {});
    }));
    st.querySelectorAll("[data-route]").forEach((b) => b.addEventListener("click", () => {
      const id = b.dataset.route, sel = st.querySelector(`[data-route-for="${id}"]`);
      if (!sel || !sel.value) { sel && sel.focus(); return showError(t("routeTo")); }
      act("alert", { id, choice: "route", station: sel.value });
    }));
    st.querySelectorAll("form[data-own]").forEach((f) => f.addEventListener("submit", (e) => {
      e.preventDefault(); const v = f.querySelector("input").value.trim(); if (!v) return;
      act(f.dataset.own, { text: v });
    }));
    st.querySelectorAll("[data-loc]").forEach((b) => b.addEventListener("click", () => {
      const k = b.dataset.loc;
      if (b.getAttribute("aria-disabled") === "true") return showError(t("locked"));
      A.sfx("ui");
      if (S.phase === "prologue") { if (k === "briefing") act("travel", { to: "briefing" }); return; }
      if (k === "fuel" && !S.noor_done) { ui.scene = "noor"; ui.loc = null; lastKey = ""; return update(); }
      ui.loc = k; lastKey = ""; update();
    }));
    st.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => { ui.loc = null; lastKey = ""; update(); }));
    st.querySelectorAll("[data-scene]").forEach((b) => b.addEventListener("click", () => { ui.scene = b.dataset.scene || null; ui.loc = null; lastKey = ""; update(); }));
    st.querySelectorAll("[data-pick]").forEach((b) => b.addEventListener("click", () => {
      const k = b.dataset.pick;
      if (ui.picks.has(k)) ui.picks.delete(k); else if (ui.picks.size < 3) ui.picks.add(k); else return showError(t("pick3"));
      b.setAttribute("aria-pressed", String(ui.picks.has(k))); $("pick-n").textContent = `${ui.picks.size} / 3`; A.sfx("ui");
    }));
    const note = $("ho-note"); if (note) note.addEventListener("input", () => { ui.typed.note = note.value; });
    st.querySelectorAll("textarea[id^='rw-']").forEach((ta) => ta.addEventListener("input", () => { ui.typed[ta.id.slice(3)] = ta.value; }));
    const ho = st.querySelector("[data-handover]");
    if (ho) ho.addEventListener("click", () => act("handover", { actions: [...ui.picks], note: ($("ho-note").value || "").trim() }));
    const rw = st.querySelector("[data-realwork]");
    if (rw) rw.addEventListener("click", () => act("realwork", Object.fromEntries(S.realwork.map(([k]) => [k, ($("rw-" + k).value || "").trim()]))));
    const ts = st.querySelector("[data-test-sound]");
    if (ts) ts.addEventListener("click", () => { A.unlock(); const a = new Audio("/static/launch/sfx/success.mp3"); a.play().catch(() => {}); });
    st.querySelectorAll("[data-count]").forEach((el) => countUp(el, +el.dataset.count));
  }

  function typeLines(st) {
    st.querySelectorAll("[data-type]").forEach((p) => {
      const id = p.dataset.type; if (reduced || ui.typed["line:" + id]) return;
      ui.typed["line:" + id] = 1;
      const full = p.textContent; p.textContent = ""; let i = 0;
      const step = () => { i += 2; p.textContent = full.slice(0, i); if (i < full.length) setTimeout(step, 18); };
      step();
    });
  }

  function countUp(el, to) {
    const t0 = performance.now();
    const step = (now) => { const k = Math.min(1, (now - t0) / 1400); el.textContent = Math.round(to * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }

  // ===================================================================== cinematics
  const fx = { c: $("lw-fx"), parts: [], on: false, mode: null };
  function fxStart(mode) {
    fx.mode = mode; if (fx.on || reduced) return; fx.on = true;
    const ctx = fx.c.getContext("2d");
    const loop = () => {
      if (!fx.on) return;
      const w = fx.c.width = fx.c.clientWidth, h = fx.c.height = fx.c.clientHeight;
      ctx.clearRect(0, 0, w, h);
      const ex = w * 0.5, ey = h * (fx.mode === "launch" ? 0.8 : 0.78);
      const n = fx.mode === "launch" ? 14 : 2;
      for (let i = 0; i < n; i++) fx.parts.push({ x: ex + (Math.random() - 0.5) * 30, y: ey, vx: (Math.random() - 0.5) * (fx.mode === "launch" ? 7 : 0.6), vy: -Math.random() * (fx.mode === "launch" ? 3 : 0.6), r: 6 + Math.random() * 14, life: 1 });
      fx.parts = fx.parts.filter((p) => p.life > 0).slice(-900);
      for (const p of fx.parts) {
        p.x += p.vx; p.y += p.vy; p.r *= 1.012; p.life -= fx.mode === "launch" ? 0.008 : 0.006;
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r);
        const hot = fx.mode === "launch" && p.life > 0.8;
        g.addColorStop(0, hot ? `rgba(255,220,160,${p.life})` : `rgba(210,225,255,${p.life * 0.35})`);
        g.addColorStop(1, "rgba(200,215,255,0)");
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill();
      }
      if (fx.mode === "launch") { const g = ctx.createRadialGradient(ex, ey, 0, ex, ey, h * 0.35); g.addColorStop(0, "rgba(255,190,120,.55)"); g.addColorStop(1, "rgba(255,120,60,0)"); ctx.fillStyle = g; ctx.fillRect(0, 0, w, h); }
      requestAnimationFrame(loop);
    };
    loop();
  }
  function fxStop() { fx.on = false; fx.parts = []; const ctx = fx.c.getContext("2d"); ctx.clearRect(0, 0, fx.c.width, fx.c.height); }

  function skipBtn(onSkip) {
    const b = document.createElement("button"); b.className = "btn ghost"; b.type = "button"; b.textContent = t("skip");
    b.style.cssText = "position:fixed;z-index:35;bottom:110px;inset-inline-end:24px";
    b.addEventListener("click", () => { b.remove(); onSkip(); }); document.body.appendChild(b); return b;
  }

  function openingShot() {
    ui.seen.prologue = true;
    setBg("pad"); root.classList.add("cine"); fxStart("steam");
    setTimeout(() => root.classList.add("lights"), 900);
    let ended = false;
    const end = () => { if (ended) return; ended = true; sk.remove(); A.stop(); root.classList.remove("cine", "lights"); fxStop(); lastKey = ""; update(); };
    const sk = skipBtn(end);
    A.stop(); A.say(["N01"], () => setTimeout(end, 900));
  }

  function alarmShot() {
    if (!reduced) { root.classList.add("shake"); setTimeout(() => root.classList.remove("shake"), 1600); }
  }

  function launchShot() {
    ui.seen.launch = true;
    root.classList.add("cine"); setBg("pad"); A.stop();
    const cd = document.createElement("div"); cd.className = "countdown"; document.body.appendChild(cd);
    let n = 10, finished = false;
    const done = () => {
      if (finished) return; finished = true; sk.remove(); cd.remove(); clearInterval(iv);
      setTimeout(() => { root.classList.remove("cine", "liftoff"); fxStop(); ui.seen.launchDone = true; lastKey = ""; update(); A.sfx("rankup"); }, 300);
    };
    const sk = skipBtn(done);
    A.say(["N11"]);
    const iv = setInterval(() => {
      if (n > 0) { cd.innerHTML = `<b>${n}</b>`; n--; return; }
      clearInterval(iv); cd.innerHTML = "";
      const f = document.createElement("div"); f.className = "lw-flash"; document.body.appendChild(f); setTimeout(() => f.remove(), 1500);
      A.sfx("ignition"); fxStart("launch"); root.classList.add("liftoff", "shake");
      setTimeout(() => root.classList.remove("shake"), 1600);
      setTimeout(done, 7000);
    }, 900);
  }

  // ===================================================================== tools + boot
  $("lw-sound").addEventListener("click", () => A.toggle());
  $("lw-lang").addEventListener("click", () => { lang = lang === "ar" ? "en" : "ar"; store.set("lw-lang", lang); A.stop(); lastKey = ""; api("poll"); });
  $("lw-whatnow").addEventListener("click", () => {
    A.unlock(); const ob = $("lw-objective"); ob.classList.remove("flash"); void ob.offsetWidth; ob.classList.add("flash");
    if (S && S.objective_line) { A.stop(); A.say([S.objective_line]); }
  });
  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, textarea, select")) return;
    const k = e.key.toUpperCase(); if (k.length !== 1 || k < "A" || k > "F") return;
    const b = $("lw-stage").querySelectorAll(".opts .opt")[k.charCodeAt(0) - 65]; if (b) b.click();
  });

  setInterval(clockTick, 250);
  setInterval(() => { if (S && !S.finished && S.phase !== "intro") api("poll"); }, 6000);

  (async function boot() {
    await api("poll");
    if (S && S.phase !== "intro" && !S.finished) {
      // A saved game: one click to resume (browsers only play sound after a click).
      root.classList.add("cine");
      const st = $("lw-stage");
      st.innerHTML = `<div class="title-card"><div class="inner"><h1>LAUNCH WINDOW</h1><div class="ar-title">نافذة الإطلاق</div><p class="tag">${esc(t("resumeText"))}</p>
        <div class="row"><button class="btn" type="button" id="lw-resume">${esc(t("resume"))}</button></div></div></div>`;
      $("lw-resume").addEventListener("click", () => {
        A.unlock(); root.classList.remove("cine");
        if (S.phase === "prologue") ui.seen.prologue = false;
        if (S.phase === "launch") { ui.seen.launch = true; ui.seen.launchDone = true; }
        ui.seen.act3 = true; lastCue = null; lastKey = ""; update();
      });
    } else if (S && S.phase === "intro") {
      lastCue = S.cue ? S.cue.seq : null;
    }
  })();
  document.addEventListener("click", () => { if (!ui.unlocked) A.unlock(); }, { once: true });
})();
