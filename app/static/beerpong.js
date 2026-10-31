// 🍺 Beer pong : on joue sur une vraie table ; l'app ne gère pas les tours. L'animateur (ou le marqueur désigné)
// touche le gobelet tombé, qui l'a perdu, puis choisit la sentence parmi trois. Tout le monde voit les deux tables
// et la dernière sentence. Chargé après games.js (utilise gameAction, pressed, esc, haptic, manualForm…).
GAME_THEME.beerpong = "g-bp";
GAME_RULES.beerpong = `
  <h3>Le principe</h3>
  <p>Vous jouez au beer pong sur une <b>vraie table</b>, avec vos règles : l'app ne gère pas les tours. Elle sert à suivre les gobelets et à donner les <b>sentences</b>.</p>
  <h3>Les équipes</h3>
  <p>Avant la partie, l'app répartit les joueurs en <b>Rouges</b> et <b>Bleus</b> (l'animateur peut déplacer quelqu'un ou tout mélanger) et l'animateur choisit 6, 10 ou 15 gobelets.</p>
  <h3>Un gobelet tombe</h3>
  <p>L'animateur, ou le <b>marqueur</b> qu'il désigne, touche le gobelet sur l'écran, puis la personne qui l'a perdu. Trois sentences sont proposées : il en choisit une (ou en tire trois autres).</p>
  <h3>Les sentences</h3>
  <p>🍺 Gorgées, 🥃 Shot, 🎭 Gage, 🤪 Question WTF, 🧠 Quiz (mauvaise réponse : 2 gorgées), 💪 Sport (pompes, abdos…), 🎁 Bonus (un gobelet revient…) et 💣 Malus (un gobelet de plus tombe…). L'animateur coche les familles du soir.</p>
  <h3>La fin</h3>
  <p>L'équipe qui n'a plus de gobelets a perdu. Une erreur de saisie ? « Annuler » remet le gobelet.</p>`;

const BP_ROWS = { 6: [3, 2, 1], 10: [4, 3, 2, 1], 15: [5, 4, 3, 2, 1] };
let bpPick = null;  // gobelet touché par le marqueur, en attente du joueur qui l'a perdu : { team, cup }
const BP_KIND_ICON = { sips: "🍺", shot: "🥃", dare: "🎭", wtf: "🤪", quiz: "🧠", sport: "💪", bonus: "🎁", malus: "💣" };
const BP_KIND_NAME = { sips: "Gorgées", shot: "Shot", dare: "Gage", wtf: "Question WTF", quiz: "Quiz", sport: "Sport", bonus: "Bonus", malus: "Malus" };

function bpRack(v, team, canMark) {
  const cups = v.racks[team] || [];
  const rows = BP_ROWS[cups.length] || [cups.length];
  let i = 0;
  const html = rows.map((n) => `<div class="bp-row">${Array.from({ length: n }, () => {
    const k = i++, up = cups[k], picked = bpPick && bpPick.team === team && bpPick.cup === k;
    const pend = v.pending && v.pending.team === team && v.pending.cup === k;
    return `<button type="button" class="bp-cup ${up ? "" : "down"} ${picked || pend ? "picked" : ""}" ${canMark && up && !v.pending ? `data-bp-cup="${team}:${k}"` : "disabled"}
      aria-label="Gobelet ${k + 1}${up ? "" : " (tombé)"}"></button>`;
  }).join("")}</div>`).join("");
  const players = v.players.filter((p) => p.team === team).map((p) => esc(p.name)).join(" · ");
  return `<div class="bp-team ${team}"><div class="bp-team-h"><b>${team === "red" ? "🔴" : "🔵"} ${v.team_names[team]}</b>
      <span class="bp-alive">${v.alive[team]} / ${cups.length}</span></div>
    <div class="bp-rack ${team}">${html}</div><div class="bp-players">${players || "—"}</div></div>`;
}

