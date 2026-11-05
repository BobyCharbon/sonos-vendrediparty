// 🪩 Réactions de Zicou (décision F, 4.11.2026) : petit bandeau éphémère en haut de l'écran (« +5 🪙 pour Zicou »)
// après un titre ajouté, une partie de soirée ou de Méninges terminée. Le serveur décide (plafonds du jour, jamais pour
// un jeu à boire, rien sans Zicou sauf une proposition d'adoption, une fois) : app/pet_reactions.py.
// Aucune notification push ; coupable dans Réglages › Compagnon (« Réactions de Zicou »).
// Branchement : une réponse de l'API porte l'en-tête X-Zicou quand un bandeau attend → on va le chercher ; la file et
// Méninges renvoient leurs bandeaux dans la réponse même (champ « zicou »).
// Pour l'onglet Zicou et la pastille : chaque bandeau est aussi annoncé par l'événement window « zicou:reaction »
// (detail = { kind, source, coins, text }) ; window.ZicouReactions.show(item) en affiche un à la main.
(() => {
  const SHOW_MS = 2600, GAP_MS = 250, PULL_DELAY_MS = 400;
  const BODY_URLS = /\/api\/(queue|brain\/result)(\?|$)/;
  const nativeFetch = window.fetch.bind(window);
  let queue = [], showing = false, pullTimer = null, pulling = false;

  const guest = () => { try { return localStorage.getItem("vp_guest") || ""; } catch { return ""; } };
  const isMember = () => /^acct-[0-9a-f]{40}$/.test(guest());
  const reduced = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  function banner() {
    let el = document.getElementById("zicouReaction");
    if (el) return el;
    const style = document.createElement("style");
    style.textContent = `
      #zicouReaction { position: fixed; z-index: 9000; left: 50%; top: calc(10px + env(safe-area-inset-top));
        transform: translate(-50%, -140%); max-width: min(420px, calc(100vw - 32px)); display: flex; gap: 10px;
        align-items: center; padding: 10px 14px; border-radius: 16px; background: rgba(36, 29, 53, .94);
        color: #f4f1fa; font: 600 14px/1.3 -apple-system, system-ui, sans-serif; box-shadow: 0 8px 30px rgba(0,0,0,.35);
        -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px); pointer-events: none;
        transition: transform .35s cubic-bezier(.2,.9,.3,1.2), opacity .25s; opacity: 0; }
      #zicouReaction.on { transform: translate(-50%, 0); opacity: 1; pointer-events: auto; }
      #zicouReaction .zr-face { font-size: 22px; flex: none; animation: zr-bop .6s ease-in-out 2; }
      #zicouReaction button { margin-left: 4px; padding: 6px 10px; border-radius: 10px; font-size: 13px; flex: none; }
      @keyframes zr-bop { 50% { transform: translateY(-3px) rotate(-8deg); } }
      @media (prefers-reduced-motion: reduce) { #zicouReaction { transition: opacity .2s; }
        #zicouReaction .zr-face { animation: none; } }`;
    document.head.append(style);
    el = document.createElement("div");
    el.id = "zicouReaction";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    document.body.append(el);
    return el;
  }

  function openZicou() {
    window.dispatchEvent(new CustomEvent("zicou:open"));
    // Onglet Zicou (id « pet », pet/zicou-home.js) ; sans lui, l'onglet Jeux (carte du Compagnon).
    const tab = document.querySelector('#tabs [data-tab="pet"]') || document.querySelector('#tabs [data-tab="games"]');
    tab?.click();
  }

  function render(item) {
    const el = banner();
    el.replaceChildren();
    const face = document.createElement("span");
    face.className = "zr-face";
    face.textContent = item.kind === "adopt" ? "🥚" : "🪩";
    const text = document.createElement("span");
    text.textContent = String(item.text || "");   // texte du serveur, jamais interprété comme du HTML
    el.append(face, text);
    if (item.kind === "adopt") {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = "Adopter";
      b.onclick = () => { hide(); openZicou(); };
      el.append(b);
    }
    void el.offsetWidth;
    el.classList.add("on");
  }

  function hide() {
    document.getElementById("zicouReaction")?.classList.remove("on");
  }

  function next() {
    const item = queue.shift();
    if (!item) { showing = false; return; }
    showing = true;
    render(item);
    window.dispatchEvent(new CustomEvent("zicou:reaction", { detail: item }));
    setTimeout(() => { hide(); setTimeout(next, GAP_MS + (reduced() ? 0 : 300)); },
      item.kind === "adopt" ? SHOW_MS * 2 : SHOW_MS);
  }

  function show(items) {
    const fresh = (Array.isArray(items) ? items : []).filter((i) => i && typeof i.text === "string");
    if (!fresh.length) return;
    queue = queue.concat(fresh).slice(-4);
    if (!showing) next();
  }

  async function token() {
    try { return typeof freshToken === "function" ? (await freshToken()) || "" : ""; } catch { return ""; }
  }

  async function pull() {
    if (pulling || !isMember()) return;
    pulling = true;
    try {
      const r = await nativeFetch("/api/pet/reactions", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ guest_id: guest(), token: await token() }) });
      if (r.ok) show((await r.json()).items);
    } catch { /* hors ligne : le bandeau attend la prochaine réponse marquée */ }
    finally { pulling = false; }
  }

  function watch(res, url) {
    if (!isMember() || !res) return;
    if (BODY_URLS.test(url) && res.ok) {
      res.clone().json().then((b) => show(b?.zicou)).catch(() => {});
    }
    if (res.headers?.get("X-Zicou") === "1") {
      clearTimeout(pullTimer);
      pullTimer = setTimeout(pull, PULL_DELAY_MS);
    }
  }

  window.fetch = async (input, init) => {
    const res = await nativeFetch(input, init);
    try { watch(res, typeof input === "string" ? input : input?.url || ""); } catch { /* jamais bloquant */ }
    return res;
  };

  window.ZicouReactions = { show: (item) => show([item]), pull };
})();
