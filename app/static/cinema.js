/* Cinematic touches for the CDP Champion Selection tool. Everything here is optional decoration:
   the pages work fully without it, and it does nothing for people who prefer reduced motion. */
(function () {
  "use strict";
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (calm) return;

  // KPI figures count up from zero when the page opens
  document.querySelectorAll(".stat .n").forEach((el, i) => {
    const target = parseInt(el.textContent.replace(/[^0-9]/g, ""), 10);
    if (!Number.isFinite(target) || target === 0 || /[^0-9\s]/.test(el.textContent.trim())) return;
    const start = performance.now() + i * 70, dur = 900 + Math.min(target, 200) * 3;
    el.textContent = "0";
    const tick = (now) => {
      const t = Math.min(1, Math.max(0, (now - start) / dur));
      el.textContent = String(Math.round(target * (1 - Math.pow(1 - t, 3))));
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  // glow follows the cursor across glass surfaces
  document.addEventListener("pointermove", (e) => {
    const el = e.target.closest && e.target.closest(".card, .stat, .init-row, .choice");
    if (!el) return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  }, { passive: true });

})();