function bpLobbyHtml(g) {
  const v = g.bp, lead = g.is_host;
  const team = (t) => `<div class="bp-col ${t}"><div class="bp-col-h">${t === "red" ? "🔴" : "🔵"} ${v.team_names[t]}</div>${v.players.filter((p) => p.team === t).map((p) =>
      `<div class="bp-mate"><span>${esc(p.name)}${p.me ? " (toi)" : ""}</span>${lead ? `<button type="button" class="bp-mini" data-bp-move="${esc(p.pid)}" data-bp-to="${t === "red" ? "blue" : "red"}" aria-label="Passer ${esc(p.name)} chez les ${t === "red" ? "Bleus" : "Rouges"}">${t === "red" ? "→ 🔵" : "← 🔴"}</button>` : ""}</div>`).join("") || `<div class="artist">Personne</div>`}</div>`;
  const free = v.players.filter((p) => !p.team);
  return `<div class="bp-hero"><div class="bp-hero-i">🍺</div><div><div class="bp-hero-t">Beer pong</div>
      <div class="bp-hero-s">Vraie table, vraies balles : l'app suit les gobelets et donne les sentences.</div></div></div>
    <div class="bp-teams">${team("red")}${team("blue")}</div>
    ${free.length ? `<div class="artist bp-free">À répartir au lancement : ${free.map((p) => esc(p.name)).join(", ")}</div>` : ""}
    ${lead ? `<div class="lk-row"><button type="button" class="lk-sub" data-bp-shuffle="1">🔀 Mélanger les équipes</button></div>
      <div class="g-label">Gobelets par équipe</div><div class="lk-chips bp-cups-pick">${v.cup_choices.map((n) => `<button type="button" class="${v.cups === n ? "on" : ""}" data-bp-cups="${n}" aria-pressed="${v.cups === n}">${n}</button>`).join("")}</div>
      ${bpKindsHtml(v)}${bpMarkerHtml(g)}
      <button type="button" class="lk-main" data-gact="start" ${v.players.length >= 2 ? "" : "disabled"}>▶ Lancer la partie</button>`
      : `<div class="lk-card bp-wait">${esc(g.host_name || "L'animateur")} prépare la table…</div>`}`;
}

function bpKindsHtml(v) {
  return `<div class="g-label">Sentences proposées</div><div class="lk-chips">${v.kind_list.map((k) =>
    `<button type="button" class="${v.kinds.includes(k.id) ? "on" : ""}" data-bp-kind="${k.id}" aria-pressed="${v.kinds.includes(k.id)}">${esc(k.label)}</button>`).join("")}</div>`;
}

function bpMarkerHtml(g) {
  const v = g.bp;
  return `<div class="g-label">Qui note les gobelets ? <small>(en plus de toi)</small></div><div class="lk-chips">
    <button type="button" class="${v.marker ? "" : "on"}" data-bp-marker="">Seulement moi</button>
    ${v.players.filter((p) => !p.me).map((p) => `<button type="button" class="${v.marker === p.pid ? "on" : ""}" data-bp-marker="${esc(p.pid)}">${esc(p.name)}</button>`).join("")}</div>`;
}

function bpLastHtml(v) {
  const l = v.last;
  if (!l) return `<div class="lk-card bp-last empty">Premier gobelet : la sentence s'affichera ici.</div>`;
  return `<div class="bp-last ${l.team}" aria-live="polite"><div class="bp-last-k">${BP_KIND_ICON[l.kind] || "🎯"} ${esc(l.name)}</div>
    <div class="bp-last-t">${esc(l.text)}</div>${l.hint ? `<div class="bp-last-h">${esc(l.hint)}</div>` : ""}
    ${l.answer && v.can_mark ? `<details class="bp-answer"><summary>Voir la réponse</summary>${esc(l.answer)}</details>` : ""}</div>`;
}

function bpPendingHtml(g) {
  const v = g.bp, P = v.pending;
  if (!P) return "";
  const opts = P.options.map((o, i) => `<button type="button" class="bp-opt ${o.kind}" ${v.can_mark ? `data-bp-sent="${i}"` : "disabled"}>
      <span class="bp-opt-k">${BP_KIND_ICON[o.kind] || "🎯"}</span><span><i class="bp-opt-kind">${BP_KIND_NAME[o.kind] || ""}</i><span class="bp-opt-t">${esc(o.text)}</span>${o.hint ? `<small>${esc(o.hint)}</small>` : ""}</span></button>`).join("");
  return `<div class="bp-pending ${P.team}"><div class="bp-pending-h">🎯 ${esc(P.name)} a perdu un gobelet : ${v.can_mark ? "choisis la sentence" : "l'animateur choisit la sentence…"}</div>
    <div class="bp-opts">${opts}</div>
    ${v.can_mark ? `<div class="lk-row"><button type="button" class="lk-sub" data-bp-reroll="1">🎲 Trois autres</button><button type="button" class="lk-sub" data-bp-undo="1" aria-label="Annuler ce gobelet (il remonte)">↶ Annuler</button></div>` : ""}</div>`;
}

