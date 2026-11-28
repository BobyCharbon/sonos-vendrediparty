// Captures App Store : la base de TEST est partagée avec les recettes ; sur la liste des événements, on ne garde que les
// cartes des événements de démonstration (demo_data.py) et on retire le bandeau des sondages des autres recettes.
// Injecté par PARTY_DEBUG_JS (build de recette E2E_HOOKS seulement), jamais dans l'app de l'App Store.
(function () {
  var keep = ['Anniversaire de Zoé', 'Raclette chez Inès', 'Soirée jeux de société', 'Karaoké de décembre', 'Week-end au chalet'];
  var card = /, (date à définir|aujourd|demain|hier|lun|mar|mer|jeu|ven|sam|dim|\d)/i;
  // Fiche : la ligne « Autre agenda : Google, Outlook… » (marques de tiers) n'apparaît pas sur une capture de l'App Store.
  function noThirdParty(doc) {
    doc.querySelectorAll('div,span').forEach(function (el) {
      var t = (el.textContent || '').trim();
      if (/^Autre (choix|agenda)\s*:\s*(Google|Outlook)/.test(t) && el.style.display !== 'none') el.style.display = 'none';
    });
  }
  function clean(doc) {
    noThirdParty(doc);
    var path = doc.location.pathname.replace(/\/+$/, '');
    if (path !== '' && path !== '/events') return;  // la liste seulement (jamais la fiche)
    doc.querySelectorAll('[role="link"][aria-label]').forEach(function (a) {
      var label = a.getAttribute('aria-label') || '';
      if (!card.test(label) || keep.some(function (t) { return label.indexOf(t) === 0; })) return;
      var shell = a.parentElement && a.parentElement.parentElement;
      if (shell) shell.style.display = 'none';
    });
    var banner = doc.querySelector('[data-testid="poll-banner"]');
    if (banner) banner.style.display = 'none';
    // Pastille de « Sondages » : le seul sondage de démonstration (le week-end au chalet).
    doc.querySelectorAll('[role="button"],[role="tab"],button').forEach(function (b) {
      if (!/^Sondages\s*\d+$/.test((b.textContent || '').trim())) return;
      b.querySelectorAll('*').forEach(function (el) {
        if (!el.children.length && /^\d+$/.test(el.textContent.trim()) && el.textContent.trim() !== '1') el.textContent = '1';
      });
    });
  }
  // Pastille de l'onglet Événements : les réponses attendues des seuls événements de démonstration (jeux + sondage du chalet).
  function badge() {
    var b = document.querySelector('#tabs [data-tab="events"] .badge');
    if (b && b.textContent.trim() && b.textContent.trim() !== '2') b.textContent = '2';
  }
  setInterval(function () {
    badge();
    var frames = document.querySelectorAll('iframe');
    for (var i = 0; i < frames.length; i++) {
      try {
        var doc = frames[i].contentDocument;
        if (doc && doc.body) clean(doc);
      } catch (e) { /* autre origine */ }
    }
  }, 150);
})();
