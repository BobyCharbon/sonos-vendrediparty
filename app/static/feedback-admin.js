// 💬 Gestion des retours — partagée par l'app (onglet « Retours » d'un compte admin) et /admin.
// Statuts, zones, plateformes, efforts et vues viennent du serveur (« meta » de GET /api/admin/feedback,
// STATUSES de app/feedback.py) : une seule source de vérité. L'invité ne voit jamais les statuts internes.
// ✏️ : classement, instructions pour Claude, mot pour l'invité, fil admin ↔ Claude, historique ;
// 🤖 : confié à Claude (issue GitHub → commit sur develop) → 🧪 à vérifier par l'admin.
// Usage : FeedbackAdmin.mount(élément, { onCount(n) }) ; FeedbackAdmin.load() pour rafraîchir ;
// FeedbackAdmin.classifyHtml() / readClassify() / create() pour le formulaire « Mon avis » de l'admin.
(function () {
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const notify = (msg, kind) => (typeof toast === "function" ? toast(msg, kind) : alert(msg));
  const CLAUDE = { pending: "🤖 Claude corrige", fixed: "🧪 Corrigé sur develop", failed: "⚠️ Échec de Claude" };
  const SORTS = [["recent", "🕒 Récents"], ["priority", "🔥 Priorité"], ["status", "🏷️ Statut"], ["area", "🧭 Zone"],
    ["effort", "⏱️ Effort"], ["oldest", "⌛ Plus ancien en attente"]];
  const FINE = [["status", "Statut"], ["area", "Zone"], ["platform", "Plateforme"], ["effort", "Effort"], ["priority", "Priorité"], ["tag", "Étiquette"]];
  const stored = (key, fallback) => { try { return localStorage.getItem(key) || fallback; } catch { return fallback; } };
  const keep = (key, value) => { try { localStorage.setItem(key, value); } catch { /* navigation privée */ } };
  let sortBy = stored("fbSort", "recent"), groupByArea = stored("fbGroup", "") === "1", view = "mine", search = "";
  let root = null, onCount = () => {}, items = [], kinds = {}, meta = null, claudeReady = false, editing = "", creating = false;
  let fine = { status: "", area: "", platform: "", effort: "", priority: "", tag: "" };
  const drafts = {};  // brouillons du formulaire ✏️ (gardés quand la liste se rafraîchit)
  let metaWaiters = [];

  const statusOf = (key) => meta?.statuses.find((s) => s.key === key) || { key, label: key, icon: "", color: "" };
  const statusRank = (key) => { const i = meta?.statuses.findIndex((s) => s.key === key); return i >= 0 ? i : 99; };
  const viewOf = (key) => meta?.views.find((v) => v.key === key) || { statuses: [] };
  const inView = (i, key) => key === "all" || viewOf(key).statuses.includes(i.status);
  const pendingCount = () => items.filter((i) => (meta?.mine || ["new", "questions", "verify"]).includes(i.status)).length;
  const optionList = (pairs, value, empty) => (empty === undefined ? "" : `<option value="">${escape(empty)}</option>`)
    + pairs.map(([k, label]) => `<option value="${escape(k)}" ${k === value ? "selected" : ""}>${escape(label)}</option>`).join("");
  const statusPairs = (all) => (meta?.statuses || []).filter((s) => all || !s.technical).map((s) => [s.key, `${s.icon} ${s.label}`]);
  const prioPairs = () => (meta?.priorities || []).map((p) => [p.key, p.label]);

  async function call(path, body) {
    const r = await fetch(path, body === undefined ? { credentials: "same-origin" }
      : { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Erreur, réessaie");
    return data;
  }

  function take(r) {
    items = r.items; kinds = r.kinds || kinds; claudeReady = !!r.claude_ready;
    const first = !meta && r.meta;
    if (r.meta) meta = r.meta;
    renderToolbar();  // étiquettes connues : le filtre suit
    if (first) { metaWaiters.forEach((f) => f(meta)); metaWaiters = []; }
    render();
  }

  // --- Champs de classement (création et ✏️) -----------------------------------------------------------
  function classifyHtml(v = {}, opts = {}) {
    if (!meta) return "";
    const platforms = v.platforms || [];
    return `<div class="fb-classify">
      <label class="fb-field"><span>Statut</span><select data-fbc="status">${optionList(statusPairs(false).filter(([k]) => !opts.creating || !["done", "declined"].includes(k)), v.status || "new")}</select></label>
      <label class="fb-field"><span>Priorité</span><select data-fbc="priority">${optionList(prioPairs(), v.priority || "", "Sans")}</select></label>
      <label class="fb-field"><span>Zone</span><select data-fbc="area">${optionList(Object.entries(meta.areas), v.area || "", opts.creating ? "Selon l'onglet" : undefined)}</select></label>
      <label class="fb-field"><span>Effort</span><select data-fbc="effort">${optionList(Object.entries(meta.efforts), v.effort || "", "Pas estimé")}</select></label>
      <fieldset class="fb-field fb-platforms"><legend>Plateformes</legend>${Object.entries(meta.platforms).map(([k, label]) =>
        `<label><input type="checkbox" data-fbc-platform="${escape(k)}" ${platforms.includes(k) ? "checked" : ""}> ${escape(label)}</label>`).join("")}</fieldset>
      <label class="fb-field fb-wide"><span>Étiquettes <small>(séparées par des virgules, ${meta.max_tags} max)</small></span>
        <input type="text" data-fbc="tags" maxlength="220" value="${escape((v.tags || []).join(", "))}" placeholder="Ex. : joystick, iOS 26"></label>
      ${opts.note === false ? "" : `<label class="fb-field fb-wide"><span>Note / instructions pour Claude</span>
        <textarea data-fbc="note" maxlength="2000" rows="2" placeholder="Ce qu'il faut faire, ce qu'il reste à décider…">${escape(v.note || "")}</textarea></label>`}
    </div>`;
  }

  function readClassify(el) {
    const val = (k) => el.querySelector(`[data-fbc="${k}"]`)?.value ?? undefined;
    const out = { status: val("status"), priority: val("priority"), area: val("area"), effort: val("effort"),
      platforms: [...el.querySelectorAll("[data-fbc-platform]")].filter((c) => c.checked).map((c) => c.dataset.fbcPlatform),
      tags: (val("tags") || "").split(",").map((t) => t.trim()).filter(Boolean) };
    if (el.querySelector('[data-fbc="note"]')) out.note = val("note");
    if (!out.area) delete out.area;  // « selon l'onglet » : le serveur la déduit du contexte
    Object.keys(out).forEach((k) => out[k] === undefined && delete out[k]);
    return out;
  }

  // --- Affichage d'un avis -----------------------------------------------------------------------------
  function metaLine(i) {
    const when = new Date(i.at * 1000).toLocaleString("fr-CH", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    const names = typeof GAME_NAMES !== "undefined" ? GAME_NAMES : {};
    const where = i.context?.game ? ` · jeu : ${escape(names[i.context.game] || i.context.game)}` : "";
    const site = i.context?.site === "Test" ? " · 🧪 site de test" : "";  // liste commune aux deux sites
    return `${escape(kinds[i.kind] || i.kind)} · ${escape(i.name)} · ${when}${where}${site}`;
  }

  function chips(i) {
    const st = statusOf(i.status), out = [];
    out.push(`<span class="fb-chip fb-stchip ${escape(i.status)}" style="--st:${escape(st.color)}">${escape(st.icon)} ${escape(st.label)}</span>`);
    if (i.area && meta?.areas[i.area]) out.push(`<span class="fb-chip">${escape(meta.areas[i.area])}</span>`);
    (i.platforms || []).forEach((p) => out.push(`<span class="fb-chip">${escape(meta?.platforms[p] || p)}</span>`));
    if (i.effort) out.push(`<span class="fb-chip">${escape(meta?.efforts[i.effort] || i.effort)}</span>`);
    (i.tags || []).forEach((t) => out.push(`<span class="fb-chip fb-tag">#${escape(t)}</span>`));
    if (i.comments?.length) out.push(`<span class="fb-chip">💬 ${i.comments.length}</span>`);
    const links = [...(i.related || []).map((r) => `🔗 #${r}`), i.duplicate_of && `♊ doublon de #${i.duplicate_of}`, i.blocked_by && `⛔ bloqué par #${i.blocked_by}`].filter(Boolean);
    links.forEach((l) => out.push(`<span class="fb-chip">${escape(l)}</span>`));
    return `<div class="fb-chips">${out.join("")}</div>`;
  }

  // Avis reformulé par l'IA à la demande de l'invité (app/ai_feedback.py) : titre et version structurée,
  // sous son texte d'origine (gardé tel quel en titre de la ligne).
  function aiHtml(i) {
    const a = i.context?.ai;
    if (!a?.title) return "";
    const rows = [["Description", a.description], ["Étapes", (a.steps || []).join(" → ")], ["Attendu", a.expected],
      ["Constaté", a.actual], ["Besoin", a.need], ["Proposition", a.proposal], ["Jeu", a.game], ["Appareil", a.device]]
      .filter(([, v]) => v).map(([k, v]) => `<div><b>${k} :</b> ${escape(v)}</div>`).join("");
    return `<details class="fb-note fb-ai-note"><summary>✨ ${escape(a.title)}</summary>${rows}</details>`;
  }

  function verifyHtml(i, id) {
    if (i.status !== "verify") return "";
    return `<div class="fb-verify"><b>🧪 À vérifier</b>
      ${i.claude?.migrations?.length ? `<div class="fb-migration"><b>⚠️ Migration Supabase à appliquer d'abord</b>
        <pre>${i.claude.migrations.map(escape).join("\n")}</pre>
        <small>Applique-la sur la base de test avant de tester (la prod seulement après ton accord).</small></div>` : ""}
      <small>${i.claude?.state === "fixed" ? "Claude a commité sa correction sur develop. Teste-la sur le site de test (après reconstruction de l'image et redéploiement), puis :" : "Vérifie que c'est bien corrigé, puis :"}</small>
      <div class="fb-edit-btns"><button data-fb="done" data-id="${id}">✅ Validé, c'est corrigé</button>
      <button class="secondary" data-fb="ready" data-id="${id}">↩︎ Pas corrigé</button></div></div>`;
  }

  function itemHtml(i) {
    const id = escape(i.id);
    const problem = i.claude?.state === "failed" ? `<div class="fb-problem"><b>⚠️ Problème à corriger</b>
        <pre>${escape(i.claude.error || "Raison en cours de récupération…")}</pre>
        <small>Corrige la cause (réglage, instructions plus précises…), puis ✏️ → 🤖 Envoyer à Claude.</small></div>` : "";
    const quick = `<select class="fb-quick" data-fb-status="${id}" aria-label="Changer le statut">${optionList(statusPairs(i.status === "sent")
      .filter(([k]) => k !== "declined"), i.status)}</select>`;
    return `<div class="track fb-item ${escape(i.status)}"><div class="meta">
        <div class="title">${i.priority ? `<span class="fb-prio ${escape(i.priority)}">${escape(meta?.priorities.find((p) => p.key === i.priority)?.label || "")}</span> ` : ""}${escape(i.text)}</div>
        <div class="artist">${metaLine(i)} · <button type="button" class="fb-id" data-fb-id="${id}" aria-label="Copier l'identifiant ${id}">#${id}</button></div>
        ${chips(i)}${aiHtml(i)}
        ${i.note && editing !== i.id ? `<div class="fb-note">📝 ${escape(i.note)}</div>` : ""}
        ${i.reply && editing !== i.id ? `<div class="fb-note">💬 ${escape(i.reply)}</div>` : ""}
        ${i.claude ? `<a class="fb-claude ${escape(i.claude.state)}" href="${escape(i.claude.url)}" target="_blank" rel="noopener">${CLAUDE[i.claude.state] || ""} · #${escape(i.claude.number)}</a>` : ""}
        ${verifyHtml(i, id)}${problem}</div>
      <div class="icon-btns">
        <button class="secondary" data-fb-edit="${id}" aria-label="Classer, instructions, mot pour l'invité, discussion">✏️</button>
        ${quick}
        <button class="danger" data-fb="delete" data-id="${id}" aria-label="Supprimer">✕</button></div>
      ${editing === i.id ? editHtml(i) : ""}</div>`;
  }

  function editHtml(i) {
    const id = escape(i.id), pending = i.claude?.state === "pending", d = { ...i, ...(drafts[i.id] || {}) };
    const who = { admin: "Toi", claude: "Claude 🤖" };
    const thread = (i.comments || []).map((c) => `<div class="fb-msg ${escape(c.by)}"><b>${escape(who[c.by] || c.by)}</b>
      <small>${new Date(c.at * 1000).toLocaleString("fr-CH", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</small>
      <div>${escape(c.text)}</div></div>`).join("") || `<p class="sub">Aucun message. Une question pour Claude, ou sa réponse, s'écrit ici.</p>`;
    const history = (i.history || []).slice().reverse().map((h) => {
      const label = (v) => (Array.isArray(v) ? v.join(", ") || "—" : (h.field === "status" ? statusOf(v).label : v) || "—");
      const change = h.field === "created" ? `créé (${escape(statusOf(h.to).label)})` : "to" in h
        ? `${escape(h.field)} : ${escape(label(h.from))} → ${escape(label(h.to))}` : `${escape(h.field)} modifié`;
      return `<li>${new Date(h.at * 1000).toLocaleString("fr-CH", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })} · ${escape(who[h.by] || h.by)} · ${change}</li>`;
    }).join("");
    return `<div class="fb-edit" data-fb-form="${id}">
      ${classifyHtml(d, { note: false })}
      <div class="fb-classify">
        <label class="fb-field"><span>Avis liés <small>(#id, virgules)</small></span><input type="text" data-fbx="related" value="${escape((d.related || []).join(", "))}"></label>
        <label class="fb-field"><span>Doublon de</span><input type="text" data-fbx="duplicate_of" value="${escape(d.duplicate_of || "")}" placeholder="#id"></label>
        <label class="fb-field"><span>Bloqué par</span><input type="text" data-fbx="blocked_by" value="${escape(d.blocked_by || "")}" placeholder="#id"></label>
      </div>
      <label class="g-label" for="fbNote-${id}">Instructions pour Claude</label>
      <textarea id="fbNote-${id}" data-fb-note="${id}" maxlength="2000" rows="3" placeholder="Ex. : sur iPhone, le bouton Révéler reste grisé avec 2 joueurs ; il doit être actif dès qu'une personne a validé.">${escape(d.note ?? "")}</textarea>
      <div class="fb-edit-btns">
        <button class="secondary" data-fb-save="${id}">💾 Enregistrer</button>
        <button class="secondary" data-fb-copy="${id}">📋 Copier le prompt</button>
        <button data-fb-claude="${id}" ${claudeReady && !pending ? "" : "disabled"}>🤖 Envoyer à Claude</button>
      </div>
      ${claudeReady ? "" : `<p class="sub">GitHub n'est pas configuré sur le serveur (GITHUB_TOKEN) : copie le prompt pour le donner à Claude toi-même.</p>`}
      <label class="g-label" for="fbReply-${id}">Mot pour l'invité <small>(affiché avec « Terminé » ou « Pas retenu »)</small></label>
      <textarea id="fbReply-${id}" data-fb-reply="${id}" maxlength="500" rows="2" placeholder="Ex. : c'est corrigé, merci ! / Pas prévu pour l'instant, mais on garde l'idée.">${escape(d.reply ?? "")}</textarea>
      <div class="fb-edit-btns">
        <button data-fb="done" data-id="${id}">✅ Terminé</button>
        <button class="secondary" data-fb="declined" data-id="${id}">🚫 Pas retenu</button>
      </div>
      <div class="g-label">Discussion avec Claude</div>
      <div class="fb-thread">${thread}</div>
      <textarea data-fb-comment="${id}" maxlength="1000" rows="2" placeholder="Réponds à Claude ou pose une question…">${escape(d.comment || "")}</textarea>
      <div class="fb-edit-btns"><button class="secondary" data-fb-send-comment="${id}">💬 Envoyer le message</button></div>
      ${history ? `<details class="fb-history"><summary>Historique</summary><ul>${history}</ul></details>` : ""}
    </div>`;
  }

  // --- Liste, vues, filtres, tris ------------------------------------------------------------------------
  function filtered() {
    const q = search.trim().toLowerCase();
    return items.filter((i) => inView(i, view)
      && (!fine.status || i.status === fine.status) && (!fine.area || i.area === fine.area)
      && (!fine.platform || (i.platforms || []).includes(fine.platform)) && (!fine.effort || (i.effort || "none") === fine.effort)
      && (!fine.priority || (i.priority || "none") === fine.priority)
      && (!fine.tag || (i.tags || []).some((t) => t.toLowerCase() === fine.tag.toLowerCase()))
      && (!q || [i.text, i.context?.ai?.title, i.note, i.name, i.id, i.reply, ...(i.tags || [])].some((s) => String(s || "").toLowerCase().includes(q))));
  }

  function sorted(list) {
    const prio = (i) => ({ high: 0, medium: 1, low: 2 }[i.priority] ?? 3);
    const area = (i) => Object.keys(meta?.areas || {}).indexOf(i.area);
    const effort = (i) => { const n = Object.keys(meta?.efforts || {}).indexOf(i.effort); return n < 0 ? 9 : n; };
    const done = (i) => (["done", "declined"].includes(i.status) ? 1 : 0);
    const by = {
      recent: (a, b) => b.at - a.at,
      priority: (a, b) => prio(a) - prio(b) || b.at - a.at,
      status: (a, b) => statusRank(a.status) - statusRank(b.status) || b.at - a.at,
      area: (a, b) => area(a) - area(b) || b.at - a.at,
      effort: (a, b) => effort(a) - effort(b) || prio(a) - prio(b),
      oldest: (a, b) => done(a) - done(b) || a.at - b.at,
    }[sortBy] || ((a, b) => b.at - a.at);
    return list.slice().sort(by);
  }

  function renderToolbar() {
    if (!root || !meta) return;
    const tags = [...new Set(items.flatMap((i) => i.tags || []))].sort();
    const pairs = { status: statusPairs(true), area: Object.entries(meta.areas), platform: Object.entries(meta.platforms),
      effort: [...Object.entries(meta.efforts), ["none", "Pas estimé"]], priority: [...prioPairs(), ["none", "Sans priorité"]], tag: tags.map((t) => [t, `#${t}`]) };
    root.querySelector(".fb-fine").innerHTML = FINE.map(([k, label]) =>
      `<label class="fb-field"><span>${label}</span><select data-fb-fine="${k}">${optionList(pairs[k], fine[k], "Tous")}</select></label>`).join("")
      + `<label class="fb-field"><span>Tri</span><select data-fb-sortsel>${optionList(SORTS, sortBy)}</select></label>
         <label class="fb-check"><input type="checkbox" data-fb-group ${groupByArea ? "checked" : ""}> Regrouper par zone</label>`;
  }

  function render() {
    if (!root) return;
    const n = pendingCount();
    root.querySelector(".fb-filter").innerHTML = (meta?.views || []).map((v) => {
      const count = v.key === "all" || v.key === "finished" ? 0 : items.filter((i) => inView(i, v.key)).length;
      return `<button type="button" class="${v.key === view ? "on" : ""}" data-fb-filter="${escape(v.key)}">${escape(v.label)}${count ? ` <i class="badge">${count}</i>` : ""}</button>`;
    }).join("");
    const shown = sorted(filtered());
    const empty = `<p class="empty" style="padding:12px">${view === "mine" ? "Rien à faire de ton côté pour l'instant 🎉" : "Aucun retour."}</p>`;
    let html = shown.map(itemHtml).join("");
    if (groupByArea && meta) {
      html = Object.entries(meta.areas).map(([k, label]) => {
        const group = shown.filter((i) => i.area === k);
        return group.length ? `<h3 class="fb-group">${escape(label)} <small>${group.length}</small></h3>${group.map(itemHtml).join("")}` : "";
      }).join("");
    }
    root.querySelector("#fbList").innerHTML = html || empty;
    onCount(n);
  }

  function renderCreate() {  // à part : un rafraîchissement de la liste ne vide jamais l'avis en cours d'écriture
    root.querySelector(".fb-create").innerHTML = creating ? createHtml() : "";
  }

  function createHtml() {
    return `<form class="card fb-form fb-new" data-fb-new>
      <div class="seg fb-kinds" role="radiogroup" aria-label="Type">${Object.entries(kinds).map(([k, label], n) =>
        `<button type="button" role="radio" class="${n === 0 ? "on" : ""}" aria-checked="${n === 0}" data-fb-newkind="${escape(k)}">${escape(label)}</button>`).join("")}</div>
      <textarea data-fb-newtext maxlength="1000" aria-label="Ton avis" placeholder="Ton idée, le bug, ce qu'il faut retravailler…"></textarea>
      ${classifyHtml({ status: "new" }, { creating: true })}
      <div class="fb-edit-btns"><button type="submit">＋ Créer l'avis</button><button type="button" class="secondary" data-fb-newcancel>Annuler</button></div>
    </form>`;
  }

  async function load(body) {
    try {
      take(await call("/api/admin/feedback", body));
      return true;
    } catch (e) { notify(e.message, "err"); return false; }
  }

  // --- Actions -------------------------------------------------------------------------------------------
  function formFields(id) {
    const form = root.querySelector(`[data-fb-form="${CSS.escape(id)}"]`);
    if (!form) return {};
    const ids = (k) => (form.querySelector(`[data-fbx="${k}"]`)?.value || "").split(",").map((s) => s.trim().replace(/^#/, "")).filter(Boolean);
    return { ...readClassify(form), related: ids("related"), duplicate_of: ids("duplicate_of")[0] || "", blocked_by: ids("blocked_by")[0] || "",
      note: form.querySelector("[data-fb-note]")?.value ?? "", reply: form.querySelector("[data-fb-reply]")?.value ?? "" };
  }

  function changed(id, fields) {
    const i = items.find((x) => x.id === id) || {};
    const same = (a, b) => JSON.stringify(a ?? "") === JSON.stringify(b ?? "");
    return Object.fromEntries(Object.entries(fields).filter(([k, v]) => !same(v, k === "priority" || k === "effort" ? i[k] || "" : i[k])));
  }

  async function saveEdit(id, extra = {}) {
    const fields = { ...changed(id, editing === id ? formFields(id) : {}), ...extra };
    if (!Object.keys(fields).length) return true;
    const ok = await load({ ids: [id], action: "edit", fields });
    if (ok) delete drafts[id];
    return ok;
  }

  async function setStatus(id, action) {
    if (action === "delete") {
      if (!confirm("Supprimer ce retour ?")) return;
      return load({ ids: [id], action: "delete" });
    }
    const reply = ((editing === id ? formFields(id).reply : null) ?? items.find((i) => i.id === id)?.reply ?? "").trim();
    if (action === "declined" && !reply) {
      editing = id; render();
      root.querySelector(`[data-fb-reply="${CSS.escape(id)}"]`)?.focus();
      return notify("Écris d'abord un mot pour l'invité : il verra pourquoi ce n'est pas retenu", "err");
    }
    if (await saveEdit(id, { status: action, ...(reply ? { reply } : {}) })) {
      if (["done", "declined"].includes(action)) { editing = ""; render(); notify(action === "done" ? "✅ Terminé : l'invité est averti" : "🚫 Pas retenu : l'invité voit ton mot", "ok"); }
    }
  }

  async function copyPrompt(id) {
    if (!await saveEdit(id)) return;
    try {
      const { prompt } = await call(`/api/admin/feedback/${encodeURIComponent(id)}/prompt`);
      await navigator.clipboard.writeText(prompt);
      notify("📋 Prompt copié", "ok");
    } catch (e) { notify(e.message || "Copie impossible", "err"); }
  }

  async function sendToClaude(id, btn) {
    if (!confirm("Confier ce retour à Claude ? Il corrigera selon tes instructions et commitera sur develop.")) return;
    btn.disabled = true;
    try {
      if (!await saveEdit(id)) return;
      take(await call(`/api/admin/feedback/${encodeURIComponent(id)}/claude`, {}));
      editing = ""; render();
      notify("🤖 Envoyé à Claude : suis-le dans « Pour Claude »", "ok");
    } catch (e) { notify(e.message, "err"); }
    finally { btn.disabled = false; }
  }

  async function sendComment(id) {
    const box = root.querySelector(`[data-fb-comment="${CSS.escape(id)}"]`);
    const text = (box?.value || "").trim();
    if (!text) return notify("Écris d'abord ton message", "err");
    if (await load({ ids: [id], action: "comment", text })) { if (drafts[id]) delete drafts[id].comment; render(); }
  }

  async function create(body) {
    const r = await call("/api/admin/feedback/new", body);
    take(r);
    return r.item;
  }

  async function submitNew(form) {
    const text = form.querySelector("[data-fb-newtext]").value.trim();
    if (text.length < 5) return notify("Écris ton avis (5 caractères au moins)", "err");
    const kind = form.querySelector("[data-fb-newkind].on")?.dataset.fbNewkind || "idea";
    try {
      await create({ kind, text, name: typeof guestName === "string" ? guestName : "", guest_id: typeof guestId === "string" ? guestId : "",
        fields: readClassify(form) });
      creating = false; renderCreate();
      notify("＋ Avis créé", "ok");
    } catch (e) { notify(e.message, "err"); }
  }

  function onClick(ev) {
    const t = ev.target;
    const f = t.closest("[data-fb-filter]");
    if (f) { view = f.dataset.fbFilter; return render(); }
    if (t.closest("[data-fb-newopen]")) { creating = !creating; renderCreate(); return root.querySelector("[data-fb-newtext]")?.focus(); }
    if (t.closest("[data-fb-newcancel]")) { creating = false; return renderCreate(); }
    const nk = t.closest("[data-fb-newkind]");
    if (nk) { nk.parentElement.querySelectorAll("[data-fb-newkind]").forEach((b) => { b.classList.toggle("on", b === nk); b.setAttribute("aria-checked", b === nk); }); return; }
    const ed = t.closest("[data-fb-edit]");
    if (ed) { editing = editing === ed.dataset.fbEdit ? "" : ed.dataset.fbEdit; render(); return root.querySelector(`[data-fb-note="${CSS.escape(editing)}"]`)?.focus(); }
    const sv = t.closest("[data-fb-save]");
    if (sv) return saveEdit(sv.dataset.fbSave).then((ok) => ok && notify("💾 Enregistré", "ok"));
    const cp = t.closest("[data-fb-copy]");
    if (cp) return copyPrompt(cp.dataset.fbCopy);
    const sc = t.closest("[data-fb-send-comment]");
    if (sc) return sendComment(sc.dataset.fbSendComment);
    const fid = t.closest("[data-fb-id]");
    if (fid) {  // identifiant unique de l'avis : à donner à Claude pour qu'il le retrouve tout de suite
      return navigator.clipboard.writeText(fid.dataset.fbId).then(() => notify(`📋 #${fid.dataset.fbId} copié`, "ok"),
        () => notify("Copie impossible", "err"));
    }
    const cl = t.closest("[data-fb-claude]");
    if (cl && !cl.disabled) return sendToClaude(cl.dataset.fbClaude, cl);
    const a = t.closest("[data-fb]");
    if (a) return setStatus(a.dataset.id, a.dataset.fb);
  }

  function onChange(ev) {
    const t = ev.target;
    if (t.matches("[data-fb-status]")) return setStatus(t.dataset.fbStatus, t.value);
    if (t.matches("[data-fb-fine]")) { fine = { ...fine, [t.dataset.fbFine]: t.value }; return render(); }
    if (t.matches("[data-fb-sortsel]")) { sortBy = t.value; keep("fbSort", sortBy); return render(); }
    if (t.matches("[data-fb-group]")) { groupByArea = t.checked; keep("fbGroup", groupByArea ? "1" : ""); return render(); }
    onInput(ev);
  }

  function onInput(ev) {
    const t = ev.target;
    if (t.matches("[data-fb-search]")) { search = t.value; return render(); }
    const form = t.closest("[data-fb-form]");
    if (form) {
      const id = form.dataset.fbForm;
      drafts[id] = { ...(drafts[id] || {}), ...formFields(id), comment: form.querySelector("[data-fb-comment]")?.value || "" };
    }
  }

  window.FeedbackAdmin = {
    mount(el, opts = {}) {
      root = el;
      onCount = opts.onCount || onCount;
      root.innerHTML = `<div class="fb-top"><button type="button" class="fb-newbtn" data-fb-newopen>＋ Nouvel avis</button>
          <input type="search" data-fb-search placeholder="Rechercher (texte, #id, étiquette)" aria-label="Rechercher dans les avis"></div>
        <div class="fb-create"></div>
        <div class="seg fb-filter" role="group" aria-label="Vues"></div>
        <details class="fb-filters"><summary>Filtres et tri</summary><div class="fb-fine fb-classify"></div></details>
        <div id="fbList" class="list" style="margin-top:10px"></div>`;
      root.addEventListener("click", onClick);
      root.addEventListener("change", onChange);
      root.addEventListener("input", onInput);
      root.addEventListener("submit", (ev) => { const f = ev.target.closest("[data-fb-new]"); if (f) { ev.preventDefault(); submitNew(f); } });
      return load();
    },
    load,
    create,
    classifyHtml,
    readClassify,
    /** Le serveur a envoyé meta (statuts, zones…) : le formulaire « Mon avis » de l'admin peut s'afficher. */
    whenMeta() { return meta ? Promise.resolve(meta) : new Promise((resolve) => metaWaiters.push(resolve)); },
    get pending() { return pendingCount(); },
  };
})();
