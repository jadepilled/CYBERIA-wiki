// The cursor is the light. Every [data-light] element is shaded from the cursor's direction: its lit side faces the
// cursor wherever it is, and the glow strengthens as the cursor comes close. Without a fine pointer, or after it rests,
// the light wanders slowly so the page keeps a little life.
(() => {
  const root = document.documentElement;
  const lit = [...document.querySelectorAll("[data-light]")];
  const fine = matchMedia("(pointer: fine)").matches;
  let x = innerWidth * 0.5, y = innerHeight * 0.4, tx = x, ty = y, raf = 0, lastMove = 0, idle = !fine;
  const paint = () => {
    root.style.setProperty("--mx", `${x.toFixed(1)}px`); root.style.setProperty("--my", `${y.toFixed(1)}px`);
    for (const el of lit) {
      const r = el.getBoundingClientRect();
      if (!r.width) continue;
      const dx = x - (r.left + r.width / 2), dy = y - (r.top + r.height / 2), dist = Math.hypot(dx, dy);
      const reach = Math.hypot(r.width, r.height) / 2;            // centre to corner
      const radius = dist + reach;                                 // the far corner sits at the gradient's end
      el.style.setProperty("--lx", `${(x - r.left).toFixed(1)}px`);
      el.style.setProperty("--ly", `${(y - r.top).toFixed(1)}px`);
      el.style.setProperty("--lr", `${radius.toFixed(0)}px`);
      // full light up to the text's near edge, then it falls off towards the far edge: lit from the cursor's side
      el.style.setProperty("--ln", `${Math.max(0, Math.min(90, (dist - reach) / radius * 100)).toFixed(1)}%`);
      el.style.setProperty("--li", (0.5 + 0.5 * Math.max(0, 1 - dist / 1200)).toFixed(3)); // never dark, brighter up close
    }
  };
  const tick = (t) => {
    raf = 0;
    if (idle || t - lastMove > 4000) {           // resting cursor: drift the light in a slow figure
      const k = t / 1000;
      tx = innerWidth * (0.5 + 0.36 * Math.sin(k * 0.21)); ty = innerHeight * (0.45 + 0.3 * Math.sin(k * 0.13 + 1.3));
    }
    x += (tx - x) * 0.12; y += (ty - y) * 0.12;
    paint();
    raf = requestAnimationFrame(tick);
  };
  if (fine) addEventListener("pointermove", (e) => { tx = e.clientX; ty = e.clientY; lastMove = performance.now(); }, { passive: true });
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches || fine) raf = requestAnimationFrame(tick);
  else paint();
})();
