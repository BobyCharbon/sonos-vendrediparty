// Barre d'onglets sur iPhone, app installée (bug iOS 26) — chargé en tête de page, avant tout affichage.
// Au lancement, iOS croit l'écran ~80 px plus court et pose la barre d'onglets trop haut (bande vide dessous),
// tant que la page n'est pas plus haute que l'écran PHYSIQUE : c'est pour ça que seul Jeux (page longue) la recalait.
// Les unités CSS (100vh, 100lvh…) suivent la hauteur erronée ; screen.height, elle, est juste.
// → La page fait toujours au moins la hauteur physique + 1 px (règle « html.ios-app body » de style.css).
// Voir CLAUDE.md et tests/e2e/test_ios_tab_bar.py. Ne jamais remplacer ça par 100vh / 100lvh / 100dvh.
// Pas de zoom (l'app doit se sentir native) : le viewport l'interdit déjà, mais Safari l'ignore ; on bloque donc
// aussi le pincement (gesturestart, propre à iOS). Le double-tap est coupé par « touch-action: manipulation » (style.css).
document.addEventListener("gesturestart", function (e) { e.preventDefault(); }, {passive: false});

(function () {
  if (navigator.standalone !== true) return;  // seulement l'app installée sur l'écran d'accueil d'un iPhone / iPad
  var root = document.documentElement;
  root.classList.add("ios-app");
  function fit() {
    // screen.width / height ne s'échangent pas en paysage sur iOS : on prend le bon côté selon l'orientation.
    var landscape = window.matchMedia("(orientation: landscape)").matches;
    var h = landscape ? Math.min(screen.width, screen.height) : Math.max(screen.width, screen.height);
    root.style.setProperty("--ios-screen-h", h + "px");
  }
  fit();
  window.addEventListener("orientationchange", fit);
  window.addEventListener("resize", fit);
})();
