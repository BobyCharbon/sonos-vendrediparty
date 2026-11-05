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

App iOS native (ios/, WKWebView) : la barre d'onglets y est une vraie UITabBar, sous la vue web. La page la décrit
(`app/static/native-tabs.js` → `window.PartyNative.tabs.update`) et l'app renvoie les touchers (`PartyTabs.select`).
`ios-app.js` ajoute alors `html.native-tabs` au lieu de `html.ios-app` (pas de bug iOS 26 dans une WKWebView) ;
la barre web reste dans le DOM, sans place ni visibilité. Un nouvel onglet = un bouton `#tabs [data-tab]` de plus
(icône SF Symbol dans `ios/Party/NativeTabBar.swift`). Tests : `tests/e2e/test_native_tabs.py`.

## Module Événements (web/events) — défilement tactile
- Jamais de règle `overscroll-behavior` ni `touch-action` sur `*` (web/events/scripts/postbuild.mjs). Sous Android,
  Chrome traite chaque carte en `overflow: hidden` comme un conteneur de défilement : avec
  `overscroll-behavior: contain`, le doigt posé sur une carte ne faisait plus défiler la liste (retour #10).
  `touch-action: pan-x pan-y` sur `*` ne corrige rien et bloque le zoom à deux doigts.
- Test réel : `test_android_finger_on_an_event_card_scrolls_the_list` (geste tactile Chrome, départ sur une carte).
  Tout bug de défilement / toucher doit d'abord être reproduit par un test de ce type avant d'être corrigé.
- Billets QR : option par événement (`events.tickets_enabled`, éteinte par défaut) activée par l'organisateur lui-même ;
  l'IA de création / modification (app/ai_events.py, ai_event_edit.py) ne l'active JAMAIS (hors de son schéma) ; un QR
  n'existe que si l'option est active ET le billet remis (`issue_event_ticket`, ou place payée confirmée).

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

## Conformité App Store / Play Store (jeux, Zicou, économie) — contrôle du 04.11.2026
Avant de concevoir une nouvelle mécanique de jeu ou d'économie (tirage, coffre, monnaie, échange, concours, cadeau
d'événement, classement, notification, mesure de données), faire d'abord une revue de conformité et dire les blocages à
l'admin. Toujours :
- Jamais d'argent réel ni de lot réel (boisson, bon, place, objet physique) dans le jeu ; le paiement entre amis et les
  billets de Party ne touchent jamais un objet du jeu. Pas de NFT, de crypto ni de portefeuille.
- Hasard : chances affichées pour chaque tirage, même pour un objet masqué (« Objet mystère : 2 % ») ; pas de tirage payé
  en pièces sans revue ; pas d'animation de machine à sous.
- Tirages d'événement et concours : faits par le serveur, dans les bornes fixées par l'admin ; l'éligibilité ne dépend
  JAMAIS d'un paiement (billet) ; chances et exemplaires publiés avant puis figés ; règlement dans l'app avec « Apple et
  Google ne sont ni organisateurs ni sponsors » (Apple 5.3.1, 5.3.2).
- Contenu des joueurs (noms, mots, offres, vitrine, codes) : filtre, « Signaler », blocage commun à toute l'app, CGU
  acceptées avant le premier contenu/échange, contact publié (Apple 1.2, Google UGC). Aucun texte libre de joueur à
  l'Apple TV ni dans un widget sans modération.
- Échanges : objet contre objet seulement ; CGU « aucune valeur monétaire, vente interdite » ; journal, plafonds, délais ;
  un code d'échange transfère un objet possédé, il n'en crée jamais (pas de code promo admin).
- Récompenses : jamais pour noter l'app, laisser un avis, télécharger ou partager (3.2.2) ; jamais pour boire ni pour un
  jeu à boire (1.4.3) ; inviter des amis n'est jamais obligatoire.
- Notifications : chaque type a son interrupteur, le jeu marche sans, pas de pub sans consentement (4.5.4), ton sans
  culpabilité. Live Activity seulement pour un épisode borné (< 8 h) ; le compagnon permanent va dans le widget.
- Revue Apple : toute grosse fonction livrée par le web (échanges, tirages, rangs, numérotés) est décrite dans les Notes for
  Review d'une version soumise AVANT son ouverture en production iOS, avec un compte de démo (2.3.1(a), 2.5.19).
- Données : toute nouvelle mesure → politique de confidentialité, App Privacy, Data safety, durée de conservation ; aucun
  SDK tiers d'analyse ou de pub ; tout part avec la suppression du compte.
- Questionnaire d'âge App Store Connect à refaire dès qu'on ajoute concours, tirage, chat, contenu de joueur ou achat.
  Distribution : Suisse seulement ; tout nouveau pays ou une app Android publique → nouvelle revue.

## Zicou : bêta seulement (décision de l'admin, 04.11.2026)
- Zicou est ÉTEINT hors site de test par `compagnon_enabled()` (`app/features.py` : `COMPAGNON_ENABLED`
  "1"/"0", sinon allumé seulement si l'adresse publique est `partytest.bobycharbon.ch`). Éteint : `/api/pet/*`,
  `/api/tv/zicou`, `/zicou/*`, `/static/pet/*` → 404 « Zicou arrive bientôt. », aucune réaction calculée
  (`zicou_react`), la page reçoit `data-compagnon="off"` et perd ses blocs `<!-- compagnon -->…<!-- /compagnon -->`
  (index.html) ; module Événements : `compagnonOn` (`web/events/src/lib/features.ts`) ; iOS : `GET /api/features`.
- Tout nouvel élément de Zicou (route, onglet, carte, réglage, notification, écran natif) passe par ce drapeau.
- Jamais allumé en production ni migré en production avant que l'admin dise « le projet Compagnon est complet ».
- Ne jamais changer l'icône de Vendredi Party.
- Tests : `tests/test_compagnon_flag.py`, `tests/e2e/test_compagnon_off.py` (les autres tests tournent allumé).
- Nom : toujours « Zicou » dans un texte visible (web, module Événements, iOS, Apple TV, admin, notifications, réglages,
  CGU, erreurs de la base), JAMAIS « Compagnon » ; les identifiants de code (pet, compagnon_enabled…) restent.
- Pièces : être présent ou répondre à un événement ne rapporte rien automatiquement. Les pièces d'un événement passent
  par le droit `zicou.event_coins` (page des cadeaux Zicou de l'événement, 5 à 100 par présent, versées une fois par la
  base, journal `pet_event_coin_grants`, migration 20261105090000).

## Tests
`python -m pytest -q --ignore=tests/e2e` avant tout commit.
