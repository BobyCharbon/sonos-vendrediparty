# Consignes pour Claude (sessions locales et corrections automatiques « claude-fix »)

## Branches
- Toute correction va sur `develop`. Jamais de code poussé directement sur `main` : l'admin teste sur le site
  de test puis merge lui-même `develop` → `main`.

## Barre d'onglets sur iPhone (bug iOS 26, app installée) — ne jamais le réintroduire
Dans une web app installée sur l'écran d'accueil, la barre d'onglets (fixée en bas) reste posée trop haut, avec une
bande vide dessous, tant que la page n'a jamais défilé. La correction est globale et doit le rester :
- `body { min-height: calc(100lvh + 1px); }` (app/static/style.css) : la page est toujours défilable d'au moins 1 px ;
- `nudgeViewport()` est appelé sans condition à la fin de `showTab` (app/static/index.html) ;
- test : `test_every_tab_keeps_the_page_scrollable_for_the_ios_tab_bar` (tests/test_release_regressions.py).

Pour tout onglet ou vue plein écran, nouveau ou existant :
- ne jamais mettre `overflow: hidden`, `height: 100vh` / `100dvh` ou un `min-height` réduit sur `html` / `body` ;
- ne pas rendre `nudgeViewport()` conditionnel à une liste d'onglets ;
- un contenu plein écran = un panneau `position: fixed` au-dessus de la page (comme `.events-panel`),
  la page derrière restant défilable.

Un navigateur de bureau ne reproduit pas ce bug : seul un vrai iPhone (app fermée puis rouverte) le confirme.

## Tests
`python -m pytest -q --ignore=tests/e2e` avant tout commit.
