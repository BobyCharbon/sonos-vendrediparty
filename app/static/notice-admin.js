// Réglages › « Annonce et maintenance » (Root et admins, avis eb710b132330) : un message pour tout le monde, sur tous
// les onglets de l'app, web et iPhone. Trois sortes : Maintenance (écran « Mise à jour en cours » qui couvre l'app),
// Information et Annonce (bandeau en haut, que chacun ferme). Usage : NoticeAdmin.mount(élément) ; .refresh().
// API : GET / POST / DELETE /api/admin/notice (session admin) ; l'affichage chez tous : notice.js.
(function () {
  const escape = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const KINDS = {
    maintenance: { icon: "🔧", label: "Maintenance", title: "Mise à jour en cours",
      hint: "Un écran « Mise à jour en cours » couvre toute l'app pour tout le monde, sauf toi. Les parties sont gardées. Pense à le retirer.",
      placeholder: "Ex. : Retour vers 18 h. Ta partie est gardée." },
    info: { icon: "ℹ️", label: "Information", title: "Information",
      hint: "Un bandeau en haut de tous les onglets. Chacun peut le fermer ; un nouveau message revient chez tout le monde.",
      placeholder: "Ex. : Le Wi-Fi de la soirée s'appelle « Party »." },
    announce: { icon: "📣", label: "Annonce", title: "Annonce",
      hint: "Un bandeau mis en avant en haut de tous les onglets. Chacun peut le fermer.",
      placeholder: "Ex. : Karaoké à 22 h dans le salon !" },
  };
  const MAX = 280;
  const when = (t) => new Date(t * 1000).toLocaleString("fr-CH", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  let root = null, kind = "announce", current = null, busy = false;

  function say(msg, bad) { if (typeof toast === "function") toast(msg, bad ? "err" : "ok"); }

  async function call(method, body) {
    const r = await fetch("/api/admin/notice", {
      method, credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await r.json().catch(() => null);
    if (!r.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Le message n'a pas pu être enregistré. Réessaie.");
    return data;
  }

  function nowCard() {
    if (!current) return `<p class="artist" data-notice-now>Aucun message en ce moment.</p>`;
    const k = KINDS[current.kind] || KINDS.info;
    return `<div class="track" data-notice-now><div class="meta">
        <div class="title">${k.icon} <b>${escape(current.title)}</b> · ${escape(k.label)}</div>
        ${current.message ? `<div class="artist" style="white-space:pre-line">${escape(current.message)}</div>` : ""}
        <div class="artist">Affiché à tous depuis le ${when(current.at)} · ${escape(current.by)}</div>
      </div></div>
      <button type="button" class="secondary" data-notice-stop style="width:100%;margin-top:8px">Retirer le message</button>`;
  }

  function render() {
    const k = KINDS[kind];
    root.innerHTML = `
      <div class="card" style="margin-bottom:14px">
        <h3 style="margin:0 0 8px">En ce moment</h3>
        ${nowCard()}
      </div>
      <div class="card">
        <h3 style="margin:0 0 10px">Nouveau message pour tout le monde</h3>
        <div class="seg" role="radiogroup" aria-label="Sorte de message" data-notice-kinds>
          ${Object.entries(KINDS).map(([key, v]) => `<button type="button" role="radio" data-kind="${key}" aria-checked="${key === kind}" class="${key === kind ? "on" : ""}">${v.icon} ${v.label}</button>`).join("")}
        </div>
        <p class="artist" data-notice-hint style="margin:10px 0">${escape(k.hint)}</p>
        <label class="artist" for="noticeTitle">Titre (facultatif)</label>
        <input type="text" id="noticeTitle" maxlength="60" placeholder="${escape(k.title)}" style="width:100%;margin:4px 0 10px">
        <label class="artist" for="noticeText">Message${kind === "maintenance" ? " (facultatif)" : ""}</label>
        <textarea id="noticeText" rows="3" maxlength="${MAX}" placeholder="${escape(k.placeholder)}" style="width:100%;margin-top:4px"></textarea>
        <p class="artist" data-notice-count style="text-align:right;margin:2px 0 10px">0 / ${MAX}</p>
        <button type="button" data-notice-send style="width:100%">Afficher à tout le monde</button>
      </div>`;
  }

  function readForm() {
    return { kind, title: root.querySelector("#noticeTitle").value, message: root.querySelector("#noticeText").value };
  }

  function pick(next) {
    const keep = readForm();
    kind = next;
    render();
    root.querySelector("#noticeTitle").value = keep.title;
    root.querySelector("#noticeText").value = keep.message;
    count();
  }
  function count() { root.querySelector("[data-notice-count]").textContent = `${root.querySelector("#noticeText").value.length} / ${MAX}`; }

  async function publish() {
    if (busy) return;
    const body = readForm();
    if (kind !== "maintenance" && !body.message.trim()) return say("Écris le message à afficher.", true);
    if (kind === "maintenance" && !confirm("Tout le monde verra l'écran « Mise à jour en cours » à la place de l'app, jusqu'à ce que tu le retires. Continuer ?")) return;
    busy = true;
    try {
      current = (await call("POST", body)).notice;
      window.PartyNotice?.shown?.(current);
      say(kind === "maintenance" ? "Maintenance affichée à tout le monde" : "Message affiché à tout le monde");
      render();
    } catch (e) { say(e.message, true); } finally { busy = false; }
  }

  async function stop() {
    if (busy) return;
    busy = true;
    try {
      current = (await call("DELETE")).notice;
      window.PartyNotice?.shown?.(null);
      say("Message retiré");
      render();
    } catch (e) { say(e.message, true); } finally { busy = false; }
  }

  async function refresh() {
    if (!root) return;
    try { current = (await call("GET")).notice; render(); }
    catch (e) { /* hors ligne : l'écran garde ce qu'il montre */ }
  }

  function mount(el) {
    root = el;
    render();
    root.addEventListener("click", (ev) => {
      const k = ev.target.closest("[data-kind]");
      if (k) return pick(k.dataset.kind);
      if (ev.target.closest("[data-notice-send]")) return publish();
      if (ev.target.closest("[data-notice-stop]")) return stop();
    });
    root.addEventListener("input", (ev) => { if (ev.target.id === "noticeText") count(); });
    refresh();
  }

  window.NoticeAdmin = { mount, refresh };
})();
