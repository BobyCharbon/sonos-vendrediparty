// « Ton avis » écrit avec l'IA (demande de l'admin, 04.11 ; serveur : app/ai_feedback.py).
// La personne parle (« Dis-le à voix haute », dictée du navigateur) ou écrit ; à l'envoi, l'IA reformule en un avis
// clair (type, zone, titre, description, étapes…), pose au besoin UNE question, puis demande « C'est bien ça ? » :
// Oui, envoyer · Corriger · Envoyer mon texte tel quel. Rien ne part à l'IA sans l'accord de la feuille (Apple 5.1.2) ;
// sans accord, IA indisponible ou limite atteinte : l'avis s'écrit comme avant (index.html, fbPost).
// Globales de index.html utilisées : $, api, esc, toast, freshToken, guestId, guestName, fbKind, fbPost.
window.FeedbackAI = (() => {
  const AI_MIN = 8;  // FEEDBACK_AI_MIN_LENGTH (app/main.py)
  const KIND = { idea: "💡 Idée", bug: "🐞 Bug", other: "💬 Autre" };
  const AREA = { music: "🎵 Musique", games: "🎲 Jeux", pet: "🐾 Zicou", events: "📅 Événements", calendar: "🗓️ Calendrier",
    chats: "💬 Discussions", account: "⚙️ Réglages", admin: "🛠️ Retours", tv: "📺 Apple TV", general: "🌐 Général" };
  const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  let status = null;  // { configured, consent: "" | "accepted" | "declined", remaining }
  let turns = [], draft = null, context = {}, busy = false;
  let rec = null, recTarget = null, recBase = "", recDone = null;

  const tokenNow = async () => (await freshToken()) || "";
  const body = async (extra = {}) => JSON.stringify({ guest_id: guestId, token: await tokenNow(), ...extra });

  // ── État : configurée, accord, reformulations restantes ──
  async function refresh() {
    try {
      status = await api("/api/feedback/ai/status", { method: "POST", body: await body() });
    } catch { status = null; }
    render();
  }
  const usable = () => !!(status && status.configured && status.consent !== "declined" && status.remaining > 0);
  function render() {
    const row = $("fbAiRow");
    if (!row) return;
    $("fbMic").classList.toggle("hidden", !Speech);
    row.classList.toggle("hidden", !(status && status.configured));
    if (!status) return;
    const on = status.consent === "accepted";
    $("fbAiState").textContent = on ? "✨ L'IA t'aide à écrire ton avis" : "✨ L'IA peut t'aider à écrire ton avis";
    $("fbAiToggle").textContent = on ? "Retirer mon accord" : status.consent === "declined" ? "Activer l'IA" : "";
    $("fbAiToggle").classList.toggle("hidden", !status.consent);
  }

  // ── Feuille d'accord (avant la 1re utilisation) ──
  function askConsent() {
    return new Promise((resolve) => {
      const sheet = $("fbAiConsent");
      const done = async (accept) => {
        sheet.classList.add("hidden");
        $("fbAiYes").onclick = $("fbAiNo").onclick = null;
        try {
          status = await api("/api/feedback/ai/consent", { method: "POST", body: await body({ accept }) });
        } catch (e) { toast(e.message, "err"); status = { ...(status || {}), consent: accept ? "" : "declined" }; }
        render();
        resolve(status.consent === "accepted");
      };
      $("fbAiYes").onclick = () => done(true);
      $("fbAiNo").onclick = () => done(false);
      sheet.classList.remove("hidden");
      $("fbAiYes").focus();
    });
  }

  // ── Dictée (navigateur : Safari, Chrome…) ; le texte s'écrit dans le champ pendant qu'on parle ──
  function listening() { return !!rec; }
  function stopDictation() { if (rec) rec.stop(); }
  function dictate(textarea, button, onDone) {
    if (rec) { stopDictation(); return; }
    if (!Speech) return toast("La dictée n'est pas disponible dans ce navigateur : écris ton avis.", "err");
    rec = new Speech();
    rec.lang = "fr-CH"; rec.interimResults = true; rec.continuous = true;
    recTarget = textarea; recBase = textarea.value.trim(); recDone = onDone;
    button.classList.add("on"); button.setAttribute("aria-pressed", "true");
    const label = button.querySelector("[data-mic-label]");
    if (label) { label.dataset.idle = label.dataset.idle || label.textContent; label.textContent = "Je t'écoute… touche pour finir"; }
    rec.onresult = (ev) => {
      const heard = Array.from(ev.results).map((r) => r[0].transcript).join(" ").replace(/\s+/g, " ").trim();
      recTarget.value = [recBase, heard].filter(Boolean).join(" ").slice(0, 1000);
      recTarget.dispatchEvent(new Event("input"));
    };
    rec.onerror = (ev) => {
      if (ev.error === "not-allowed" || ev.error === "service-not-allowed") toast("Autorise le micro pour dicter, ou écris ton avis.", "err");
    };
    rec.onend = () => {
      rec = null;
      button.classList.remove("on"); button.setAttribute("aria-pressed", "false");
      if (label) label.textContent = label.dataset.idle;
      const done = recDone; recDone = null;
      if (done) done();
    };
    try { rec.start(); } catch { rec = null; toast("Le micro n'a pas pu démarrer : écris ton avis.", "err"); }
  }

  // ── Reformulation ──
  function device() {
    const ua = navigator.userAgent;
    const where = /iPhone/.test(ua) ? "iPhone" : /iPad/.test(ua) ? "iPad" : /Android/.test(ua) ? "Android" : /Mac/.test(ua) ? "Mac" : /Windows/.test(ua) ? "Windows" : "";
    const browser = /Edg\//.test(ua) ? "Edge" : /CriOS|Chrome\//.test(ua) ? "Chrome" : /FxiOS|Firefox\//.test(ua) ? "Firefox" : /Safari\//.test(ua) ? "Safari" : "";
    const build = typeof siteBuild !== "undefined" && siteBuild ? String(siteBuild).slice(0, 12) : "";
    return { platform: "web", os: [where, browser].filter(Boolean).join(" "), ...(build ? { app: build } : {}) };
  }

  async function rewrite() {
    busy = true; showReview("loading");
    let r;
    try {
      r = await api("/api/feedback/ai/rewrite", { method: "POST", body: await body({ name: guestName || "", turns, context }) });
    } catch (e) {
      busy = false;
      if (e.status === 403) { await refresh(); }
      toast(e.message, "err");
      closeReview(false);
      return;
    }
    busy = false;
    if (r.status === "unavailable") {
      // IA indisponible (limite du jour, budget, panne) : l'avis part quand même, tel quel (retour du 11.11).
      if (status) status.remaining = 0;
      await send(false);
      return;
    }
    draft = r.draft;
    if (status) status.remaining = r.remaining ?? status.remaining;
    showReview(r.status === "needs_info" ? "question" : "ready", r.question);
  }

  function draftHtml(d) {
    const rows = [];
    if (d.description) rows.push(`<p>${esc(d.description)}</p>`);
    if (d.steps?.length) rows.push(`<div class="fb-ai-k">Étapes</div><ol>${d.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>`);
    [["expected", "Attendu"], ["actual", "Ce qui se passe"], ["need", "Le besoin"], ["proposal", "La proposition"], ["device", "Appareil"]]
      .forEach(([k, label]) => { if (d[k]) rows.push(`<div class="fb-ai-k">${label}</div><p>${esc(d[k])}</p>`); });
    return `<div class="fb-chips"><span class="fb-chip">${esc(KIND[d.kind] || "")}</span><span class="fb-chip">${esc(AREA[d.area] || "")}</span></div>
      <h3 class="fb-ai-title">${esc(d.title)}</h3>${rows.join("")}`;
  }

  function showReview(step, question = "") {
    $("fbForm").classList.add("hidden");
    const box = $("fbAiReview");
    box.classList.remove("hidden");
    box.dataset.step = step;
    $("fbAiLoading").classList.toggle("hidden", step !== "loading");
    $("fbAiDraft").classList.toggle("hidden", step === "loading" || !draft);
    if (draft) $("fbAiDraft").innerHTML = draftHtml(draft);
    $("fbAiAsk").classList.toggle("hidden", step !== "ready");
    $("fbAiQuestion").classList.toggle("hidden", step !== "question");
    $("fbAiQuestion").textContent = question;
    const answering = step === "question" || step === "correct";
    $("fbAiMore").classList.toggle("hidden", !answering);
    $("fbAiActions").classList.toggle("hidden", step === "loading");
    $("fbAiOk").classList.toggle("hidden", step !== "ready");
    $("fbAiFix").classList.toggle("hidden", step !== "ready");
    $("fbAiMoreText").placeholder = step === "question" ? "Ta réponse" : "Ce qui n'est pas juste, ou ce qui manque";
    if (answering) { $("fbAiMoreText").value = ""; $("fbAiMoreText").focus(); }
  }

  function closeReview(sent) {
    stopDictation();
    $("fbAiReview").classList.add("hidden");
    $("fbForm").classList.remove("hidden");
    if (sent) { turns = []; draft = null; }
  }

  // Envoi du formulaire principal (index.html) : true si l'IA prend la main, false pour envoyer comme avant.
  async function take(text, ctx) {
    if (!usable() || busy) return false;
    if (status.consent !== "accepted" && !(await askConsent())) return false;
    if (text.length < AI_MIN) { toast(`Dis-en un peu plus (au moins ${AI_MIN} caractères)`, "err"); return true; }
    turns = [text]; draft = null; context = { ...ctx, ...device() };
    await rewrite();
    return true;
  }

  async function send(useDraft) {
    const text = turns.join(" · ");
    const btns = $("fbAiActions").querySelectorAll("button");
    btns.forEach((b) => { b.disabled = true; });
    try {
      await fbPost(text, useDraft ? draft.kind : fbKind, context, useDraft ? draft : null);
      closeReview(true);
    } catch (e) { toast(e.message, "err"); }
    btns.forEach((b) => { b.disabled = false; });
  }

  function more() {
    const extra = $("fbAiMoreText").value.replace(/\s+/g, " ").trim();
    if (!extra) return toast("Dis ou écris ta précision", "err");
    if (turns.length >= (status?.max_turns || 4)) return toast("Tu peux envoyer ton texte tel quel, ou corriger après l'envoi dans un nouvel avis.", "err");
    turns = [...turns, extra];
    rewrite();
  }

  function mount() {
    const microphone = (button, textarea, onDone) => button.addEventListener("click", () => dictate(textarea, button, onDone));
    // Fini de parler : comme l'assistant des événements, toucher à nouveau le micro envoie.
    microphone($("fbMic"), $("fbText"), () => { if ($("fbText").value.trim()) $("fbForm").requestSubmit(); });
    microphone($("fbAiMoreMic"), $("fbAiMoreText"), () => { if ($("fbAiMoreText").value.trim()) more(); });
    $("fbAiOk").addEventListener("click", () => send(true));
    $("fbAiRaw").addEventListener("click", () => send(false));
    $("fbAiFix").addEventListener("click", () => showReview("correct"));
    $("fbAiMoreSend").addEventListener("click", more);
    $("fbAiMoreText").addEventListener("keydown", (ev) => { if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); more(); } });
    $("fbAiCancel").addEventListener("click", () => closeReview(false));
    $("fbAiToggle").addEventListener("click", async () => {
      if (status?.consent === "accepted") {
        try { status = await api("/api/feedback/ai/consent", { method: "POST", body: await body({ accept: false }) }); } catch (e) { toast(e.message, "err"); }
        render();
        toast("Accord retiré : plus rien n'est envoyé à l'IA.", "ok");
      } else {
        await askConsent();
      }
    });
  }

  return { mount, refresh, take, usable, listening, minimum: () => (usable() ? AI_MIN : null), draftHtml };
})();
