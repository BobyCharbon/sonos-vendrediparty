// 📺 Écran TV de l'hôte (/tv) : titre en cours, prochaines demandes, code et QR, parties de jeu en cours.
// Ouvert sur le Mac et affiché sur l'Apple TV par AirPlay. Se met à jour seul (flux /api/events + filet toutes les 10 s).
// Tous les textes passent par textContent ou esc() : un prénom ou un titre ne peut jamais injecter du HTML.
(function () {
  const $ = (id) => document.getElementById(id);
  const SAFETY_REFRESH = 10000;
  let refreshTimer = null, source = null, shownArt = null, shownNow = null, shownGames = null;
  let backdrops = [$("backdrop"), $("backdrop2")];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const plural = (n, one, many) => `${n} ${n > 1 ? many : one}`;

  function setArt(img, src) {
    if (src) img.src = src; else img.removeAttribute("src");
  }

  // Nouveau titre : la pochette et le texte entrent en fondu (classe tv-swap, relancée seulement à ce moment-là).
  function replay(node, cls) {
    node.classList.remove(cls);
    void node.offsetWidth;
    node.classList.add(cls);
  }

  function renderNow(s) {
    const now = s.active && !s.error ? s.now : null;
    const title = !s.active ? "La soirée va commencer" : s.error || now?.title || "Rien ne joue pour l'instant";
    const key = [title, now?.artist, now?.art, now?.by].join("\u0001");
    $("nowLabel").textContent = !s.active ? "Bientôt" : s.error ? "Musique" : s.state === "PLAYING" ? "En ce moment" : "En pause";
    if (key !== shownNow) {
      const changed = shownNow !== null;
      shownNow = key;
      $("nowTitle").textContent = title;
      $("nowArtist").textContent = !s.active ? "Scanne le QR pour ajouter tes titres" : now?.artist || "";
      $("nowBy").textContent = now?.by ? `🙋 Demandé par ${now.by}` : "";
      $("nowBy").classList.toggle("hidden", !now?.by);
      setArt($("nowArt"), now?.art);
      if (changed) replay(document.querySelector(".tv-now"), "tv-swap");
    }
    NowProgress.update($("nowProgress"), now, s.state === "PLAYING");
    // Fond : seulement quand la pochette change ; la nouvelle apparaît en fondu par-dessus l'ancienne.
    if ((now?.art || "") !== shownArt) {
      shownArt = now?.art || "";
      const [back, front] = backdrops;
      back.style.backgroundImage = shownArt ? `url("${encodeURI(shownArt)}")` : "";
      back.classList.add("on");
      front.classList.remove("on");
      backdrops = [front, back];
    }
  }

  function renderUpcoming(list) {
    // Liste animée (list-motion.js) : un titre qui passe s'efface, les suivants remontent, un ajout glisse en place.
    // Prénoms et titres échappés (esc) : jamais interprétés comme du HTML.
    const keys = ListMotion.occurrenceKeys(list, (t) => `${t.title}\u0001${t.artist}`);
    ListMotion.patch($("upcoming"), list.map((t, i) => ({ key: keys[i], html: `<li>
      ${t.art ? `<img alt="" src="${esc(t.art)}">` : `<span class="tv-thumb"></span>`}
      <div><b>${esc(t.title)}</b><small>${esc(t.artist)}${t.by ? ` · <em>${esc(t.by)}</em>` : ""}</small></div></li>` })),
    { empty: `<li class="tv-empty">Ajoute un titre depuis ton téléphone !</li>` });
  }

  function renderJoin(s) {
    $("pinCode").textContent = s.pin || "····";
    $("url").textContent = s.url ? s.url.replace(/^https?:\/\//, "").replace(/\/$/, "") : "";
    const qr = "/qr.svg?v=" + encodeURIComponent(s.pin || "");
    if ($("qr").getAttribute("src") !== qr) $("qr").src = qr;
  }

  function renderBar(s) {
    $("event").textContent = s.event ? `🎉 ${s.event}` : s.room ? `🔊 ${s.room}` : "";
    // Parties en cours : un nouveau jeu (ou une partie qui se termine) passe en fondu, pas d'un coup.
    const games = (s.games || []).map((g) => `🎮 ${g.name} · ${plural(g.players, "joueur", "joueurs")}`).join("   ");
    if (games !== shownGames) {
      const changed = shownGames !== null;
      shownGames = games;
      $("games").textContent = games;
      if (changed) replay($("games"), "tv-swap");
    }
  }

  function render(s) {
    document.body.classList.toggle("waiting", !s.active);
    $("login").classList.add("hidden");
    $("stage").classList.remove("hidden");
    $("bar").classList.remove("hidden");
    renderNow(s);
    renderUpcoming(s.upcoming || []);
    renderJoin(s);
    renderBar(s);
  }

  async function refresh() {
    try {
      const r = await fetch("/api/tv", { credentials: "same-origin" });
      if (r.status === 401) return showLogin();
      if (r.ok) render(await r.json());
    } catch { /* réseau coupé : on garde l'affichage, le filet réessaie */ }
  }

  function showLogin() {
    $("stage").classList.add("hidden");
    $("bar").classList.add("hidden");
    $("login").classList.remove("hidden");
    $("pin").focus();
  }

  function listen() {
    if (source) source.close();
    source = new EventSource("/api/events");
    source.onmessage = () => { clearTimeout(refreshTimer); refreshTimer = setTimeout(refresh, 200); };
    source.onerror = () => { source.close(); setTimeout(listen, 3000); };
  }

  $("login").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const r = await fetch("/api/admin/login", {
      method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin: $("pin").value }),
    });
    const data = await r.json().catch(() => ({}));
    $("pin").value = "";
    $("loginError").textContent = r.ok ? "" : data.detail || "Code incorrect";
    if (r.ok) refresh();
  });

  refresh();
  listen();
  setInterval(refresh, SAFETY_REFRESH);
})();
