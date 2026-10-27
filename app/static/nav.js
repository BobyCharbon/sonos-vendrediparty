// Navigation façon iOS pour toute l'app : une seule pile d'écrans, de feuilles et de menus, liée à l'historique.
// ‹ Retour, bouton retour d'Android / du navigateur, glisser depuis le bord gauche (écrans), tirer vers le bas
// (feuilles) ou vers la gauche (menu latéral) : tout passe par la même pile, donc tout se comporte pareil.
//
// Deux façons d'entrer dans la pile :
// - déclarative : un élément porte data-nav="sheet|drawer" ; il entre dans la pile dès qu'il est visible
//   (sans classe « hidden ») et en sort quand il est caché. data-nav-surface : sélecteur de la partie qui bouge ;
//   data-nav-close : sélecteur du bouton qui le ferme (« self » : un toucher sur le fond lui-même) ;
// - explicite : Nav.open({ key, kind, surface, under, close }) puis Nav.closed(key) quand l'interface le ferme.
(function () {
  const M = window.Motion;
  const EDGE = 28;            // px depuis le bord gauche où le glisser « retour » peut commencer
  const SLOP = 10;            // px avant de décider de la direction (hystérésis, comme iOS)
  const PARALLAX = 0.3;       // l'écran du dessous ne glisse que de 30 % (profondeur)
  const SCRIM = "rgba(6, 3, 14, .62)";
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const AXIS = { screen: { axis: "x", dir: 1 }, sheet: { axis: "y", dir: 1 }, drawer: { axis: "x", dir: -1 } };

  let stack = [];             // [{ key, kind, el, surface, under, close, declared, value, anim }]
  let rewinding = false;      // un retour d'historique lancé par nous : on ne referme rien en plus
  let queued = [];            // ouvertures demandées pendant ce retour
  let seq = 0;

  const top = () => stack[stack.length - 1];
  const depth = () => history.state?.navDepth || 0;

  // ── Pile ⇄ historique ──
  function pushEntry() { history.pushState({ ...(history.state || {}), navDepth: stack.length }, ""); }
  function open(layer) {
    if (stack.some((l) => l.key === layer.key)) return;
    if (rewinding) { queued = [...queued, layer]; return; }
    const entry = { value: 0, anim: null, ...layer };
    stack = [...stack, entry];
    resetSurface(entry);
    pushEntry();
    if (entry.kind === "screen" && entry.animateIn !== false) slideIn(entry);
  }
  /** L'interface a fermé elle-même la couche (bouton ✕, fin de partie…) : on retire son entrée d'historique. */
  function closed(key) {
    const i = stack.findIndex((l) => l.key === key);
    if (i < 0) return;
    const removed = stack.length - i;
    stack.slice(i).forEach(resetSurface);   // arrêtée en plein glissement : rien ne reste décalé (dessous compris)
    stack = stack.slice(0, i);
    rewind(removed);
  }
  let rewindTimer = 0;
  function rewind(n) {
    if (n <= 0) return;
    rewinding = true;
    clearTimeout(rewindTimer);
    rewindTimer = setTimeout(rewound, 800);   // filet : un retour qui n'aboutit pas ne bloque jamais la pile
    history.go(-n);
  }
  function rewound() {
    clearTimeout(rewindTimer);
    rewinding = false;
    const waiting = queued;
    queued = [];
    waiting.forEach(open);
  }
  addEventListener("popstate", () => {
    // Fin de notre propre retour… mais un vrai « retour » de l'utilisateur juste après n'est pas absorbé.
    if (rewinding && depth() === stack.length) return rewound();
    const d = depth();
    if (d > stack.length) return rewind(d - stack.length);   // entrée périmée (rechargement, « suivant »)
    while (stack.length > d) {
      const layer = top();
      stack = stack.slice(0, -1);
      dismiss(layer);
    }
  });
  // Rechargement sur une entrée de couche : la page repart à la racine.
  if (depth()) history.replaceState({ ...history.state, navDepth: 0 }, "");

  /** ‹ Retour : referme la couche du dessus (comme le bouton retour d'Android). */
  function back() { if (stack.length) history.back(); }

  // ── Animations ──
  const dimension = (l) => (l.kind === "screen" ? innerWidth
    : l.kind === "sheet" ? l.surface.getBoundingClientRect().height || innerHeight
    : l.surface.getBoundingClientRect().width || 320);
  function apply(l, value) {
    l.value = value;
    const { axis, dir } = AXIS[l.kind];
    const offset = value * dir;
    l.surface.style.transform = axis === "x" ? `translate3d(${offset}px,0,0)` : `translate3d(0,${offset}px,0)`;
    const progress = Math.max(0, Math.min(1, value / dimension(l)));
    if (l.kind === "screen") {
      const under = l.under?.();
      if (under) under.style.transform = `translate3d(${-PARALLAX * innerWidth * (1 - progress)}px,0,0)`;
    } else if (l.el !== l.surface) {
      l.el.style.backgroundColor = SCRIM.replace(".62", (0.62 * (1 - progress)).toFixed(3));
    }
  }
  function resetSurface(l) {
    l.anim?.stop();
    l.value = 0;
    l.el.classList.remove("nav-dismissed", "nav-dragging");
    ["transform", "transition"].forEach((p) => l.surface.style.removeProperty(p));
    l.el.style.removeProperty("background-color");
    const under = l.under?.();
    if (under) under.style.removeProperty("transform");
  }
  function animate(l, to, velocity, done) {
    l.anim?.stop();
    if (reduceMotion.matches) { apply(l, to); done?.(); return; }
    l.anim = M.spring({ from: l.value, to, velocity, response: to ? 0.32 : 0.38, damping: 1,
      onUpdate: (x) => apply(l, x), onDone: () => { l.anim = null; done?.(); } });
  }
  function slideIn(l) {
    l.el.classList.add("nav-dragging");
    apply(l, dimension(l));
    animate(l, 0, 0, () => resetSurface(l));
  }
  /** Sortie de la couche (retour, geste) : elle part par le chemin d'où elle est venue, puis se ferme. */
  function dismiss(l, velocity = 0) {
    if (l.selfAnimated) return l.close();
    l.el.classList.add("nav-dragging");
    animate(l, dimension(l), velocity, () => {
      l.el.classList.add("nav-dismissed");
      l.close();
      if (l.kind === "screen") resetSurface(l);
    });
  }

  // ── Gestes : un seul doigt, la couche du dessus, 1:1 avec le doigt ──
  let drag = null;
  const INTERACTIVE = "input, textarea, select, [contenteditable], [data-no-drag], .g-stepper, canvas";
  function scrolledAway(target, surface) {
    for (let el = target; el && el !== surface.parentElement; el = el.parentElement) {
      if (el.scrollTop > 0) return true;
    }
    return false;
  }
  function canStart(l, e) {
    if (!l.surface || !l.surface.isConnected) return false;
    if (l.kind === "screen") return e.clientX <= EDGE;
    if (!l.surface.contains(e.target) || e.target.closest(INTERACTIVE)) return false;
    if (l.kind === "sheet" && l.handle && !e.target.closest(l.handle)) return false;
    return !(l.kind === "sheet" && scrolledAway(e.target, l.surface));
  }
  addEventListener("pointerdown", (e) => {
    const l = top();
    if (!l || !e.isPrimary || e.button > 0 || l.gestures === false || !canStart(l, e)) return;
    drag = { l, id: e.pointerId, x0: e.clientX, y0: e.clientY, active: false, tracker: M.velocityTracker() };
    drag.tracker.add(e.clientX, e.clientY, e.timeStamp);
  }, true);
  function along(e) {
    const { axis, dir } = AXIS[drag.l.kind];
    const dx = e.clientX - drag.x0, dy = e.clientY - drag.y0;
    return { main: (axis === "x" ? dx : dy) * dir, cross: axis === "x" ? dy : dx };
  }
  addEventListener("pointermove", (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    drag.tracker.add(e.clientX, e.clientY, e.timeStamp);
    const { main, cross } = along(e);
    if (!drag.active) {
      if (Math.hypot(main, cross) < SLOP) return;
      if (main <= 0 || Math.abs(main) < Math.abs(cross)) { drag = null; return; }
      drag.active = true;
      document.documentElement.classList.add("nav-gesture");   // pas de sélection de texte pendant le geste
      getSelection()?.removeAllRanges();
      drag.l.anim?.stop();   // attrapée en plein vol : elle repart de là où elle est, sans saut
      drag.l.anim = null;
      drag.from = drag.l.value;
      drag.start = main;     // la surface part de là où le doigt a franchi le seuil
      drag.l.el.classList.add("nav-dragging");
      try { e.target.releasePointerCapture?.(e.pointerId); } catch { /* pas capturé */ }
    }
    const raw = drag.from + main - drag.start;
    apply(drag.l, raw >= 0 ? raw : M.rubberband(raw, dimension(drag.l)));
  }, true);
  function release(e, cancelled) {
    if (!drag || e.pointerId !== drag.id) return;
    const { l, active, tracker } = drag;
    drag = null;
    if (!active) return;
    document.documentElement.classList.remove("nav-gesture");
    tracker.add(e.clientX, e.clientY, e.timeStamp);   // une pause avant de lâcher = pas d'élan
    suppressClick();
    const { axis, dir } = AXIS[l.kind];
    const velocity = cancelled ? 0 : tracker.velocity()[axis] * dir;
    const landing = l.value + M.project(velocity);   // là où l'élan l'emmènerait
    if (!cancelled && landing > dimension(l) / 2) {
      stack = stack.filter((x) => x !== l);
      rewind(1);
      dismiss(l, velocity);
    } else {
      animate(l, 0, velocity, () => resetSurface(l));
    }
  }
  addEventListener("pointerup", (e) => release(e, false), true);
  addEventListener("pointercancel", (e) => release(e, true), true);
  // Dès qu'un glisser est engagé, la page ne défile plus (ni « tirer pour rafraîchir ») sous le doigt.
  addEventListener("touchmove", (e) => {
    if (!drag || e.touches.length !== 1) return;
    const t = e.touches[0];
    const { main, cross } = along({ clientX: t.clientX, clientY: t.clientY });
    if (drag.active || (main > 0 && Math.abs(main) > Math.abs(cross))) e.preventDefault();
  }, { passive: false, capture: true });
  // Le clic de synthèse part juste après le relâcher : on n'avale que lui, jamais le toucher suivant.
  function suppressClick() {
    const stop = (ev) => { ev.stopPropagation(); ev.preventDefault(); };
    addEventListener("click", stop, { capture: true, once: true });
    setTimeout(() => removeEventListener("click", stop, { capture: true }), 80);
  }

  // ── Couches déclarées dans le HTML ──
  const isShown = (el) => el.isConnected && !el.hidden && !el.classList.contains("hidden") && !el.classList.contains("out");
  function requestClose(el) {
    const sel = el.dataset.navClose;
    const target = sel === "self" ? el : sel ? el.querySelector(sel) : null;
    if (target) target.click();
    else el.classList.add("hidden");
  }
  function syncDeclared() {
    document.querySelectorAll("[data-nav]").forEach((el) => {
      if (!isShown(el) || stack.some((l) => l.el === el)) return;
      if (!el.dataset.navKey) el.dataset.navKey = el.id || `nav-${++seq}`;
      open({ key: el.dataset.navKey, kind: el.dataset.nav, el, declared: true, handle: el.dataset.navHandle,
        surface: (el.dataset.navSurface && el.querySelector(el.dataset.navSurface)) || el, close: () => requestClose(el) });
    });
    stack.filter((l) => l.declared && !isShown(l.el)).forEach((l) => closed(l.key));
  }
  let syncQueued = false;
  new MutationObserver(() => {
    if (syncQueued) return;
    syncQueued = true;
    queueMicrotask(() => { syncQueued = false; syncDeclared(); });
  }).observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: ["class", "hidden"] });

  // ── Grand titre qui se replie dans une barre translucide en défilant (comme les apps iOS) ──
  function largeTitle(titleEl, barEl) {
    if (!titleEl || !barEl || !("IntersectionObserver" in window)) return;
    new IntersectionObserver(([entry]) => {
      document.body.classList.toggle("nav-compact", !entry.isIntersecting && entry.boundingClientRect.top < 0);
    }, { threshold: 0, rootMargin: "-44px 0px 0px 0px" }).observe(titleEl);
    barEl.addEventListener("click", () => scrollTo({ top: 0, behavior: reduceMotion.matches ? "auto" : "smooth" }));
  }

  // iOS n'applique :active (enfoncement immédiat des boutons) que si la page écoute le toucher.
  addEventListener("touchstart", () => {}, { passive: true });

  window.Nav = { open, closed, back, largeTitle, has: (key) => stack.some((l) => l.key === key), get depth() { return stack.length; } };
})();
