// Message pour tout le monde (avis eb710b132330) : maintenance, information ou annonce, sur tous les onglets.
// - Maintenance : un écran par-dessus toute l'app (« Mise à jour en cours ») ; l'admin, lui, garde la main (bandeau).
// - Information / Annonce : un bandeau en haut, qu'on ferme d'un ✕ (il revient pour un nouveau message).
// - Serveur qui redémarre (mise à jour) : l'app ne montre jamais d'erreur ; elle affiche « Mise à jour en cours »,
//   réessaie toute seule et reprend où on était.
// Chargé en tête de index.html et admin.html, avant tout appel au serveur. Un nouveau message arrive aussitôt par le
// flux /api/events (index.html → PartyNotice.seen) et par chaque réponse de l'API (en-tête X-Party-Notice) ;
// une coupure du flux ou une requête qui échoue fait vérifier si le serveur répond encore.
// App iPhone : si elle sait l'afficher (PartyNative.notice), c'est elle qui le dessine, au-dessus de ses écrans natifs.
(function () {
  "use strict";
  var POLL_MS = 30000, RETRY_MS = 3000, TIMEOUT_MS = 6000, DOWN_AFTER = 2;
  var HIDDEN_KEY = "vp_notice_hidden";
  var send = window.fetch.bind(window);
  var known = null;          // identifiant du message affiché ("" : aucun ; null : pas encore lu)
  var notice = null, down = false, failures = 0, sawBusy = false, timer = null, probing = false;

  function native() {
    var n = window.PartyNative && window.PartyNative.notice;
    return n && typeof n.update === "function" ? n : null;
  }
  function isAdmin() {
    try { return !!(window.partyIsAdmin && window.partyIsAdmin()); } catch (e) { return false; }
  }
  function hiddenId() { try { return localStorage.getItem(HIDDEN_KEY) || ""; } catch (e) { return ""; } }
  function hide(id) { try { localStorage.setItem(HIDDEN_KEY, id); } catch (e) { /* navigation privée */ } }

  function apiPath(input) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    try {
      var u = new URL(url, location.href);
      return u.origin === location.origin && u.pathname.indexOf("/api/") === 0 ? u.pathname : null;
    } catch (e) { return null; }
  }
  function busy(status) { return status === 502 || status === 503 || status === 504; }

  // Chaque réponse de l'API : un nouveau message ? un serveur qui ne répond plus ?
  window.fetch = function (input, init) {
    var path = apiPath(input);
    var p = send(input, init);
    if (!path || path === "/api/notice") return p;
    return p.then(function (r) {
      if (busy(r.status)) { sawBusy = true; probe(); return r; }
      var id = r.headers.get("X-Party-Notice");
      if (down || (id !== null && known !== null && id !== known)) refresh();
      return r;
    }, function (e) {
      probe();
      throw e;
    });
  };

  function read() {
    var ctl = typeof AbortController === "function" ? new AbortController() : null;
    var t = setTimeout(function () { if (ctl) ctl.abort(); }, TIMEOUT_MS);
    return send("/api/notice", { cache: "no-store", signal: ctl ? ctl.signal : undefined })
      .then(function (r) {
        if (busy(r.status)) { sawBusy = true; throw new Error("busy"); }
        if (!r.ok) throw new Error("http " + r.status);
        return r.json();
      })
      .finally(function () { clearTimeout(t); });
  }

  function schedule(ms) { clearTimeout(timer); timer = setTimeout(refresh, ms); }

  function refresh() {
    if (probing) return;
    probing = true;
    read().then(function (data) {
      var wasDown = down;
      failures = 0; sawBusy = false; down = false;
      notice = data && data.notice ? data.notice : null;
      known = notice ? notice.id : "";
      render();
      if (wasDown) window.dispatchEvent(new CustomEvent("party:back"));
      schedule(POLL_MS);
    }, function () {
      failures += 1;
      if (failures >= DOWN_AFTER && navigator.onLine !== false) { down = true; render(); }
      schedule(RETRY_MS);
    }).finally(function () { probing = false; });
  }
  // Une requête a échoué : on vérifie vite (une seule fois) si le serveur répond encore.
  function probe() { if (!probing && !down) schedule(failures ? RETRY_MS : 0); }

  // ── Ce qu'on montre ──
  function state() {
    if (down) {
      var update = sawBusy || !!(notice && notice.kind === "maintenance");
      return { id: "down", kind: "down", title: update ? "Mise à jour en cours" : "Party ne répond pas",
        message: update ? "Party revient tout seul dans une minute. Ta partie est gardée."
          : "On réessaie tout seul. Ta partie est gardée." };
    }
    if (!notice) return null;
    if (notice.kind !== "maintenance" && hiddenId() === notice.id) return null;
    return notice;
  }
  function blocks(s, admin) { return !!s && (s.kind === "down" || (s.kind === "maintenance" && !admin)); }

  var root = null;
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  var ICONS = { maintenance: "🔧", down: "🔧", info: "ℹ️", announce: "📣" };

  function render() {
    var s = state(), admin = isAdmin(), app = native();
    var html = document.documentElement;
    html.classList.toggle("native-notice", !!app);
    if (root) { root.remove(); root = null; }
    if (app) {
      try { app.update(s ? { id: s.id, kind: s.kind, title: s.title, message: s.message || "", admin: admin } : null); }
      catch (e) { /* app d'avant : rien */ }
      return;
    }
    if (!document.body) { document.addEventListener("DOMContentLoaded", render, { once: true }); return; }
    html.classList.toggle("notice-blocking", blocks(s, admin));
    if (!s) return;
    root = blocks(s, admin) ? overlay(s) : banner(s, admin);
    root.id = "partyNotice";
    document.body.appendChild(root);
  }

  function overlay(s) {
    var o = el("div", "pn-overlay");
    o.setAttribute("role", "alertdialog");
    o.setAttribute("aria-modal", "true");
    o.setAttribute("aria-labelledby", "pnTitle");
    var card = el("div", "pn-card");
    card.appendChild(el("div", "pn-icon", ICONS[s.kind] || "🔧"));
    var h = el("h2", "pn-title", s.title);
    h.id = "pnTitle";
    card.appendChild(h);
    if (s.message) card.appendChild(el("p", "pn-text", s.message));
    var wait = el("p", "pn-wait");
    wait.appendChild(el("span", "pn-dots"));
    wait.appendChild(document.createTextNode(s.kind === "down" ? "Reconnexion automatique" : "Ça revient tout seul"));
    card.appendChild(wait);
    o.appendChild(card);
    return o;
  }

  function banner(s, admin) {
    var b = el("div", "pn-banner pn-" + s.kind);
    b.setAttribute("role", "status");
    b.appendChild(el("span", "pn-banner-icon", ICONS[s.kind] || "ℹ️"));
    var body = el("div", "pn-banner-body");
    body.appendChild(el("strong", "pn-banner-title", s.kind === "maintenance" ? s.title + " · affiché à tous" : s.title));
    if (s.message) body.appendChild(el("span", "pn-banner-text", s.message));
    b.appendChild(body);
    if (s.kind === "maintenance") {
      if (admin && window.partyOpenNotice) {
        var manage = el("button", "pn-banner-act", "Gérer");
        manage.type = "button";
        manage.addEventListener("click", function () { window.partyOpenNotice(); });
        b.appendChild(manage);
      }
      return b;
    }
    var close = el("button", "pn-banner-close", "✕");
    close.type = "button";
    close.setAttribute("aria-label", "Masquer ce message");
    close.addEventListener("click", function () { hide(s.id); render(); });
    b.appendChild(close);
    return b;
  }

  window.PartyNotice = {
    refresh: refresh,
    render: render,
    current: function () { return notice; },
    // Flux /api/events (index.html) : identifiant du message en cours ; coupure du flux : le serveur répond-il ?
    seen: function (id) { if (known === null || String(id || "") !== known) refresh(); },
    probe: function () { probe(); },
    // ✕ de l'app iPhone (bandeau natif) : même mémoire que le ✕ du web.
    hide: function (id) { if (typeof id === "string" && id) { hide(id); render(); } },
    // Écran de l'admin : son message vient d'être enregistré, on le montre tout de suite.
    shown: function (n) { notice = n; known = n ? n.id : ""; render(); },
  };

  window.addEventListener("online", refresh);
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") refresh(); });
  refresh();
})();
