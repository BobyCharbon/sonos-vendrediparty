// Effets originaux synthétisés localement : aucun téléchargement ni musique en boucle.
const GameAudio = (() => {
  const key = "vp-game-sounds";
  let enabled = true;
  try { enabled = localStorage.getItem(key) !== "off"; } catch {}
  let ctx, active = false, previous = null, lastTick = "";
  const voices = new Set();
  const tunes = {
    start: [392, 523, 659], turn: [659, 880], card: [260, 390],
    reveal: [440, 554, 659], win: [523, 659, 784, 1047],
    lose: [330, 277, 220], tick: [880], spin: [220, 294, 392, 523],
  };
  function stop() {
    for (const voice of voices) { try { voice.stop(); } catch {} }
    voices.clear();
  }
  function unlock() {
    if (!enabled || !active) return;
    try {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) return;
      ctx ||= new Audio();
      if (ctx.state !== "running") ctx.resume().catch(() => {});
    } catch {} // Le jeu reste utilisable si le navigateur refuse l'audio.
  }
  function play(kind) {
    if (!enabled || !active || document.hidden || ctx?.state !== "running") return;
    stop(); // Une seule annonce à la fois, même lors d'un rafraîchissement groupé.
    const notes = tunes[kind] || tunes.reveal;
    notes.forEach((frequency, i) => {
      const oscillator = ctx.createOscillator(), gain = ctx.createGain();
      const t = ctx.currentTime + i * 0.11, duration = kind === "tick" ? 0.055 : 0.16;
      oscillator.type = kind === "card" ? "triangle" : "sine";
      oscillator.frequency.setValueAtTime(frequency, t);
      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(0.075, t + 0.008);
      gain.gain.exponentialRampToValueAtTime(0.001, t + duration);
      oscillator.connect(gain); gain.connect(ctx.destination);
      voices.add(oscillator);
      oscillator.onended = () => { voices.delete(oscillator); oscillator.disconnect(); gain.disconnect(); };
      oscillator.start(t); oscillator.stop(t + duration + 0.01);
    });
  }
  function observe(g, turn) {
    active = !!g && !g.kicked && !g.excluded;
    if (!active) { previous = null; lastTick = ""; stop(); return; }
    const next = { id: g.id, type: g.type, phase: g.phase, round: g.round,
      turn, card: JSON.stringify([g.president?.pile, g.divan?.n, g.bk?.drawn, g.pyr?.step]) };
    const old = previous;
    previous = next;
    // Reconnexion / changement de table : ne pas rejouer une annonce ancienne.
    if (!old || old.id !== next.id || old.type !== next.type) { stop(); lastTick = ""; return; }
    if (old.phase !== next.phase && next.phase === "end") play("win");
    else if (old.phase === "lobby" && next.phase !== "lobby") play("start");
    else if (next.turn && old.turn !== next.turn) play("turn");
    else if (old.card !== next.card) play("card");
    else if (old.round !== next.round || old.phase !== next.phase) {
      // Les roues et résultats de quiz ont leurs annonces synchronisées propres.
      if (!["roulette", "casino", "quiz"].includes(g.type)) play("reveal");
    }
  }
  function tick(id, seconds) {
    const n = Math.ceil(seconds), token = `${id}:${n}`;
    if (n < 1 || n > 5 || token === lastTick) return;
    lastTick = token; play("tick");
  }
  function button() {
    return `<button type="button" class="py-icon" data-game-sound aria-pressed="${enabled}" aria-label="Sons du jeu : ${enabled ? "activés" : "coupés"}" title="${enabled ? "Couper les sons" : "Activer les sons"}">${enabled ? "🔊" : "🔇"}</button>`;
  }
  document.addEventListener("pointerdown", unlock, { passive: true });
  document.addEventListener("keydown", unlock);
  document.addEventListener("touchend", unlock, { passive: true });
  document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
  document.addEventListener("click", (event) => {
    if (!event.target.closest("[data-game-sound]")) return;
    enabled = !enabled;
    try { localStorage.setItem(key, enabled ? "on" : "off"); } catch {}
    if (!enabled) stop(); else { unlock(); play("turn"); }
    document.querySelectorAll("[data-game-sound]").forEach(el => { el.outerHTML = button(); });
  });
  return { play, observe, tick, button };
})();
