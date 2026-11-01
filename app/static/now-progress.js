// Barre de progression du titre en cours (page invités, écran /tv) : le serveur donne la position et la durée
// (« 0:01:23 ») ; la barre avance ensuite seule, en une animation linéaire jusqu'à la fin du titre (aucun calcul à
// chaque image). Elle n'est relancée que si la position réelle s'écarte de plus de 2 s de celle affichée : les
// rafraîchissements fréquents de la page ne la font jamais « sauter ».
(function () {
  const DRIFT_S = 2;
  const state = new WeakMap();   // barre → { key, start, dur, anim }

  /** « 0:03:45 », « 3:45 » ou un nombre de secondes → secondes (null si inconnu). */
  function seconds(v) {
    if (typeof v === "number") return Number.isFinite(v) ? v : null;
    const parts = String(v || "").split(":").map(Number);
    if (!parts.length || parts.some((x) => !Number.isFinite(x)) || !String(v || "").trim()) return null;
    return parts.reduce((acc, x) => acc * 60 + x, 0);
  }

  /** Position affichée en ce moment par la barre (en secondes), d'après son animation. */
  function shownPosition(s) {
    if (!s?.anim) return s ? s.start : null;
    return s.start + (s.anim.currentTime || 0) / 1000;
  }

  /**
   * bar : élément .now-progress (son premier enfant est la jauge) ; now : { position, duration, track_id… } ;
   * playing : la musique joue (sinon la barre reste figée).
   */
  function update(bar, now, playing) {
    if (!bar) return;
    const fill = bar.firstElementChild;
    const dur = seconds(now?.duration), pos = seconds(now?.position);
    if (!fill || !dur || pos == null || dur < 1) { bar.classList.add("hidden"); return; }
    bar.classList.remove("hidden");
    const key = `${now.track_id || now.title}|${dur}`;
    const at = Math.max(0, Math.min(dur, pos));
    const s = state.get(bar);
    const sameTrack = s && s.key === key;
    const drift = sameTrack ? Math.abs(shownPosition(s) - at) : Infinity;
    const runningOk = sameTrack && s.playing === playing && (!playing || drift < DRIFT_S) && (playing || drift < 0.5);
    if (runningOk) return;
    s?.anim?.cancel();
    const from = `scaleX(${(at / dur).toFixed(4)})`;
    if (!playing || typeof fill.animate !== "function") {
      fill.style.transform = from;
      state.set(bar, { key, start: at, dur, playing, anim: null });
      return;
    }
    fill.style.transform = "scaleX(1)";
    const anim = fill.animate([{ transform: from }, { transform: "scaleX(1)" }],
      { duration: Math.max(1, (dur - at) * 1000), easing: "linear", fill: "both" });
    state.set(bar, { key, start: at, dur, playing, anim });
  }

  window.NowProgress = { update, seconds };
})();
