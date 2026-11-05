// 🎁 Zicou — la barre « petit cadeau » (avis de l'admin du 5.11 ; serveur : app/pet_bar.py, action « bar »).
// · En haut de l'écran de Zicou : la barre qui se remplit (2 h 30, en pause la nuit), « pleine vers 16 h 10 », puis
//   « Récupérer » ; « i » montre les chances de la petite table.
// · Dans la pastille de l'en-tête (#zicouChip, #zicouFloat) : un petit anneau qui suit la barre, qui brille une fois pleine.
// Le SERVEUR fait foi (remplissage, plafond de 4 par jour, tirage HMAC) : la page ne fait qu'afficher et animer.
// Règles stores (revue du 5.11) : chances affichées, rien ne la remplit plus vite, aucune perte si on ne vient pas,
// affichage calme (une heure, jamais un compte à rebours ni du rouge), rien de payant.
// Inséré par un seul point d'appel dans pet.js (home : window.ZicouBar.html(p)).
(function () {
  "use strict";
  const TICK_MS = 30000;          // l'anneau et la barre avancent doucement (la vraie valeur vient du serveur)
  const RING_IDS = ["zicouChip", "zicouFloat"];
  const PER_DAY_TEXT = (b) => `${b.today}/${b.per_day} aujourd'hui`;

  const UI = () => window.PetUI;
  const esc = (s) => (UI()?.esc ? UI().esc(s) : String(s ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`));
  const calm = () => { try { return matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; } };

  let latest = null, latestAt = 0, busy = false, introduced = false;

  /** Progression estimée maintenant (entre deux relectures du serveur) : linéaire, figée la nuit. */
  function progressNow(b) {
    if (!b) return 0;
    if (b.state === "full") return 1;
    if (b.state !== "filling" || b.night || !b.left_s) return Number(b.progress) || 0;
    const p = Number(b.progress) || 0, elapsed = (Date.now() - latestAt) / 1000;
    return Math.min(0.999, p + (1 - p) * Math.max(0, elapsed) / b.left_s);
  }
  function remember(b) {
    if (!b || typeof b !== "object") return;
    latest = b;
    latestAt = Date.now();
    ring();
  }

  // ── Barre de l'écran de Zicou ──
  function line(b) {
    if (b.state === "full") return "Pleine ! Un petit cadeau t'attend, quand tu veux.";
    if (b.state === "rest") return `${PER_DAY_TEXT(b)} · elle repart ${b.when}`;
    if (b.night) return `En pause la nuit · pleine ${b.when}`;
    return `Pleine ${b.when}`;
  }
  /** Texte court de la ligne fine (la phrase complète est lue par VoiceOver, aria-valuetext). */
  function short(b) {
    if (b.state === "rest") return `${b.today}/${b.per_day} · ${b.when}`;
    return b.night ? `🌙 ${b.when}` : b.when;
  }
  /** Une ligne fine sous l'en-tête (les boutons de soin restent visibles sans défiler, playtest « Léa »). */
  function html(p) {
    const b = p?.bar;
    if (!b || b.state === "off" || ["egg", "dead"].includes(p.stage)) return "";
    remember(b);
    const pct = Math.round(progressNow(b) * 100);
    const full = b.state === "full";
    const end = full
      ? `<button type="button" class="zb-claim" data-zb="claim">Récupérer</button>`
      : `<span class="zb-when">${esc(short(b))}</span>`;
    const intro = !introduced && !calm();   // la toute première fois : la barre se remplit sous les yeux
    introduced = true;
    return `<section class="zb zb-${esc(b.state)}${calm() ? " zb-calm" : ""}${intro ? " zb-intro" : ""}" aria-label="Petit cadeau de Zicou">
      <span class="zb-i" aria-hidden="true">🎁</span>
      <div class="zb-track" role="meter" aria-label="Petit cadeau" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}"
        aria-valuetext="${esc(line(b))}"><i class="zb-fill" style="--zb-s:${pct / 100}"></i>${full ? '<i class="zb-glow" aria-hidden="true"></i>' : ""}</div>
      ${end}<button type="button" class="zb-info" data-zb="odds" aria-label="Petit cadeau : chances et règles">i</button></section>`;
  }

  function oddsScreen() {
    const ui = UI(), b = latest;
    if (!ui || !b) return;
    const rows = (b.odds || []).map((o) => `<li><span>${esc(o.label)}</span><b>${esc(o.text)}</b></li>`).join("");
    ui.show(`${ui.top("Le petit cadeau", true)}<div class="pt-card pt-odds"><p class="zb-today">${esc(line(b))} · ${esc(PER_DAY_TEXT(b))}</p>
      <h2>Chances du petit cadeau</h2><ul>${rows}</ul>
      <p class="pt-muted">La barre se remplit en ${Math.round((b.fill_minutes || 150) / 6) / 10} h, entre 8 h et 23 h : la nuit, elle se met en pause.
        Pleine, elle t'attend sans limite de temps : rien ne se perd si tu ne viens pas (et rien ne s'empile non plus).
        ${b.per_day || 4} petits cadeaux par jour au plus. Rien ne la remplit plus vite.
        Le tirage est fait par Party, pas par ton téléphone. Rien ne s'achète avec de l'argent, rien n'a de valeur en argent.</p></div>`, "odds");
  }

  async function claim(btn) {
    const ui = UI();
    if (busy || !ui) return;
    busy = true;
    btn?.setAttribute("aria-disabled", "true");
    try {
      const data = await ui.api("act", { action: "bar" });
      ui.set(data.pet);
      remember(data.pet?.bar);
      window.ZicouHome?.petChanged?.(data.pet, data.news);
      ui.home();
      const f = data.effect?.found;
      if (!f) return;
      const reveal = window.ZicouReveal?.play || window.PetReveal?.play;
      if (reveal) {
        await reveal({ kind: f.kind, amount: f.amount, label: f.label, emoji: f.emoji, title: "Petit cadeau", pack: "bar",
          mode: "auto", odds: data.pet?.bar?.odds || latest?.odds || [] });
      } else {
        ui.burst(`${f.emoji} ${f.label}`);
        ui.cue("win");
      }
      ui.say(`Récupéré : ${f.label}`);
      ui.announce(data.news);
    } catch (err) {
      if (err.login) return ui.login();
      ui.home();
      ui.say(err.message, true);
    } finally {
      busy = false;
    }
  }

  // ── Anneau de la pastille ──
  function ring() {
    const b = latest || window.ZicouHome?.state?.()?.status?.bar;
    RING_IDS.forEach((id) => {
      const chip = document.getElementById(id);
      if (!chip) return;
      let r = chip.querySelector(".zb-ring");
      const on = b && !["off"].includes(b.state) && window.ZicouHome?.state?.()?.status?.adopted !== false;
      if (!on) { r?.remove(); return; }
      if (!r) {
        r = document.createElement("i");
        r.className = "zb-ring";
        r.setAttribute("aria-hidden", "true");
        chip.append(r);
      }
      r.style.setProperty("--zb-p", `${Math.round(progressNow(b) * 100)}%`);
      r.classList.toggle("zb-ring-full", b.state === "full");
      r.classList.toggle("zb-ring-rest", b.state === "rest");
    });
  }
  /** La pastille relit le serveur de son côté : on ne prend sa barre que si elle est plus récente (jamais l'ancienne
   *  barre gardée par la pastille juste après une récupération). */
  function newer(b, than) {
    if (!b || b === than) return false;
    if (!than) return true;
    const a = Date.parse(b.from), c = Date.parse(than.from);
    return a > c || (a === c && b.state !== than.state && b.state !== "filling");
  }
  function tick() {
    if (document.hidden) return;
    const fromStatus = window.ZicouHome?.state?.()?.status?.bar;
    if (newer(fromStatus, latest)) remember(fromStatus);
    else ring();
    const track = document.querySelector(".pt-root .zb-filling .zb-fill");
    if (track && latest) track.style.setProperty("--zb-s", String(Math.round(progressNow(latest) * 100) / 100));
    if (latest?.state === "filling" && !latest.night && latest.left_s && (Date.now() - latestAt) / 1000 >= latest.left_s) {
      window.ZicouHome?.refresh?.(true);   // pleine : le serveur confirme (pastille), l'écran suit à la prochaine relecture
      const root = UI()?.root?.();
      if (root && !root.hidden && root.dataset.screen === "home" && !busy) UI().api("me", { src: "none" }).then((d) => {
        if (d?.pet) { UI().set(d.pet); remember(d.pet.bar); if (root.dataset.screen === "home") UI().home(); }
      }).catch(() => { /* hors ligne : on réessaiera */ });
      latestAt = Date.now() + TICK_MS * 4;   // une seule relecture à la fois
    }
  }

  document.addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-zb]");
    if (!b) return;
    if (b.dataset.zb === "claim") return claim(b);
    if (b.dataset.zb === "odds") return oddsScreen();
  });
  setInterval(tick, TICK_MS);
  document.addEventListener("visibilitychange", tick);
  setTimeout(tick, 1500);

  window.ZicouBar = Object.freeze({ html, ring, remember, current: () => latest });
})();