function bpWhoHtml(g) {
  const v = g.bp;
  if (!bpPick || v.pending) return "";
  const mates = v.players.filter((p) => p.team === bpPick.team);
  return `<div class="bp-who ${bpPick.team}"><div class="bp-pending-h">Qui a perdu ce gobelet ?</div><div class="bp-opts">${mates.map((p) =>
    `<button type="button" class="bp-opt" data-bp-who="${esc(p.pid)}">${esc(p.name)}</button>`).join("")}</div>
    <div class="lk-row"><button type="button" class="lk-sub" data-bp-cancel="1">Annuler</button></div></div>`;
}

function beerpongHtml(g) {
  const v = g.bp;
  if (!v) return "";
  if (g.phase === "lobby") return bpLobbyHtml(g);
  if (bpPick && (v.pending || !v.racks[bpPick.team]?.[bpPick.cup])) bpPick = null;
  const end = g.phase === "end";
  return `${end ? `<div class="bp-win ${v.winner}">🏆 Les ${v.team_names[v.winner] || "?"} gagnent !</div>` : ""}
    ${bpPendingHtml(g)}${bpWhoHtml(g)}
    ${!end && v.can_mark && !v.pending && !bpPick ? `<div class="bp-tip">👇 Touche le gobelet qui vient de tomber</div>` : ""}
    <div class="bp-table">${bpRack(v, "red", v.can_mark && !end)}<div class="bp-net" aria-hidden="true"></div>${bpRack(v, "blue", v.can_mark && !end)}</div>
    ${bpLastHtml(v)}
    ${end && g.is_host ? `<button type="button" class="lk-main" data-gact="restart">🔁 Revanche</button>` : ""}`;
}

function renderBeerpongHost(g) {
  if (!g.is_host) { patch.gameHost = ""; return; }
  patch.gameHost = g.phase === "lobby" ? manualForm(g) : `<details class="bp-settings"><summary>⚙️ Sentences et marqueur</summary>${bpKindsHtml(g.bp)}${bpMarkerHtml(g)}</details>`;
}

document.addEventListener("click", (ev) => {
  if (game?.type !== "beerpong" || !game.bp) return;
  const v = game.bp;
  const t = (sel) => ev.target.closest(sel);
  let b;
  if ((b = t("[data-bp-cup]"))) {
    const [team, cup] = b.dataset.bpCup.split(":");
    bpPick = { team, cup: +cup };
    haptic(20);
    const mates = v.players.filter((p) => p.team === team);
    if (mates.length === 1) return pressed(b, gameAction("bphit", { settings: { team, cup: +cup, pid: mates[0].pid } }));
    return renderGame(game);
  }
  if ((b = t("[data-bp-who]")) && bpPick) {
    const pick = bpPick;
    return pressed(b, gameAction("bphit", { settings: { team: pick.team, cup: pick.cup, pid: b.dataset.bpWho } }));
  }
  if (t("[data-bp-cancel]")) { bpPick = null; return renderGame(game); }
  if ((b = t("[data-bp-sent]"))) { haptic(40); bpPick = null; return pressed(b, gameAction("bpsent", { amount: +b.dataset.bpSent })); }
  if ((b = t("[data-bp-reroll]"))) return pressed(b, gameAction("bpreroll"));
  if ((b = t("[data-bp-undo]"))) { bpPick = null; return pressed(b, gameAction("bpundo")); }
  if ((b = t("[data-bp-move]"))) return pressed(b, gameAction("bpset", { settings: { team: { pid: b.dataset.bpMove, team: b.dataset.bpTo } } }));
  if ((b = t("[data-bp-shuffle]"))) return pressed(b, gameAction("bpset", { settings: { shuffle: true } }));
  if ((b = t("[data-bp-cups]"))) return pressed(b, gameAction("bpset", { settings: { cups: +b.dataset.bpCups } }));
  if ((b = t("[data-bp-kind]"))) {
    const k = b.dataset.bpKind, kinds = v.kinds.includes(k) ? v.kinds.filter((x) => x !== k) : [...v.kinds, k];
    return pressed(b, gameAction("bpset", { settings: { kinds } }));
  }
  if ((b = t("[data-bp-marker]"))) return pressed(b, gameAction("bpset", { settings: { marker: b.dataset.bpMarker } }));
});
