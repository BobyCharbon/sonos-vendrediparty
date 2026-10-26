// Contrôles segmentés (.seg) façon iOS : la pastille du choix glisse avec un ressort vers le bouton touché,
// en partant de là où elle est (un second toucher en plein vol la redirige sans saut).
// Seuls les segments sur une ligne sont concernés ; les autres gardent leur fond par bouton.
(function () {
  const M = window.Motion;
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const state = new WeakMap();   // seg → { thumb, x, anim }
  const watched = new WeakSet();

  function buttons(seg) { return [...seg.children].filter((el) => el.tagName === "BUTTON"); }
  function oneRow(btns) { return btns.length > 1 && btns.every((b) => b.offsetTop === btns[0].offsetTop); }

  function place(seg, animate) {
    const btns = buttons(seg), on = btns.find((b) => b.classList.contains("on"));
    if (!on || !seg.offsetWidth || !oneRow(btns)) { seg.classList.remove("seg-glide"); return; }
    let s = state.get(seg);
    if (!s || !s.thumb.isConnected) {
      const thumb = document.createElement("i");
      thumb.className = "seg-thumb";
      thumb.setAttribute("aria-hidden", "true");
      seg.append(thumb);
      s = { thumb, x: null, anim: null };
      state.set(seg, s);
    }
    seg.classList.add("seg-glide");
    s.thumb.style.width = `${on.offsetWidth}px`;
    const to = on.offsetLeft, move = (x) => { s.x = x; s.thumb.style.transform = `translate3d(${x}px,0,0)`; };
    s.anim?.stop();
    s.anim = null;
    if (!animate || s.x === null || reduceMotion.matches) return move(to);
    s.anim = M.spring({ from: s.x, to, response: 0.32, damping: 1, onUpdate: move, onDone: () => { s.anim = null; } });
  }

  function watch(seg) {
    if (watched.has(seg)) return;
    watched.add(seg);
    // Affiché, redimensionné, ou bouton déplacé par un nouveau rendu : on recale sans animer.
    if ("ResizeObserver" in window) new ResizeObserver(() => place(seg, false)).observe(seg);
    new MutationObserver((records) => {
      if (records.some((r) => [...r.addedNodes].some((n) => n.tagName === "BUTTON"))) place(seg, false);
    }).observe(seg, { childList: true });
    place(seg, false);
  }

  // Le gestionnaire du segment change la classe « on » au clic : on fait glisser la pastille juste après.
  addEventListener("click", (ev) => {
    const seg = ev.target.closest?.(".seg");
    if (seg) requestAnimationFrame(() => place(seg, true));
  });
  const scan = () => document.querySelectorAll(".seg").forEach(watch);
  let queued = false;
  new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; scan(); });
  }).observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", scan, { once: true });
  else scan();

  window.Segmented = { refresh: (seg) => place(seg, true) };
})();
