// App iOS native (ios/) : la barre d'onglets est une vraie UITabBar, dessinée par l'app.
// La page reste la référence : elle décrit ses onglets à l'app (libellés, onglet actif, badges, plein écran)
// à chaque changement, et l'app lui renvoie les touchers (PartyTabs.select), qui passent par le même clic qu'ici.
// Sans pont natif (navigateur, app Android, PWA), ce fichier ne fait rien. Tests : tests/e2e/test_native_tabs.py.
(function () {
  const bridge = window.PartyNative && window.PartyNative.tabs;
  const bar = document.getElementById("tabs");
  if (!bridge || !bar) return;

  const DOT = "●";

  /** null : pas de badge ; "" : un point ; sinon le texte (nombre…). */
  function badgeOf(button) {
    const badge = button.querySelector(".badge");
    if (!badge || badge.classList.contains("hidden") || getComputedStyle(badge).display === "none") return null;
    const text = badge.textContent.trim();
    return text === DOT ? "" : text;
  }

  // Onglets que l'app peut afficher en natif. L'hôte aussi : l'app lui propose « Gérer la soirée » /
  // « Gérer les retours », qui rouvrent l'onglet de la page avec ses réglages. Réglages (account) : écran natif,
  // qui ouvre encore dans la page les écrans du compte pas encore natifs (profil, confidentialité…).
  const NATIVE_SCREENS = ["music", "feedback", "chats", "account"];
  // fbIsAdmin est déclarée plus loin dans index.html : tant qu'elle n'existe pas, on est invité.
  const isHost = () => typeof fbIsAdmin === "function" && fbIsAdmin();

  function describe() {
    const soon = document.documentElement.classList.contains("events-soon");
    return {
      native: NATIVE_SCREENS,
      host: isHost(),
      // Page affichée, y compris une page des Réglages sans bouton dans la barre (« Ton avis » : écran natif).
      screen: document.body.dataset.tab || null,
      // Ligne « Ton avis » / « Retours » des Réglages natifs (sortie de la barre le 4.11) : libellé et pastille.
      feedback: typeof window.fbInfo === "function" ? window.fbInfo() : null,
      // Un jeu en plein écran masque la barre web (display: none) : la barre native suit.
      hidden: getComputedStyle(bar).display === "none",
      // Onglet masqué par la page (« Ton avis » sans le droit d'écrire un avis) : absent de la barre native aussi.
      tabs: [...bar.querySelectorAll("button[data-tab]")].filter((button) => !button.classList.contains("hidden")).map((button) => ({
        id: button.dataset.tab,
        label: (button.querySelector("span")?.textContent || "").trim(),
        active: button.classList.contains("on"),
        badge: badgeOf(button),
        soon: ["events", "chats"].includes(button.dataset.tab) && soon,
      })),
    };
  }

  let sent = "";
  let pending = false;
  function send() {
    pending = false;
    const state = describe();
    const json = JSON.stringify(state);
    if (json === sent) return;
    sent = json;
    bridge.update(state);
  }
  // Plusieurs changements dans la même image (onglet + badge + titre) : un seul envoi.
  function schedule() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(send);
  }

  new MutationObserver(schedule).observe(bar, { subtree: true, childList: true, characterData: true, attributes: true });
  new MutationObserver(schedule).observe(document.body, { attributes: true, attributeFilter: ["class", "data-tab"] });
  new MutationObserver(schedule).observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  addEventListener("pageshow", schedule);

  window.PartyTabs = {
    /** Toucher d'un onglet natif : même chemin qu'un toucher dans la page (clic délégué → showTab). */
    select(id) {
      const button = [...bar.querySelectorAll("button[data-tab]")].find((b) => b.dataset.tab === id);
      if (button) button.click();
      // Page sans bouton dans la barre (« Ton avis », sous Réglages) : ouverte directement, liens profonds compris.
      else if (typeof showTab === "function") showTab(id);
    },
    /** La page a changé quelque chose hors de la barre (pastille de « Ton avis ») : nouvelle description. */
    refresh: schedule,
  };
  send();
})();
