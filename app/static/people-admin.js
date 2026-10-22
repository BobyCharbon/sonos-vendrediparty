// 👥 Messages, invités et bannis de la soirée — en bas de l'onglet Musique de l'app (compte admin).
// Reprend Réglages de /admin : messages des invités (lire, répondre, supprimer), invités présents (renommer,
// déconnecter, bloquer 10 min, bannir, retirer leurs titres), bloqués / bannis des soirées précédentes.
// Ne lit pas l'état lui-même : music-admin.js lui transmet chaque état (PeopleAdmin.render), et chaque action
// renvoie le nouvel état à la musique (onState) pour que tout l'onglet reste cohérent.
// Usage : PeopleAdmin.mount(élément, { onState(état), onUnread(n) }) ; PeopleAdmin.render(état).
(function () {
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const notify = (msg, kind, action) => (typeof toast === "function" ? toast(msg, kind, action) : alert(msg));
  const usesSpotify = (source) => ["spotify", "spotify_sonos"].includes(source);
  const hhmm = (t) => new Date(t * 1000).toLocaleTimeString("fr-CH", { hour: "2-digit", minute: "2-digit" });
  const ONLINE = 30;  // s : « en ligne » si vu il y a moins de 30 s
  let root = null, onState = () => {}, onUnread = () => {}, seen = null;
  const drafts = {};  // réponses en cours de saisie, conservées entre deux rafraîchissements
  const q = (name) => root.querySelector(`[data-pa="${name}"]`);

  async function api(path, body) {
    const r = await fetch(path, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Erreur, réessaie");
    return data;
  }

  // 🔔 Notifications de l'hôte sur ce téléphone (même réglage que /admin : nouveaux messages, nouvelles parties).
  const NOTIF = { messages: "des nouveaux messages", games: "des nouvelles parties" };
  const SKELETON = `
    <div class="card hidden" data-pa="notifBox" style="margin-top:8px">
      <label class="switch-row"><span class="grow">🔔 Me prévenir des nouveaux messages</span><input type="checkbox" class="switch" data-pa-notif="messages"></label>
      <label class="switch-row" style="margin-top:8px"><span class="grow">🎮 Me prévenir quand quelqu'un lance un jeu</span><input type="checkbox" class="switch" data-pa-notif="games"></label>
      <p class="artist" data-pa="notifHelp" style="margin:6px 0 0;white-space:normal"></p>
    </div>
    <h2>Messages des invités <span class="badge hidden" data-pa="msgBadge"></span></h2>
    <div data-pa="messages" class="list"></div>
    <button type="button" class="secondary hidden" data-pa-act="readAll" style="width:100%;margin-top:8px">✓ Tout marquer comme lu</button>
    <h2>Invités</h2>
    <div data-pa="guests" class="list"></div>
    <div data-pa="bansBox" class="hidden"><h2>Bloqués / bannis</h2><div data-pa="bans" class="list"></div></div>`;

  function banLabel(ban) {
    if (!ban) return "";
    if (ban.until === 0) return "⛔ banni";
    return `⏸ bloqué ${Math.max(1, Math.round((ban.until * 1000 - Date.now()) / 60000))} min`;
  }
  // « vu il y a 12 min » (déconnecté automatiquement après 3 h sans activité).
  function seenAgo(t) {
    const m = Math.max(1, Math.round((Date.now() / 1000 - t) / 60));
    return m < 60 ? `il y a ${m} min` : `il y a ${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`;
  }

  function renderMessages(s) {
    const messages = s.messages || [];
    const unread = messages.filter((m) => !m.read).length;
    q("msgBadge").textContent = unread > 9 ? "9+" : unread;
    q("msgBadge").classList.toggle("hidden", !unread);
    root.querySelector('[data-pa-act="readAll"]').classList.toggle("hidden", !unread);
    onUnread(unread);
    // Nouveau message depuis le dernier état : on prévient.
    const ids = new Set(messages.map((m) => m.id));
    if (seen) {
      const fresh = messages.filter((m) => !seen.has(m.id));
      if (fresh.length) notify(`💬 ${fresh[0].name} : ${fresh[0].text}`, "ok");
    }
    seen = ids;
    const focused = document.activeElement?.dataset?.paReply;
    const caret = focused ? document.activeElement.selectionStart : 0;
    q("messages").innerHTML = messages.length ? messages.map((m) => {
      const id = escape(m.id);
      return `<div class="msg ${m.read ? "" : "unread"}">
        <div class="row"><div class="grow"><b>${escape(m.name)}</b> <span class="artist">· ${hhmm(m.at)}</span></div>
          <div class="icon-btns">
            <button class="secondary" data-pa-msg="${m.read ? "unread" : "read"}" data-id="${id}" title="${m.read ? "Marquer non lu" : "Marquer lu"}">${m.read ? "↺" : "✓"}</button>
            <button class="danger" data-pa-msg="delete" data-id="${id}" title="Supprimer">✕</button></div></div>
        <div class="text">${escape(m.text)}</div>
        ${m.reply ? `<div class="reply">↩︎ <b>Ta réponse</b> <span class="artist">· ${hhmm(m.reply_at)}</span><div class="text">${escape(m.reply)}</div></div>` : ""}
        <form class="row" data-pa-reply-form="${id}" style="margin-top:6px">
          <input class="grow" type="text" maxlength="300" data-pa-reply="${id}" placeholder="${m.reply ? "Modifier ta réponse…" : "Répondre…"}" aria-label="Répondre à ${escape(m.name)}">
          <button>↩︎</button></form>
      </div>`;
    }).join("") : `<p class="empty" style="padding:12px">Aucun message</p>`;
    root.querySelectorAll("[data-pa-reply]").forEach((el) => {
      el.value = drafts[el.dataset.paReply] || "";
      if (el.dataset.paReply === focused) { el.focus(); el.setSelectionRange(caret, caret); }
    });
  }

  function renderGuests(s) {
    const now = Date.now() / 1000, ext = usesSpotify(s.source);
    q("guests").innerHTML = (s.guests || []).length ? s.guests.map((g) => {
      const gid = escape(g.guest_id), online = now - g.last_seen < ONLINE, via = g.via || [];
      return `<div class="track" style="flex-wrap:wrap">
        <div class="meta"><div class="title">${online ? `<span class="dot" title="En ligne"></span>` : ""}${escape(g.name)}
          ${via.includes("music") ? "🎵" : ""}${via.includes("games") ? "🎮" : ""} ${g.ban ? `<span class="pill">${banLabel(g.ban)}</span>` : ""}</div>
        <div class="artist">arrivé à ${hhmm(g.joined_at)} · ${online ? "en ligne" : `vu ${seenAgo(g.active_at)}`}${via.includes("music") ? ` · ${g.total} titre${g.total > 1 ? "s" : ""} · ${g.queued} ${ext ? "envoi(s) Spotify sans lecture observée" : "en attente"}` : ""}</div></div>
        <div class="row" style="gap:6px">
          ${g.ban ? `<button class="secondary" data-pa-guest="unban" data-g="${gid}">Débloquer</button>`
            : `<button class="secondary" data-pa-guest="rename" data-g="${gid}" data-name="${escape(g.name)}" title="Renommer">✏️</button>
               <button class="secondary" data-pa-guest="kick" data-g="${gid}" title="Déconnecter (redemande le code)">⏏︎</button>
               <button class="secondary" data-pa-guest="ban10" data-g="${gid}" title="Bloquer 10 minutes">⏸ 10 min</button>
               <button class="danger" data-pa-guest="ban" data-g="${gid}" title="Bannir">⛔</button>`}
          ${g.queued && !ext ? `<button class="danger" data-pa-guest="purge" data-g="${gid}" title="Retirer ses titres en attente">🗑</button>` : ""}
        </div></div>`;
    }).join("") : `<p class="empty">Aucun invité pour l'instant</p>`;
  }

  function renderBans(s) {
    // Les bannis des soirées précédentes n'apparaissent plus dans la liste des invités.
    const listed = new Set(s.active ? (s.guests || []).map((g) => g.guest_id) : []);
    const others = (s.bans || []).filter((b) => !listed.has(b.guest_id));
    q("bansBox").classList.toggle("hidden", !others.length);
    q("bans").innerHTML = others.map((b) => `<div class="track"><div class="meta"><div class="title">${escape(b.name || "Invité")}</div>
      <div class="artist">${banLabel(b)}</div></div>
      <button class="secondary" data-pa-guest="unban" data-g="${escape(b.guest_id)}">Débloquer</button></div>`).join("");
  }

  // Interrupteurs : cochés seulement si ce téléphone est abonné ET que le réglage est actif.
  let pushOk = null;
  async function renderNotif(s) {
    const box = q("notifBox"), help = q("notifHelp");
    if (typeof Push === "undefined" || !Push.supported()) {
      const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) && !navigator.standalone;
      box.classList.toggle("hidden", !ios);
      root.querySelectorAll("[data-pa-notif]").forEach((t) => { t.disabled = true; });
      help.textContent = "Sur iPhone : ouvre Party depuis l'icône de l'écran d'accueil pour recevoir les notifications.";
      return;
    }
    box.classList.remove("hidden");
    help.textContent = Notification.permission === "denied" ? "Notifications bloquées dans les réglages du téléphone." : "";
    if (pushOk === null) pushOk = !!(await Push.current("/").catch(() => null)) && Notification.permission === "granted";
    const prefs = s.admin_notify || {};
    root.querySelectorAll("[data-pa-notif]").forEach((t) => { if (!t.disabled) t.checked = pushOk && !!prefs[t.dataset.paNotif]; });
  }

  async function toggleNotif(t) {
    const kind = t.dataset.paNotif, on = t.checked;
    t.disabled = true;
    try {
      // Abonnement de l'app (portée « / ») enregistré aussi pour l'hôte.
      if (on) { const sub = await Push.current("/") || await Push.subscribe("/", "/api/admin/push/subscribe"); await Push.send("/api/admin/push/subscribe", { subscription: sub.toJSON() }); pushOk = true; }
      const r = await fetch("/api/admin/notify", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind, on }) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Erreur, réessaie");
      root.querySelectorAll("[data-pa-notif]").forEach((x) => { x.checked = pushOk && !!data.admin_notify?.[x.dataset.paNotif]; });
      notify(on ? `Tu seras prévenu ${NOTIF[kind]} 🔔` : `Plus de notifications ${NOTIF[kind]}`, on ? "ok" : "");
    } catch (e) { t.checked = !on; notify(e.message, "err"); }
    t.disabled = false;
  }

  function render(s) {
    if (!root || !s) return;
    renderNotif(s);
    renderMessages(s);
    renderGuests(s);
    renderBans(s);
  }

  // Après une action : le nouvel état repart vers la musique, qui le renvoie ici (un seul chemin de rendu).
  const share = (res) => onState(res);

  // Après une purge : « Annuler » remet les titres à leur place.
  function purged(res) {
    notify("Titres retirés", "ok", res.undo ? { label: "Annuler", run: async () => {
      try { share(await api("/api/admin/undo", { token: res.undo })); notify("Remis dans la file ↩︎", "ok"); }
      catch (e) { notify(e.message, "err"); }
    } } : null);
  }

  async function guestAction(b) {
    const g = b.dataset.g, act = b.dataset.paGuest;
    let name;
    if (act === "rename") {
      name = prompt("Nouveau prénom :", b.dataset.name || "");
      if (!name || !name.trim() || name.trim() === b.dataset.name) return;
    }
    if (act === "ban" && !confirm("Bannir cet invité ? Il ne pourra plus ajouter de titres ni rejoindre les jeux.")) return;
    const calls = {
      rename: ["/api/admin/rename", { guest_id: g, name }, "Invité renommé"],
      kick: ["/api/admin/kick", { guest_id: g }, "Invité déconnecté : il devra ressaisir le code"],
      ban10: ["/api/admin/ban", { guest_id: g, minutes: 10 }, "Bloqué 10 minutes"],
      ban: ["/api/admin/ban", { guest_id: g, minutes: null }, "Invité banni"],
      unban: ["/api/admin/unban", { guest_id: g }, "Invité débloqué"],
      purge: ["/api/admin/purge", { guest_id: g }, ""],
    };
    const [path, body, msg] = calls[act];
    b.disabled = true;
    try {
      const res = await api(path, body);
      share(res);
      if (act === "purge") purged(res); else notify(msg, "ok");
    } catch (e) { b.disabled = false; notify(e.message, "err"); }
  }

  async function onClick(ev) {
    const t = ev.target;
    const g = t.closest("[data-pa-guest]");
    if (g) return guestAction(g);
    const m = t.closest("[data-pa-msg]");
    if (m) {
      if (m.dataset.paMsg === "delete" && !confirm("Supprimer ce message ?")) return;
      m.disabled = true;
      try { share(await api("/api/admin/messages", { ids: [m.dataset.id], action: m.dataset.paMsg })); }
      catch (e) { m.disabled = false; notify(e.message, "err"); }
      return;
    }
    if (t.closest('[data-pa-act="readAll"]')) {
      try { share(await api("/api/admin/messages", { ids: null, action: "read" })); } catch (e) { notify(e.message, "err"); }
    }
  }

  async function onSubmit(ev) {
    const form = ev.target.closest("[data-pa-reply-form]");
    if (!form) return;
    ev.preventDefault();
    const id = form.dataset.paReplyForm, text = (drafts[id] || "").trim();
    if (!text) return;
    form.querySelector("button").disabled = true;
    try {
      delete drafts[id];
      share(await api("/api/admin/messages/reply", { id, text }));
      notify("Réponse envoyée ↩︎", "ok");
    } catch (e) { drafts[id] = text; notify(e.message, "err"); form.querySelector("button").disabled = false; }
  }

  function onChange(ev) {
    const t = ev.target.closest("[data-pa-notif]");
    if (t) toggleNotif(t);
  }

  function onInput(ev) {
    const r = ev.target.closest("[data-pa-reply]");
    if (r) drafts[r.dataset.paReply] = r.value;
  }

  window.PeopleAdmin = {
    mount(el, opts = {}) {
      root = el;
      onState = opts.onState || onState;
      onUnread = opts.onUnread || onUnread;
      root.innerHTML = SKELETON;
      root.addEventListener("click", onClick);
      root.addEventListener("submit", onSubmit);
      root.addEventListener("input", onInput);
      root.addEventListener("change", onChange);
    },
    render,
  };
})();
