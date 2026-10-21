// Release countdown: 1 November 2026, 18:00 in Melbourne (AEDT, UTC+11). Shows 00:00:00 for a week after, then hides.
(() => {
  const el = document.getElementById("countdown");
  if (!el) return;
  const box = el.closest(".count") || el;
  const target = Date.parse(el.getAttribute("datetime") || "2026-11-01T07:00:00Z");
  const pad = (n) => String(n).padStart(2, "0");
  const tick = () => {
    const left = target - Date.now();
    if (left < -7 * 86400e3) { box.hidden = true; return; }
    box.hidden = false;
    if (left <= 0) { el.textContent = "00:00:00:00"; el.title = "Released"; return; }
    const s = Math.floor(left / 1000), d = Math.floor(s / 86400);
    el.textContent = `${pad(d)}:${pad(Math.floor(s % 86400 / 3600))}:${pad(Math.floor(s % 3600 / 60))}:${pad(s % 60)}`;
    setTimeout(tick, 1000 - (Date.now() % 1000));
  };
  tick();
})();
