// 📺 Écran TV de l'hôte (/tv) : titre en cours, prochaines demandes, code et QR, parties de jeu en cours.
// Ouvert sur le Mac et affiché sur l'Apple TV par AirPlay. Se met à jour seul (flux /api/events + filet toutes les 10 s).
// Tous les textes passent par textContent : un prénom ou un titre ne peut jamais injecter du HTML.
(function () {
  const $ = (id) => document.getElementById(id);
  const SAFETY_REFRESH = 10000;
  let refreshTimer = null, source = null, shownArt = null;

  const plural = (n, one, many) => `${n} ${n > 1 ? many : one}`;

  function el(tag, text, cls) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }

  function setArt(img, src) {
    if (src) img.src = src; else img.removeAttribute("src");
  }

  function renderNow(s) {
    const now = s.active && !s.error ? s.now : null;
    $("nowLabel").textContent = !s.active ? "Bientôt" : s.error ? "Musique" : s.state === "PLAYING" ? "En ce moment" : "En pause";
    $("nowTitle").textContent = !s.active ? "La soirée va commencer" : s.error || now?.title || "Rien ne joue pour l'instant";
    $("nowArtist").textContent = !s.active ? "Scanne le QR pour ajouter tes titres" : now?.artist || "";
    $("nowBy").textContent = now?.by ? `🙋 Demandé par ${now.by}` : "";
    $("nowBy").classList.toggle("hidden", !now?.by);
    setArt($("nowArt"), now?.art);
    // Fond : seulement quand la pochette change (évite de relancer le fondu à chaque rafraîchissement).
    if ((now?.art || "") !== shownArt) {
      shownArt = now?.art || "";
      $("backdrop").style.backgroundImage = shownArt ? `url("${encodeURI(shownArt)}")` : "";
    }
  }

  function renderUpcoming(list) {
    const ol = $("upcoming");
    ol.replaceChildren(...list.map((t) => {
      const li = el("li");
      const thumb = t.art ? el("img") : el("span", null, "tv-thumb");
      if (t.art) { thumb.alt = ""; thumb.src = t.art; }
      const text = el("div");
      const sub = el("small", t.artist);
      if (t.by) sub.append(" · ", el("em", t.by));
      text.append(el("b", t.title), sub);
      li.append(thumb, text);
      return li;
    }));
    if (!list.length) ol.append(el("li", "Ajoute un titre depuis ton téléphone !", "tv-empty"));
  }

  function renderJoin(s) {
    $("pinCode").textContent = s.pin || "····";
    $("url").textContent = s.url ? s.url.replace(/^https?:\/\//, "").replace(/\/$/, "") : "";
    const qr = "/qr.svg?v=" + encodeURIComponent(s.pin || "");
    if ($("qr").getAttribute("src") !== qr) $("qr").src = qr;
  }

  function renderBar(s) {
    $("event").textContent = s.event ? `🎉 ${s.event}` : s.room ? `🔊 ${s.room}` : "";
    $("games").textContent = (s.games || []).map((g) => `🎮 ${g.name} · ${plural(g.players, "joueur", "joueurs")}`).join("   ");
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
