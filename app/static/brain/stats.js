// 🧠 Méninges : onglet de Réglages → « Mes stats de jeu ». Température (°M), domaines (radar + barres), évolution,
// série 🔥, forces et faiblesses, vitesse vs précision, record et niveau par jeu, classement entre membres.
// Connecté : /api/brain/me + /api/brain/compare. Sans compte : profil calculé par /api/brain/local à partir des
// parties gardées sur ce téléphone (rien n'est enregistré). Tout texte venu d'un joueur passe par esc().
// Ni hauteur ni défilement sur html/body (bug iOS 26, voir CLAUDE.md) : tout vit dans le panneau de l'onglet.
(function () {
  "use strict";
  const INDEX_MAX = 2000;
  const LOCAL_KEY = "brain_local", LOCAL_MAX = 500;
  const BALANCE_GAP = 15;          // écart (points sur 100) au-delà duquel on penche vers la vitesse ou la précision
  const CHART = { w: 320, h: 150, left: 6, right: 6, top: 16, bottom: 22 };
  const RADAR = { size: 240, r: 80, rings: 4 };
  // Icônes de secours (les mini-jeux ne sont chargés qu'à l'ouverture de Méninges) ; Brain.list() a priorité.
  const ICONS = { pareil: "⚡", motif: "💡", autoroute: "🚗", grille: "🟩", deux_avant: "🃏", tresor: "🍄", nuee: "🐦",
    aiguillage: "🚂", intrus: "🔭", encre: "🖋️", bascule: "🔀", courant: "🍃", balance: "⚖️", gouttes: "💧", syllabes: "🔤" };
  const COLORS = { vitesse: "#4f8cff", memoire: "#b07cff", attention: "#2ee6c5", flexibilite: "#ff6fb5", logique: "#8be36b", calcul: "#ff7a7a" };

  const h = (s) => (typeof esc === "function" ? esc(s)
    : String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])));
  const fmt = (n) => Math.round(+n || 0).toLocaleString("fr-CH");
  const plural = (n, word) => `${fmt(n)} ${word}${n > 1 ? "s" : ""}`;
  const clamp01 = (v) => Math.max(0, Math.min(1, v));
  const root = () => document.getElementById("brainStats");

  // ── Données ──
  async function post(url, body) {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const msg = r.status === 401 ? "ta connexion a expiré, reconnecte-toi" : typeof data.detail === "string" ? data.detail : "erreur réseau";
      throw new Error(msg);
    }
    return data;
  }
  let catalogCache = null;
  function fallbackCatalog() {
    const domains = (window.Brain?.domains || Object.keys(COLORS).map((id) => [id, id, "🧠"]))
      .map(([id, label, icon], i) => ({ id, label, icon, in_temperature: i < 5 }));
    return { domains, games: Object.keys(ICONS).map((id) => ({ id, name: id, domain: "" })) };
  }
  async function catalog() {
    if (catalogCache) return catalogCache;
    try {
      const r = await fetch("/api/brain/catalog");
      if (!r.ok) throw new Error();
      catalogCache = await r.json();
      return catalogCache;
    } catch { return fallbackCatalog(); }  // pas mis en cache : on réessaiera à la prochaine ouverture
  }
  function localSessions() {
    try {
      const list = JSON.parse(localStorage.getItem(LOCAL_KEY));
      return Array.isArray(list) ? list.slice(-LOCAL_MAX) : [];
    } catch { return []; }
  }
  async function token() {
    try { return typeof freshToken === "function" ? await freshToken() : null; } catch { return null; }
  }
  async function load() {
    const t = await token();
    const cat = catalog();
    if (!t) return { connected: false, cat: await cat, me: await post("/api/brain/local", { sessions: localSessions() }), board: null };
    const [me, board] = await Promise.all([post("/api/brain/me", { token: t }),
      post("/api/brain/compare", { token: t }).catch(() => null)]);  // classement indisponible : le reste s'affiche
    return { connected: true, cat: await cat, me, board };
  }

  // ── Morceaux d'écran ──
  const iconOf = (id) => window.Brain?.list?.().find((g) => g.id === id)?.icon || ICONS[id] || "🧠";
  const domainLabel = (cat, id) => cat.domains.find((d) => d.id === id)?.label || id;
  const totalPlays = (me) => Object.values(me.games || {}).reduce((n, g) => n + (+g.plays || 0), 0);

  function hero(me) {
    const temp = +me.temperature || 0, st = me.streak || {}, mp = me.month_progress;
    const pct = me.percentile;
    const progress = mp == null ? `<span class="brs-chip">Pas encore un mois de recul</span>`
      : `<span class="brs-chip ${mp > 0 ? "up" : mp < 0 ? "down" : ""}">${mp > 0 ? "▲ +" : mp < 0 ? "▼ −" : "= "}${fmt(Math.abs(mp))} °M en un mois</span>`;
    return `<section class="brs-hero" aria-label="Ta Température">
      <p class="brs-kicker">Ta Température</p>
      <p class="brs-temp"><b>${fmt(temp)}</b><span>°M</span></p>
      <div class="brs-meter" aria-hidden="true"><i style="transform:scaleX(${clamp01(temp / INDEX_MAX).toFixed(3)})"></i></div>
      ${pct != null ? `<p class="brs-pct">Tu fais mieux que <b>${fmt(pct)} %</b> des joueurs Party</p>` : ""}
      <div class="brs-chips">${progress}
        <span class="brs-chip ${st.current ? "hot" : ""}">🔥 ${st.current ? `${plural(st.current, "jour")} d'affilée` : "Pas de série en cours"}</span>
        <span class="brs-chip">Meilleure série : ${plural(st.best || 0, "jour")}</span></div>
    </section>`;
  }

  function radar(cat, me) {
    const doms = cat.domains.filter((d) => d.in_temperature);
    if (doms.length < 3) return "";
    const c = RADAR.size / 2, n = doms.length;
    const pt = (i, ratio) => {
      const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
      return [c + Math.cos(a) * RADAR.r * ratio, c + Math.sin(a) * RADAR.r * ratio];
    };
    const poly = (ratioOf) => doms.map((d, i) => pt(i, ratioOf(d)).map((v) => v.toFixed(1)).join(",")).join(" ");
    const rings = Array.from({ length: RADAR.rings }, (_, k) => `<polygon class="brs-ring" points="${poly(() => (k + 1) / RADAR.rings)}"/>`).join("");
    const axes = doms.map((d, i) => { const [x, y] = pt(i, 1); return `<line class="brs-axis" x1="${c}" y1="${c}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}"/>`; }).join("");
    const value = (d) => clamp01((me.domains?.[d.id]?.index || 0) / INDEX_MAX);
    const dots = doms.map((d, i) => { const [x, y] = pt(i, value(d)); return `<circle class="brs-dot" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4" style="fill:${COLORS[d.id] || "#fff"}"/>`; }).join("");
    const labels = doms.map((d, i) => {
      const [x, y] = pt(i, 1.28);
      return `<text x="${x.toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="middle">${h(d.icon)} ${h(d.label)}</text>`;
    }).join("");
    const summary = doms.map((d) => `${d.label} ${fmt(me.domains?.[d.id]?.index || 0)} °M`).join(", ");
    return `<svg class="brs-radar" viewBox="-30 -10 ${RADAR.size + 60} ${RADAR.size + 20}" role="img" aria-label="Profil par domaine : ${h(summary)}">
      ${rings}${axes}<polygon class="brs-shape" points="${poly(value)}"/>${dots}${labels}</svg>`;
  }

  function domainBars(cat, me) {
    return `<ul class="brs-doms">${cat.domains.map((d) => {
      const v = me.domains?.[d.id]?.index || 0, played = me.domains?.[d.id]?.played || 0;
      return `<li class="brs-dom${d.in_temperature ? "" : " brs-apart"}" style="--c:${COLORS[d.id] || "#8b5cff"}">
        <span aria-hidden="true">${h(d.icon)}</span><span class="brs-dom-l">${h(d.label)}</span>
        <span class="brs-bar" aria-hidden="true"><i style="transform:scaleX(${clamp01(v / INDEX_MAX).toFixed(3)})"></i></span>
        <b>${played ? fmt(v) : "–"}</b></li>`;
    }).join("")}</ul>
    <p class="brs-note">La Température combine Vitesse, Mémoire, Attention, Flexibilité et Logique ; Calcul a son indice à part.</p>`;
  }

  function strengths(cat, me) {
    const list = (ids) => ids.map((id) => `${h(domainLabel(cat, id))} (${fmt(me.domains?.[id]?.index || 0)} °M)`).join(", ");
    const strong = me.strengths || [], weak = me.weaknesses || [];
    const rows = [];
    if (strong.length) rows.push(`<li class="brs-sw up"><span aria-hidden="true">💪</span><p><b>Tes points forts</b><br>${list(strong)}</p></li>`);
    if (weak.length) rows.push(`<li class="brs-sw down"><span aria-hidden="true">🌱</span><p><b>À travailler</b><br>${list(weak)}</p></li>`);
    return `<section class="brs-card" aria-labelledby="brsSwH"><h3 id="brsSwH">Forces et faiblesses</h3>
      ${me.insight ? `<p class="brs-insight">${h(me.insight)}</p>` : ""}
      ${rows.length ? `<ul class="brs-sws">${rows.join("")}</ul>` : ""}</section>`;
  }

  function chart(history) {
    const pts = (history || []).filter((p) => p && typeof p.day === "string");
    if (pts.length < 2) return `<p class="brs-note">Ta courbe apparaîtra après quelques jours de jeu.</p>`;
    const vals = pts.map((p) => +p.temperature || 0);
    const max = Math.max(...vals), min = Math.min(...vals);
    const lo = Math.max(0, min - 50), hi = Math.max(max + 50, lo + 100);
    const iw = CHART.w - CHART.left - CHART.right, ih = CHART.h - CHART.top - CHART.bottom;
    const x = (i) => CHART.left + (iw * i) / (pts.length - 1);
    const y = (v) => CHART.top + ih * (1 - (v - lo) / (hi - lo));
    const line = vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
    const base = (CHART.top + ih).toFixed(1);
    const area = `${line} L${x(pts.length - 1).toFixed(1)} ${base} L${x(0).toFixed(1)} ${base} Z`;
    const day = (s) => new Date(`${s}T12:00:00`).toLocaleDateString("fr-CH", { day: "numeric", month: "short" });
    const last = vals[vals.length - 1];
    return `<svg class="brs-chart" viewBox="0 0 ${CHART.w} ${CHART.h}" role="img"
      aria-label="Évolution de ta Température du ${h(day(pts[0].day))} au ${h(day(pts[pts.length - 1].day))} : de ${fmt(vals[0])} à ${fmt(last)} °M">
      <defs><linearGradient id="brsArea" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#8b5cff" stop-opacity=".45"/><stop offset="1" stop-color="#8b5cff" stop-opacity="0"/></linearGradient>
      <linearGradient id="brsLine" x1="0" x2="1"><stop offset="0" stop-color="#3fd0ff"/><stop offset=".55" stop-color="#8b5cff"/><stop offset="1" stop-color="#ff4f9a"/></linearGradient></defs>
      <line class="brs-grid" x1="${CHART.left}" x2="${CHART.w - CHART.right}" y1="${y(max).toFixed(1)}" y2="${y(max).toFixed(1)}"/>
      <text class="brs-ylab" x="${CHART.left}" y="${(y(max) - 4).toFixed(1)}">max ${fmt(max)} °M</text>
      <path class="brs-area" d="${area}"/><path class="brs-line" d="${line}"/>
      <circle class="brs-end" cx="${x(pts.length - 1).toFixed(1)}" cy="${y(last).toFixed(1)}" r="4.5"/>
      <text class="brs-xlab" x="${CHART.left}" y="${CHART.h - 4}">${h(day(pts[0].day))}</text>
      <text class="brs-xlab" x="${CHART.w - CHART.right}" y="${CHART.h - 4}" text-anchor="end">${h(day(pts[pts.length - 1].day))}</text></svg>`;
  }

  function balance(me) {
    const sa = me.speed_vs_accuracy || {}, speed = +sa.speed || 0, acc = +sa.accuracy || 0;
    if (!speed && !acc) return "";
    const line = speed - acc > BALANCE_GAP ? "Tu fonces : ta vitesse prend le pas sur ta précision. Prends une demi-seconde de plus pour viser juste."
      : acc - speed > BALANCE_GAP ? "Tu assures : très précis, mais tu peux te permettre d'aller plus vite."
        : "Bel équilibre entre vitesse et précision.";
    const bar = (label, v, cls) => `<div class="brs-sa ${cls}"><span>${label}</span><span class="brs-bar" aria-hidden="true"><i style="transform:scaleX(${clamp01(v / 100).toFixed(3)})"></i></span><b>${fmt(v)} %</b></div>`;
    return `<section class="brs-card" aria-labelledby="brsSaH"><h3 id="brsSaH">Vitesse ou précision ?</h3>
      ${bar("⚡ Vitesse", speed, "speed")}${bar("🎯 Précision", acc, "acc")}
      <p class="brs-note">${line} <span class="brs-dim">(30 derniers jours)</span></p></section>`;
  }

  function gameList(cat, me) {
    const order = cat.domains.map((d) => d.id);
    const games = [...cat.games].sort((a, b) => order.indexOf(a.domain) - order.indexOf(b.domain));
    return `<ul class="brs-games">${games.map((g) => {
      const s = me.games?.[g.id] || {}, played = +s.plays > 0;
      const detail = played ? `Record <b>${fmt(s.best)}</b> · niveau ${fmt(s.last_level || 1)}${+s.max_tier > 1 ? ` · palier ${fmt(s.max_tier)}` : ""} · ${plural(s.plays, "partie")}` : "Pas encore joué";
      return `<li class="brs-game${played ? "" : " off"}" style="--c:${COLORS[g.domain] || "#8b5cff"}">
        <span class="brs-game-i" aria-hidden="true">${h(iconOf(g.id))}</span>
        <span class="brs-game-t"><b>${h(g.name)}</b><small>${h(domainLabel(cat, g.domain))} · ${detail}</small></span>
        <span class="brs-game-x">${played ? `${fmt(s.index)}<small> °M</small>` : ""}</span></li>`;
    }).join("")}</ul>`;
  }

  function ranking(data) {
    if (!data.connected) {
      return `<section class="brs-card" aria-labelledby="brsRankH"><h3 id="brsRankH">Classement Party</h3>
        <p class="brs-note">Connecte-toi pour te comparer aux autres membres.</p></section>`;
    }
    const b = data.board;
    if (!b) return `<section class="brs-card"><h3>Classement Party</h3><p class="brs-note">Le classement n'a pas pu être chargé.</p></section>`;
    const board = Array.isArray(b.board) ? b.board : [];
    if (!board.length) return `<section class="brs-card"><h3>Classement Party</h3><p class="brs-note">Personne d'autre n'a encore joué : invite tes amis à faire chauffer leurs méninges.</p></section>`;
    const head = b.rank ? `<p class="brs-note">Tu es <b>${fmt(b.rank)}${b.rank === 1 ? "er" : "e"}</b> sur ${plural(b.players || board.length, "joueur")}.</p>` : "";
    return `<section class="brs-card" aria-labelledby="brsRankH"><h3 id="brsRankH">Classement Party</h3>${head}
      <ol class="brs-board">${board.map((p, i) => `<li class="${p.me ? "me" : ""}"${p.me ? ' aria-current="true"' : ""}>
        <span class="brs-rk">${i + 1}</span><span class="brs-nm">${h(p.name)}${p.me ? " <small>(toi)</small>" : ""}</span>
        <b>${fmt(p.temperature)} <small>°M</small></b></li>`).join("")}</ol></section>`;
  }

  const loginBanner = () => `<div class="brs-login"><span>🔒 Stats gardées sur ce téléphone seulement. Connecte-toi pour garder tes stats sur tous tes appareils.</span>
    <button type="button" class="brs-link" data-brs="login">Me connecter</button></div>`;

  function emptyHtml(connected) {
    return `${connected ? "" : loginBanner()}<div class="brs-empty">
      <div class="brs-empty-i" aria-hidden="true">🧠</div>
      <h3>Tes méninges sont encore froides</h3>
      <p>Fais l'Échauffement du jour : 5 mini-jeux d'une minute. Ta Température, tes domaines et ta courbe apparaîtront ici.</p>
      <button type="button" class="brs-cta" data-brs="open">Faire l'Échauffement</button></div>`;
  }

  function html(data) {
    const { me, cat } = data;
    if (!totalPlays(me)) return emptyHtml(data.connected);
    return `${data.connected ? "" : loginBanner()}
      ${hero(me)}
      <section class="brs-card" aria-labelledby="brsDomH"><h3 id="brsDomH">Tes domaines</h3>${radar(cat, me)}${domainBars(cat, me)}</section>
      ${strengths(cat, me)}
      <section class="brs-card" aria-labelledby="brsEvoH"><h3 id="brsEvoH">Évolution</h3>${chart(me.history)}</section>
      ${balance(me)}
      <section class="brs-card" aria-labelledby="brsGamesH"><h3 id="brsGamesH">Tes jeux</h3>${gameList(cat, me)}</section>
      ${ranking(data)}
      <button type="button" class="brs-cta" data-brs="open">🧠 Ouvrir Méninges</button>
      <p class="brs-fine">Un jeu, pour le plaisir : la Température mesure tes résultats dans Méninges, rien de plus.</p>`;
  }

  // ── Affichage : la dernière demande gagne (onglet rouvert pendant un chargement) ──
  let seq = 0;
  async function show() {
    const el = root();
    if (!el) return;
    const mine = ++seq;
    if (!el.dataset.ready) el.innerHTML = `<p class="brs-loading" role="status"><span class="brs-spin" aria-hidden="true"></span>Chargement de tes stats…</p>`;
    try {
      const data = await load();
      if (mine !== seq) return;
      el.innerHTML = html(data);
      el.dataset.ready = "1";
    } catch (e) {
      if (mine !== seq) return;
      delete el.dataset.ready;
      el.innerHTML = `<div class="brs-empty brs-error" role="alert"><div class="brs-empty-i" aria-hidden="true">📡</div>
        <p>Impossible de charger tes stats : ${h(e.message || "erreur réseau")}</p>
        <button type="button" class="brs-ghost" data-brs="retry">Réessayer</button></div>`;
    }
  }

  document.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-brs]");
    if (!b || !b.closest("#brainStats")) return;
    const what = b.dataset.brs;
    if (what === "retry") show();
    else if (what === "login" && typeof showTab === "function") showTab("account");
    else if (what === "open" && window.Brain) window.Brain.open(b);
  });

  if (typeof STATS_TABS === "object") {
    STATS_TABS.brain = show;
    if (document.body.dataset.tab === "stats" && typeof statsTab !== "undefined" && statsTab === "brain") show();
  }
})();
