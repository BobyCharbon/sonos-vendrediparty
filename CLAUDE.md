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

## Module Événements (web/events) — défilement tactile
- Jamais de règle `overscroll-behavior` ni `touch-action` sur `*` (web/events/scripts/postbuild.mjs). Sous Android,
  Chrome traite chaque carte en `overflow: hidden` comme un conteneur de défilement : avec
  `overscroll-behavior: contain`, le doigt posé sur une carte ne faisait plus défiler la liste (retour #10).
  `touch-action: pan-x pan-y` sur `*` ne corrige rien et bloque le zoom à deux doigts.
- Test réel : `test_android_finger_on_an_event_card_scrolls_the_list` (geste tactile Chrome, départ sur une carte).
  Tout bug de défilement / toucher doit d'abord être reproduit par un test de ce type avant d'être corrigé.

## Jeux — requêtes simultanées
- Tous les téléphones interrogent la partie chaque seconde, en parallèle. Toute lecture-modification d'une partie
  (action, avancée automatique type `quiz.tick`, image des jeux temps réel) passe par le verrou unique
  `app/game_lock.py` (`GAMES_LOCK` dans main.py) ; `store.save` le prend aussi. Ne jamais créer de verrou par jeu
  ni modifier une partie hors de ce verrou (bug corrigé : une question de quiz ratée retirait toutes les vies,
  la main de Blackjack était distribuée plusieurs fois).
- Test : `tests/test_game_concurrency.py` (requêtes simultanées, une seule étape appliquée).
- Tout prénom ou texte saisi par un joueur passe par `esc()` avant d'entrer dans du HTML, attributs compris
  (test : `tests/e2e/test_names_escaped.py`).

## Base Supabase (Événements, comptes)
- Deux bases (décision du 24 octobre 2026) : une base de TEST pour le site de test (développement, tests, données
  jetables) et la base de PRODUCTION. Tant que la base de test n'est pas branchée, le site de test lit encore la prod.
- Les migrations (`supabase/migrations/`) ne sont jamais appliquées par le déploiement Docker ni par le workflow.
  Claude les écrit, les applique et les teste sur la base de TEST ; il ne les applique en PRODUCTION qu'après
  l'accord explicite de l'admin, donné à chaque fois, pour cette migration précise. Jamais de SQL d'écriture en prod
  sans cet accord.
- Application en PRODUCTION : uniquement par `python3 supabase/tools/apply_prod.py supabase/prod/<fichier>.sql`
  (fichiers préparés dans `supabase/prod/`, avec leur retour arrière), et seulement après le « Ok prod » de l'admin
  pour cette migration. Le script refuse tout autre fichier et une migration déjà en prod ; `sbq.py` reste en lecture seule.
- Toute la structure doit vivre dans `supabase/migrations/` : rejouer les migrations sur une base vide doit recréer
  la base de test à l'identique de la prod (c'est ainsi qu'on passe en prod).
- Une migration doit être purement additive et rejouable (`add column if not exists`, `drop policy if exists`
  avant `create policy`, `create or replace function`, `drop trigger if exists`), pour ne jamais casser la prod.
- Vérifier les politiques RLS existantes : une politique `for update` donne accès à toute la ligne ; protéger les
  colonnes sensibles avec un trigger de garde (modèle : `guard_profile`, `guard_bring_item`).

## Tests
`python -m pytest -q --ignore=tests/e2e` avant tout commit.
