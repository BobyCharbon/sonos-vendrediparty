// 🪙 Zicou — à quoi servent les pièces (économie du 4.11.2026, en bêta) : festins, niveau, festin offert à un ami,
// chambre et teintures, caisse commune du groupe, Zicou en vedette à l'Apple TV. Dans le même panneau que pet/pet.js
// (window.PetUI), données du serveur (/api/pet/me, /api/pet/coll, /api/pet/pot, /api/pet/star). Pièces GAGNÉES
// seulement : elles ne s'achètent jamais, ne s'envoient jamais, ne paient aucun tirage, ne touchent jamais la musique
// ni l'accès à une partie. Aucun classement.
(function () {
  "use strict";
  const UI = () => window.PetUI;
  const e = (s) => UI().esc(s);
  const fmt = (n) => Number(n || 0).toLocaleString("fr-CH");
  let coll = null, busy = false;

  const until = (iso) => {
    const left = Math.max(0, (new Date(iso).getTime() - Date.now()) / 60000);
    return left >= 60 ? `${Math.floor(left / 60)} h ${String(Math.round(left % 60)).padStart(2, "0")}` : `${Math.round(left)} min`;
  };
  const coinsOf = (p) => p?.daily?.coins ?? coll?.coins ?? 0;

  // ── Accueil : pastilles et boutons ──
  function chips(p) {
    const out = [];
    if (p.xp) {
      const star = p.xp.stars ? ` ★${p.xp.stars}` : "";
      out.push(`<button type="button" class="pt-chip pt-chip-btn" data-pt="eco-level" aria-label="Niveau ${p.xp.level}${star}">⭐ Niv. ${p.xp.level}${star}</button>`);
    }
    const f = p.feast?.active;
    if (f) out.push(`<button type="button" class="pt-chip pt-chip-btn pt-feast-chip" data-pt="eco-feasts" aria-label="${e(f.label)} encore ${until(f.until)}">${e(f.emoji)} ${until(f.until)}</button>`);
    if (p.coll?.room) out.push(`<span class="pt-chip">🏠 Chambre ${p.coll.room}</span>`);
    return out.join("");
  }
  function moreButtons() {
    return `<button type="button" class="pt-ghost" data-pt="eco-feasts">🍽️ Festins</button>
      <button type="button" class="pt-ghost" data-pt="eco-room">🏠 Chambre</button>
      <button type="button" class="pt-ghost" data-pt="eco-pot">🪩 Caisse commune</button>
      <button type="button" class="pt-ghost" data-pt="eco-star">🌟 Apple TV</button>`;
  }

  // ── Festins ──
  function feastsScreen() {
    const p = UI().current();
    if (!p?.feast) return UI().home();
    const f = p.feast, coins = coinsOf(p);
    const active = f.active ? `<div class="pt-card pt-feast-on"><b>${e(f.active.emoji)} ${e(f.active.label)}</b> en cours : ${e(f.active.effect.toLowerCase())}
        <p class="pt-muted pt-tiny">Encore ${until(f.active.until)}${f.active.by ? ` · offert par ${e(f.active.by)} 💜` : ""}</p></div>` : "";
    const waiting = f.waiting.length ? `<p class="pt-muted pt-tiny">Ensuite : ${f.waiting.map((w) => `${e(w.by || "un ami")}`).join(", ")} lui ont offert un festin, il attend son tour.</p>` : "";
    const blocked = f.active || f.waiting.length ? "Un festin à la fois" : f.bought_today ? "Un festin par jour" : "";
    const menu = f.menu.map((x) => `<li class="pc-buy"><span class="pc-mini pc-none" aria-hidden="true">${e(x.emoji)}</span>
      <span><b>${e(x.label)}</b><small>${e(x.effect)}</small></span>
      <button type="button" class="pt-cta pc-price" data-pt="eco-feast" data-i="${e(x.id)}" ${blocked || coins < x.price ? 'aria-disabled="true"' : ""}
        aria-label="Servir ${e(x.label)} pour ${x.price} pièces">${x.price} 🪙</button></li>`).join("");
    UI().show(`${UI().top("Festins", true)}<div class="pc-wallet"><span>🪙 ${fmt(coins)}</span></div>${active}${waiting}
      <section class="pt-card"><h2>🍽️ La carte</h2><ul class="pc-list">${menu}</ul>
      <p class="pt-muted pt-tiny">${blocked ? `${e(blocked)} : reviens plus tard 😋 ` : ""}Un festin actif à la fois, un achat par jour. Les festins ne changent
        aucune chance des coffres et ne donnent aucun avantage contre tes amis. Tu peux aussi offrir une Pizza dorée ou une Fondue au
        Zicou d'un ami (👫 Amis).</p></section>`, "feasts");
  }

  // ── Niveau ──
  function levelScreen() {
    const p = UI().current();
    const x = p?.xp;
    if (!x) return UI().home();
    const pct = Math.round(100 * x.xp / x.need);
    const kinds = [["care", "🧼 Soins (repas, jeu, câlin, toilette, goûter)"], ["game", "🧠 Parties (Méninges, jeux de Party)"], ["social", "👫 Amis (visite, cadeau)"]];
    const rows = kinds.map(([k, label]) => `<li><span>${label}</span><small>${x.today[k]}/${x.caps[k]} XP</small></li>`).join("");
    UI().show(`${UI().top("Niveau", true)}<div class="pt-card pt-level">
      <div class="pt-big" aria-label="Niveau ${x.level}">⭐ ${x.level}${x.stars ? ` <small>★${x.stars}</small>` : ""}</div>
      <div class="pc-bar" role="meter" aria-label="XP du niveau" aria-valuemin="0" aria-valuemax="${x.need}" aria-valuenow="${x.xp}"><i style="--v:${pct}%"></i></div>
      <p class="pt-muted">${fmt(x.xp)} / ${fmt(x.need)} XP ${x.level >= 50 ? "avant la prochaine étoile ★" : "avant le niveau suivant"}</p>
      ${x.boost ? '<p class="pt-tip">🍕 Pizza dorée : XP ×2 aujourd\'hui (plafonds doublés)</p>' : ""}
      <h3>Aujourd'hui</h3><ul class="pt-xp-today">${rows}</ul>
      <p class="pt-muted pt-small">Le niveau ne redescend jamais, même si ${e(p.name)} s'envole : il reste à ton compte. Après le niveau 50, chaque
        tranche de 1 000 XP ajoute une étoile ★. Jamais d'XP pour boire, noter l'app ou partager.</p></div>`, "level");
  }

  // ── Chambre et teintures ──
  async function roomScreen() {
    UI().show(`${UI().top("Chambre", true)}${UI().loadingHtml("Ouverture de la chambre…")}`, "room");
    try {
      const data = await UI().api("collection", {});
      if (data?.pet) UI().set(data.pet);
      coll = data.collection;
      renderRoom();
    } catch (err) {
      if (err.login) return UI().login();
      UI().show(`${UI().top("Chambre", true)}<div class="pt-card"><p>${e(err.message)}</p></div>`, "room");
    }
  }
  function renderRoom() {
    const p = UI().current();
    if (!coll || !p) return;
    const r = coll.room, d = coll.dyes;
    const lights = "✨".repeat(Math.min(10, r.level));
    const owned = coll.dex.flatMap((s) => s.items).filter((x) => x.owned && !x.masked && d.prices[x.rarity] && !["decor", "facets"].includes(x.slot));
    const dyeRows = owned.map((x) => {
      const mine = d.owned[x.id] || [], worn = d.worn[x.id] || "";
      const swatches = d.colors.map((c) => {
        const has = mine.includes(c.id);
        return `<button type="button" class="pt-swatch${worn === c.id ? " on" : ""}" style="--sw:${c.hex}" data-pt="${has ? "eco-dye-wear" : "eco-dye"}"
          data-i="${e(x.id)}" data-c="${e(c.id)}" aria-pressed="${worn === c.id}" ${!has && coll.coins < d.prices[x.rarity] ? 'aria-disabled="true"' : ""}
          aria-label="${e(c.label)}${has ? "" : `, ${d.prices[x.rarity]} pièces`}">${has ? "" : "🔒"}</button>`;
      }).join("");
      return `<li class="pt-dye-row"><span><b>${e(x.label)}</b><small>${has0(mine) ? "" : `${d.prices[x.rarity]} 🪙 la couleur`}</small></span>
        <span class="pt-swatches">${worn ? `<button type="button" class="pt-swatch pt-sw-none" data-pt="eco-dye-wear" data-i="${e(x.id)}" data-c="" aria-label="Couleur d'origine">↺</button>` : ""}${swatches}</span></li>`;
    }).join("");
    UI().show(`${UI().top("Chambre", true)}<div class="pc-wallet"><span>🪙 ${fmt(coll.coins)}</span></div>
      <div class="pt-hero pt-room" data-room="${r.level}"><div class="pt-room-lights" aria-hidden="true">${lights}</div>${UI().art(p)}
        <p class="pt-line">Chambre niveau ${r.level}</p></div>
      <section class="pt-card"><h2>🏠 Agrandir la chambre</h2>
        <p class="pt-muted pt-tiny">Tes amis voient le niveau de sa chambre. Chaque niveau coûte un peu plus que le précédent, sans fin.</p>
        ${r.level >= r.max ? "<p>Sa chambre est déjà immense ✨</p>" : `<button type="button" class="pt-cta" data-pt="eco-room-grow" ${coll.coins < r.price ? 'aria-disabled="true"' : ""}>
          Passer au niveau ${r.level + 1} · ${fmt(r.price)} 🪙</button>`}
        <p class="pt-muted pt-tiny">Les fonds (décor) s'achètent dans la Boutique › Décor de la chambre.</p></section>
      <section class="pt-card"><h2>🎨 Teintures</h2>
        <p class="pt-muted pt-tiny">Recolore un accessoire à toi : chaque couleur s'achète une fois par objet (Commun 60, Rare 120, Épique 250,
          Légendaire 500 🪙), puis se porte ou s'enlève à volonté.</p>
        ${dyeRows ? `<ul class="pc-list">${dyeRows}</ul>` : "<p class='pt-muted'>Pas encore d'accessoire à teindre.</p>"}</section>`, "room");
  }
  const has0 = (list) => list.length > 0;

  // ── Caisse commune ──
  async function potScreen() {
    UI().show(`${UI().top("Caisse commune", true)}${UI().loadingHtml("On compte les pièces…")}`, "pot");
    try {
      renderPot(await UI().api("pot", {}));
    } catch (err) {
      if (err.login) return UI().login();
      UI().show(`${UI().top("Caisse commune", true)}<div class="pt-card"><p>${e(err.message)}</p></div>`, "pot");
    }
  }
  function renderPot(pot, given) {
    const p = UI().current(), coins = coinsOf(p);
    const g = pot.current;
    const reached = pot.reached.map((x) => `<li>✅ ${e(x.emoji)} ${e(x.label)}</li>`).join("");
    const goal = g ? `<div class="pt-card pt-pot"><div class="pt-big" aria-hidden="true">${e(g.emoji)}</div><h2>${e(g.label)}</h2>
        <div class="pc-bar" role="meter" aria-label="Caisse commune" aria-valuemin="0" aria-valuemax="${g.target}" aria-valuenow="${g.total}"><i style="--v:${Math.round(100 * g.total / g.target)}%"></i></div>
        <p><b>${fmt(g.total)}</b> / ${fmt(g.target)} pièces · ${pot.donors} participant${pot.donors > 1 ? "s" : ""}</p>
        <div class="pt-acts pt-acts-4">${pot.steps.map((n) => `<button type="button" class="pt-act" data-pt="eco-pot-give" data-n="${n}"
          ${coins < n || pot.left_today < 10 ? 'aria-disabled="true"' : ""} aria-label="Verser ${n} pièces"><span class="pt-act-i" aria-hidden="true">🪙</span><span>${n}</span></button>`).join("")}</div>
        <p class="pt-muted pt-tiny">Encore ${fmt(pot.left_today)} pièces possibles aujourd'hui (${fmt(pot.daily_max)} par jour au plus). Tu as versé ${fmt(pot.mine)} pièces en tout.</p></div>`
      : `<div class="pt-card"><p>🎉 Tous les objectifs sont atteints. Le prochain arrive bientôt !</p></div>`;
    const thanks = pot.friends.length ? `<p class="pt-muted pt-small">💜 Merci à ${pot.friends.map(e).join(", ")}${pot.donors > pot.friends.length ? " et aux autres" : ""}.</p>` : "";
    UI().show(`${UI().top("Caisse commune", true)}<div class="pc-wallet"><span>🪙 ${fmt(coins)}</span></div>
      ${given ? `<p class="pt-tip">${given}</p>` : ""}${goal}${thanks}
      ${reached ? `<section class="pt-card"><h3>Débloqué pour tout le groupe</h3><ul class="pt-reached">${reached}</ul></section>` : ""}
      <p class="pt-muted pt-small">Tout le groupe met des pièces en commun pour un décor que tout le monde voit (dans le Salon de Party et à
        l'Apple TV). Pas de classement : chaque pièce compte autant. Les pièces versées ne vont à personne.</p>`, "pot");
  }

  // ── Apple TV ──
  async function starScreen() {
    UI().show(`${UI().top("Apple TV", true)}${UI().loadingHtml("On regarde la soirée…")}`, "star");
    try {
      renderStar(await UI().api("star", {}));
    } catch (err) {
      if (err.login) return UI().login();
      UI().show(`${UI().top("Apple TV", true)}<div class="pt-card"><p>${e(err.message)}</p></div>`, "star");
    }
  }
  function renderStar(st) {
    const p = UI().current(), coins = coinsOf(p);
    let body;
    if (st.booked) {
      body = st.booked.starts_in > 0
        ? `<p class="pt-line">🌟 ${e(p.name)} passe à l'écran dans ${Math.ceil(st.booked.starts_in / 60)} min environ.</p>`
        : `<p class="pt-line">🌟 ${e(p.name)} danse en ce moment sur l'Apple TV !</p>`;
    } else if (!st.open) {
      body = `<p>${st.present === false ? "La vedette à l'Apple TV, c'est pour les présents de la soirée 🪩" : "Pas de soirée en cours pour l'instant. Reviens pendant la prochaine soirée 🪩"}</p>`;
    } else {
      body = `<button type="button" class="pt-cta" data-pt="eco-star-book" ${coins < st.price ? 'aria-disabled="true"' : ""}>🌟 Faire passer ${e(p.name)} · ${st.price} 🪙</button>`;
    }
    UI().show(`${UI().top("Apple TV", true)}<div class="pc-wallet"><span>🪙 ${fmt(coins)}</span></div>
      <div class="pt-hero">${UI().art(p)}${body}</div>
      <p class="pt-muted pt-small">Pendant une soirée, ton Zicou entre en dansant au milieu de l'écran de l'Apple TV pendant 30 secondes, avec sa tenue.
        Une fois par soirée, chacun son tour. La musique n'est jamais touchée.</p>`, "star");
  }

  // ── Festin offert (visite d'un ami) ──
  function giftFeasts(f, p) {
    const menu = (p?.feast?.menu || []).filter((x) => x.giftable);
    if (!menu.length) return "";
    const coins = coinsOf(p);
    return `<div class="pt-acts pt-acts-2 pt-gift-feasts">${menu.map((x) => `<button type="button" class="pt-act" data-pt="gift" data-k="feast_${e(x.id)}"
      data-id="${e(f.id)}" ${coins < x.price ? 'aria-disabled="true"' : ""} aria-label="Offrir ${e(x.label)} pour ${x.price} pièces">
      <span class="pt-act-i" aria-hidden="true">${e(x.emoji)}</span><span>${e(x.label)}</span><small>${x.price} 🪙</small></button>`).join("")}</div>
      <p class="pt-muted pt-tiny">Un festin offert lui fait plaisir (un effet, jamais des pièces). Un cadeau par ami et par jour.</p>`;
  }
  function giftSaid(kind) {
    const x = (UI().current()?.feast?.menu || []).find((m) => `feast_${m.id}` === kind);
    return x ? `${x.emoji} ${x.label} offerte !` : "";
  }

  // ── Actions ──
  async function run(path, body, after) {
    if (busy) return;
    busy = true;
    try {
      const data = await UI().api(path, body);
      UI().cue("win");
      UI().buzz([20, 40, 20]);
      after(data);
      UI().announce(data.news);
    } catch (err) {
      if (err.login) return UI().login();
      UI().say(err.message, true);
      UI().cue("lose");
    } finally {
      busy = false;
    }
  }
  const accept = (data) => {
    if (data?.pet) UI().set(data.pet);
    if (data?.collection) coll = data.collection;
  };

  function click(b) {
    const disabled = b.getAttribute("aria-disabled") === "true";
    switch (b.dataset.pt) {
      case "eco-level": return levelScreen(), true;
      case "eco-feasts": return feastsScreen(), true;
      case "eco-room": return roomScreen(), true;
      case "eco-pot": return potScreen(), true;
      case "eco-star": return starScreen(), true;
      case "eco-feast":
        if (disabled) return UI().say("Pas maintenant : un festin à la fois, un par jour, avec des pièces gagnées 🪙", true), true;
        run("coll", { action: "feast", item: b.dataset.i }, (d) => { accept(d); feastsScreen(); });
        return true;
      case "eco-room-grow":
        if (disabled) return UI().say("Pas assez de pièces pour l'instant 🪙 Elles se gagnent en jouant.", true), true;
        run("coll", { action: "room" }, (d) => { accept(d); renderRoom(); });
        return true;
      case "eco-dye":
        if (disabled) return UI().say("Pas assez de pièces pour cette couleur 🪙", true), true;
        run("coll", { action: "dye", item: b.dataset.i, slot: b.dataset.c }, (d) => { accept(d); renderRoom(); });
        return true;
      case "eco-dye-wear":
        run("coll", { action: "dye_wear", item: b.dataset.i, slot: b.dataset.c || "" }, (d) => { accept(d); renderRoom(); });
        return true;
      case "eco-pot-give":
        if (disabled) return UI().say("Pas assez de pièces (ou plus de versement possible aujourd'hui) 💜", true), true;
        run("pot/give", { coins: Number(b.dataset.n) }, (d) => {
          const p = UI().current();
          if (p?.daily) UI().set({ ...p, daily: { ...p.daily, coins: Math.max(0, p.daily.coins - d.given) } });
          renderPot(d, d.just_reached ? `🎉 Objectif atteint : ${e(d.goal.label)} ! Merci à tout le groupe` : `🪙 Merci ! ${d.given} pièces dans la caisse commune`);
        });
        return true;
      case "eco-star-book":
        if (disabled) return UI().say("Pas assez de pièces pour l'instant 🪙", true), true;
        run("star/book", {}, (d) => {
          const p = UI().current();
          if (p?.daily) UI().set({ ...p, daily: { ...p.daily, coins: Math.max(0, p.daily.coins - d.price) } });
          renderStar(d);
        });
        return true;
      default:
        return false;
    }
  }

  window.PetEconomy = Object.freeze({ chips, moreButtons, giftFeasts, giftSaid, click });
})();
