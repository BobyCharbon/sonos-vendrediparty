// Listes animées (file d'attente, résultats, demandes…) : chaque ligne porte une clé ; d'un rendu à l'autre,
// les lignes gardées ne sont pas recréées, celles qui arrivent glissent en place, celles qui partent s'effacent et
// les autres rejoignent leur nouvelle place (technique FLIP : transform et opacity seulement).
// Un rendu identique ne touche à rien : la page interroge le serveur souvent, rien ne doit « se rejouer ».
(function () {
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const SPRING = "cubic-bezier(.22, 1, .36, 1)";   // même courbe que --spring (style.css)
  const EXIT = "cubic-bezier(.4, 0, 1, 1)";
  const MOVE_MS = 420, ENTER_MS = 380, EXIT_MS = 180, STAGGER_MS = 35, MAX_STAGGER = 8;
  const MOVE_AFTER_EXIT_MS = 70;   // une ligne retirée commence à s'effacer avant que les autres comblent sa place

  const canAnimate = (box) => !document.hidden && box.isConnected && box.getClientRects().length > 0
    && typeof box.animate === "function";

  function build(html) {
    const t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstElementChild || document.createElement("div");
  }
  function keyed(key, html) {
    const el = build(html);
    el.dataset.lmKey = key;
    el.lmHtml = html;
    return el;
  }

  /** Arrivée d'une ligne : elle descend un peu et apparaît (sans mouvement si l'utilisateur l'a demandé). */
  function enter(el, delay = 0) {
    const to = getComputedStyle(el).opacity;   // une ligne atténuée (titre joué…) arrive à son opacité, sans saut
    const frames = reduceMotion.matches
      ? [{ opacity: 0 }, { opacity: to }]
      : [{ opacity: 0, transform: "translate3d(0,-10px,0) scale(.98)" }, { opacity: to, transform: "none" }];
    return el.animate(frames, { duration: reduceMotion.matches ? 180 : ENTER_MS, delay, easing: SPRING, fill: "backwards" });
  }

  /** Départ d'une ligne : posée en absolu là où elle était, elle s'efface pendant que les autres comblent la place. */
  function leave(box, el, at) {
    // Sous les autres lignes (la liste isole ses couches : z-index -1 reste au-dessus de son propre fond).
    box.style.isolation = "isolate";
    Object.assign(el.style, { position: "absolute", top: `${at.top}px`, left: `${at.left}px`, width: `${at.width}px`,
      margin: "0", pointerEvents: "none", zIndex: "-1" });
    el.setAttribute("aria-hidden", "true");
    el.dataset.lmLeaving = "1";
    box.append(el);
    const from = getComputedStyle(el).opacity;
    const frames = reduceMotion.matches
      ? [{ opacity: from }, { opacity: 0 }]
      : [{ opacity: from, transform: "none" }, { opacity: 0, transform: "translate3d(-24px,0,0) scale(.96)" }];
    el.animate(frames, { duration: EXIT_MS, easing: EXIT, fill: "forwards" }).finished.then(() => el.remove(), () => el.remove());
  }

  /**
   * Met la liste « box » à jour avec items = [{ key, html }] (html = UNE ligne, déjà échappée).
   * empty : html affiché quand la liste est vide. animate=false : simple remplacement (premier affichage…).
   */
  function patch(box, items, { empty = "", animate = true } = {}) {
    const signature = items.length ? items.map((i) => `${i.key}\u0001${i.html}`).join("\u0002") : `\u0003${empty}`;
    // Même contenu et liste intacte (personne n'a réécrit son HTML entre-temps) : on ne touche à rien.
    if (box.lmSignature === signature && box.firstElementChild === box.lmFirst) return;
    const firstRender = box.lmSignature === undefined;
    box.lmSignature = signature;
    render(box, items, empty, animate && !firstRender);
    box.lmFirst = box.firstElementChild;
  }

  function render(box, items, empty, animate) {
    box.removeAttribute("aria-busy");
    box.querySelectorAll("[data-lm-leaving]").forEach((el) => el.remove());
    const old = new Map([...box.children].filter((el) => el.dataset.lmKey).map((el) => [el.dataset.lmKey, el]));
    const motion = animate && canAnimate(box);
    if (!items.length) {
      if (!motion || !old.size) { box.innerHTML = empty; return; }
      // La dernière ligne part : on la laisse s'effacer avant d'afficher le message « liste vide ».
      if (getComputedStyle(box).position === "static") box.style.position = "relative";
      const spots = new Map([...old].map(([k, el]) => [k, { top: el.offsetTop, left: el.offsetLeft, width: el.offsetWidth }]));
      box.innerHTML = empty;
      const msg = box.firstElementChild;
      if (msg) enter(msg, EXIT_MS * 0.6);
      old.forEach((el, k) => leave(box, el, spots.get(k)));
      return;
    }
    if (!motion) {
      box.replaceChildren(...items.map(({ key, html }) => keyed(key, html)));
      return;
    }
    if (getComputedStyle(box).position === "static") box.style.position = "relative";
    const before = new Map([...old].map(([k, el]) => [k, el.getBoundingClientRect()]));
    const spots = new Map([...old].map(([k, el]) => [k, { top: el.offsetTop, left: el.offsetLeft, width: el.offsetWidth }]));
    const fresh = [];
    const next = items.map(({ key, html }) => {
      const kept = old.get(key);
      if (kept) {
        old.delete(key);
        if (kept.lmHtml === html) return kept;
        const redrawn = keyed(key, html);   // même ligne, contenu changé (heure de passage…) : elle garde sa place
        return redrawn;
      }
      const el = keyed(key, html);
      fresh.push(el);
      return el;
    });
    const hadRows = before.size > 0;
    box.replaceChildren(...next);
    // Lignes gardées : elles partent de leur ancienne place et glissent vers la nouvelle.
    next.forEach((el) => {
      const was = before.get(el.dataset.lmKey);
      if (!was || fresh.includes(el)) return;
      const now = el.getBoundingClientRect();
      const dy = was.top - now.top, dx = was.left - now.left;
      if (Math.abs(dy) < 1 && Math.abs(dx) < 1) return;
      if (reduceMotion.matches) return;
      // Pendant le trajet, la ligne a un fond plein (elle croise les autres) ; celle qui monte passe devant.
      el.classList.add("lm-moving");
      if (dy > 0) el.classList.add("lm-rising");
      const done = () => el.classList.remove("lm-moving", "lm-rising");
      el.animate([{ transform: `translate3d(${dx}px,${dy}px,0)` }, { transform: "none" }],
        { duration: MOVE_MS, delay: old.size ? MOVE_AFTER_EXIT_MS : 0, easing: SPRING, fill: "backwards" }).finished.then(done, done);
    });
    // Lignes nouvelles : en cascade courte (une liste entière qui arrive ne tombe pas d'un bloc).
    fresh.forEach((el, i) => enter(el, (hadRows ? EXIT_MS * 0.4 : 0) + Math.min(i, MAX_STAGGER) * STAGGER_MS));
    old.forEach((el, k) => leave(box, el, spots.get(k)));
  }

  /** Clés stables pour des titres qui peuvent apparaître plusieurs fois (doublons dans la file). */
  function occurrenceKeys(list, base) {
    const seen = new Map();
    return list.map((t) => {
      const b = base(t);
      const n = (seen.get(b) || 0) + 1;
      seen.set(b, n);
      return n > 1 ? `${b}#${n}` : b;
    });
  }

  window.ListMotion = { patch, enter, occurrenceKeys };
})();
