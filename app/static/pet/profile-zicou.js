// 🪩 Zicou sur la fiche profil (avis de l'admin, 4.11) : « si on clique sur le profil d'une personne, on doit voir son
// Zicou » — UNE présentation pour tout le web : fiche d'un joueur (profile-card.js, jeux) et fiche d'un membre du module
// Événements (Discussions, participants, amis : web/events, composant ZicouOnProfile).
//   · avec un Zicou : bloc vedette, fond lumineux à la couleur de son humeur, halo, respiration et petit éclat (coupés si
//     l'on réduit les animations), nom, « Génération N · N jours », éclat chrome s'il est shiny, ce qu'il porte ;
//     toucher → sa visite si c'est un ami (onglet Zicou), rien sinon ;
//   · sans Zicou (ou envolé) : un œuf gris, sans lumière, un peu tristounet, « Pas encore de Zicou » ; sur MA fiche, ou si
//     je n'en ai pas moi-même : « Adopter le mien » (onglet Zicou, qui pond l'œuf) ;
//   · Zicou éteint (production : /api/pet/* répond 404) ou membre bloqué : rien du tout.
// Données : POST /api/pet/profile (app/pet_profile.py), apparence publique seulement. Tout texte passe par esc().
// Usage : ZicouProfile.load(token, memberId) → données ou null ; ZicouProfile.html(data) → chaîne ;
//         ZicouProfile.bind(el, { visit(id), adopt() }) pour les touchers (délégation, data-zp).
(function () {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const MEMBER_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  const STAGES = { egg: "Œuf", baby: "Bébé", teen: "Ado", adult: "Adulte" };
  const MOODS = { egg: "bien au chaud", happy: "content", party: "en mode fête", hungry: "a un petit creux", tired: "fatigué",
    sad: "un peu triste", sick: "pas en forme", sleep: "endormi" };
  const FALLBACK_MOOD = "#5ee7ff";
  const off = () => typeof document !== "undefined" && document.documentElement.dataset.compagnon === "off";

  async function load(token, member) {
    if (off() || !token || !MEMBER_ID.test(String(member || ""))) return null;
    try {
      const r = await fetch("/api/pet/profile", { method: "POST", headers: { "Content-Type": "application/json" },
        credentials: "same-origin", body: JSON.stringify({ token, member }) });
      if (!r.ok) return null;   // 404 : éteint, bloqué ou introuvable — rien sur la fiche
      const data = await r.json();
      return data && typeof data === "object" && data.member === member ? data : null;
    } catch { return null; }   // réseau : la fiche reste sans Zicou plutôt que d'afficher une erreur
  }

  const age = (z) => {
    if (z.stage === "egg") return "dans son œuf";
    const d = Math.max(0, Math.floor(Number(z.age_days) || 0));
    return d === 0 ? "né aujourd'hui" : `${d} jour${d > 1 ? "s" : ""}`;
  };
  const rarityChip = (p) => `<span class="zp-chip" style="--zp-r:${p.color === "rainbow" ? "#ff8cc2" : esc(p.color)}"${p.color === "rainbow" ? ' data-rainbow=""' : ""}>`
    + `<span aria-hidden="true">${esc(p.emoji)}</span> ${esc(p.label)}</span>`;

  function art(z, label) {
    const skin = window.PetSkin;
    if (!skin) return "";
    return skin.render({ stage: z.stage, variant: z.variant, emotion: z.emotion, outfit: z.outfit || null,
      accessories: z.acc || {}, shiny: !!z.shiny, label });
  }

  function featured(d) {
    const z = d.zicou;
    const name = z.name || "Son Zicou";
    const mood = window.PetSkin?.moodColor?.(z.emotion) || FALLBACK_MOOD;
    const label = `${name}, ${STAGES[z.stage] || ""}${MOODS[z.emotion] ? `, ${MOODS[z.emotion]}` : ""}${z.shiny ? ", shiny" : ""}`;
    const chips = (z.acc_items || []).map(rarityChip).join("");
    const best = z.best && ["epic", "legendary", "mythic"].includes(z.best.rarity)
      ? `<p class="zp-best">Sa plus belle pièce : <b style="color:${z.best.color === "rainbow" ? "#ff8cc2" : esc(z.best.color)}">${esc(z.best.label)}</b> · ${esc(z.best.rarity_label)}</p>` : "";
    const stage = `<span class="zp-halo" aria-hidden="true"></span><span class="zp-art">${art(z, label)}</span>`
      + `<span class="zp-glint" aria-hidden="true"></span>${z.shiny ? '<span class="zp-chrome" aria-hidden="true"></span>' : ""}`;
    const visit = d.friend && !d.me;
    return `<section class="zp zp-on${z.shiny ? " zp-shiny" : ""}" style="--zp-mood:${esc(mood)}" aria-label="Zicou de ce profil">
      ${visit ? `<button type="button" class="zp-stage" data-zp="visit" data-id="${esc(d.member)}" aria-label="${esc(label)} : lui rendre visite">${stage}</button>`
        : `<div class="zp-stage">${stage}</div>`}
      <div class="zp-text"><b class="zp-name">${esc(name)}</b>${z.shiny ? '<span class="zp-shiny-tag">✨ Shiny</span>' : ""}
        <span class="zp-age">Génération ${esc(Math.max(1, Number(z.gen) || 1))} · ${esc(age(z))}</span></div>
      ${chips ? `<div class="zp-chips">${chips}</div>` : ""}${best}
      ${visit ? `<button type="button" class="zp-visit" data-zp="visit" data-id="${esc(d.member)}">Lui rendre visite ›</button>` : ""}
    </section>`;
  }

  // L'œuf « standard » : gris, mat, penché, sans aucune lumière (ni halo, ni reflet) — on a envie qu'il éclose.
  const DULL_EGG = `<svg class="zp-egg" viewBox="0 0 120 120" aria-hidden="true" focusable="false">
    <ellipse cx="60" cy="104" rx="28" ry="5" fill="#000" opacity=".18"/>
    <g transform="rotate(-9 60 64)"><path d="M60 18 C40 18 28 48 28 68 C28 88 42 100 60 100 C78 100 92 88 92 68 C92 48 80 18 60 18 Z" fill="#6f6a7c" stroke="#4a4656" stroke-width="2.5"/>
    <path d="M44 62 l7 -6 l6 7 l7 -7 l6 6" fill="none" stroke="#4a4656" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity=".55"/>
    <circle cx="51" cy="80" r="3" fill="#5d5869"/><circle cx="70" cy="44" r="2.4" fill="#5d5869"/></g></svg>`;

  function empty(d) {
    const adopt = d.me || !d.mine;
    return `<section class="zp zp-none" aria-label="Pas encore de Zicou">
      <div class="zp-stage">${DULL_EGG}</div>
      <div class="zp-text"><b class="zp-name">Pas encore de Zicou</b>
        <span class="zp-age">${d.me ? "Ton œuf t'attend. Il éclot en 3 minutes." : "Son œuf attend encore d'être adopté."}</span></div>
      ${adopt ? '<button type="button" class="zp-adopt" data-zp="adopt">Adopter le mien</button>' : ""}
    </section>`;
  }

  function html(d) {
    if (!d || off()) return "";
    return d.zicou ? featured(d) : empty(d);
  }

  // Touchers : visite d'un ami, adopter le mien. Les actions viennent de la page qui affiche la fiche.
  function bind(el, actions) {
    el.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-zp]");
      if (!b || !el.contains(b)) return;
      ev.preventDefault();
      if (b.dataset.zp === "visit" && MEMBER_ID.test(b.dataset.id || "")) actions?.visit?.(b.dataset.id);
      if (b.dataset.zp === "adopt") actions?.adopt?.();
    });
  }

  window.ZicouProfile = Object.freeze({ load, html, bind, esc });
})();
