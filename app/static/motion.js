// Physique des gestes, façon iOS : ressorts interruptibles, élan projeté, résistance élastique aux bords.
// Partagé par la navigation (nav.js) et testé seul (tests/motion.test.cjs).
(function (root) {
  const STEP = 1 / 240;           // pas d'intégration (s) : stable même pour les ressorts raides
  const REST_DISTANCE = 0.5;      // px : on considère le ressort arrivé…
  const REST_SPEED = 8;           // px/s : …quand il est presque immobile
  const MAX_FRAME = 1 / 20;       // un onglet en arrière-plan ne fait pas « sauter » l'animation

  /** Paramètres Apple (amortissement, réponse en s) → raideur et frottement pour une masse de 1. */
  function springConstants(response, damping) {
    const stiffness = (2 * Math.PI / response) ** 2;
    return { stiffness, friction: 4 * Math.PI * damping / response };
  }

  /** Avance un ressort de dt secondes ; renvoie un nouvel état sans modifier l'ancien. */
  function stepSpring(state, target, dt, response, damping) {
    const { stiffness, friction } = springConstants(response, damping);
    let { x, v } = state;
    for (let t = 0; t < dt; t += STEP) {
      const h = Math.min(STEP, dt - t);
      v += (-stiffness * (x - target) - friction * v) * h;
      x += v * h;
    }
    return { x, v };
  }

  const atRest = (s, target) => Math.abs(s.x - target) < REST_DISTANCE && Math.abs(s.v) < REST_SPEED;

  /**
   * Anime une valeur vers « to » en partant de la valeur et de la vitesse ACTUELLES (geste relâché).
   * Amortissement 1 par défaut (pas de rebond) ; un peu de rebond seulement après un geste avec élan.
   * Renvoie { stop } : un nouveau geste peut attraper la valeur en plein vol.
   */
  function spring({ from, to, velocity = 0, response = 0.35, damping = 1, onUpdate, onDone }) {
    let state = { x: from, v: velocity }, last = 0, frame = 0, stopped = false;
    const raf = root.requestAnimationFrame || ((fn) => setTimeout(() => fn(Date.now()), 16));
    const caf = root.cancelAnimationFrame || clearTimeout;
    const tick = (now) => {
      if (stopped) return;
      const dt = last ? Math.min(MAX_FRAME, (now - last) / 1000) : 1 / 60;
      last = now;
      state = stepSpring(state, to, dt, response, damping);
      if (atRest(state, to)) {
        onUpdate?.(to, 0);
        onDone?.();
        return;
      }
      onUpdate?.(state.x, state.v);
      frame = raf(tick);
    };
    frame = raf(tick);
    return { stop() { stopped = true; caf(frame); return state; } };
  }

  /** Distance parcourue par l'élan d'un geste (décélération du défilement iOS). velocity en px/s. */
  function project(velocity, decelerationRate = 0.998) {
    return (velocity / 1000) * decelerationRate / (1 - decelerationRate);
  }

  /** Au-delà d'un bord, l'élément suit de moins en moins le doigt (il ralentit avant de s'arrêter). */
  function rubberband(overshoot, dimension, constant = 0.55) {
    const sign = Math.sign(overshoot), d = Math.abs(overshoot);
    return sign * (d * dimension * constant) / (dimension + constant * d);
  }

  /** Vitesse du doigt (px/s) à partir des derniers points, pour la transmettre au ressort au relâchement. */
  function velocityTracker(windowMs = 100) {
    let points = [];
    return {
      add(x, y, t) { points = [...points.filter((p) => t - p.t <= windowMs), { x, y, t }]; },
      velocity() {
        if (points.length < 2) return { x: 0, y: 0 };
        const a = points[0], b = points[points.length - 1], dt = (b.t - a.t) / 1000;
        return dt > 0 ? { x: (b.x - a.x) / dt, y: (b.y - a.y) / dt } : { x: 0, y: 0 };
      },
      reset() { points = []; },
    };
  }

  const api = { springConstants, stepSpring, spring, project, rubberband, velocityTracker };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Motion = api;
})(typeof window !== "undefined" ? window : globalThis);
