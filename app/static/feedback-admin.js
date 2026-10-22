// 💬 Gestion des retours des invités — partagée par l'app (onglet « Retours » d'un compte admin) et /admin.
// Statuts : à traiter → 🔧 en cours (l'invité voit « en cours de correction ») → ✅ terminé ou 🚫 pas retenu
// (l'invité est averti : notification + pastille). ✏️ : instructions pour Claude et mot pour l'invité ;
// 🤖 : confié à Claude (issue GitHub → commit sur develop) → 🧪 à vérifier par l'admin.
// Usage : FeedbackAdmin.mount(élément, { onCount(n) }) ; FeedbackAdmin.load() pour rafraîchir.
(function () {
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const notify = (msg, kind) => (typeof toast === "function" ? toast(msg, kind) : alert(msg));
  const FILTERS = [["new", "À traiter"], ["progress", "🔧 En cours"], ["verify", "🧪 À vérifier"], ["finished", "Terminés"], ["all", "Tout"]];
  const IN_FILTER = { new: ["new"], progress: ["progress", "sent"], verify: ["verify"], finished: ["done", "declined"] };
  const STATUS = { new: "À traiter", progress: "🔧 En cours", sent: "🤖 Chez Claude", verify: "🧪 À vérifier", done: "✅ Terminé", declined: "🚫 Pas retenu" };
  const CLAUDE = { pending: "🤖 Claude corrige", fixed: "🧪 Corrigé sur develop", failed: "⚠️ Échec de Claude" };
  let root = null, onCount = () => {}, items = [], kinds = {}, filter = "new", claudeReady = false, editing = "";
  const notes = {}, replies = {};

  async function call(path, body) {
    const r = await fetch(path, body === undefined ? { credentials: "same-origin" }
      : { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Erreur, réessaie");
    return data;
  }

  function meta(i) {
    const when = new Date(i.at * 1000).toLocaleString("fr-CH", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    const names = typeof GAME_NAMES !== "undefined" ? GAME_NAMES : {};
    const where = i.context?.game ? ` · jeu : ${escape(names[i.context.game] || i.context.game)}`
      : i.context?.tab ? ` · depuis ${escape({ music: "Musique", games: "Jeux", events: "Événements" }[i.context.tab] || i.context.tab)}` : "";
    return `${escape(kinds[i.kind] || i.kind)} · ${escape(i.name)} · ${when}${where}`;
  }

  function editHtml(i) {
    const id = escape(i.id), pending = i.claude?.state === "pending";
    return `<div class="fb-edit">
      <label class="g-label" for="fbNote-${id}">Instructions pour Claude</label>
      <textarea id="fbNote-${id}" data-fb-note="${id}" maxlength="2000" rows="3" placeholder="Ex. : sur iPhone, le bouton Révéler reste grisé avec 2 joueurs ; il doit être actif dès qu'une personne a validé.">${escape(notes[i.id] ?? i.note ?? "")}</textarea>
      <div class="fb-edit-btns">
        <button class="secondary" data-fb-save="${id}">💾 Enregistrer</button>
        <button class="secondary" data-fb-copy="${id}">📋 Copier le prompt</button>
        <button data-fb-claude="${id}" ${claudeReady && !pending ? "" : "disabled"}>🤖 Envoyer à Claude</button>
      </div>
      ${claudeReady ? "" : `<p class="sub">GitHub n'est pas configuré sur le serveur (GITHUB_TOKEN) : copie le prompt pour le donner à Claude toi-même.</p>`}
      <label class="g-label" for="fbReply-${id}">Mot pour l'invité <small>(affiché avec « Terminé » ou « Pas retenu »)</small></label>
      <textarea id="fbReply-${id}" data-fb-reply="${id}" maxlength="500" rows="2" placeholder="Ex. : c'est corrigé, merci ! / Pas prévu pour l'instant, mais on garde l'idée.">${escape(replies[i.id] ?? i.reply ?? "")}</textarea>
      <div class="fb-edit-btns">
        <button data-fb="done" data-id="${id}">✅ Terminé</button>
        <button class="secondary" data-fb="declined" data-id="${id}">🚫 Pas retenu</button>
      </div>
    </div>`;
  }

  function itemHtml(i) {
    const id = escape(i.id);
    const verify = i.status === "verify" ? `<div class="fb-verify"><b>🧪 À vérifier</b>
        ${i.claude?.migrations?.length ? `<div class="fb-migration"><b>⚠️ Migration Supabase à appliquer d'abord</b>
          <pre>${i.claude.migrations.map(escape).join("\n")}</pre>
          <small>La base est partagée entre le test et la prod : applique-la à la main (Supabase → SQL Editor) avant de tester.</small></div>` : ""}
        <small>Claude a commité sa correction sur develop. Teste-la sur le site de test (après reconstruction de l'image et redéploiement), puis :</small>
        <div class="fb-edit-btns"><button data-fb="done" data-id="${id}">✅ Validé, c'est corrigé</button>
        <button class="secondary" data-fb="new" data-id="${id}">↩︎ Pas corrigé</button></div></div>` : "";
    const problem = i.claude?.state === "failed" ? `<div class="fb-problem"><b>⚠️ Problème à corriger</b>
        <pre>${escape(i.claude.error || "Raison en cours de récupération…")}</pre>
        <small>Corrige la cause (réglage, instructions plus précises…), puis ✏️ → 🤖 Envoyer à Claude.</small></div>` : "";
    const progress = ["new", "done", "declined"].includes(i.status)
      ? `<button class="secondary" data-fb="progress" data-id="${id}" aria-label="Marquer en cours">🔧</button>` : "";
    const finish = ["new", "progress"].includes(i.status)
      ? `<button class="secondary" data-fb="done" data-id="${id}" aria-label="Terminé (l'invité est averti)">✅</button>` : "";
    const reopen = ["done", "declined"].includes(i.status)
      ? `<button class="secondary" data-fb="new" data-id="${id}" aria-label="Remettre à traiter">↺</button>` : "";
    return `<div class="track fb-item ${escape(i.status)}"><div class="meta">
        <div class="title">${escape(i.text)}</div>
        <div class="artist">${meta(i)} · <span class="fb-st ${escape(i.status)}">${STATUS[i.status] || ""}</span></div>
        ${i.note && editing !== i.id ? `<div class="fb-note">📝 ${escape(i.note)}</div>` : ""}
        ${i.reply && editing !== i.id ? `<div class="fb-note">💬 ${escape(i.reply)}</div>` : ""}
        ${i.claude ? `<a class="fb-claude ${escape(i.claude.state)}" href="${escape(i.claude.url)}" target="_blank" rel="noopener">${CLAUDE[i.claude.state] || ""} · #${escape(i.claude.number)}</a>` : ""}
        ${verify}${problem}</div>
      <div class="icon-btns">
        <button class="secondary" data-fb-edit="${id}" aria-label="Instructions, mot pour l'invité, statut">✏️</button>
        ${progress}${finish}${reopen}
        <button class="danger" data-fb="delete" data-id="${id}" aria-label="Supprimer">✕</button></div>
      ${editing === i.id ? editHtml(i) : ""}</div>`;
  }

  function render() {
    if (!root) return;
    const shown = items.filter((i) => filter === "all" || IN_FILTER[filter].includes(i.status));
    root.querySelector(".fb-filter").innerHTML = FILTERS.map(([k, label]) => {
      const n = k === "all" ? 0 : items.filter((i) => IN_FILTER[k].includes(i.status)).length;
      return `<button type="button" class="${k === filter ? "on" : ""}" data-fb-filter="${k}">${label}${n && k !== "finished" ? ` <i class="badge">${n}</i>` : ""}</button>`;
    }).join("");
    root.querySelector("#fbList").innerHTML = shown.map(itemHtml).join("")
      || `<p class="empty" style="padding:12px">${{ new: "Rien à traiter pour l'instant 🎉", verify: "Rien à vérifier." }[filter] || "Aucun retour."}</p>`;
    onCount(items.filter((i) => ["new", "verify"].includes(i.status)).length);
  }

  async function load(body) {
    try {
      const r = await call("/api/admin/feedback", body);
      items = r.items; kinds = r.kinds; claudeReady = r.claude_ready;
      render();
      return true;
    } catch (e) { notify(e.message, "err"); return false; }
  }

  async function saveNote(id) {
    const draft = notes[id];
    if (draft === undefined || draft === (items.find((i) => i.id === id)?.note || "")) return true;
    const ok = await load({ ids: [id], action: "note", note: draft });
    if (ok) delete notes[id];
    return ok;
  }

  async function setStatus(id, action) {
    if (action === "delete" && !confirm("Supprimer ce retour ?")) return;
    const reply = (replies[id] ?? items.find((i) => i.id === id)?.reply ?? "").trim();
    if (action === "declined" && !reply) {
      editing = id; render();
      root.querySelector(`[data-fb-reply="${CSS.escape(id)}"]`)?.focus();
      return notify("Écris d'abord un mot pour l'invité : il verra pourquoi ce n'est pas retenu", "err");
    }
    if (!await saveNote(id)) return;
    if (await load({ ids: [id], action, reply: ["done", "declined"].includes(action) ? reply : "" })) {
      delete replies[id];
      if (["done", "declined"].includes(action)) { editing = ""; render(); notify(action === "done" ? "✅ Terminé : l'invité est averti" : "🚫 Pas retenu : l'invité voit ton mot", "ok"); }
    }
  }

  async function copyPrompt(id) {
    if (!await saveNote(id)) return;
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
      if (!await saveNote(id)) return;
      const r = await call(`/api/admin/feedback/${encodeURIComponent(id)}/claude`, {});
      items = r.items; editing = "";
      render();
      notify("🤖 Envoyé à Claude : suis-le dans « En cours »", "ok");
    } catch (e) { notify(e.message, "err"); }
    finally { btn.disabled = false; }
  }

  function onClick(ev) {
    const t = ev.target;
    const f = t.closest("[data-fb-filter]");
    if (f) { filter = f.dataset.fbFilter; return render(); }
    const ed = t.closest("[data-fb-edit]");
    if (ed) { editing = editing === ed.dataset.fbEdit ? "" : ed.dataset.fbEdit; render(); return root.querySelector(`[data-fb-note="${CSS.escape(editing)}"]`)?.focus(); }
    const sv = t.closest("[data-fb-save]");
    if (sv) return saveNote(sv.dataset.fbSave).then((ok) => ok && notify("💾 Enregistré", "ok"));
    const cp = t.closest("[data-fb-copy]");
    if (cp) return copyPrompt(cp.dataset.fbCopy);
    const cl = t.closest("[data-fb-claude]");
    if (cl && !cl.disabled) return sendToClaude(cl.dataset.fbClaude, cl);
    const a = t.closest("[data-fb]");
    if (a) return setStatus(a.dataset.id, a.dataset.fb);
  }

  function onInput(ev) {
    const n = ev.target.closest("[data-fb-note]");
    if (n) notes[n.dataset.fbNote] = n.value;
    const r = ev.target.closest("[data-fb-reply]");
    if (r) replies[r.dataset.fbReply] = r.value;
  }

  window.FeedbackAdmin = {
    mount(el, opts = {}) {
      root = el;
      onCount = opts.onCount || onCount;
      root.innerHTML = `<div class="seg fb-filter" role="group" aria-label="Filtrer"></div><div id="fbList" class="list" style="margin-top:10px"></div>`;
      root.addEventListener("click", onClick);
      root.addEventListener("input", onInput);
      return load();
    },
    load,
    get pending() { return items.filter((i) => ["new", "verify"].includes(i.status)).length; },
  };
})();
