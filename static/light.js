// The cursor is the light. Every [data-light] element is shaded from the cursor's direction: its lit side faces the
// cursor wherever it is, and the glow strengthens as the cursor comes close. Without a fine pointer, or after it rests,
// the light wanders slowly so the page keeps a little life.
(() => {
  const root = document.documentElement;
  const lit = [...document.querySelectorAll("[data-light]")];
  const fine = matchMedia("(pointer: fine)").matches;
  let x = innerWidth * 0.5, y = innerHeight * 0.4, tx = x, ty = y, raf = 0, lastMove = 0, idle = !fine;
  // The light is a direction first and a glow second. Direction (--la) always applies, so the lit side faces the
  // cursor even when it is off the window; its contrast (--li) and a very wide, soft glow (--gi) grow as it nears.
  const paint = () => {
    root.style.setProperty("--mx", `${x.toFixed(1)}px`); root.style.setProperty("--my", `${y.toFixed(1)}px`);
    for (const el of lit) {
      const r = el.getBoundingClientRect();
      if (!r.width) continue;
      const dx = x - (r.left + r.width / 2), dy = y - (r.top + r.height / 2), dist = Math.hypot(dx, dy);
      const near = Math.max(0, 1 - dist / 1500);                       // 1 at the text, 0 far away
      el.style.setProperty("--la", `${(Math.atan2(dx, -dy) * 180 / Math.PI).toFixed(1)}deg`);
      el.style.setProperty("--li", (0.22 + 0.5 * near).toFixed(3));   // directional contrast: faint far away, clear up close
      el.style.setProperty("--gi", (0.42 * near * near).toFixed(3));  // glow only once close, and soft even then
      el.style.setProperty("--gr", `${Math.round(1200 + Math.max(r.width, r.height))}px`);
      el.style.setProperty("--lx", `${(x - r.left).toFixed(1)}px`);
      el.style.setProperty("--ly", `${(y - r.top).toFixed(1)}px`);
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
  if (fine) {
    addEventListener("pointermove", (e) => { tx = e.clientX; ty = e.clientY; lastMove = performance.now(); }, { passive: true });
    document.addEventListener("pointerleave", (e) => {   // out of the window: carry the light on in the same direction
      const cx = innerWidth / 2, cy = innerHeight / 2, vx = e.clientX - cx, vy = e.clientY - cy, n = Math.hypot(vx, vy) || 1;
      tx = cx + vx / n * 2200; ty = cy + vy / n * 2200; lastMove = performance.now() + 20000;   // and hold it there a while
    });
  }
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches || fine) raf = requestAnimationFrame(tick);
  else paint();
})();
