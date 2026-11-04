// 📖 Compagnon — la collection (lot A, 4.11.2026) : garde-robe, Zicoudex, boutique, atelier, vitrine, certificats,
// révélations (accessoire, Mythique « waouh », cadeau d'événement, Zicou shiny), extras de la visite d'un ami
// (vitrine, Signaler, Bloquer). Dans le même panneau que pet/pet.js (window.PetUI), données du serveur
// (/api/pet/collection, /api/pet/coll). Les Mythiques pas encore à soi restent MASQUÉS (« ??? », ni nom ni image) :
// le serveur ne les envoie jamais. Pièces gagnées seulement, jamais d'argent réel.
(function () {
  "use strict";
  const UI = () => window.PetUI;
  const e = (s) => UI().esc(s);
  const TABS = [["wear", "👕", "Porter"], ["dex", "📖", "Zicoudex"], ["shop", "🛍️", "Boutique"], ["craft", "🔨", "Atelier"],
    ["showcase", "🏆", "Vitrine"], ["certs", "📜", "Certificats"]];
  const RARITY = { common: "Commun", rare: "Rare", epic: "Épique", legendary: "Légendaire", mythic: "Mythique" };
  const REASONS = [["harassment", "Harcèlement"], ["shocking", "Contenu choquant"], ["spam", "Spam"], ["scam", "Arnaque ou vente"], ["other", "Autre"]];
  let coll = null, tab = "dex", slot = "head", picked = null, queue = [], busy = false, visiting = null;

  const fmtPct = (v) => `${String(v).replace(".", ",")} %`;
  const serial = (x) => (x.serial ? `n° ${x.serial}${x.of ? `/${x.of}` : ""}` : "");

  // ── Dessin ──
  function mini(item, cls) {
    const S = window.PetSkin;
    if (!S) return "";
    const acc = item ? { [item.slot]: item.id } : {};
    return `<span class="pc-mini ${cls || ""}" aria-hidden="true">${S.render({ stage: "adult", variant: "classic", emotion: "happy", accessories: acc })}</span>`;
  }
  const tag = (r) => `<span class="pc-rar pc-${e(r)}">${e(RARITY[r] || r)}</span>`;

  // ── Écran Collection ──
  async function open(which) {
    tab = TABS.some(([k]) => k === which) ? which : "dex";
    picked = null;
    UI().show(`${UI().top("Collection", true)}${UI().loadingHtml("Ouverture de la collection…")}`, "coll");
    try {
      const data = await UI().api("collection", {});
      accept(data);
      render();
    } catch (err) {
      if (err.login) return UI().login();
      UI().show(`${UI().top("Collection", true)}<div class="pt-card"><p>${e(err.message)}</p></div>`, "coll");
    }
  }
  function accept(data) {
    if (data?.pet) UI().set(data.pet);
    if (data?.collection) coll = data.collection;
  }
  function render() {
    if (!coll) return;
    const p = UI().current();
    const tabs = TABS.map(([k, icon, label]) => `<button type="button" class="pc-tab${k === tab ? " on" : ""}" data-pt="pc-tab" data-t="${k}"
      aria-pressed="${k === tab}"><span aria-hidden="true">${icon}</span>${label}</button>`).join("");
    const head = `<div class="pc-wallet"><span aria-label="${coll.coins} pièces">🪙 ${coll.coins}</span><span aria-label="${coll.dust} poussières d'étoile">✨ ${coll.dust}</span>
      ${coll.shiny ? '<span class="pc-shiny">Shiny ✨</span>' : ""}</div>`;
    const body = { wear: wearTab, dex: dexTab, shop: shopTab, craft: craftTab, showcase: showcaseTab, certs: certsTab }[tab](p);
    UI().show(`${UI().top("Collection", true)}${head}<nav class="pc-tabs" aria-label="Collection">${tabs}</nav>${body}`, "coll");
  }

  // Porter : Zicou au milieu, les emplacements, ce qu'on a pour l'emplacement choisi.
  function wearTab(p) {
    const owned = coll.dex.flatMap((s) => s.items).filter((x) => x.owned && !x.masked);
    const slots = coll.slots.map((s) => {
      const n = owned.filter((x) => x.slot === s.id).length, on = coll.acc[s.id];
      return `<button type="button" class="pc-slot${s.id === slot ? " on" : ""}" data-pt="pc-slot" data-s="${e(s.id)}" aria-pressed="${s.id === slot}">
        ${e(s.label)}${on ? " •" : ""}<small>${n}</small></button>`;
    }).join("");
    const mine = owned.filter((x) => x.slot === slot);
    const tiles = mine.map((x) => `<button type="button" class="pc-tile pc-b-${e(x.rarity)}${coll.acc[slot] === x.id ? " on" : ""}" data-pt="pc-wear" data-i="${e(x.id)}"
        aria-pressed="${coll.acc[slot] === x.id}">${mini(x)}<b>${e(x.label)}</b>${tag(x.rarity)}${x.serial ? `<small>${serial(x)}</small>` : ""}</button>`).join("");
    return `<div class="pt-hero pc-wear-hero">${UI().art(p)}</div><div class="pc-slots" role="group" aria-label="Emplacements">${slots}</div>
      <div class="pc-grid">${coll.acc[slot] ? `<button type="button" class="pc-tile" data-pt="pc-wear" data-i="" data-s="${e(slot)}"><span class="pc-mini pc-none" aria-hidden="true">🚫</span><b>Retirer</b></button>` : ""}
      ${tiles || `<p class="pt-muted">Rien pour cet emplacement pour l'instant : coffres, boutique et atelier en donnent.</p>`}</div>`;
  }

  // Zicoudex : toutes les séries, par rareté. Pas à toi : grisé ; Mythique pas à toi : « ??? » scintillant.
  function dexTab() {
    const have = coll.dex.reduce((n, s) => n + s.have, 0), total = coll.dex.reduce((n, s) => n + s.total, 0);
    const myth = coll.dex.flatMap((s) => s.items).filter((x) => x.rarity === "mythic" && !x.masked).length;
    const series = coll.dex.map((s) => {
      const done = s.have >= s.total;
      const items = s.items.map((x, i) => x.masked
        ? `<button type="button" class="pc-tile pc-masked" data-pt="pc-detail" data-s="${e(s.id)}" data-n="${i}" aria-label="Mythique mystère, pas encore trouvé">
            <span class="pc-mini pc-mystery" aria-hidden="true">???</span><b>???</b>${tag("mythic")}</button>`
        : `<button type="button" class="pc-tile pc-b-${e(x.rarity)}${x.owned ? "" : " pc-off"}" data-pt="pc-detail" data-s="${e(s.id)}" data-n="${i}"
            aria-label="${e(x.label)}, ${e(RARITY[x.rarity])}, ${x.owned ? "à toi" : "pas encore"}">${mini(x)}<b>${e(x.label)}</b>${tag(x.rarity)}
            ${x.serial ? `<small>${serial(x)}</small>` : ""}</button>`).join("");
      return `<section class="pc-series${done ? " done" : ""}"><h3>${e(s.emoji)} ${e(s.label)} <small>${s.have}/${s.total}${done ? " ✅" : ""}</small></h3>
        <div class="pc-bar" role="meter" aria-label="Série ${e(s.label)}" aria-valuemin="0" aria-valuemax="${s.total}" aria-valuenow="${s.have}"><i style="--v:${Math.round(100 * s.have / s.total)}%"></i></div>
        <p class="pt-muted pt-tiny">Série complète : +${s.bonus.coins} 🪙 et +${s.bonus.dust} ✨${done ? " (gagné)" : ""}</p><div class="pc-grid">${items}</div></section>`;
    }).join("");
    return `<div class="pt-card pc-dex-top"><b>${have} / ${total}</b> objets · Mythiques : <b>${myth}</b>
      <p class="pt-muted pt-tiny">Touchez un objet pour savoir où le trouver. Les Mythiques restent un mystère jusqu'à ce que tu en trouves un.</p></div>${series}${detail()}`;
  }
  function detail() {
    if (!picked) return "";
    const x = coll.dex.find((s) => s.id === picked.s)?.items[picked.n];
    if (!x) return "";
    if (x.masked) {
      return `<div class="pt-card pc-detail" role="dialog" aria-label="Objet mystère"><b>??? · Mythique numéroté</b><p>${e(x.where)}</p>
        <p class="pt-muted pt-tiny">Chance d'un Objet mystère dans chaque coffre : ${fmtPct((coll.odds.find((o) => o.kind === "mythic") || {}).pct || 0)}.
        Exemplaires limités, jamais réédités.</p><button type="button" class="pt-ghost" data-pt="pc-close">Fermer</button></div>`;
    }
    const acts = [];
    if (x.owned) acts.push(`<button type="button" class="pt-cta" data-pt="pc-wear" data-i="${e(x.id)}">Le porter</button>`);
    if (!x.owned && x.craft) acts.push(`<button type="button" class="pt-cta" data-pt="pc-craft" data-i="${e(x.id)}" ${coll.dust < x.craft ? 'aria-disabled="true"' : ""}>Fabriquer · ${x.craft} ✨</button>`);
    if (x.code) acts.push(`<a class="pt-ghost" href="/zicou/certificat?code=${encodeURIComponent(x.code)}" target="_blank" rel="noopener">📜 Certificat</a>`);
    return `<div class="pt-card pc-detail pc-b-${e(x.rarity)}" role="dialog" aria-label="${e(x.label)}">${mini(x, "pc-big")}<b>${e(x.label)}</b> ${tag(x.rarity)}
      ${x.serial ? `<p class="pc-serial">${serial(x)}</p>` : ""}<p>${x.owned ? "✅ À toi" : `Où le trouver : ${e(x.where)}`}</p>
      <div class="pc-acts">${acts.join("")}<button type="button" class="pt-ghost" data-pt="pc-close">Fermer</button></div></div>`;
  }

  function shopTab() {
    const card = (x, what) => `<li class="pc-buy pc-b-${e(x.rarity || "common")}">${x.slot ? mini(x) : `<span class="pc-mini pc-none" aria-hidden="true">${e(x.emoji)}</span>`}
      <span><b>${e(x.label)}</b>${x.rarity ? tag(x.rarity) : ""}</span>
      ${x.owned ? '<small class="pc-own">Déjà à toi ✓</small>' : x.bought ? '<small class="pc-own">Acheté ✓</small>'
        : `<button type="button" class="pt-cta pc-price" data-pt="pc-buy" data-i="${e(what || x.id)}" ${coll.coins < x.price ? 'aria-disabled="true"' : ""}
            aria-label="Acheter ${e(x.label)} pour ${x.price} pièces">${x.price} 🪙</button>`}</li>`;
    return `<section class="pt-card"><h2>🛍️ Boutique du jour</h2><p class="pt-muted pt-tiny">4 articles, renouvelés chaque jour à minuit. Un objet qui part revient un autre jour.</p>
        <ul class="pc-list">${coll.shop.map((x) => card(x)).join("")}</ul></section>
      <section class="pt-card"><h2>🏠 Décor de la chambre</h2><p class="pt-muted pt-tiny">Le fond derrière ${e(UI().current()?.name || "Zicou")}. Toujours en vente.</p>
        <ul class="pc-list">${coll.decor.map((x) => card(x)).join("")}</ul></section>
      <section class="pt-card"><h2>🧁 Goûters rares</h2><p class="pt-muted pt-tiny">${coll.snacks_left} encore aujourd'hui (3 par jour au plus). Rangés dans son sac.</p>
        <ul class="pc-list">${coll.snacks.map((x) => card({ ...x, rarity: "", owned: false }, `snack:${x.id}`)).join("")}</ul></section>
      <p class="pt-muted pt-small">Les pièces se gagnent en jouant avec lui (coffres, missions, séries). Elles ne s'achètent jamais avec de l'argent
        et ne valent rien en argent.</p>`;
  }

  function craftTab() {
    const rates = coll.rates.map((r) => `<tr><th>${tag(r.rarity)}</th><td>${r.dust} ✨</td><td>${r.craft} ✨</td></tr>`).join("");
    const todo = coll.craft.filter((x) => !x.owned);
    const groups = ["common", "rare", "epic", "legendary"].map((r) => {
      const list = todo.filter((x) => x.rarity === r);
      if (!list.length) return "";
      return `<h3>${e(RARITY[r])}</h3><ul class="pc-list">${list.map((x) => `<li class="pc-buy pc-b-${e(r)}">${mini(x)}<span><b>${e(x.label)}</b>${tag(r)}</span>
        <button type="button" class="pt-cta pc-price" data-pt="pc-craft" data-i="${e(x.id)}" ${coll.dust < x.cost ? 'aria-disabled="true"' : ""}
          aria-label="Fabriquer ${e(x.label)} pour ${x.cost} poussières">${x.cost} ✨</button></li>`).join("")}</ul>`;
    }).join("");
    return `<section class="pt-card"><h2>🔨 L'atelier</h2><p>Tu as <b>${coll.dust} ✨</b> poussières d'étoile.</p>
      <table class="pc-rates"><thead><tr><th>Rareté</th><th>Un doublon donne</th><th>Fabriquer coûte</th></tr></thead><tbody>${rates}</tbody></table>
      <p class="pt-muted pt-tiny">Un accessoire déjà à toi, tiré d'un coffre, devient de la poussière. Les Mythiques et les souvenirs de soirée ne se
        fabriquent jamais. Un Légendaire fabriqué reçoit son numéro et son certificat.</p></section>
      <section class="pt-card">${groups || "<p>Tu as tout ce que l'atelier sait faire 🎉</p>"}</section>`;
  }

  function showcaseTab() {
    const owned = coll.dex.flatMap((s) => s.items).filter((x) => x.owned && !x.masked);
    const cur = coll.showcase || { title: "", items: [] };
    const chosen = new Set(cur.items.map((x) => x.id));
    const tiles = owned.map((x) => `<label class="pc-tile pc-b-${e(x.rarity)}"><input type="checkbox" name="item" value="${e(x.id)}" ${chosen.has(x.id) ? "checked" : ""}>
      ${mini(x)}<b>${e(x.label)}</b>${tag(x.rarity)}</label>`).join("");
    return `<form class="pt-card pc-showcase" data-pt-form="showcase"><h2>🏆 Ma vitrine</h2>
      <p class="pt-muted pt-tiny">3 objets au plus, que tes amis voient en visite. Le titre est vérifié (ni insulte, ni lien, ni numéro) ;
        tes amis peuvent le signaler.</p>
      <label for="pcTitle">Titre</label><input id="pcTitle" name="title" maxlength="40" autocomplete="off" value="${e(cur.title)}" placeholder="Ma collection disco">
      <div class="pc-grid">${tiles || "<p class='pt-muted'>Ta collection est encore vide.</p>"}</div>
      <button type="submit" class="pt-cta">Enregistrer la vitrine</button></form>`;
  }

  function certsTab() {
    const list = coll.items.map((x) => `<li class="pc-cert pc-b-${e(x.rarity)}">${mini(x)}<span><b>${e(x.label)}</b>${tag(x.rarity)}
        <span class="pc-serial">${serial(x)}</span><small>Frappé le ${e(new Date(x.minted_at).toLocaleDateString("fr-CH"))} · ${e(x.code || "certificat en cours")}</small></span>
        ${x.code ? `<a class="pt-ghost" href="/zicou/certificat?code=${encodeURIComponent(x.code)}" target="_blank" rel="noopener">Vérifier</a>` : ""}</li>`).join("");
    return `<section class="pt-card"><h2>📜 Certificats</h2>
      <p class="pt-muted pt-tiny">Chaque Légendaire et Mythique a un numéro, un certificat signé par Party et l'historique de ses propriétaires.
        Rien à voir avec une crypto-monnaie : aucune valeur en argent.</p>
      ${list ? `<ul class="pc-list">${list}</ul>` : "<p>Pas encore de Légendaire ni de Mythique.</p>"}</section>
      <form class="pt-card" data-pt-form="verify"><label for="pcCode">Vérifier un objet (code ZC-…)</label>
        <div class="pt-name-row"><input id="pcCode" name="code" maxlength="20" autocomplete="off" placeholder="ZC-XXXX-XXXX-XXXX"><button type="submit" class="pt-ghost">Vérifier</button></div></form>`;
  }

  // ── Actions ──
  async function act(body, done) {
    if (busy) return;
    busy = true;
    try {
      const data = await UI().api("coll", body);
      accept(data);
      UI().cue("win");
      UI().buzz([20, 40, 20]);
      render();
      UI().announce(data.news);
      if (done) done(data);
    } catch (err) {
      if (err.login) return UI().login();
      UI().say(err.message, true);
      UI().cue("lose");
    } finally {
      busy = false;
    }
  }

  function click(b) {
    switch (b.dataset.pt) {
      case "pc-tab": tab = b.dataset.t; picked = null; return render();
      case "pc-slot": slot = b.dataset.s; return render();
      case "pc-wear": return act({ action: "equip", item: b.dataset.i || "", slot: b.dataset.s || "" });
      case "pc-detail": picked = { s: b.dataset.s, n: Number(b.dataset.n) }; render(); return UI().root()?.querySelector(".pc-detail")?.scrollIntoView({ block: "nearest" });
      case "pc-close": picked = null; return render();
      case "pc-buy":
        if (b.getAttribute("aria-disabled") === "true") return UI().say("Pas assez de pièces pour l'instant 🪙 Elles se gagnent en jouant.", true);
        return act({ action: "buy", item: b.dataset.i });
      case "pc-craft":
        if (b.getAttribute("aria-disabled") === "true") return UI().say("Pas assez de poussière d'étoile ✨ Les doublons en donnent.", true);
        return act({ action: "craft", item: b.dataset.i }, (data) => {
          const made = data.effect;
          if (made?.serial) revealItem({ kind: "item", item: made.item, rarity: "legendary", serial: made.serial, code: made.code, label: "Fabriqué à l'atelier" });
        });
      case "pc-next": return nextReveal();
      case "pc-wear-new": return act({ action: "equip", item: b.dataset.i }, () => UI().home());
      case "pc-report": return reportScreen(b.dataset.k);
      case "pc-reason": return sendReport(b.dataset.k, b.dataset.r);
      case "pc-block":
        if (b.dataset.sure !== "1") { b.dataset.sure = "1"; b.textContent = `Confirmer : bloquer ${visiting?.member || ""}`; b.classList.add("pc-danger"); return; }
        return block();
      case "pc-back-visit": return visiting && UI().root()?.querySelector('[data-pt="home"]')?.click();
      default:
    }
  }
  function submit(form) {
    if (form.dataset.ptForm === "showcase") {
      const fd = new FormData(form);
      const items = fd.getAll("item").map(String);
      if (items.length > 3) return UI().say("3 objets au plus dans la vitrine.", true);
      return act({ action: "showcase", items, title: String(fd.get("title") || "").trim() }, () => UI().say("🏆 Vitrine enregistrée"));
    }
    if (form.dataset.ptForm === "verify") {
      const code = String(new FormData(form).get("code") || "").trim();
      if (code) window.open(`/zicou/certificat?code=${encodeURIComponent(code)}`, "_blank", "noopener");
    }
  }

  // ── Révélations ──
  // Accessoire du coffre : carte à la couleur de sa rareté. Mythique : le grand moment, en plusieurs temps.
  function revealItem(found) {
    const info = found.item_info || itemInfo(found.item) || { id: found.item, label: found.label, slot: "head", rarity: found.rarity };
    if (found.rarity === "mythic" && !found.dup) return mythic(info, found);
    const p = UI().current();
    const extra = found.dup ? {} : { [info.slot]: info.id };
    UI().show(`${UI().top("Surprise !", true)}<div class="pt-card pt-reveal pc-reveal pc-b-${e(found.rarity)}">
      <div class="pc-glow" aria-hidden="true"></div>${p ? UI().art(p, "pc-reveal-art", extra) : ""}
      <h2>${e(found.dup ? found.label : info.label)}</h2>${tag(found.rarity)}${found.serial ? `<p class="pc-serial">${serial(found)}</p>` : ""}
      <p class="pt-muted">${found.dup ? "Tu l'avais déjà : il devient de la poussière d'étoile pour l'atelier ✨" : "Rangé dans ta collection."}</p>
      <div class="pc-acts">${found.dup ? "" : `<button type="button" class="pt-cta" data-pt="pc-wear-new" data-i="${e(info.id)}">Le porter</button>`}
      <button type="button" class="${found.dup ? "pt-cta" : "pt-ghost"}" data-pt="home">Super !</button></div></div>`, "reveal");
    UI().say(`Trouvé : ${found.dup ? found.label : info.label}`);
    UI().cue("win");
    UI().buzz([30, 60, 30]);
  }
  function itemInfo(id) {
    for (const s of coll?.dex || []) for (const x of s.items) if (x.id === id) return x;
    return null;
  }
  // Mythique : 1) antennes arc-en-ciel, 2) la boule se brise en éclats, 3) l'objet apparaît, numéro tamponné.
  function mythic(info, found) {
    const p = UI().current();
    const calm = UI().calm();
    const shards = Array.from({ length: 14 }, (_, i) => `<i style="--a:${i * 25.7}deg;--d:${70 + (i % 4) * 22}px"></i>`).join("");
    UI().show(`<div class="pc-myth${calm ? " pc-calm" : ""}" data-step="1" role="dialog" aria-label="Objet mythique">
      <div class="pc-myth-stage">${p ? UI().art(p, "pc-myth-zicou") : ""}<div class="pc-shards" aria-hidden="true">${shards}</div>
        <div class="pc-myth-item" aria-hidden="true">${mini(info, "pc-huge")}</div></div>
      <p class="pc-myth-kicker">Objet mystère…</p>
      <h2 class="pc-myth-name">${e(info.label)}</h2>${tag("mythic")}
      <div class="pc-stamp" aria-label="Numéro ${e(serial(found))}">${e(serial(found))}</div>
      <p class="pt-muted pc-myth-note">Exemplaire numéroté, jamais réédité. Son certificat est signé par Party${found.code ? ` (${e(found.code)})` : ""}.</p>
      <div class="pc-acts pc-myth-acts"><button type="button" class="pt-cta" data-pt="pc-wear-new" data-i="${e(info.id)}">Le porter</button>
        <button type="button" class="pt-ghost" data-pt="coll" data-s="showcase">Mettre en vitrine</button>
        ${found.code ? `<a class="pt-ghost" href="/zicou/certificat?code=${encodeURIComponent(found.code)}" target="_blank" rel="noopener">📜 Certificat</a>` : ""}
        <button type="button" class="pt-ghost" data-pt="home">Plus tard</button></div></div>`, "reveal");
    const root = UI().root()?.querySelector(".pc-myth");
    const step = (n, ms, vib) => setTimeout(() => {
      if (!root?.isConnected) return;
      root.dataset.step = String(n);
      if (!calm && vib) UI().buzz(vib);
    }, ms);
    UI().cue("start");
    if (calm) { root.dataset.step = "4"; } else { step(2, 1300, [20, 30, 40, 50]); step(3, 2300, [60]); step(4, 3100, [120]); }
    setTimeout(() => { UI().cue("win"); UI().say(`Mythique ! ${info.label}, ${serial(found)}`); }, calm ? 50 : 3100);
  }

  // File de révélations (cadeaux d'événement, Zicou shiny), montrées à l'ouverture, une à une.
  function reveals(list) {
    queue = [...list];
    setTimeout(nextReveal, 600);
  }
  function nextReveal() {
    const r = queue.shift();
    if (!r) return UI().home();
    if (r.kind === "shiny") {
      const p = UI().current();
      UI().show(`${UI().top("Incroyable !", true)}<div class="pt-card pt-reveal pc-reveal pc-b-mythic">${p ? UI().art(p, "pc-reveal-art") : ""}
        <h2>Ton Zicou est SHINY ✨</h2><p class="pt-muted">Facettes chromées et irisées : 1 chance sur 64 à l'éclosion.</p>
        <button type="button" class="pt-cta" data-pt="${queue.length ? "pc-next" : "home"}">Trop beau !</button></div>`, "reveal");
      UI().cue("win");
      return UI().buzz([30, 60, 30, 60]);
    }
    const found = { kind: "item", item: r.item.id, item_info: r.item, rarity: r.item.rarity, dup: r.dup, serial: r.serial, of: r.of, code: r.code,
      label: r.dup ? `Doublon : ${r.item.label} (+${r.dust} poussière ✨)` : r.item.label };
    revealItem(found);
    const card = UI().root()?.querySelector(".pt-reveal, .pc-myth");
    card?.insertAdjacentHTML("afterbegin", `<p class="pc-from">🎁 Cadeau de « ${e(r.event)} »</p>`);
    if (queue.length) UI().root()?.querySelectorAll('[data-pt="home"]').forEach((b) => { b.dataset.pt = "pc-next"; b.textContent = "Suivant"; });
  }

  // ── Chez un ami : vitrine, Signaler, Bloquer ──
  function visitExtras(f) {
    visiting = f;
    const sc = f.pet.showcase;
    const show = sc ? `<section class="pt-card pc-their"><h3>🏆 ${e(sc.title || "Sa vitrine")}</h3><div class="pc-grid">${sc.items.map((x) =>
      `<div class="pc-tile pc-b-${e(x.rarity)}">${mini(x)}<b>${e(x.label)}</b>${tag(x.rarity)}${x.serial ? `<small>${serial(x)}</small>` : ""}</div>`).join("")}</div></section>` : "";
    return `${show}<div class="pc-safety"><button type="button" class="pt-ghost" data-pt="pc-report" data-k="pet_name">⚑ Signaler</button>
      <button type="button" class="pt-ghost" data-pt="pc-block">🚫 Bloquer ${e(f.member)}</button></div>`;
  }
  function reportScreen(kind) {
    if (!visiting) return;
    const what = visiting.pet.showcase?.title
      ? `<div class="pc-acts"><button type="button" class="pt-ghost${kind === "pet_name" ? " on" : ""}" data-pt="pc-report" data-k="pet_name">Son nom</button>
         <button type="button" class="pt-ghost${kind === "pet_showcase" ? " on" : ""}" data-pt="pc-report" data-k="pet_showcase">Sa vitrine</button></div>` : "";
    UI().show(`${UI().top("Signaler", true)}<div class="pt-card"><p>Qu'est-ce qui ne va pas dans ${kind === "pet_showcase" ? "la vitrine" : "le nom"} de
      « ${e(visiting.pet.name)} » ? L'équipe de modération de Party regarde chaque signalement.</p>${what}
      <ul class="pc-list">${REASONS.map(([r, l]) => `<li><button type="button" class="pt-ghost pc-wide" data-pt="pc-reason" data-k="${kind}" data-r="${r}">${l}</button></li>`).join("")}</ul></div>`, "report");
  }
  async function token() {
    try { return typeof freshToken === "function" ? await freshToken() : null; } catch { return null; }
  }
  async function moderation(path, body) {
    const t = await token();
    if (!t) return UI().login();
    const r = await fetch(`/api/account/moderation/${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: t, ...body }) });
    const data = await r.json().catch(() => null);
    if (!r.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Ça n'a pas marché, réessaie dans un instant.");
    return data;
  }
  async function sendReport(kind, reason) {
    try {
      await moderation("report", { kind, target: visiting.id, reason, comment: "" });
      UI().home();
      UI().say("Merci, c'est signalé. La modération va regarder 💜");
    } catch (err) {
      UI().say(err.message, true);
    }
  }
  async function block() {
    if (!visiting) return;
    try {
      await moderation("block", { user_id: visiting.id, on: true });
      visiting = null;
      UI().home();
      UI().say("Personne bloquée : vous ne vous verrez plus (Compagnon, messages, mentions, invitations). Réglages › Confidentialité pour débloquer.");
    } catch (err) {
      UI().say(err.message, true);
    }
  }

  window.PetCollection = Object.freeze({ open, click, submit, revealItem, reveals, visitExtras });
})();
