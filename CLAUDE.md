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

## Page Party ↔ module Événements (iframe)
- Une page ouverte de l'extérieur (app iPhone : `PartyEvents.open('/events/event/<id>/invite')`) doit mettre à jour
  `frameAt` (app/static/index.html) : sinon, au « prêt » du module, la page le renvoie à son ancienne page (bug de prod du
  06.11 : l'étape 2 « Qui est invité » se refermait). Test : `test_iphone_app_opens_step_two_in_the_party_page_and_it_stays_open`.
  Essai réel simulateur + base de TEST : `ios/PartyUITests/AIEventRealE2EUITests.swift` (ignoré sans son environnement).
  En configuration Release (comme l'App Store) : `xcodebuild test -configuration Release ENABLE_TESTABILITY=YES
  PARTY_SWIFT_CONDITIONS=E2E_HOOKS PARTY_BASE_URL=http://127.0.0.1:<port>` ; `E2E_HOOKS` ne va jamais dans project.yml
  ni dans un workflow (test `test_recette_hooks_never_reach_the_app_store_build`). Brouillon de recette : `"notify": false`
  (la base de TEST contient de vrais comptes).
- Étape 2 « Qui est invité » : un toucher sur « qui voit » publie (ou envoie pour validation) ; on invite APRÈS, l'événement
  en ligne. Jamais de lien « disponible à la publication ».

## Module Événements (web/events) — défilement tactile
- Jamais de règle `overscroll-behavior` ni `touch-action` sur `*` (web/events/scripts/postbuild.mjs). Sous Android,
  Chrome traite chaque carte en `overflow: hidden` comme un conteneur de défilement : avec
  `overscroll-behavior: contain`, le doigt posé sur une carte ne faisait plus défiler la liste (retour #10).
  `touch-action: pan-x pan-y` sur `*` ne corrige rien et bloque le zoom à deux doigts.
- Test réel : `test_android_finger_on_an_event_card_scrolls_the_list` (geste tactile Chrome, départ sur une carte).
  Tout bug de défilement / toucher doit d'abord être reproduit par un test de ce type avant d'être corrigé.
- Feuilles et fenêtres (Inviter, QR, Signaler, billet, payer, CGU, toute nouvelle) : `components/SheetGesture.tsx` —
  `useSheetDrag` (glisser vers le bas depuis la poignée / le titre, ou le contenu tout en haut, ferme), ✕ `SheetClose`
  en haut à droite, fond `SheetBackdrop` qui ferme, marge `useSheetTop` (jamais sous la barre d'état d'iOS, qui garde
  les touchers : la poignée ne s'attrapait pas). Une feuille ouverte prévient Party (`party-events:sheet`) qui cache la
  pastille de Zicou (elle couvrait le ✕, vidéo de l'admin du 06.11). Tests : `tests/test_sheets_touch_scroll_browser.py`,
  `ios/PartyUITests/InviteSheetScrollUITests.swift` (simulateur + base de TEST).
- Billets QR : option par événement (`events.tickets_enabled`, éteinte par défaut) activée par l'organisateur lui-même ;
  l'IA de création / modification (app/ai_events.py, ai_event_edit.py) ne l'active JAMAIS (hors de son schéma) ; un QR
  n'existe que si l'option est active ET le billet remis (`issue_event_ticket`, ou place payée confirmée).
- « Créer avec l'IA » en étapes (06.11) : 1 « La soirée » (l'IA ne demande JAMAIS qui inviter ni qui voit
  l'événement ; ce qui est dit spontanément n'est qu'un pré-réglage), récapitulatif + « C'est juste ? » ;
  2 « Qui est invité » (web `/event/<id>/invite`, brouillon public + lien en attendant) : le bandeau / choix « qui voit »
  (public + lien public par défaut, en surbrillance) est ICI, puis les invités, puis Publier ; 3 la fiche s'ouvre.
  Jamais de bandeau ni de choix de visibilité à l'étape 1. Accord IA, filtre de modération et droits inchangés.
- Lien d'invitation « Plusieurs » (11.11) : sans limite de places par défaut (∞ = 10000 en base, `create_event_invite(e, 0)`),
  − / + pour 50 à 2 places ; valable jusqu'au lendemain de l'événement (suit sa date, sondage sans date : 1 an), jamais de
  choix de durée à l'écran ; l'organisateur l'arrête quand il veut (« Arrêter », `revoke_invite_link`).
  Tests : `tests/supabase_live/test_lien_sans_limite_live.py`, `tests/test_invitations_v2_browser.py`.
- Menu de partage commun (avis 83ebee37aa0f, 11.11) : chaque invité a la carte « Invités » de l'organisateur avec les
  CHIFFRES seulement (jamais un nom, ni relance ni retrait), crée ses propres liens nommés (20 en attente au plus), les recopie
  et les arrête (`event_guest_list` vue `guest`, `create_event_invite`, `revoke_invite_link`, migration 20261111120000).
  Tout lien se nomme (« Plusieurs » compris) et se recopie (« Copier ») : le même lien, jamais un nouveau.
  Tests : `tests/supabase_live/test_partage_commun_live.py`, `tests/test_partage_commun_browser.py`.
- Accord de l'organisateur (12.11) : sans lien public (sur invitation, groupe, Membres Vendredi Party), la personne venue par
  le lien d'un INVITÉ attend l'accord (`event_join_requests`, `accept_invite` → `pending`, « À accepter » dans la carte
  Invités, `decide_join_request`) ; elle ne voit ni la fiche ni l'adresse avant. Seuls l'organisateur et les co-organisateurs
  (et `events.manage_all`) font entrer directement (`private.needs_approval`). Leur lien vaut accord, même après un refus (refus par erreur). Événement public : inchangé.
  Tests : `tests/supabase_live/test_invitation_accord_live.py`, `tests/test_invitation_accord_browser.py`.
- Agenda (11.11) : partout la même méthode, le calendrier abonné « Vendredi Party » de la personne (un lien par personne,
  `calendar_feed_token(e, add)` / `calendar_feed`, `/api/calendar-feed/<jeton>.ics`) : ajouter un événement (bouton
  « Ajouter à mon agenda », « Valider mes dates ») l'y met, et l'agenda suit tout changement sans rouvrir Party. Ouvrir une
  fiche n'ajoute rien (add = false). Une fois l'agenda activé, chaque réponse Présent / Peut-être (ou vote Oui / Si besoin)
  y met l'événement toute seule (`private.feed_includes`), Pas présent l'en retire ; titre « [Peut-être] » / « [Si besoin] ». Fichier .ics ponctuel / calendrier natif de l'app seulement en secours.
  Tests : `tests/test_calendar_feed.py`, `tests/test_calendar_poll_dates.py`, `tests/supabase_live/test_agenda_abonnement_live.py`.
- Groupes : on ne réserve un événement qu'aux groupes dont on FAIT PARTIE, « Membres Vendredi Party » compris
  (écrans : `choosableGroups` / `mayUseVip`, assistant IA ; base : migration 20261106090000, triggers
  `guard_event_group` et `guard_event_vip_visibility`). Un admin (events.manage_all) garde tous les groupes.
- Public par défaut (formulaire et IA) ; un événement public ne prévient JAMAIS personne à sa publication (base : `events_public_silent`, 20261106200000).

## Inscription des invités (avis 39f148377a8f, 10.11.2026) — profil complet, parcours normal
- Toute personne invitée (lien d'invitation, lien public « Partager », groupe) passe par la connexion NORMALE de l'app
  (`/sign-in` : pays, numéro, code SMS), puis « Faisons connaissance » (`IdentityForm` : prénom, nom, surnom ; photo
  facultative ; CGU au premier surnom), puis revient à l'invitation (intention gardée, `lib/inviteIntent.ts`, 10 min).
  Plus jamais de compte « au prénom seul » : `accept_invite` refuse `profile_required` (migration 20261110090000).
- Sondage de dates : on vote les dates (jamais « Présent » sur la page publique d'un sondage) ; la carte compte les
  votants (`voters`). La purge des invités légers compte les votes (bug du paintball : votants effacés avec leurs votes).
- La base refuse toute réponse (`rsvps`) ou vote (`date_votes`) CRÉÉ pour soi avec un profil incomplet (`profile_required`,
  déclencheurs `rsvps_identity` / `date_votes_identity`, migration 20261110100000) ; l'organisateur note toujours une présence
  (`set_rsvp_for`). Photo jamais exigée : « vivement conseillée » (web et iOS, `test_photo_facultative.py`).
- Recette réelle du 10.11 (migration 20261110100100) : un lien « Après l'événement » suit la date fixée (`follows_event`) ;
  supprimer l'événement supprime ses liens ; un votant retiré du groupe garde le sondage ; on quitte soi-même un groupe
  (jamais Membres Vendredi Party). Dans Party installée (app iPhone, écran d'accueil), rien ne propose d'installer Party
  (`insideInstalledApp`). Lien « Partager » rechargé : l'adresse garde `?tab=events&event=<id>` (jamais un billet).
  Tests : `test_invitations_recette_live.py`, `test_reponse_profil_complet_live.py`, `test_invitations_recette_browser.py`,
  `test_shared_link_reload_browser.py`.
- Tests : `tests/supabase_live/test_inscription_complete_live.py`, `test_inscription_complete_browser_live.py` (vrai
  navigateur ; base de TEST ou copie locale via PARTY_TEST_SUPABASE_URL / PARTY_TEST_DB_CONTAINER / PARTY_TEST_EVENTS_DIST).

## Jeux — requêtes simultanées
- Tous les téléphones interrogent la partie chaque seconde, en parallèle. Toute lecture-modification d'une partie
  (action, avancée automatique type `quiz.tick`, image des jeux temps réel) passe par le verrou unique
  `app/game_lock.py` (`GAMES_LOCK` dans main.py) ; `store.save` le prend aussi. Ne jamais créer de verrou par jeu
  ni modifier une partie hors de ce verrou (bug corrigé : une question de quiz ratée retirait toutes les vies,
  la main de Blackjack était distribuée plusieurs fois).
- Test : `tests/test_game_concurrency.py` (requêtes simultanées, une seule étape appliquée).
- Tout prénom ou texte saisi par un joueur passe par `esc()` avant d'entrer dans du HTML, attributs compris
  (test : `tests/e2e/test_names_escaped.py`).

## Annonces aux groupes (décision du 06.11.2026, migration 20261106220000)
- Un événement public ne prévient jamais personne. Un événement de groupe (groupe choisi ou Membres Vendredi Party) ne
  prévient le groupe que par « Prévenir le groupe » (`events.announce_group`, éteint par défaut) : demande à valider
  (`event_announcements` : créateur / admins / organisateurs du groupe, droit `groups.announce_approve`, première réponse
  gagne, d'office après 48 h par pg_cron), ou envoi direct si l'organisateur est valideur ou le groupe « libre ».
- Jamais de notification à un groupe hors de `private.send_announcement` (ni `private_invite` à un membre venu par le
  groupe, ni « Nouvel événement » aux Membres VIP) : `private.should_invite` le garantit ; l'IA n'allume jamais
  `announce_group`. Tests : `tests/supabase_live/test_annonces_groupe_live.py`, banc des bots phase `annonces`.

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
- Les CGU sont exigées en prod (terms_enforced) : tout nouveau chemin qui publie du contenu doit gérer terms_required (feuille CGU puis nouvel essai). Serveur : `db_refusal` / `refusal` lèvent `TermsRequired` → 403 `{"code": "terms_required"}` ; iOS : `PartyAPIError.termsRequired` + `TermsAcceptSheet` ; web : `useTermsGate().ensure()`. Tests : `tests/test_terms_required.py`, `tests/supabase_live/test_terms_required_live.py`, `AIEventTermsTests`.
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
  Distribution (décision de l'admin du 09.11.2026) : les 26 pays francophones de l'App Store (Suisse, France, Belgique,
  Luxembourg, Canada, Afrique francophone, Maghreb, Liban, Maurice, Seychelles, Vanuatu) ; tout autre pays ou une app
  Android publique → nouvelle revue. UE (France, Belgique, Luxembourg) : statut DSA déclaré et RGPD dans la politique.

## Zicou : bêta seulement (décision de l'admin, 04.11.2026)
- Zicou est ÉTEINT hors site de test par `compagnon_enabled()` (`app/features.py` : `COMPAGNON_ENABLED`
  "1"/"0", sinon allumé seulement si l'adresse publique est `partytest.bobycharbon.ch`). Éteint : `/api/pet/*`,
  `/api/tv/zicou`, `/zicou/*`, `/static/pet/*` → 404 « Zicou arrive bientôt. », aucune réaction calculée
  (`zicou_react`), la page reçoit `data-compagnon="off"` et perd ses blocs `<!-- compagnon -->…<!-- /compagnon -->`
  (index.html) ; module Événements : `compagnonOn` (`web/events/src/lib/features.ts`) ; iOS : `GET /api/features`.
- Tout nouvel élément de Zicou (route, onglet, carte, réglage, notification, écran natif) passe par ce drapeau.
- Bulle de Zicou (avis 3cd6d282745b) : dans l'app iOS BETA, elle est native (`ios/Party/Pet/ZicouBubble.swift`,
  déplaçable vers 6 emplacements, Réglages › « Bulle de Zicou ») ; la page la décrit (`PartyNative.zicou.update`,
  pet/zicou-home.js) et cache sa pastille (`html.native-zicou`). Navigateur : `zc_bubble_off`. Tests :
  `tests/e2e/test_zicou_bubble.py`, `ZicouBubbleTests`, `ZicouBubbleUITests` (serveur local, TEST_RUNNER_PARTY_ZICOU_UI=1).
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

### Avant toute mise en production : recette RÉELLE (règle de l'admin, 06.11.2026)
Des tests avec des faux (Supabase simulé, écrans isolés) ne suffisent pas : l'assistant IA « testé » a cassé en prod
(CGU exigées en prod seulement, invitations v2 allumées en prod). Avant tout merge dans `main` et tout changement de
réglage de prod :
- Parcourir pour de vrai chaque parcours touché, de bout en bout, comme un utilisateur : app iPhone dans le simulateur
  (configuration Release, comme l'App Store) + serveur local branché sur la base TEST, et le site web dans un vrai
  navigateur (Playwright), avec des captures de chaque étape.
- Avec EXACTEMENT les réglages de la prod : drapeaux (`/api/features` de prod : compagnon, discussions, invites_v2…),
  `terms_enforced`, rôles/droits du compte (admin ET simple membre ET Guest), données réalistes.
- Changer un réglage de prod (drapeau, CGU, droit) = refaire la recette des parcours qu'il touche AVANT de le changer.
- Le rapport dit ce qui a été testé pour de vrai et ce qui ne l'a été qu'avec des faux. Pas de « prêt » sans recette.
- La production n'est pas un banc d'essai : en cas de doute, ça reste sur develop / le site de test.
