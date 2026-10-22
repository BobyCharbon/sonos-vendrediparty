// 🎛️ Pilotage de la musique par l'hôte, dans l'onglet Musique de l'app (compte admin connecté).
// Reprend la page Soirée de /admin : démarrer (maison / extérieur, pièce Sonos, mode), lecture, volume, ajout de
// titres, file d'attente, mode d'insertion, top playlists, enceintes, demandes des invités, compte Spotify, arrêt.
// Balisage propre (attributs data-ma, aucun id) : il cohabite avec la page invités. /admin garde son code en secours.
// Usage : MusicAdmin.mount(élément) — l'état se recharge seul (événements serveur) ; MusicAdmin.render(état) pour les tests.
(function () {
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const notify = (msg, kind, action) => (typeof toast === "function" ? toast(msg, kind, action) : alert(msg));
  const usesSpotify = (source) => ["spotify", "spotify_sonos"].includes(source);
  const MODES = { next: "Juste après", fair: "Équitable" };
  const HELP = {
    next: "Chaque titre ajouté passe juste après celui en cours (le dernier ajouté passe en premier).",
    fair: "Les demandes passent avant ta playlist, une par invité à tour de rôle : personne ne monopolise la file. L'activer réorganise aussi la file actuelle.",
  };
  let root = null, state = null, stateAt = Date.now(), chosenMode = "next", chosenSource = "spotify_sonos";
  let volumeDragging = false, volumeSentAt = 0, volumeTimer = null, addTimer = null, addResults = [];
  let speakersDragging = null, speakersTimer = null, sonosPlaylists = null, events = null, refreshTimer = null;
  const q = (name) => root.querySelector(`[data-ma="${name}"]`);

  async function api(path, body) {
    const r = await fetch(path, body === undefined ? { credentials: "same-origin" }
      : { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const err = new Error(typeof data.detail === "string" ? data.detail : data.detail?.message || "Erreur, réessaie");
      err.detail = data.detail;
      throw err;
    }
    return data;
  }

  function etaText(eta) {
    if (eta == null) return "";
    const left = eta - (Date.now() - stateAt) / 1000;
    if (left < 60) return "dans moins d'1 min";
    if (left < 3600) return `dans ~${Math.round(left / 60)} min`;
    return "vers " + new Date(Date.now() + left * 1000).toLocaleTimeString("fr-CH", { hour: "2-digit", minute: "2-digit" });
  }

  // Après une suppression : « Annuler » remet les titres à leur place.
  function removedToast(res, msg) {
    notify(msg, "ok", res.undo ? { label: "Annuler", run: async () => {
      try { render(await api("/api/admin/undo", { token: res.undo })); notify("Remis dans la file ↩︎", "ok"); }
      catch (e) { notify(e.message, "err"); }
    } } : null);
  }

  const SKELETON = `
    <div data-ma="setup" class="hidden">
      <div class="src-pick" role="group" aria-label="Où se passe la soirée ?">
        <button type="button" class="src on" data-ma-src="spotify_sonos"><b>🏠 Party maison</b><small>Spotify sur tes Sonos</small></button>
        <button type="button" class="src" data-ma-src="spotify"><b>🏕️ Party extérieur</b><small>Spotify sur ton téléphone → enceinte Bluetooth</small></button>
      </div>
      <div class="card">
        <div data-ma="srcSonos">
          <p class="sub" style="margin-top:0">1. Dans Spotify, choisis ta pièce Sonos dans les appareils disponibles et lance un titre.<br>2. Sélectionne la même pièce ici, puis démarre la soirée.</p>
          <h2 style="margin-top:0">Pièce Sonos</h2>
          <div class="row"><select data-ma="room" class="grow" aria-label="Pièce Sonos"></select>
            <button class="secondary" type="button" data-ma-act="rooms" title="Actualiser">↻</button></div>
        </div>
        <div data-ma="srcSpotify" class="hidden">
          <p class="sub" style="margin-top:0">1. Connecte ton téléphone à l'enceinte Bluetooth.<br>2. Lance une playlist dans l'app Spotify.<br>3. Démarre la soirée : les invités ajoutent directement à ta file Spotify.</p>
        </div>
        <div data-ma="spotifyStart"></div>
        <h2 data-ma="modeTitle">Mode d'insertion</h2>
        <div class="seg" data-ma="modes"></div>
        <button type="button" data-ma-act="start" style="width:100%;margin-top:16px">🎉 Démarrer la soirée</button>
      </div>
    </div>
    <div data-ma="live" class="hidden">
      <p class="sub"><span class="pill live">● Soirée en cours</span> <span data-ma="liveRoom"></span></p>
      <div data-ma="warn" class="warn hidden"></div>
      <div class="card now" data-ma="now"></div>
      <div class="row" style="margin-top:8px">
        <button type="button" class="secondary grow" data-ma-act="playpause">⏸ Pause</button>
        <button type="button" class="secondary grow" data-ma-act="skip">⏭ Passer</button>
      </div>
      <div class="artist" style="margin:12px 0 4px" data-ma="volumeText">Volume global (toutes les enceintes du groupe)</div>
      <div class="card row"><span>🔈</span>
        <input data-ma="volume" class="grow" type="range" min="0" max="100" step="1" aria-label="Volume">
        <span>🔊</span><span data-ma="volumeLabel" style="width:2.5em;text-align:right;font-variant-numeric:tabular-nums"></span></div>
      <h2>Ajouter un titre</h2>
      <input data-ma="addQ" type="search" placeholder="Titre, artiste… ou colle un lien (Spotify, Deezer, YouTube)" autocomplete="off" enterkeyhint="search" aria-label="Ajouter un titre">
      <div data-ma="addResults" class="list" style="margin-top:8px"></div>
      <h2>File d'attente <span data-ma="queueCount"></span></h2>
      <p data-ma="queueHelp" class="sub" style="margin-top:-4px;font-size:.85rem"></p>
      <div data-ma="queue" class="list"></div>
      <h2 data-ma="modeTitle">Mode d'insertion</h2>
      <div class="seg" data-ma="modes"></div>
      <p class="sub" data-ma="modeHelp" style="margin-top:8px"></p>
      <h2>Top playlists</h2>
      <p class="sub" style="margin-top:-4px;font-size:.85rem">▶︎ remplace la file et lance la playlist en aléatoire. Les demandes en attente sont gardées et passent en premier.</p>
      <div data-ma="top" class="list"></div>
      <details data-ma="topAdd" style="margin-top:8px"><summary><span class="artist">＋ Ajouter une playlist ▸</span></summary>
        <form data-ma="topLink" class="row" style="margin-top:8px">
          <input class="grow" type="text" data-ma="topUrl" placeholder="Lien Spotify d'une playlist" autocomplete="off" aria-label="Lien Spotify d'une playlist">
          <button>Ajouter</button></form>
        <div class="row" style="margin-top:8px"><select class="grow" data-ma="sonosPlaylists" aria-label="Playlist Sonos"><option value="">Depuis Sonos (playlists et favoris)…</option></select>
          <button type="button" class="secondary" data-ma-act="addSonosPlaylist">Ajouter</button></div>
      </details>
      <div data-ma="speakersBox"><h2>Enceintes</h2>
        <p class="sub" style="margin-top:-4px;font-size:.85rem">Ajoute des enceintes au groupe de la soirée ; chaque curseur règle une enceinte.</p>
        <div data-ma="speakers" class="list"><p class="empty">Chargement…</p></div></div>
      <h2>Demandes des invités</h2>
      <div data-ma="requests" class="list"></div>
      <h2>Compte Spotify</h2>
      <div class="card" data-ma="spotifyAccount"></div>
      <button type="button" class="danger" data-ma-act="stop" style="width:100%;margin-top:20px">Arrêter la soirée</button>
    </div>`;

  function spotifyAccountHtml(s) {
    const a = s.spotify_account;
    if (!a) return `<p class="sub">Spotify n'est pas configuré sur le serveur.</p>`;
    return a.connected
      ? `<div class="row"><div class="grow">🟢 Connecté à Spotify : <b>${escape(a.name)}</b>${a.premium ? "" : ` <span class="pill">⚠️ Premium requis</span>`}</div>
          <button class="secondary" type="button" data-ma-act="spotifyLogout">Déconnecter</button></div>`
      : `<a class="sp-connect" href="/api/admin/spotify/login">Se connecter à Spotify</a>
         <p class="sub" style="margin:8px 0 0;font-size:.85rem">Une seule fois : Spotify Premium est nécessaire pour piloter la lecture.</p>`;
  }

  function renderModes(current) {
    const ext = usesSpotify(state?.active ? state.source : chosenSource);
    root.querySelectorAll('[data-ma="modes"], [data-ma="modeTitle"]').forEach((el) => el.classList.toggle("hidden", ext));
    root.querySelectorAll('[data-ma="modes"]').forEach((el) => {
      el.innerHTML = Object.entries(MODES).map(([k, v]) => `<button type="button" data-ma-mode="${k}" class="${k === current ? "on" : ""}">${v}</button>`).join("");
    });
    q("modeHelp").textContent = ext ? "Chaque ajout est envoyé immédiatement à Spotify. Gère l'ordre et les suppressions depuis Spotify." : HELP[current] || "";
  }

  function renderNow(s, ext) {
    const so = s.sonos;
    q("liveRoom").textContent = s.source === "spotify_sonos" ? `🏠 Party maison · ${s.room_name} · Spotify`
      : ext ? `🏕️ Party extérieur · Spotify${so?.device ? ` · ${so.device}` : ""}` : s.room_name || "";
    const warn = s.sonos_error ? (ext ? "Spotify : " : "Sonos injoignable : ") + s.sonos_error
      : ext && so && so.state === "STOPPED" ? "⚠️ Rien ne joue sur Spotify : lance une playlist sur ton téléphone."
      : so && so.from_queue === false ? "⚠️ La musique ne joue pas depuis la file Sonos (Spotify Connect / Jam ?). Lance une playlist depuis l'app Sonos." : "";
    q("warn").textContent = warn;
    q("warn").classList.toggle("hidden", !warn);
    q("now").innerHTML = so?.now?.title
      ? `${so.now.art ? `<img src="${escape(so.now.art)}" alt="" onerror="this.removeAttribute('src')">` : `<img alt="">`}
        <div style="min-width:0"><div class="artist">${so.state === "PLAYING" ? "▶︎ En cours" : "⏸ " + escape(so.state)}</div>
        <div class="title">${escape(so.now.title)}</div><div class="artist">${escape(so.now.artist)}</div>
        ${so.now.by ? `<span class="by">ajouté par ${escape(so.now.by)}</span>` : ""}</div>`
      : `<div class="artist">Rien ne joue</div>`;
    const playing = so && (so.state === "PLAYING" || so.state === "TRANSITIONING");
    const pp = root.querySelector('[data-ma-act="playpause"]');
    pp.textContent = playing ? "⏸ Pause" : "▶︎ Lecture";
    pp.dataset.action = playing ? "pause" : "play";
    q("volumeText").textContent = s.source === "spotify" ? "Volume (téléphone)" : "Volume global (toutes les enceintes du groupe)";
    // Pas de mise à jour pendant qu'on fait glisser le curseur.
    if (so && so.volume != null && !volumeDragging && Date.now() - volumeSentAt > 3000) {
      q("volume").value = so.volume;
      q("volumeLabel").textContent = so.volume;
    }
  }

  function renderQueue(s, ext) {
    const list = s.queue || [];
    q("queueHelp").textContent = ext ? "Aperçu de la file Spotify : change l'ordre ou retire des titres directement dans Spotify."
      : "⏫ jouer ensuite · ⬆⬇ déplacer · ▶︎ jouer maintenant · ✕ retirer";
    q("queueCount").textContent = list.length ? `(${list.length})` : "";
    q("queue").innerHTML = list.length ? list.map((t, i) => {
      const at = `data-pos="${t.pos}" data-key="${escape(t.key)}"`;
      return `<div class="track ${t.by ? "guest" : ""}">
        ${t.art ? `<img src="${escape(t.art)}" alt="" loading="lazy" onerror="this.removeAttribute('src')">` : `<img alt="">`}
        <div class="meta"><div class="title">${escape(t.title)}</div><div class="artist">${escape(t.artist)}</div>
          ${t.by ? `<span class="by">ajouté par ${escape(t.by)}</span>` : ""}${etaText(t.eta) ? `<span class="eta">${etaText(t.eta)}</span>` : ""}</div>
        ${ext ? "" : `<div class="icon-btns">
          ${i > 0 ? `<button class="secondary" data-ma-q="next" ${at} title="Jouer ensuite">⏫</button>
                     <button class="secondary" data-ma-q="up" ${at} title="Monter">⬆</button>` : ""}
          ${i < list.length - 1 ? `<button class="secondary" data-ma-q="down" ${at} title="Descendre">⬇</button>` : ""}
          <button class="secondary" data-ma-q="play" ${at} title="Jouer maintenant">▶︎</button>
          <button class="danger" data-ma-q="remove" ${at} title="Retirer">✕</button></div>`}
      </div>`;
    }).join("") : `<p class="empty">${ext ? "Aucun titre à venir renvoyé par Spotify" : "La file est vide"}</p>`;
  }

  function renderTop(s) {
    const top = s.top_playlists || [];
    q("top").innerHTML = top.length ? top.map((p, i) => `<div class="track">
        <div class="meta"><div class="title">${p.id.startsWith("spotify:") ? "🟢" : "🔀"} ${escape(p.title)}</div>
          <div class="artist">${p.id.startsWith("spotify:") ? "Spotify" : "Sonos"}</div></div>
        <div class="icon-btns">
          <button data-ma-top="launch" data-id="${escape(p.id)}" title="Lancer en aléatoire" ${s.active && (!usesSpotify(s.source) || p.id.startsWith("spotify:playlist:")) ? "" : "disabled"}>▶︎</button>
          ${i > 0 ? `<button class="secondary" data-ma-top="up" data-id="${escape(p.id)}" title="Monter">⬆</button>` : ""}
          <button class="danger" data-ma-top="remove" data-id="${escape(p.id)}" title="Retirer de la liste">✕</button></div>
      </div>`).join("") : `<p class="empty" style="padding:12px">Aucune playlist : ajoute un lien Spotify ci-dessous</p>`;
  }

  function renderRequests(s, ext) {
    const labels = { queued: ext ? "envoyé à Spotify" : "en attente", played: "joué", removed: "retiré" };
    q("requests").innerHTML = (s.requests || []).length ? s.requests.map((r) => `
      <div class="track ${r.status === "queued" ? "guest" : ""}" style="${r.status !== "queued" ? "opacity:.55" : ""}">
        ${r.image ? `<img src="${escape(r.image)}" alt="">` : `<img alt="">`}
        <div class="meta"><div class="title">${escape(r.title)}</div><div class="artist">${escape(r.artist)}</div>
        <span class="by">${escape(r.guest_name)} · ${new Date(r.added_at * 1000).toLocaleTimeString("fr-CH", { hour: "2-digit", minute: "2-digit" })} · ${labels[r.status] || ""}</span></div>
        ${r.status === "queued" && !ext ? `<button class="danger" data-ma-remove="${escape(r.id)}" title="Retirer de la file">✕</button>` : ""}
      </div>`).join("") : `<p class="empty">Aucune demande pour l'instant</p>`;
  }

  function render(s) {
    if (!root || !s) return;
    state = s; stateAt = Date.now();
    q("setup").classList.toggle("hidden", !!s.active);
    q("live").classList.toggle("hidden", !s.active);
    q("spotifyStart").innerHTML = spotifyAccountHtml(s);
    q("spotifyAccount").innerHTML = spotifyAccountHtml(s);
    if (!s.active) { renderModes(chosenMode); return; }
    const ext = usesSpotify(s.source);
    renderModes(s.mode);
    renderNow(s, ext);
    renderQueue(s, ext);
    renderTop(s);
    renderRequests(s, ext);
    q("speakersBox").classList.toggle("hidden", s.source === "spotify");
  }

  async function refresh() {
    try { render(await api("/api/admin/state")); } catch { /* hors ligne : on garde l'affichage */ }
  }

  async function loadRooms() {
    const sel = q("room");
    sel.innerHTML = `<option value="">Recherche des enceintes…</option>`;
    try {
      const rooms = await api("/api/admin/rooms");
      sel.innerHTML = rooms.map((r) => `<option value="${escape(r.uid)}">${escape(r.name)}</option>`).join("") || `<option value="">Aucune pièce trouvée</option>`;
    } catch (e) { sel.innerHTML = `<option value="">${escape(e.message)}</option>`; }
  }

  async function loadSpeakers(list) {
    if (!state?.active || state.source === "spotify" || root.offsetParent === null) return;
    try { renderSpeakers(list || await api("/api/admin/speakers")); }
    catch (e) { q("speakers").innerHTML = `<p class="empty">${escape(e.message)}</p>`; }
  }
  function renderSpeakers(list) {
    if (speakersDragging) return;  // pas de redessin pendant qu'on fait glisser un curseur
    q("speakers").innerHTML = list.map((sp) => `
      <div class="track" style="flex-wrap:wrap;${sp.in_group ? "" : "opacity:.7"}">
        <div class="meta"><div class="title">${sp.in_group ? "🔊" : "🔈"} ${escape(sp.name)}</div>
          <div class="artist">${sp.coordinator ? "enceinte principale de la soirée" : sp.in_group ? "dans le groupe" : "hors du groupe"}</div></div>
        ${sp.coordinator ? "" : `<button class="${sp.in_group ? "danger" : "secondary"}" data-ma-speaker="${escape(sp.uid)}" data-join="${sp.in_group ? "0" : "1"}">${sp.in_group ? "Retirer" : "＋ Ajouter"}</button>`}
        <div class="row" style="width:100%;margin-top:6px">
          <input class="grow" type="range" min="0" max="100" step="1" value="${sp.volume}" data-ma-speaker-volume="${escape(sp.uid)}" aria-label="Volume ${escape(sp.name)}">
          <span style="width:2.5em;text-align:right;font-variant-numeric:tabular-nums">${sp.volume}</span></div>
      </div>`).join("") || `<p class="empty">Aucune enceinte trouvée</p>`;
  }

  async function loadSonosPlaylists() {
    if (sonosPlaylists) return;
    try {
      sonosPlaylists = await api("/api/admin/playlists");
      q("sonosPlaylists").innerHTML = `<option value="">Depuis Sonos (playlists et favoris)…</option>`
        + sonosPlaylists.map((p) => `<option value="${escape(p.id)}">${p.kind === "sonos" ? "Playlist" : "Favori"} · ${escape(p.title)}</option>`).join("");
    } catch (e) { q("sonosPlaylists").innerHTML = `<option value="">${escape(e.message)}</option>`; }
  }
  async function editTop(body, msg) {
    try { render(await api("/api/admin/playlists/top", body)); if (msg) notify(msg, "ok"); return true; }
    catch (e) { notify(e.message, "err"); return false; }
  }

  async function sendVolume() {
    volumeSentAt = Date.now();
    try { await api("/api/admin/volume", { volume: +q("volume").value }); } catch (e) { notify(e.message, "err"); }
  }

  function search() {
    clearTimeout(addTimer);
    const text = q("addQ").value.trim();
    if (text.length < 2) { q("addResults").innerHTML = ""; return; }
    addTimer = setTimeout(async () => {
      try {
        addResults = await api("/api/admin/search?q=" + encodeURIComponent(text));
        if (q("addQ").value.trim() !== text) return;
        const ext = usesSpotify(state?.source);
        q("addResults").innerHTML = addResults.length ? addResults.map((t, i) => `<div class="track">
            ${t.image ? `<img src="${escape(t.image)}" alt="" loading="lazy">` : `<img alt="">`}
            <div class="meta"><div class="title">${escape(t.title)}</div><div class="artist">${escape(t.artist)}${t.explicit ? " · 🅴" : ""}${t.via ? ` · 🔗 ${escape(t.via)}` : ""}</div></div>
            <div class="icon-btns">${ext ? "" : `<button data-ma-add="next" data-i="${i}" title="Jouer ensuite">⏫</button>`}
              <button class="secondary" data-ma-add="end" data-i="${i}" title="${ext ? "Ajouter à Spotify" : "À la suite des demandes"}">＋</button></div>
          </div>`).join("") : `<p class="empty">Aucun résultat</p>`;
      } catch (e) { notify(e.message, "err"); }
    }, 350);
  }

  async function addTrack(b) {
    const t = addResults[+b.dataset.i];
    b.disabled = true;
    const add = (force) => api("/api/admin/add", { track_id: t.id, where: b.dataset.maAdd, force });
    try {
      let res;
      try { res = await add(false); }
      catch (e) {
        // Doublon : on prévient, l'hôte décide.
        if (!e.detail?.duplicate || !confirm(e.message)) throw e.detail?.duplicate ? new Error("Ajout annulé") : e;
        res = await add(true);
      }
      render(res);
      notify(`« ${t.title} » ${usesSpotify(res.source) ? "envoyé à Spotify" : b.dataset.maAdd === "next" ? "passera juste après" : "ajouté à la suite des demandes"} 🎶`, "ok");
      clearTimeout(addTimer);
      q("addQ").value = ""; q("addResults").innerHTML = ""; addResults = [];
      q("addQ").blur();
    } catch (e) { b.disabled = false; notify(e.message, "err"); }
  }

  async function act(name, b) {
    try {
      if (name === "rooms") return loadRooms();
      if (name === "start") {
        if (chosenSource === "spotify_sonos" && !q("room").value) return notify("Choisis une pièce", "err");
        if (usesSpotify(chosenSource) && !state?.spotify_account?.connected) return notify("Connecte d'abord ton compte Spotify", "err");
        b.disabled = true;
        render(await api("/api/admin/start", { room_uid: q("room").value, mode: chosenMode, source: chosenSource }));
        return notify("Soirée démarrée 🎉", "ok");
      }
      if (name === "stop") {
        if (!confirm("Arrêter la soirée ? La file des invités se ferme.")) return;
        render(await api("/api/admin/stop", {})); loadRooms(); return notify("Soirée arrêtée");
      }
      if (name === "playpause") return render(await api("/api/admin/playback", { action: b.dataset.action }));
      if (name === "skip") { await api("/api/admin/skip", {}); return setTimeout(refresh, 800); }
      if (name === "spotifyLogout") {
        if (!confirm("Déconnecter ton compte Spotify ?")) return;
        render(await api("/api/admin/spotify/logout", {})); return notify("Compte Spotify déconnecté");
      }
      if (name === "addSonosPlaylist") return q("sonosPlaylists").value && editTop({ action: "add", id: q("sonosPlaylists").value }, "Playlist ajoutée");
    } catch (e) { notify(e.message, "err"); }
    finally { if (b) b.disabled = false; }
  }

  async function onClick(ev) {
    const t = ev.target;
    const a = t.closest("[data-ma-act]");
    if (a) return act(a.dataset.maAct, a);
    const src = t.closest("[data-ma-src]");
    if (src) {
      chosenSource = src.dataset.maSrc;
      root.querySelectorAll("[data-ma-src]").forEach((x) => x.classList.toggle("on", x === src));
      q("srcSonos").classList.toggle("hidden", chosenSource !== "spotify_sonos");
      q("srcSpotify").classList.toggle("hidden", chosenSource !== "spotify");
      return renderModes(chosenMode);
    }
    const m = t.closest("[data-ma-mode]");
    if (m) {
      if (!state?.active) { chosenMode = m.dataset.maMode; return renderModes(chosenMode); }
      try {
        const res = await api("/api/admin/mode", { mode: m.dataset.maMode });
        render(res);
        notify("Mode : " + MODES[m.dataset.maMode] + (res.reordered ? ` · file réorganisée (${res.reordered} déplacement${res.reordered > 1 ? "s" : ""})` : ""), "ok");
      } catch (e) { notify(e.message, "err"); }
      return;
    }
    const add = t.closest("[data-ma-add]");
    if (add) return addTrack(add);
    const qb = t.closest("[data-ma-q]");
    if (qb) {
      qb.disabled = true;
      try {
        const res = await api("/api/admin/queue", { pos: +qb.dataset.pos, key: qb.dataset.key, action: qb.dataset.maQ });
        render(res);
        if (qb.dataset.maQ === "remove") removedToast(res, "Titre retiré");
      } catch (e) { notify(e.message, "err"); refresh(); }
      qb.disabled = false;
      return;
    }
    const rm = t.closest("[data-ma-remove]");
    if (rm) {
      rm.disabled = true;
      try { const res = await api("/api/admin/remove", { request_id: rm.dataset.maRemove }); render(res); removedToast(res, "Titre retiré"); }
      catch (e) { rm.disabled = false; notify(e.message, "err"); }
      return;
    }
    const top = t.closest("[data-ma-top]");
    if (top) {
      const p = (state?.top_playlists || []).find((x) => x.id === top.dataset.id);
      if (!p) return;
      if (top.dataset.maTop !== "launch") return editTop({ action: top.dataset.maTop, id: p.id });
      if (!confirm(`Lancer « ${p.title} » en aléatoire ?\nLa file actuelle sera remplacée (les demandes en attente sont gardées).`)) return;
      top.disabled = true;
      try { render(await api("/api/admin/playlist", { id: p.id })); notify(`« ${p.title} » lancée en aléatoire 🔀`, "ok"); }
      catch (e) { notify(e.message, "err"); top.disabled = false; }
      return;
    }
    const sp = t.closest("[data-ma-speaker]");
    if (sp) {
      sp.disabled = true; sp.textContent = "…";
      try { renderSpeakers(await api("/api/admin/speakers/group", { uid: sp.dataset.maSpeaker, join: sp.dataset.join === "1" })); }
      catch (e) { notify(e.message, "err"); loadSpeakers(); }
    }
  }

  function onInput(ev) {
    const t = ev.target;
    if (t.matches('[data-ma="addQ"]')) return search();
    if (t.matches('[data-ma="volume"]')) {
      volumeDragging = true;
      q("volumeLabel").textContent = t.value;
      // Pendant le glissement : au plus un envoi toutes les 250 ms.
      if (!volumeTimer) volumeTimer = setTimeout(() => { volumeTimer = null; sendVolume(); }, 250);
      return;
    }
    const r = t.closest("[data-ma-speaker-volume]");
    if (r) {
      speakersDragging = r.dataset.maSpeakerVolume;
      r.nextElementSibling.textContent = r.value;
      clearTimeout(speakersTimer);
      speakersTimer = setTimeout(() => api("/api/admin/speakers/volume", { uid: r.dataset.maSpeakerVolume, volume: +r.value }).catch((e) => notify(e.message, "err")), 200);
    }
  }

  function onChange(ev) {
    const t = ev.target;
    if (t.matches('[data-ma="volume"]')) { volumeDragging = false; clearTimeout(volumeTimer); volumeTimer = null; return sendVolume(); }
    const r = t.closest("[data-ma-speaker-volume]");
    if (r) {
      clearTimeout(speakersTimer);
      api("/api/admin/speakers/volume", { uid: r.dataset.maSpeakerVolume, volume: +r.value })
        .catch((e) => notify(e.message, "err")).finally(() => { speakersDragging = null; });
    }
  }

  async function onSubmit(ev) {
    if (!ev.target.matches('[data-ma="topLink"]')) return;
    ev.preventDefault();
    if (await editTop({ action: "add", url: q("topUrl").value.trim() }, "Playlist ajoutée")) q("topUrl").value = "";
  }

  // Mises à jour en direct : le serveur signale chaque changement, on relit l'état peu après.
  function listen() {
    if (events) events.close();
    events = new EventSource("/api/events");
    events.onmessage = () => { clearTimeout(refreshTimer); refreshTimer = setTimeout(refresh, 150); };
    events.onerror = () => { events.close(); setTimeout(listen, 3000); };
  }

  window.MusicAdmin = {
    mount(el, { live = true } = {}) {
      root = el;
      root.innerHTML = SKELETON;
      root.addEventListener("click", onClick);
      root.addEventListener("input", onInput);
      root.addEventListener("change", onChange);
      root.addEventListener("submit", onSubmit);
      q("topAdd").addEventListener("toggle", (ev) => { if (ev.target.open) loadSonosPlaylists(); });
      renderModes(chosenMode);
      if (!live) return Promise.resolve();
      listen();
      // Enceintes : relues toutes les 10 s tant que l'onglet est affiché.
      setInterval(() => loadSpeakers(), 10000);
      return refresh().then(() => { if (!state?.active) loadRooms(); else loadSpeakers(); });
    },
    render,
    refresh,
    show() { refresh().then(() => (state?.active ? loadSpeakers() : loadRooms())); },
  };
})();
