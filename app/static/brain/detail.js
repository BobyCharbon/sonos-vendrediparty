// 🧠 Méninges : statistiques PAR JEU, dans le jeu lui-même (façon Lumosity).
// - Écran de fin enrichi : comparaison à ta moyenne et à ton record (petite fête si record), mini-courbe des 10 dernières
//   parties, indice du jeu et sa variation, percentile du jeu si la base le donne.
// - Fiche d'un jeu (depuis l'accueil, jeu déjà joué) : record, niveau, parties, courbe, précision, réaction, Jouer.
// Chargé par core.js, qui l'appelle par window.BrainDetail (prefetch, enrich, saved, sheet). Tout texte passe par esc().
(function () {
  "use strict";
  const END_CURVE = 10, SHEET_CURVE = 30, LOCAL_MAX = 300, CONFETTI = 26, CONFETTI_MS = 1800;
  const cache = new Map();   // jeu → Promise des stats AVANT la partie en cours

  const api = () => window.Brain?.api;
  const fmt = (n) => Math.round(+n || 0).toLocaleString("fr-CH");
  const pctTxt = (x) => `${Math.round(x * 100)} %`;

  (function loadCss() {
    const src = document.currentScript?.src || "/static/brain/detail.js";
    const u = new URL(src, location.href);
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `${u.pathname.replace(/detail\.js$/, "detail.css")}${u.search}`;
    document.head.append(link);
  })();

  // ── Statistiques d'un jeu : compte connecté → base ; sinon parties gardées sur ce téléphone ──
  function offline(id, sessions) {
    const rows = sessions.filter((s) => s && s.game === id);
    const scores = rows.map((s) => +s.score || 0);
    const accs = rows.filter((s) => s.accuracy != null).map((s) => +s.accuracy);
    const rts = rows.map((s) => +s.avg_rt_ms || 0).filter((v) => v > 0);
    const avg = (l) => (l.length ? l.reduce((a, b) => a + b, 0) / l.length : null);
    return { game: id, plays: rows.length, best: scores.length ? Math.max(...scores) : 0, avg: Math.round(avg(scores) || 0),
      level: rows.reduce((m, s) => Math.max(m, +s.level || 1), 0), index: null, accuracy: avg(accs), avg_rt_ms: avg(rts),
      percentile: null, history: rows.slice(-SHEET_CURVE).map((s) => ({ day: String(s.played_at || "").slice(0, 10), score: +s.score || 0, index: null })) };
  }
  async function fetchStats(id) {
    const a = api();
    if (!a) return null;
    const t = await a.token();
    const local = a.localSessions().slice(-LOCAL_MAX);
    try {
      return t ? await a.post("/api/brain/game", { token: t, game: id })
        : await a.post("/api/brain/game/local", { game: id, sessions: local });
    } catch {
      return t ? null : offline(id, local);  // hors ligne : ce que le téléphone sait
    }
  }
  function prefetch(id) {
    const p = fetchStats(id).catch(() => null);
    cache.set(id, p);
    return p;
  }

  // ── Courbe (SVG, scores) ──
  function curve(points, opts = {}) {
    const vals = points.map((p) => +p || 0);
    if (vals.length < 2) return `<p class="br-muted br-small bd-curve-empty">${vals.length ? "Joue encore pour voir ta courbe." : "Pas encore de partie."}</p>`;
    const W = 300, H = opts.height || 70, PAD = 6;
    const top = Math.max(...vals, opts.best || 0), low = Math.min(...vals);
    const span = Math.max(1, top - low);
    const x = (i) => PAD + (i * (W - 2 * PAD)) / (vals.length - 1);
    const y = (v) => H - PAD - ((v - low) / span) * (H - 2 * PAD);
    const pts = vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const last = vals.length - 1;
    const bestLine = opts.best ? `<line class="bd-best" x1="${PAD}" x2="${W - PAD}" y1="${y(opts.best).toFixed(1)}" y2="${y(opts.best).toFixed(1)}"/>` : "";
    return `<svg class="bd-curve" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${api().esc(opts.label || "Courbe de tes scores")}">
      <defs><linearGradient id="bdHeat" x1="0" x2="1"><stop offset="0" stop-color="#3fd0ff"/><stop offset=".55" stop-color="#8b5cff"/><stop offset="1" stop-color="#ff4f9a"/></linearGradient></defs>
      ${bestLine}<polyline points="${pts}"/>
      <circle cx="${x(last).toFixed(1)}" cy="${y(vals[last]).toFixed(1)}" r="4.5"/></svg>`;
  }

  // ── Écran de fin enrichi ──
  function comparison(res, pre) {
    if (!pre) return `<p class="bd-line">Statistiques du jeu indisponibles pour l'instant.</p>`;
    if (!pre.plays) return `<p class="bd-line">Première partie : c'est ton score de référence.</p>`;
    const lines = [];
    if (pre.avg > 0) {
      const d = Math.round(((res.score - pre.avg) / pre.avg) * 100);
      lines.push(d > 0 ? `<p class="bd-line bd-up"><b>+${d} %</b> sur ta moyenne (${fmt(pre.avg)})</p>`
        : d < 0 ? `<p class="bd-line bd-down"><b>−${-d} %</b> sous ta moyenne (${fmt(pre.avg)})</p>`
          : `<p class="bd-line">Pile ta moyenne (${fmt(pre.avg)})</p>`);
    }
    lines.push(res.score > pre.best
      ? `<p class="bd-line bd-rec">🎉 <b>Nouveau record !</b> +${fmt(res.score - pre.best)} sur l'ancien (${fmt(pre.best)})</p>`
      : `<p class="bd-line">À ${fmt(pre.best - res.score)} de ton record (${fmt(pre.best)})</p>`);
    return lines.join("");
  }
  function party(host) {
    if (!host || api().calm()) return;
    const box = document.createElement("div");
    box.className = "bd-party";
    box.setAttribute("aria-hidden", "true");
    const colors = ["#3fd0ff", "#8b5cff", "#ff4f9a", "#ffd166", "#3ddc97"];
    for (let i = 0; i < CONFETTI; i++) {
      const s = document.createElement("i");
      s.style.setProperty("--x", `${Math.round(Math.random() * 100)}%`);
      s.style.setProperty("--d", `${Math.round(Math.random() * 400)}ms`);
      s.style.setProperty("--r", `${Math.round(Math.random() * 720 - 360)}deg`);
      s.style.background = colors[i % colors.length];
      box.append(s);
    }
    host.append(box);
    setTimeout(() => box.remove(), CONFETTI_MS + 400);
  }
  async function enrich(res) {
    const a = api();
    const end = document.querySelector("#brainRoot .br-end");
    if (!a || !end) return;
    end.querySelector(".br-save")?.insertAdjacentHTML("beforebegin", `<section class="bd-end" aria-label="Tes statistiques de ce jeu">
      <div class="bd-cmp" aria-live="polite"><p class="bd-line br-muted">Comparaison avec tes parties…</p></div>
      <div class="bd-curve-box"></div>
      <div class="bd-idx" hidden><span>Indice du jeu</span><b></b><small class="bd-delta"></small></div>
      <p class="bd-pct br-muted br-small" hidden></p></section>`);
    const pre = await (cache.get(res.id) || Promise.resolve(null));
    const box = end.querySelector(".bd-end");
    if (!box?.isConnected) return;
    box.querySelector(".bd-cmp").innerHTML = comparison(res, pre);
    const scores = [...(pre?.history || []).map((h) => h.score), res.score].slice(-END_CURVE);
    box.querySelector(".bd-curve-box").innerHTML = curve(scores, { label: `Tes ${scores.length} dernières parties` });
    if (pre?.plays && res.score > pre.best) { box.classList.add("bd-record"); party(end); }
  }
  async function saved(res) {
    const pre = await (cache.get(res.id) || Promise.resolve(null));
    const post = await prefetch(res.id);  // stats à jour (servira aussi pour la prochaine partie)
    const box = document.querySelector("#brainRoot .bd-end");
    if (!box?.isConnected || !post) return;
    const scores = (post.history || []).map((h) => h.score).slice(-END_CURVE);
    if (scores.length >= 2) box.querySelector(".bd-curve-box").innerHTML = curve(scores, { label: `Tes ${scores.length} dernières parties` });
    if (post.index) {
      const idx = box.querySelector(".bd-idx");
      idx.hidden = false;
      idx.querySelector("b").textContent = `${fmt(post.index)} °M`;
      const d = pre?.plays && pre.index ? post.index - pre.index : null;
      const delta = idx.querySelector(".bd-delta");
      delta.textContent = d == null ? "" : d > 0 ? `▲ +${fmt(d)}` : d < 0 ? `▼ −${fmt(-d)}` : "= stable";
      delta.className = `bd-delta${d > 0 ? " bd-up" : d < 0 ? " bd-down" : ""}`;
    }
    if (post.percentile != null) {
      const p = box.querySelector(".bd-pct");
      p.hidden = false;
      p.textContent = `Dans ce jeu, tu fais mieux que ${post.percentile} % des joueurs Party.`;
    }
  }

  // ── Fiche d'un jeu ──
  async function sheet(id) {
    const a = api();
    const g = a?.game(id);
    if (!g) return;
    const e = a.esc, d = a.domain(g.domain);
    a.show(`<div class="br-loading" role="status"><span class="br-spin" aria-hidden="true"></span>Tes statistiques…</div>`, "detail");
    const s = await prefetch(id);
    if (document.querySelector("#brainRoot")?.dataset.screen !== "detail") return;  // fermé ou ailleurs entre-temps
    const stat = (label, value) => `<div class="br-stat"><span>${label}</span><b>${value}</b></div>`;
    const plays = s?.plays || 0;
    a.show(`<div class="bd-sheet" style="--g:${e(g.color)}">
      <header class="br-top"><span class="br-chip br-chip-dom" style="--c:${e(d[3])}">${e(d[2])} ${e(d[1])}</span>
        <button type="button" class="br-round" data-br="home" aria-label="Retour">✕</button></header>
      <div class="br-howto-i" aria-hidden="true">${e(g.icon)}</div>
      <h2 class="br-howto-n">${e(g.name)}</h2>
      ${g.howto[0] ? `<p class="br-muted bd-desc">${e(g.howto[0])}</p>` : ""}
      ${s ? `<div class="br-stats bd-stats">
        ${stat("Record", s.best ? fmt(s.best) : "–")}
        ${stat("Indice du jeu", s.index ? `${fmt(s.index)} °M` : "–")}
        ${stat("Niveau atteint", s.level || "–")}
        ${stat("Parties", fmt(plays))}
        ${stat("Précision moyenne", s.accuracy != null ? pctTxt(s.accuracy) : "–")}
        ${stat("Réaction moyenne", s.avg_rt_ms ? `${fmt(s.avg_rt_ms)} ms` : "–")}
      </div>
      ${s.percentile != null ? `<p class="br-muted br-small bd-pct">Tu fais mieux que ${s.percentile} % des joueurs Party dans ce jeu.</p>` : ""}
      <section class="bd-prog" aria-label="Progression"><h3 class="br-h">Progression</h3>
        ${curve((s.history || []).map((h) => h.score), { height: 110, best: s.best, label: `Tes ${(s.history || []).length} dernières parties` })}
        ${(s.history || []).length >= 2 ? `<p class="br-muted br-small">Tes ${(s.history || []).length} dernières parties · ligne pointillée : ton record</p>` : ""}</section>`
        : `<p class="br-muted">Statistiques indisponibles pour l'instant.</p>`}
      <div class="br-actions">
        <button type="button" class="br-cta" data-br="again" data-id="${e(id)}">Jouer</button>
        <button type="button" class="br-ghost" data-br="home">Retour</button>
      </div></div>`, "detail");
    document.querySelector("#brainRoot .bd-sheet .br-cta")?.focus();
  }

  window.BrainDetail = Object.freeze({ prefetch, enrich, saved, sheet });
})();
