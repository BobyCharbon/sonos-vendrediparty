// Président : animations de la table. Purement décoratives (l'état vient toujours du serveur) :
// carte qui vole jusqu'au pli, pli balayé vers son gagnant, annonce (2, famille, Président), tour, passe, place,
// distribution et échanges. « Réduire les animations » coupe les mouvements (les annonces restent dans la notice).
window.PresidentFx = (() => {
  let prev = null, oldPile = [], launched = new Map(), seenSwap = "", fresh = new Set(), freshTimer = 0;
  const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const all = (sel) => [...document.querySelectorAll(sel)];
  const mid = (r) => [r.left + r.width / 2, r.top + r.height / 2];
  const seatOf = (pid) => document.querySelector(`#game .pr-seat[data-key="seat-${CSS.escape(pid || "")}"]`);
  const gone = (anim, el) => anim.finished.then(() => el.remove(), () => el.remove());
  const BURST = {two: "2 ! Pli fermé", family: "Famille complète !", president: "👑 Président !"};

  // Avant chaque rendu : les cartes encore sur la table, pour les balayer si le pli est ramassé.
  function snapshot() {
    oldPile = all("#game .pr-pile .pr-card").map((el) => ({html: el.outerHTML, rect: el.getBoundingClientRect()}));
  }

  // Au moment de jouer : la place de mes cartes dans ma main, d'où elles partiront.
  function launch(ids) {
    launched = new Map(ids.map((id) => [id, document.querySelector(`#game [data-pr-card="${CSS.escape(id)}"]`)?.getBoundingClientRect()])
      .filter(([, r]) => r));
  }

  const isFresh = (id) => fresh.has(id);

  function ghost(html, r) {
    const el = document.createElement("div");
    el.className = "pr-ghost";
    el.innerHTML = html;
    Object.assign(el.style, {left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px`});
    document.body.append(el);
    return el;
  }

  function origin(pid, cardId, mine) {
    const r = mine && launched.get(cardId);
    const seat = seatOf(pid);
    return r ? mid(r) : seat ? mid(seat.getBoundingClientRect()) : null;
  }

  // Une carte posée traverse l'écran jusqu'au pli, grossit un peu à l'arrivée et se pose.
  function playFx(last, mine) {
    all("#game .pr-pile.pr-latest .pr-card").forEach((el, i) => {
      const from = origin(last.pid, last.cards[i]?.id, mine);
      if (!from) return;
      const [tx, ty] = mid(el.getBoundingClientRect()), dx = from[0] - tx, dy = from[1] - ty, tilt = i % 2 ? 18 : -18;
      el.animate([
        {transform: `translate(${dx}px, ${dy}px) scale(.8) rotate(${tilt}deg)`, boxShadow: "0 28px 40px rgba(0,0,0,.45)"},
        {transform: `translate(${dx * .5}px, ${dy * .5 - 40}px) scale(1.05) rotate(${tilt / 2}deg)`, boxShadow: "0 36px 44px rgba(0,0,0,.4)", offset: .45},
        {transform: `translate(0, -14px) scale(1.12) rotate(${-tilt / 4}deg)`, offset: .82},
        {transform: "none", boxShadow: "0 6px 12px rgba(0,0,0,.25)"}],
        {duration: 820, delay: i * 110, easing: "cubic-bezier(.45, .05, .35, 1)", fill: "backwards"});
    });
    launched = new Map();
    document.querySelector("#game .pr-trail-item")?.animate(
      [{transform: "translateY(-16px) scale(.92)", opacity: 0}, {transform: "none", opacity: 1}],
      {duration: 380, delay: 220, easing: "ease-out", fill: "backwards"});
  }

  // Pli ramassé : le coup qui l'a fermé arrive d'abord sur la table, puis tout le pli file vers son gagnant.
  function closeFx(closed, mine) {
    const table = document.querySelector("#game .pr-table .pr-pile");
    if (!table) return;
    const t = table.getBoundingClientRect(), seat = seatOf(closed.pid);
    const dest = seat ? mid(seat.getBoundingClientRect()) : [t.left + t.width / 2, t.top - 240];
    const sweep = (el, delay, hold) => {
      const [x, y] = mid(el.getBoundingClientRect());
      gone(el.animate([{transform: "none", opacity: 1}, {transform: "none", opacity: 1, offset: hold},
        {transform: `translate(${dest[0] - x}px, ${dest[1] - y}px) scale(.25) rotate(25deg)`, opacity: 0}],
        {duration: 1400, delay, easing: "cubic-bezier(.5, 0, .75, 0)", fill: "forwards"}), el);
    };
    oldPile.forEach(({html, rect}, i) => sweep(ghost(html, rect), i * 30, .55));
    const w = 56, h = 80, cy = t.top + t.height / 2, start = t.left + t.width / 2 - closed.cards.length * (w + 8) / 2;
    closed.cards.forEach((c, i) => {
      const left = start + i * (w + 8), el = ghost(window.President.cardHtml(c), {left, top: cy - h / 2, width: w, height: h});
      const from = origin(closed.pid, c.id, mine) || [left + w / 2, cy - 240];
      gone(el.animate([
        {transform: `translate(${from[0] - left - w / 2}px, ${from[1] - cy}px) scale(.8) rotate(-16deg)`, opacity: 1},
        {transform: "scale(1.14)", opacity: 1, offset: .3}, {transform: "none", opacity: 1, offset: .38},
        {transform: "none", opacity: 1, offset: .62},
        {transform: `translate(${dest[0] - left - w / 2}px, ${dest[1] - cy}px) scale(.25) rotate(25deg)`, opacity: 0}],
        {duration: 1800, delay: i * 90, easing: "ease-in-out", fill: "forwards"}), el);
    });
    launched = new Map();
    if (BURST[closed.reason]) burst(BURST[closed.reason]);
  }

  function burst(text) {
    const el = document.createElement("div");
    el.className = "pr-burst";
    el.textContent = text;
    document.body.append(el);
    gone(el.animate([
      {transform: "translate(-50%, -50%) scale(.4)", opacity: 0},
      {transform: "translate(-50%, -50%) scale(1.12)", opacity: 1, offset: .2},
      {transform: "translate(-50%, -50%) scale(1)", opacity: 1, offset: .75},
      {transform: "translate(-50%, -62%) scale(.96)", opacity: 0}], {duration: 1500, easing: "ease-out", fill: "forwards"}), el);
  }

  function float(pid, emoji) {
    const seat = seatOf(pid);
    if (!seat) return;
    const [x, y] = mid(seat.getBoundingClientRect()), el = document.createElement("div");
    el.className = "pr-pop";
    el.textContent = emoji;
    Object.assign(el.style, {left: `${x}px`, top: `${y}px`});
    document.body.append(el);
    gone(el.animate([{transform: "translate(-50%, -50%) scale(.3)", opacity: 0},
      {transform: "translate(-50%, -110%) scale(1.3)", opacity: 1, offset: .35},
      {transform: "translate(-50%, -190%) scale(1)", opacity: 0}], {duration: 1600, easing: "ease-out", fill: "forwards"}), el);
  }

  // Le premier à finir devient Président : grande célébration (~3,8 s) — voile doré, rayons, couronne qui tombe,
  // nom qui s'impose et pluie de confettis. Un toucher la ferme plus tôt ; « réduire les animations » : fondu seul.
  const CELEBRATE = 3800, CONFETTI = 46, CONFETTI_COLORS = ["#ffd27a", "#ff9f43", "#ffffff", "#3fcf8e", "#ff6b6b", "#7aa8ff"];
  function celebrate(name, mine) {
    document.querySelector(".pr-celebrate")?.remove();
    const el = document.createElement("div");
    el.className = "pr-celebrate";
    el.setAttribute("role", "status");
    el.innerHTML = `<div class="pr-rays" aria-hidden="true"></div>
      <div class="pr-cel-crown" aria-hidden="true">${window.President.crown}</div>
      <div class="pr-cel-name">${esc(name)}</div>
      <div class="pr-cel-sub">${mine ? "Tu es Président !" : "est Président !"}</div>`;
    document.body.append(el);
    const close = () => gone(el.animate([{opacity: 1}, {opacity: 0}], {duration: 300, fill: "forwards"}), el);
    el.addEventListener("click", close, {once: true});
    if (calm()) {
      el.animate([{opacity: 0}, {opacity: 1, offset: .1}, {opacity: 1, offset: .9}, {opacity: 0}], {duration: CELEBRATE, fill: "forwards"})
        .finished.then(() => el.remove(), () => el.remove());
      return;
    }
    el.animate([{opacity: 0}, {opacity: 1, offset: .08}, {opacity: 1, offset: .9}, {opacity: 0}], {duration: CELEBRATE, fill: "forwards"})
      .finished.then(() => el.remove(), () => el.remove());
    el.querySelector(".pr-rays").animate([{transform: "translate(-50%, -50%) rotate(0) scale(.6)"}, {transform: "translate(-50%, -50%) rotate(140deg) scale(1.15)"}],
      {duration: CELEBRATE, easing: "ease-out", fill: "forwards"});
    el.querySelector(".pr-cel-crown").animate([
      {transform: "translateY(-70vh) rotate(-25deg) scale(.6)", opacity: 0},
      {transform: "translateY(0) rotate(6deg) scale(1.15)", opacity: 1, offset: .55},
      {transform: "translateY(-18px) rotate(-3deg) scale(.96)", offset: .72},
      {transform: "none", opacity: 1}], {duration: 1100, delay: 150, easing: "cubic-bezier(.3, 1.3, .5, 1)", fill: "backwards"});
    el.querySelector(".pr-cel-name").animate([{transform: "scale(.3)", opacity: 0, letterSpacing: ".4em"}, {transform: "scale(1.12)", opacity: 1, offset: .6},
      {transform: "none", opacity: 1, letterSpacing: "0"}], {duration: 800, delay: 700, easing: "cubic-bezier(.2, 1.3, .4, 1)", fill: "backwards"});
    el.querySelector(".pr-cel-sub").animate([{transform: "translateY(16px)", opacity: 0}, {transform: "none", opacity: 1}],
      {duration: 500, delay: 1200, easing: "ease-out", fill: "backwards"});
    for (let i = 0; i < CONFETTI; i++) {
      const bit = document.createElement("i");
      bit.className = "pr-confetti";
      bit.style.left = `${Math.random() * 100}%`;
      bit.style.background = CONFETTI_COLORS[i % CONFETTI_COLORS.length];
      el.append(bit);
      const drift = (Math.random() - .5) * 160, spin = 360 + Math.random() * 720;
      bit.animate([{transform: "translate(0, -10vh) rotate(0)", opacity: 1},
        {transform: `translate(${drift}px, 105vh) rotate(${spin}deg)`, opacity: .9}],
        {duration: 2200 + Math.random() * 1000, delay: 600 + i * 50, easing: "cubic-bezier(.3, .2, .6, 1)", fill: "backwards"});
    }
    if (typeof haptic === "function") haptic([60, 40, 60, 40, 120]);
  }

  function shake(pid) {
    seatOf(pid)?.animate([{transform: "none"}, {transform: "translateX(-6px) rotate(-2deg)"}, {transform: "translateX(6px) rotate(2deg)"},
      {transform: "translateX(-3px)"}, {transform: "none"}], {duration: 420, easing: "ease-out"});
  }

  function turnFx(mePid) {
    document.querySelector("#game .pr-turn-title")?.animate([{transform: "scale(.8)", opacity: .3}, {transform: "scale(1.12)", opacity: 1, offset: .6},
      {transform: "none"}], {duration: 520, easing: "cubic-bezier(.2, 1.4, .4, 1)"});
    seatOf(mePid)?.animate([{boxShadow: "0 0 0 0 rgba(255, 210, 122, .9)"}, {boxShadow: "0 0 0 12px rgba(255, 210, 122, 0)"}],
      {duration: 700, iterations: 2, easing: "ease-out"});
    if (typeof haptic === "function") haptic(40);
  }

  function dealFx() {
    all("#game .pr-hand .pr-card").forEach((el, i) => el.animate(
      [{transform: "translateY(-180px) rotate(-12deg) scale(.7)", opacity: 0}, {transform: "none", opacity: 1}],
      {duration: 420, delay: i * 40, easing: "cubic-bezier(.2, .9, .3, 1.1)", fill: "backwards"}));
  }

  // Échanges (premier pli) : des dos de cartes volent d'un siège à l'autre ; ce que je reçois est marqué « Nouvelle ».
  function flyBack(fromPid, toPid, delay) {
    const a = seatOf(fromPid), b = seatOf(toPid);
    if (!a || !b) return;
    const [ax, ay] = mid(a.getBoundingClientRect()), [bx, by] = mid(b.getBoundingClientRect()), el = document.createElement("div");
    el.className = "pr-fly";
    Object.assign(el.style, {left: `${ax}px`, top: `${ay}px`});
    document.body.append(el);
    const to = `translate(calc(-50% + ${bx - ax}px), calc(-50% + ${by - ay}px))`;
    gone(el.animate([
      {transform: "translate(-50%, -50%) scale(.6) rotate(-10deg)", opacity: 0},
      {transform: "translate(-50%, -50%) scale(1.1) rotate(-6deg)", opacity: 1, offset: .15},
      {transform: `${to} scale(1) rotate(8deg)`, opacity: 1, offset: .85},
      {transform: `${to} scale(.7)`, opacity: 0}], {duration: 1100, delay, easing: "cubic-bezier(.4, 0, .2, 1)", fill: "both"}), el);
  }

  function swapFx(g) {
    const sw = g.president.swap;
    if (!sw || seenSwap === sw.key) return;
    seenSwap = sw.key;
    if (!calm()) {
      let delay = 0;
      sw.moves.forEach((m) => { for (let i = 0; i < m.count; i++) { flyBack(m.from, m.to, delay); delay += 200; } });
    }
    if (!sw.got.length) return;
    toast(`Tu reçois ${sw.got.map(c => c.label).join(" et ")} de ${sw.from}`);
    fresh = new Set(sw.got.map(c => c.id));
    clearTimeout(freshTimer);
    freshTimer = setTimeout(() => { fresh.clear(); if (game?.type === "president") renderGame(game); }, 6000);
    renderGame(game);
  }

  // Après chaque rendu : compare avec l'état précédent et joue ce qui vient de se passer.
  function after(g) {
    const v = g.president;
    if (!v || !v.seats) return;
    const me = v.seats.find(s => s.me), last = v.trail?.at(-1);
    const now = {round: `${g.id}:${g.round}`, myTurn: !!v.my_turn, closed: v.closed?.key || "",
      play: v.pile && last ? `${g.id}:${g.round}:${v.trick}:${last.pid}:${last.cards.map(c => c.id).join()}` : "",
      seats: Object.fromEntries(v.seats.map(s => [s.pid, {passed: s.passed, out: !!(s.place || s.dunce)}]))};
    const was = prev;
    prev = now;
    if (was && !calm()) {
      if (now.round !== was.round) {
        if (v.hand.length) dealFx();
      } else {
        if (now.closed && now.closed !== was.closed) closeFx(v.closed, v.closed.pid === me?.pid);
        if (now.play && now.play !== was.play) playFx(last, last.pid === me?.pid);
        v.seats.forEach((s) => {
          const o = was.seats[s.pid];
          if (!o) return;
          if (s.passed && !o.passed) shake(s.pid);
          if ((s.place || s.dunce) && !o.out) {
            if (s.place === 1) celebrate(s.name, s.me);
            else float(s.pid, s.dunce ? "🫠" : "🎉");
          }
        });
      }
      if (now.myTurn && !was.myTurn) turnFx(me?.pid);
    }
    if (g.phase === "play") swapFx(g);
  }

  return {snapshot, launch, after, isFresh, celebrate};
})();
