# Consignes pour Claude (sessions locales et corrections automatiques « claude-fix »)

## Branches
- Toute correction va sur `develop`. Jamais de code poussé directement sur `main` : l'admin teste sur le site
  de test puis merge lui-même `develop` → `main`.

## Barre d'onglets sur iPhone (bug iOS 26, app installée) — ne jamais le réintroduire
Symptôme : dans l'app installée sur l'écran d'accueil, au lancement sur un onglet à page courte (Musique,
Événements, Réglages, admin…), la barre d'onglets est posée ~80 px trop haut avec une bande vide dessous ; seul
Jeux (page longue) la recalait. Cause : iOS croit l'écran plus court tant que la page n'est pas plus haute que
l'écran PHYSIQUE. Les unités CSS (100vh, 100lvh, 100dvh) suivent cette hauteur erronée, et un défilement
programmé (scrollTo) ne corrige rien : deux fausses corrections l'ont prouvé.

Correction en place (à garder telle quelle) :
- `app/static/ios-app.js`, chargé en tête de index.html ET admin.html (avant style.css) : en app installée
  (`navigator.standalone`), ajoute `html.ios-app` et `--ios-screen-h` = hauteur physique (`screen.height`) ;
- `html.ios-app body { min-height: calc(var(--ios-screen-h, 100lvh) + 1px); }` (app/static/style.css) :
  vaut pour tous les onglets, sans liste ;
- tests : `tests/e2e/test_ios_tab_bar.py` (vrai navigateur : écran 844 px, viewport 765 px, chaque onglet de
  l'app et de l'admin doit dépasser l'écran physique) + `test_ios_installed_app_page_height_follows_the_physical_screen`.

Pour tout onglet, page installable ou vue plein écran, nouveau ou existant :
- ne jamais mettre `overflow: hidden`, `height: 100vh` / `100dvh` ou un `min-height` réduit sur `html` / `body` ;
- ne jamais remplacer `--ios-screen-h` par une unité CSS de viewport ;
- une nouvelle page installable (manifest) doit charger `/static/ios-app.js` en tête, comme index.html et admin.html ;
- un contenu plein écran = un panneau `position: fixed` au-dessus de la page (comme `.events-panel`),
  la page derrière gardant sa hauteur.

Un navigateur de bureau ne reproduit pas le bug lui-même : seul un vrai iPhone (app fermée puis rouverte) le confirme.

## Tests
`python -m pytest -q --ignore=tests/e2e` avant tout commit.
