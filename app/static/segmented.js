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
    const observers = [];
    const alive = () => {
      if (seg.isConnected) return true;
      observers.forEach((o) => o.disconnect());   // segment retiré par un nouveau rendu : on libère ses observateurs
      return false;
    };
    // Affiché ou redimensionné : on recale sans animer.
    if ("ResizeObserver" in window) {
      const resized = new ResizeObserver(() => alive() && place(seg, false));
      resized.observe(seg);
      observers.push(resized);
    }
    // Choix changé (au toucher ou par le code) : la pastille glisse ; boutons redessinés : elle se recale.
    const changed = new MutationObserver((records) => {
      if (!alive()) return;
      const redrawn = records.some((r) => [...r.addedNodes].some((n) => n.tagName === "BUTTON"));
      const chosen = records.some((r) => r.type === "attributes" && r.target.parentElement === seg);
      if (redrawn || chosen) place(seg, chosen && !redrawn);
    });
    changed.observe(seg, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
    observers.push(changed);
    place(seg, false);
  }

  const scan = () => document.querySelectorAll(".seg").forEach(watch);
  let queued = false;
  // Seuls les ajouts qui contiennent un segment comptent (les jeux redessinent leur écran chaque seconde).
  const bringsSeg = (n) => n.nodeType === 1 && (n.matches(".seg") || n.querySelector(".seg"));
  new MutationObserver((records) => {
    if (queued || !records.some((r) => [...r.addedNodes].some(bringsSeg))) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; scan(); });
  }).observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", scan, { once: true });
  else scan();

  window.Segmented = { refresh: (seg) => place(seg, true) };
})();
