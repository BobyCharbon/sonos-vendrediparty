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

## iPhone Duo (pliable d'Apple, iOS 27.1, 18.11) — règles à garder
- Compilée avec un SDK < iOS 27.1, l'app tourne en mode compatibilité sur le Duo (petit iPhone entouré de noir). Le job
  iPhone de `ios-testflight.yml` tourne sur l'image GitHub `xcode-27`, Xcode épinglé (≥ 27.1) ; jamais `macos-15` ni
  `latest-stable` (test `test_testflight_builds_the_iphone_app_with_the_ios_27_1_sdk`). Cible minimale : iOS 16 ; toute API
  du Duo sous `#available(iOS 27.1, *)`. Cycle de vie par scènes (SwiftUI `App`) : exigé par les derniers SDK, à garder.
- Barre d'onglets : sur les autres iPhone, `NativeTabBar` (UITabBar en bas) inchangée. Quand le système veut une barre
  verticale (`traitCollection.verticalBarEdge`, lue par `VerticalBarEdgeReader` : écran extérieur, intérieur en paysage),
  `SystemTabBar` la remplace : un vrai `UITabBarController` aux écrans vides et transparents, par-dessus la page, qui ne
  prend que les touchers de sa bande (une UITabBar posée à la main ne passe JAMAIS à la verticale). Même pont
  (`PartyNative.tabs` / `PartyTabs.select`), la page décide toujours. La vue web ne change jamais de place dans l'arbre
  SwiftUI (sinon elle est recréée et la page rechargée au pliage).
- Éléments flottants natifs (« Réglages », « Vue invité », bulle de Zicou, `SecretCardsView`, `PartyNoticeView`) : zones
  sûres de CHAQUE côté (colonne de la barre d'état à droite sur l'écran extérieur), jamais seulement le haut ; jamais sur
  le pli (cartes de la Pyramide à droite du pli en livre, bulle au-dessus du pli posé en portable).
- Pont du pli (`ios/Party/Fold.swift`) : WebKit ne voit pas le pli. L'app pose sur `<html>` `data-posture`
  (closed / flat / book / laptop / half) et `--fold-x/-y/-width/-height` (px, seulement si un pli traverse la page),
  `window.PartyFold` et l'événement `party-fold` ; page principale seulement, rien sur un iPhone sans charnière. Mise en
  page d'après le pli (régions réservées), jamais d'après l'angle de la charnière (Apple : entrée de jeu seulement).
  `ios-app.js` / `html.native-tabs` inchangés.
- « Retour » en haut de la barre verticale (comme Safari, demande du 19.11) : chaque écran vide de `SystemTabBar` est
  dans un `UINavigationController` (son bouton de gauche monte dans la barre). Affiché seulement s'il y a un écran
  derrière : la page le dit (`state.back` de native-tabs.js = `PartyBack.can()` : pile `Nav`, ou module). Dans le module,
  il TOUCHE le bouton de l'écran, comme le doigt en haut à gauche (`lib/shellBack.ts` : bouton visible nommé Retour… /
  Annuler / Fermer, le plus haut à gauche ; feuille ouverte : son « Fermer » ; signaux `party-events:back` /
  `party-shell:back`) ; jamais `router.back()` à l'aveugle (fiche ouverte de l'extérieur : pas d'historique, bouton
  sans effet, retour de l'admin du 19.11). Sinon « ‹ Réglages » (`pageDetail`). Test réel : `test_retour_duo_browser_live.py`.
  Écrans natifs (Discussions, Musique) : leur propre retour. Tests : `testBackSitsAtTheTopOfTheVerticalBar…`,
  `test_back_of_the_duo_vertical_bar_follows_the_page_stack`.
- Écran ≥ 900 px dans l'app (Duo déplié) : la page ne garde pas la place de son rail web (caché), et le panneau des
  Événements / Discussions / Réglages prend toute la largeur (style.css, `html.native-tabs`, retour du 19.11 ; test
  `test_wide_screen_in_the_app_keeps_no_room_for_the_hidden_web_rail`).
- Portrait gardé dans project.yml (iPhone classiques) ; l'écran intérieur du Duo l'ignore : tout écran doit suivre toute
  taille, et le pliage / dépliage garder l'état (page, brouillon, partie).
- Tests : `PartyTests/DuoTests.swift` ; `PartyUITests/DuoTabBarUITests.swift` (simulateur « iPhone Duo » :
  `TEST_RUNNER_PARTY_DUO_UI=1 TEST_RUNNER_PARTY_DUO_VERTICAL=1` ; autre iPhone : sans `…_VERTICAL`). La charnière ne se
  règle qu'à la main dans Device Hub (aucune commande `simctl`) : écran intérieur, livre et portable sur le vrai Duo.

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
- Relances (19.11, migration 20261119140000) : carte Invités repliée → « ↻ Relancer les N qui n'ont pas répondu » → confirmation
  → bilan (`NudgeSheet`) : prévenus par Party (`nudge_invitees`, une par jour, organisateurs et co-organisateurs) ou lien à
  partager (partage, WhatsApp, Messages, Copier, TOUJOURS appelés dans le toucher : Safari / l'app iPhone refusent
  navigator.share après une attente du réseau ; noté relancé une fois le partage parti). `private.has_app` = iPhone (APNs)
  OU webapp (Web Push, session ouverte) + notifications et « Invitations » allumées ; bloqué : ni notification ni partage ;
  terminé / date limite passée : refus. Texte « Invitation de X · Tu viens ? Réponds en un geste. ». Tests :
  `tests/supabase_live/test_relances_live.py` (push calculé par le code de send-push / send-web-push),
  `test_relances_browser_live.py`, `tests/test_relances_browser.py`.
- Agenda (11.11) : partout la même méthode, le calendrier abonné « Vendredi Party » de la personne (un lien par personne,
  `calendar_feed_token(e, add)` / `calendar_feed`, `/api/calendar-feed/<jeton>.ics`) : ajouter un événement (bouton
  « Ajouter à mon agenda », « Valider mes dates ») l'y met, et l'agenda suit tout changement sans rouvrir Party. Ouvrir une
  fiche n'ajoute rien (add = false). Une fois l'agenda activé, chaque réponse Présent / Peut-être (ou vote Oui / Si besoin)
  y met l'événement toute seule (`private.feed_includes`), Pas présent l'en retire ; titre « [Peut-être] » / « [Si besoin] ». Fichier .ics ponctuel / calendrier natif de l'app seulement en secours.
  Choix de l'agenda (avis du 19.11) : hors iPhone, jamais Google d'office (`AgendaChoices` : Apple, Google, Outlook, « Samsung
  ou autre » = lien copié + ICSx⁵, « Juste cet événement ») ; « ✓ Dans ton agenda » veut seulement dire « lu par un agenda » :
  « Pas dans ton agenda ? Le rajouter » et Réglages › Agenda Vendredi Party (`/settings/calendar`, `calendar_feed_link`).
  Tests : `tests/test_calendar_feed.py`, `tests/test_calendar_poll_dates.py`, `tests/supabase_live/test_agenda_abonnement_live.py`.
- Groupes : on ne réserve un événement qu'aux groupes dont on FAIT PARTIE, « Membres Vendredi Party » compris
  (écrans : `choosableGroups` / `mayUseVip`, assistant IA ; base : migration 20261106090000, triggers
  `guard_event_group` et `guard_event_vip_visibility`). Un admin (events.manage_all) garde tous les groupes.
- Étape 2 « Qui est invité », carte « 👥 Des groupes » (avis 8eb031acd60f, 13.11) : on coche les Membres Vendredi Party et/ou
  un ou plusieurs groupes, puis « Publier pour … » (jamais de publication au premier toucher pour les groupes) ; un seul
  « Prévenir » pour tous les groupes cochés. Public et « Sur invitation » publient toujours d'un toucher.
- Paiement (maquette validée le 15.11, migration 20261115120000) : l'organisateur choisit « On me paie » (défaut, lien
  facultatif : Revolut…), « Paiement en ligne » (lien https obligatoire : billetterie) ou « Sur place » (`events.payment_mode`,
  `payment_url`). « On me paie » : la personne note « J'ai payé », l'organisateur confirme « Reçu ✓ » (jamais payé sur sa
  seule parole : une place payée remet le billet QR). En ligne (demande du 19.11, migration 20261119180000) : « J'ai payé »
  se note et compte sans « Reçu ✓ » (« ✓ Payé en ligne », liste « Ont payé » chez l'organisateur), mais ne passe jamais la
  place en `paid` (pas de billet QR sur sa parole). Sur place : aucun « J'ai payé » ni « Reçu ✓ » (`declare_ticket_payment`
  refuse) ; l'entrée peut cocher « payé ». Un organisateur qui encaisse sur son site : « On me paie » + son lien. L'IA ne
  choisit jamais le mode. Le lien de l'événement remplace celui du même service dans le profil (un seul « Payer avec Revolut »).
  Tests : `tests/supabase_live/test_paiement_mode_live.py`, `test_paiement_mode_browser_live.py` (recette réelle),
  `test_event_tickets_browser.py`.
  « A payé ✓ » (20.11) : dans la carte « Paiements » de la fiche, l'organisateur coche lui-même qui a payé (sur le site
  ou à lui, sans l'avoir noté) et peut « Annuler » (`set_ticket_paid`, « On me paie » et en ligne) ; l'invité ne se note
  jamais payé lui-même. Tests : `test_the_organizer_marks_a_guest_as_paid_from_the_event`,
  `test_the_organizer_marks_paid_himself_and_a_guest_cannot`.
  « Paiement ouvert » (16.11, migration 20261116130000, `events.payment_open`, allumé par défaut) : l'organisateur prépare
  tout puis l'allume ; éteint, les invités voient « ⏳ paiement bientôt possible » sans lien ni bouton, `event_pay_info`
  ne donne aucun lien, `declare_ticket_payment` refuse « J'ai payé ». Tests : `test_paiement_mode_live.py`,
  `test_event_tickets_browser.py`, `test_event_organizer_browser.py`.
  L'allumer prévient les « Présent » pas encore payés (« 💳 Le paiement est ouvert », texte générique : place, billet,
  réservation ; seulement si l'organisateur garde « Prévenir les participants à l'ouverture », `events.payment_open_notify`,
  allumé par défaut ; interrupteur `event_changed`, une fois par personne, jamais « Sur place » ; migration 20261117135000,
  `test_paiement_ouvert_notification_live.py`).
  Tout lien de paiement est un vrai lien (`Button href` → `<a target="_blank">`), jamais `Linking.openURL` / `window.open`
  depuis un toucher : Safari en navigation privée l'ignorait (avis du 16.11). La fiche reste ouverte derrière.
- Bar : devise du bar par événement, francs (défaut) ou euros (« Options » › Devise, `event_bars.currency`,
  `bar_set_currency`, migration 20261116090000), choisie avant les premières commandes payantes ; montants affichés
  (`barChf` / `barUnit`), messages de la base (`private.bar_chf(n, e)`) et carte Wallet suivent. Tests :
  `test_bar_options_live.py`, `test_bar_options_browser.py`, `test_bar_wallet.py`.
  Carte Wallet du bar : chaque geste qui change le solde ou « À servir » (commande, service, annulation, correction,
  remboursement confirmé, réglages) prévient l'iPhone aussitôt (`walletAfter` dans lib/bar.ts → `/api/wallet/notify`) ;
  la base redate le pass, mais sans ce signal Cartes gardait l'ancien solde (bug du 16.11).
  Récapitulatif de la soirée (organisateurs, 16.11, migration 20261116100000) : « 📄 Récapitulatif de la soirée » dans
  « Gérer le bar » → qui a pris quoi (articles, quantités), montant, remboursé, reste dû ; par article ; barmans ; tris
  (doit le plus, a pris le plus, plus commandé…) ; en direct toute la soirée ; « Exporter en PDF » (lib/pdf.ts, écrit à la
  main, aucune bibliothèque : partagé sur téléphone, téléchargé sinon). Tests : `test_bar_recap_live.py`,
  `test_bar_options_browser.py`. Bar et Discussions allumés en prod le 16.11.2026 (BAR_ENABLED / DISCUSSIONS_ENABLED dans compose.yaml de la stack) ; migrations du bar appliquées.
  Notification « verre servi » (16.11, migration 20261116120000) : titre « 🍹 Barman : −2 Vodka Red Bull », texte « Servi par
  … · 9 CHF · à rembourser : … · soirée » : se comprend sans l'ouvrir ; coupable (« Bar : verres servis », web et iPhone).
- Temps réel de l'événement (avis du 16.11, migration 20261116110000) : bar, billets, paiements et covoiturage passent par
  des fonctions, invisibles du temps réel Supabase. Chaque changement écrit un signal `live_pings` (personne, événement,
  sans contenu ; RLS : on ne lit que les siens) pour chaque personne concernée ; `useLivePing(eventId, reload)` (lib/data.ts)
  relit l'écran aussitôt (fiche, billet, tous les écrans du bar). Toute nouvelle table « par fonctions » visible sur la fiche
  ou dans le bar = un déclencheur `live_ping`. La relecture régulière reste en secours. Test : verre servi visible chez
  l'invité en ~1 s (`test_a_served_glass_shows_on_the_guest_screen_without_reloading`, `test_bar_recap_live.py`).
  TOUT l'événement en temps réel (avis du 16.11, migration 20261116140000) : chaque table de l'événement a le déclencheur
  `event_changed` → signal sans contenu sur le canal public `event:<id>` (`private.party_signal`, une fois par transaction),
  suppressions comprises (le temps réel par tables ne voit pas une suppression filtrée : vote ou « J'amène » retiré). Liste :
  canal `events` ; rôle / statut / groupes d'une personne : `user:<id>` (`access_changed`, droits relus par auth.tsx) ;
  droits des rôles : `access`. Côté web : `useSignal` / `useLivePing` (lib/data.ts). Toute nouvelle table de l'événement
  = ajoutée à la liste de `event_changed`. Test réel : `tests/supabase_live/test_temps_reel_tout_browser_live.py` (~0,9 s).
- Covoiturage (avis 34d5c07f2e56, 13.11, migration 20261113090000) : option de l'organisateur (`events.carpool_enabled`,
  éteinte par défaut, jamais allumée par l'IA) ; seuls les participants (Présent / Peut-être) et les organisateurs y prennent
  part, tout par les fonctions `carpool*` (table sans accès direct, places comptées sous verrou, ville filtrée comme un nom,
  CGU) ; « Pas présent » fait quitter le covoiturage. Carte `CarpoolCard`. Aucun argent ni partage de frais ici.
  Tests : `tests/supabase_live/test_covoiturage_live.py`, `test_covoiturage_browser_live.py`, `tests/test_covoiturage_browser.py`.
- Date fixée (bouton « Fixer » ou formulaire) : les créneaux du sondage et leurs votes ne sont JAMAIS effacés (cachés ;
  repasser en « Date à définir » les retrouve). Le formulaire les effaçait : votes du paintball perdus (prod, 13.11).
  Test : `test_editing_a_fixed_date_keeps_the_poll_dates_and_their_votes`. Ces créneaux cachés ne comptent nulle part en date
  fixe : agenda (votes pris seulement en sondage, migration 20261115230000), IA de modification (`draft_of`). Recette réelle :
  `tests/supabase_live/test_sondage_date_fixee_browser_live.py`.
- Événements récurrents (demande du 16.11, migration 20261116170000) : « Répéter » sous la date (chaque jour, semaine,
  2 semaines, mois, année ; « Jusqu'au » facultatif), `set_event_recurrence` (organisateurs de l'événement ET droit `events.recurring` : Admin, Co-admin, Organisateur au départ,
  réglable dans Rôles et droits ; l'arrêter : tout organisateur ; la règle part de CET événement).
  UNE seule date à la fois : `private.spawn_series` (pg_cron, 5 min) crée la suivante seulement quand la précédente est
  terminée (sa fin, sinon le lendemain 0 h), en recopiant la DERNIÈRE (options, groupes, invités un à un, co-organisateurs,
  étiquettes, « qui amène quoi » de l'organisateur ; jamais réponses, votes, messages, billets, bar, covoiturage, liens) ;
  publiée comme un événement neuf (invités un à un prévenus, public silencieux, jamais d'annonce au groupe). Mois comptés
  depuis la 1re date, heure de Suisse. Fiche « 🔁 … · la suivante s'affiche après celle-ci », carte 🔁.
  Tests : `tests/supabase_live/test_evenements_recurrents_live.py`, `test_a_weekly_event_is_set_from_the_form…`.
- Discussion de l'événement façon WhatsApp (demande du 16.11, migration 20261116180000) : app iPhone = écran NATIF
  (`ConversationView`, le même que Discussions : `ChatsStore(forEvents: true)`, routes `/api/account/event-chat/*`,
  app/event_chats.py) ouvert par `PartyNative.chat.openEvent(id)` (fiche › Discussion, page `/event/<id>/chat`, notification
  `?tab=events&event=<id>&chat=1` : send-push / send-web-push) ; web = `GroupChat` mode `event`. Séparateurs de jours,
  séries par personne, heure dans la bulle, @citations en couleur, citation → message d'origine, bouton ↓, bandeau des
  annonces et épinglés (1/N), annonce en carte, photos et vocaux (dossier `<événement>/` de chat-photos).
  @toutlemonde (invités + participants) et @present (Présent / Peut-être) : organisation de l'événement et admins /
  co-admins seulement (`private.event_chat_staff`) ; annonce = 📣 ou @annonce (épinglée, notifiée à tous). La base décide
  d'après le texte (`guard_message_change`), l'app ne fait que proposer. Les invités sans réponse ne sont listés qu'à
  l'organisation (`event_chat_people`). Temps réel natif : signal `event:<id>`. Tests : `test_discussion_evenement_live.py`,
  `test_discussion_evenement_browser_live.py`, `tests/test_event_chats_native.py`, `tests/test_event_chat_browser.py`,
  `EventChatTests`, recette `RecetteDiscussionUITests` (Release + serveur local + base de TEST).
- Discussion d'un événement RÉSERVÉE à ceux qui viennent (décision de l'admin du 19.11, migration 20261119120000) : Présent /
  Peut-être et l'organisation (créateur, co-organisateurs, admins : `private.event_chat_member`, `event_chat_open`) la voient
  dans Discussions, la lisent (RLS « lire messages »), y écrivent, la trouvent et en reçoivent les notifications ; pas répondu
  ou Absent : rien (fiche : « réponds Présent ou Peut-être pour la rejoindre », `CHAT_FOR_GUESTS` web et serveur). @toutlemonde
  et les annonces ne touchent donc plus les invités sans réponse. Recherche des Discussions : « Événements »
  (`chat_event_search`, mes événements même sans message) et « Messages » (`chat_search`). Tests :
  `tests/supabase_live/test_discussion_evenement_presents_live.py`, `test_discussions_recherche_evenements_live.py`.
- Sondages de la fiche (19.11, migration 20261119170000) : juste sous « Tu viens ? » ; sur un événement à date fixe, on ne
  vote qu'après Présent ou Peut-être (organisation et admins toujours : `private.event_chat_member`, déclencheur
  `poll_votes_presence`, refus `present_required`) ; sinon « Réponds Présent ou Peut-être pour voter. ». Sondage de dates :
  inchangé. Tests : `tests/supabase_live/test_sondage_presents_live.py`, `test_a_poll_asks_to_answer_present_or_maybe_before_voting`.
- Réponses (20.11, migration 20261120090000) : l'organisateur n'est prévenu que de « vient » / « peut-être » (réponses
  regroupées `flush_rsvp_digests`, lien d'invitation `link_join`) ; « ne vient pas » ne notifie jamais. Tests :
  `test_rsvp_digest_live.py`, `test_lien_invitation_reponse_live.py`.
- Public par défaut (formulaire et IA) ; un événement public ne prévient JAMAIS personne à sa publication (base : `events_public_silent`, 20261106200000).
- Modifier un événement (avis 27b5eea5121c, 20.11, migration 20261120200000) : notification seulement quand le LIEU change
  (nom, sinon adresse ; espaces ignorés), la DATE de début d'une date fixe (à la minute), ou le retour au sondage. Titre = le
  nom de l'événement ; texte = une phrase par changement (demande de l'admin) : « La date a été modifiée au 05.12 à 20:30. »,
  « Le nouveau lieu de l'événement est Salle B. ». Description, titre, prix, heure de fin, lien du lieu : rien.
  La date est gardée exprès (venir le mauvais jour). Les sondages gardent « Nouveau sondage » (notify_poll). Test :
  `test_only_place_date_or_a_new_vote_tell_participants_of_a_change` (test_notifications_recette_live.py).
- Activité (la cloche, avis 85cd4af01e3e) : glisser une notification NON lue de droite à gauche (≥ 80 px) la marque lue
  sans l'ouvrir ; un toucher l'ouvre toujours (et la marque lue, comme « Tout marquer lu » pour VoiceOver : react-native-web
  ignore accessibilityActions). Test réel au doigt :
  `test_swiping_a_notification_left_marks_it_read_without_opening_it`.
- Photo de profil en grand (avis 163be6ce5df6) : toucher la photo du mini-profil ou de la fiche l'ouvre en plein écran, le
  fichier enregistré (1024 px), jamais une miniature ; zoom (iPhone : pincer / double toucher ; web : double toucher puis
  glisser pour se déplacer), glisser vers le bas, toucher hors de la photo ou ✕ ferme.
  Web `PhotoTap` (components/ProfilePhotoViewer.tsx), iPhone `opensProfilePhoto` (Chats/People/ProfilePhotoViewer.swift).
- Discussions, ordre des épinglées (avis e75a1d5af3ee, migration 20261120200100) : `reorder_chat_pins` réécrit les pinned_at
  de MES épingles (la première = à gauche) ; iPhone : « Réorganiser les épinglées » (appui long d'une tuile ou « … »,
  `ChatPinOrderSheet`), web : « Déplacer à gauche / à droite » (appui long). Tests : `test_pinned_chats_follow_the_order_i_choose`,
  `test_pinned_chats_move_left_and_right_and_the_order_stays`.
- iPhone, tuiles épinglées : JAMAIS de `.contextMenu` ni de `Menu` sur une tuile. Toutes les tuiles sont dans UNE ligne de
  la `List`, où iOS ne garde qu'un menu contextuel (l'appui long ouvrait le menu de la PREMIÈRE tuile : « Désépingler »
  touchait la mauvaise discussion) ; un `Menu` s'ouvrait sous le doigt et se choisissait en le levant. Appui long =
  `confirmationDialog` des actions de CETTE tuile (`tileActions`). Recette : `RecetteAvis2011UITests` (Release + TEST).
- Tout ✕ en `position: absolute` dans une feuille web a `zIndex` : le ✕ du menu d'une discussion était recouvert par la
  ligne du nom et ne fermait rien (recette du 20.11).

## Avis du 13.11.2026 (à garder)
- Ouverture de l'app (web, iPhone, Android plus tard) : toujours l'onglet Événements (`startTab()`, index.html), sauf au
  milieu d'une partie (dernier onglet Jeux + partie en cours). Les tests qui veulent Musique la touchent eux-mêmes.
- « Nouveau compte » (migration 20261113100000) : ceux qui ont `members.approve` sont prévenus quand un profil devient
  complet, une seule fois ; interrupteur `notification_prefs.member_signups` (web + iPhone, section « Comptes et
  modération »), respecté par `web_push_allowed`. Tests : `tests/supabase_live/test_nouveau_compte_live.py`.
- Bandeau « Ne rate rien de cet événement » en haut de la fiche (`NotifyBanner`) tant que les notifications de CET appareil
  sont éteintes ; app iPhone : `PartyNative.push.enable()` (demande d'iOS + abonnement ; refusées : Réglages d'iOS).
- Groupes : « Inviter avec un lien » (lien réutilisable du groupe) en haut de son groupe, web et iPhone ; le groupe s'ouvre
  juste après sa création. Qui ouvre le lien rejoint directement (connexion SMS et profil d'abord).
- Recette simulateur de ces avis : `ios/PartyUITests/RecetteAvisUITests.swift` (serveur local + base de TEST).
- Date de création (« Événement créé le … · modifié le … », « Sondage créé le … ») tout en bas de chaque fiche (`createdLine`).
- « Lieu à définir » (avis 2237524ab14b) : dit à l'IA, la date est réservée sans lieu (`place_kind` « later », `LATER_PLACE`
  en base, aucune question d'adresse, pas d'itinéraire sur la fiche) ; un lieu dit exige toujours son adresse complète
  confirmée. Tests : `test_place_to_be_defined_*`, `AIEventPlaceLaterTests`, recette `test8AIPlaceToBeDefined`.

## Message pour tout le monde et mises à jour (avis eb710b132330, 13.11.2026)
- Réglages › « Annonce et maintenance » (Root / Admin, web `notice-admin.js`, iPhone ligne native → page `notice`) :
  Maintenance (écran qui couvre l'app, sauf chez l'admin : bandeau « Gérer »), Information, Annonce (bandeau en haut,
  ✕ par message). Serveur : `app/notice.py`, `/api/notice` (public), `/api/admin/notice` (session admin, journal).
- Affichage : `app/static/notice.js` en tête de index.html ET admin.html (avant tout appel au serveur) ; sur tous les
  onglets ; nouveau message aussitôt par le flux `/api/events` (événement `notice`) et l'en-tête `X-Party-Notice`.
  App iPhone : `PartyNative.notice.update` → `PartyNoticeView` natif par-dessus tous les écrans (Réglages compris).
- Mise à jour du serveur : TOUJOURS `deploy/update.sh prod|test` (pose « Mise à jour en cours » avant de redémarrer,
  le serveur revenu l'efface ; l'annonce de l'admin est gardée à part). Serveur injoignable (502/503/504, flux coupé) :
  « Mise à jour en cours » / « Party ne répond pas », réessai tout seul ; jamais « injoignable ». iOS : `OfflineView`
  (réessai automatique, page d'erreur du relais jamais affichée).
- Fin de la maintenance ou serveur revenu (15.11) : `notice.js` recharge TOUTE la page (`location.reload()`), web et app
  iPhone ; sinon la page garde l'ancienne version et Jeux / Événements restent vides. Ne jamais retirer ce rechargement.
- Tests : `tests/test_notice.py`, `tests/e2e/test_notice.py` (serveur arrêté puis relancé), `PartyNoticeTests`.

## Jamais coincé hors de Party (retour de l'admin du 19.11 : invité du paintball sans moyen de voir les autres événements)
- Le module Événements ouvert SEUL (pas dans le cadre `#eventsFrame` : lien, agenda, app iPhone ouverte par un lien) ne
  garde que les pages qui doivent l'être : invite, share, group-invite, join, prono-invite, sign-in, welcome, terms,
  privacy, admin (`ALONE`, web/events/src/lib/partyShell.ts). Toute autre page repart aussitôt dans Party, même page
  (`leaveIfAlone(path)` dans _layout.tsx, chemin du ROUTEUR, jamais `location.pathname` qui est en retard) ; jamais
  pendant le passage par « / » juste après la connexion quand un lien attend (`toLink`, `LINK_INTENT`) : sinon la
  réponse de l'invité était perdue (recette du 19.11). Fins de parcours : `openInParty(path)` (« Voir l'événement »,
  « Découvrir Party » de « Demande envoyée »). Party ouvre `?tab=events&event=<id>` ou `&path=<chemin>`
  (`PartyEvents.validPath`, gardé au rechargement). Tests simulés du module seul : `localStorage.party_module_alone = '1'`
  (`mock_services`). Recettes réelles : `test_inconnu_jamais_coince_browser_live.py`, aides `tests/supabase_live/party_shell.py`.

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
- Une partie en plein écran ne vaut que dans l'onglet Jeux : `showTab` appelle `syncGameChrome()` à chaque changement
  d'onglet (sinon « Se connecter » d'un jeu laissait un écran vide sans barre d'onglets, native comprise ; avis 8d5ec90f63da).
  Test : `tests/e2e/test_purity_game.py`.
- Accueil des Jeux (maquette approuvée le 15.11.2026) : carte « Salle de jeux » (Créer une salle / ou rejoindre + code),
  puis « 🧠 Jeux solo » (Méninges). Les jeux à plusieurs ne se lancent que dans la salle : leurs cartes restent dans
  `#gHome`, sections cachées (`hidden`), car `openRoomSheet` les recopie. Dans un jeu de la salle, « 🎮 Changer de jeu »
  (`#gRoomSwitch`, animateur seulement) = « Terminer ce jeu et revenir à la salle ». Tests : `test_room_votes_ui.py`,
  helper `show_game_cards` pour les tests d'une partie seule.
- Tout prénom ou texte saisi par un joueur passe par `esc()` avant d'entrer dans du HTML, attributs compris
  (test : `tests/e2e/test_names_escaped.py`).
- Tout texte libre d'un jeu montré aux autres (prénom ajouté par l'animateur, roue, réponse écrite, règle, devinette)
  passe aussi le filtre commun : `games.shown_text` (« name » refuse, « answer » masque une insulte) ; en base, prénom,
  nom, nom de lien d'invitation et nom du lieu sont filtrés (migration 20261114123000). Test : `tests/test_compliance_1411_contenu.py`.
- Pyramide (avis 4c55c231a4d2) : après la distribution, phase « look » : chacun voit SES cartes (et l'animateur celles
  des joueurs sans téléphone) au moins `PYR_LOOK_SECONDS` (30 s), puis l'animateur lance la pyramide (`plook`). Dans l'app
  iPhone, la page ne dessine pas ces cartes : `PartyNative.secret.update` → panneau natif `SecretCardsView`, qu'une
  capture ou un enregistrement d'écran rend noir (ScreenshotProof). Navigateur : impossible de bloquer une capture.
  Tests : `tests/test_games.py`, `tests/e2e/test_pyramid_memorise.py`, `SecretCardsTests`, `SecretCardsUITests`
  (TEST_RUNNER_PARTY_SECRET_SHOT=/chemin.png : vraie capture du système, contrôlée noire).

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

## Revue Apple du 16.11.2026 (bar et Discussions ouverts en prod) — à garder
- Dossier de soumission : `docs/app-store/` (notes, tutoriel, fiche, checklist) ; `ios/appstore/review-notes.txt` = partie A
  (≤ 4 000 caractères, `tests/test_ios_app.py`). Données de démo en prod : « Soirée démo Vendredi Party » (Apple-test
  co-organisateur, bar ouvert) et groupe « Démo Apple » (`supabase/prod/2026-11-16-demo-apple-bar-discussions-*.sql`).
- Bloquer (`set_direct_block`) masque aussitôt les messages de la personne (événement, groupes web `GroupChat.tsx` et natif
  `group_chats.py`) ET la signale aux modérateurs (une fois). Bar : ni tabac ni drogue (`bar_item_allowed`) ; bar PAYANT
  seulement sur un événement non public (`bar_private_only`, `event_public_bar_guard`). Jeux : classement aux points,
  jamais aux gorgées. CGU 2026-11-16 (18 ans et plus, « Paiements, billets et bar »). Pas de mise en prod pendant une revue.
  Tests : `tests/test_compliance_1611.py`, `tests/supabase_live/test_conformite_app_store_live.py`.

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

## Discussions : vitesse (demande de l'admin du 18.11 : « fluide, rapide, le plus rapide possible ») — à garder
- Envoi optimiste PARTOUT : la bulle s'affiche avant toute réponse (« Envoi… »), le champ se vide, on écrit la suite.
  Réseau absent : 2 nouveaux essais (0,8 s, 2,5 s), puis « Pas envoyé · Toucher pour réessayer » ; renvoyé tout seul
  au retour du réseau (web : événement `online` / lecture réussie ; iPhone : prochaine lecture de la conversation). Même
  identifiant à chaque essai ; « déjà enregistré » (409 / 23505) = envoyé (`already_sent`, serveur ; web : `outbox.ts`).
  Refus de la base (filtre, demande, CGU) : jamais renvoyé, le texte revient dans le champ s'il est vide. Un message en
  attente n'est jamais perdu quand l'écran se ferme (web : file `components/chats/conversation/outbox.ts` ; iPhone :
  `ChatsStore.outgoing` par conversation) ; jamais renvoyé avec le jeton d'un autre compte (`authors`).
- Rien d'affiché n'attend une relecture complète : message reçu en temps réel = ligne montrée aussitôt (web : `onRow`
  de `useRealtime`), puis relecture ; réactions LUES AVEC les messages (jointure PostgREST, web et `/chats/open`) ;
  iPhone : champs v2 (carte, citation) lus dans la MÊME réponse que la conversation (`Conversation.extras`), plus de
  deuxième `/chats/open` ; liste : l'adresse du temps réel vient avec `chat_list` ; CGU lues dès l'ouverture.
- Cache : liste (web : localStorage par compte, effacé à la déconnexion ; iPhone : fichier + mémoire), conversations
  (mémoire), 3 premières discussions préchargées (lecture seule : `prefetch` ne consomme pas le bandeau « Tu es dans le
  groupe », rien n'est marqué lu, jamais une demande reçue), conversation ouverte au toucher depuis la liste sans
  requête « est-ce un message direct ? » (`knownKinds`). La conversation s'ouvre EN BAS du fil (web : tout le fil rendu
  d'un coup + `onContentSizeChange`) : avant, un long fil s'ouvrait en haut.
- SQL (migration 20261118190000) : `met_events` part des soirées en commun ; `dm_link` une seule fois par personne dans
  « Nouveau message » (`chat_person_linked`). Réponses identiques (vérifié sur TEST).
- Mesures : `ios/PartyUITests/VitesseDiscussionsUITests.swift` (marques `ChatTiming`, E2E_HOOKS seulement),
  `tests/supabase_live/test_discussions_vitesse_browser_live.py` ; tests `tests/test_chats_send_browser.py`,
  `ChatsSendTests` (iOS), `test_group_chats_native.py` (jointure, préchargement, déjà enregistré).

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

## Groupes : nouveau graphisme (17.11)
- Maquette A « Néon & couvertures » + bulles et QR de B. Chaque groupe a un emoji (liste fermée) et une des 6 couleurs
  (`member_groups.emoji` / `color`, contraintes + `private.group_look_guard`, migration 20261117100000) ; couverture =
  dégradé de la couleur + emoji. Photo FACULTATIVE (demande du 17.11, migration 20261117130000) : `member_groups.photo_path`
  (compartiment privé `group-photos`, dossier = le groupe ; écrire : qui le gère ; lire : ses membres + modérateurs ; garde
  `private.group_photo_guard`, CGU) remplace l'emoji et devient la couverture ; « Signaler la photo du groupe » (`group_photo`,
  « Masquer » la retire, fichier retiré par l'appli). Membres Vendredi Party : JAMAIS de photo, son image = le logo officiel
  de Party (`/static/icon-192.png`), personne ne la change ; 🎉 lavande fixe. Tests : `test_groupes_photo_live.py`,
  `test_groupes_photo_browser_live.py`.
  Mêmes listes : `web/events/src/lib/groups.ts`, `ios/Party/Chats/GroupLook.swift`.
- Web : `/groups` (liste façon WhatsApp, `my_groups_overview`), `/group/new` (2 étapes : nom/emoji/couleur avec CGU, puis
  Inviter : lien WhatsApp/Copier/Autre + QR + `group_invite_suggestions` = personnes croisées à un événement, jamais tout
  le site), `/group/<id>` (page : `group_events`, « Créer un événement pour le groupe » = `/event/new?group=<id>`, groupe
  coché, « Prévenir » éteint), `/group/<id>/settings` (Modifier, numéro, règles, retirer, liens, quitter, supprimer),
  `/group/<id>/invite`. Bulles « Tes groupes » en haut d'Événements, étiquette du groupe sur les cartes (mes groupes seulement).
- iOS : lignes de Discussions avec emoji/couleur (`my_chats`). Groupes 100 % NATIFS (demande du 18.11 « tout en natif »,
  `ios/Party/Chats/Groups/`) : liste, page, réglages, Nouveau groupe (2 étapes), Inviter (lien, QR CoreImage, personnes
  croisées), mêmes règles que les pages web. ✎ « Nouveau groupe » et Réglages › Groupes : `OpenGroupPageAction` →
  `WebModel.groupRoute` (plein écran natif) ; « Gérer le groupe » (infos d'une discussion) : page native poussée sur place.
  Serveur : relais `/api/account/chats/rpc` + `app/group_pages.py` (mêmes lectures / écritures que le web, session du
  membre ; RLS vide → `forbidden`), photo `POST /api/account/chats/group-photo`. Restent web : la fiche d'un événement et
  « Créer un événement pour le groupe » (`/event/new?group=<id>`, onglet Événements). Discussions coupées : pages web d'avant.
  Tests : `tests/test_group_pages.py`, `tests/supabase_live/test_groupes_natifs_live.py`, `GroupsNativeTests`, recette
  `RecetteGroupesNatifsUITests` (Release + serveur local + base de TEST).
- Tests : `tests/test_groups_browser.py`, `tests/supabase_live/test_groupes_graphisme_live.py`,
  `test_groupes_graphisme_browser_live.py`, `GroupLookTests`.

## Invités → groupe (17.11, migration 20261117110000)
- Option par événement `events.guest_group` (éteinte par défaut, jamais allumée par l'IA : hors du schéma de ai_events.py /
  ai_event_edit.py) : un seul groupe, que l'organisateur gère ET dont il fait partie (`private.manages_guest_group`, garde
  `events_guest_group_guard`), jamais Membres Vendredi Party. Étape 2 « Qui est invité » et carte Invités › « Régler »
  (`set_event_guest_group`, « Nouveau groupe » = groupe créé d'un coup, nom filtré, CGU).
- Case « Rejoindre aussi le groupe « … » de … » DÉCOCHÉE par défaut (RGPD Planet49, Apple 5.1.2), grande, sous les réponses,
  texte complet (`JOIN_DETAIL`, lib/guestGroup.ts). L'écran envoie `join_group` true/false AVEC la réponse
  (`accept_invite_group` ; fiche : `set_guest_group_choice`) ; sans paramètre ou false : jamais d'entrée. Coché : entrée pour
  Je viens, Peut-être ET Pas présent ; en attente d'accord : à l'accord (déclencheur `rsvps_guest_group`). Pas de case sur un
  sondage de dates. Répondu sans cocher : bouton « Rejoindre le groupe » sur la fiche, sans relance ni notification.
- Jamais : blocage (organisateur ou créateur du groupe), profil incomplet, personne partie du groupe après la création de
  l'événement (`private.group_departures` : groupe, personne, date ; noté seulement quand on part soi-même, jamais par la
  cascade d'un groupe ou d'un compte supprimé ; effacé quand elle revient d'elle-même).
- Après l'entrée : notification personnelle `group_added` (interrupteur `notification_prefs.group_added`, web + iPhone,
  `web_push_allowed`, `may_receive_push`, `drop_blocked_notification` ; toucher → discussion du groupe) ; bandeau
  « Tu es dans le groupe X · Quitter » une fois (`take_group_join_note`, web GroupChat, iOS ConversationView). Aucune
  notification aux membres (le créateur garde « X a rejoint ton groupe ») ; jamais d'annonce (send_announcement seul).
- « 🎉 Garder cette bande ? » (`keep_band`) : organisateur, de la fin à 7 jours après, une seule fois (`private.band_offers`),
  INVITATIONS à accepter seulement, jamais ceux qui ont décoché ni ceux partis. `invite_to_group` refuse aussi une personne en blocage avec le créateur du groupe.
- Un événement qui RÉUNIT ses invités dans un groupe compte parmi les événements du groupe (page, prochain événement de
  la liste ; `private.group_event_ids`, migration 20261117120000), toujours sous `can_see_event`.
- Recette iPhone (Release + serveur local + base de TEST) : `ios/PartyUITests/RecetteGroupesUITests.swift` (case cochée,
  « Absent », groupe dans Discussions, bandeau Quitter, Réglages › Groupes, page du groupe).
- Tests : `tests/supabase_live/test_invites_groupe_live.py`, `test_invites_groupe_browser_live.py` (recette réelle),
  `tests/test_invites_groupe.py`, `tests/test_invites_groupe_browser.py`, `GuestGroupTests` (iOS).

## Agenda (17.11, migration 20261117140000) — base, serveur, page publique, écrans web ; écrans iPhone à suivre
- Rendez-vous créés dans Party : `agenda_items` (propriétaire seul, RLS), calendriers `agenda_calendars` (« Mes soirées
  Party », « Juste pour moi », agendas .ics à adresse secrète, lus par le serveur pour leur seul propriétaire :
  `POST /api/account/agenda/ics`, app/agenda_ics.py, https seulement, jamais une adresse privée). Contrat complet des
  fonctions : `agenda_*` (relais iPhone `POST /api/account/agenda/rpc`, liste blanche `RELAY` d'app/agenda.py).
- Partage des dispos : groupe par groupe (`agenda_set_sharing`, tout décoché, accord daté, jamais Membres Vendredi Party
  d'office), bloqués exclus, quitter le groupe = arrêt (déclencheur), arrêter = tout effacé ; le serveur ne reçoit que des
  plages « pris » arrondies à 30 min sur 60 jours (`agenda_set_busy`, jamais titre ni lieu). « Qui est libre ? » :
  `agenda_group_free` (ceux qui ne partagent pas : `shares: false`, sans état, jamais « N'a pas partagé »).
- Liens publics (`private.agenda_links`, jeton 144 bits, 10 au plus, PERMANENTS par défaut ou 90 jours (`expires_at` null =
  permanent, migration 20261117150000), arrêter / rallumer à la même adresse, vues
  pour le propriétaire seul) ; page `GET /d/<jeton>` rendue par le serveur (app/agenda.py) : vouvoiement, polices système,
  aucune ressource externe (CSP nonce), noindex / no-referrer, même 404 neutre pour inconnu / arrêté / expiré, délai minimum
  choisi par lien (`min_notice_min` : sur le moment, 30 min, 1 h, 2 h, 8 h, 12 h par défaut, 24 h, 48 h, 7 jours ; sous 24 h le jour
  même devient possible ; `agenda_link_set_notice`), 60 jours au plus. Plusieurs durées par lien (`agenda_links.durations`,
  15 min à 4 h, 6 au plus, `agenda_link_set_durations` ; la plus courte = `duration_min`) : la personne qui réserve choisit
  (« Durée » sur la page, `slots_by`, `duration` de `agenda_booking_request`, refusée si le lien ne la propose pas ; migration
  20261117200000). Toute adresse depuis PARTY_PUBLIC_URL, jamais un domaine en dur.
- Demandes de rendez-vous (option du lien, éteinte par défaut) : créneau réservé 48 h, 5 en attente par lien, 1 par e-mail /
  téléphone, 3 / h par IP hachée (24 h), 20 / jour par lien, champ piège + 3 s de saisie, filtre (lien refusé dans le
  message, motif dit à l'inconnu), Accepter / Refuser / Signaler (`content_reports` : `booking_request`, `agenda_link`) /
  Bloquer l'expéditeur (empreintes) / Couper ; suivi par lien secret `/d/r/<secret>` (Annuler, Effacer mes données, .ics).
  Effacé aussitôt si refus / annulation / 48 h sans réponse, 30 jours après le rendez-vous sinon (pg_cron `agenda-tick`) ;
  l'agenda du membre garde « Rendez-vous · Prénom N. ». Jamais de SMS, d'appel ni de rapprochement avec un compte Party.
- Chaque lien choisit « Ce qui te rend occupé » (`agenda_links.calendars` : id des calendriers de Party / .ics, `ios:<id>`
  pour l'iPhone, jamais un nom ; null = tout, liens d'avant ; nouveau lien : tout coché). Les plages arrivent par calendrier
  (`agenda_busy.cal`, `for_groups`) : « Qui est libre ? » ne lit que les calendriers qui comptent pour les groupes ; l'iPhone
  envoie aussi ceux choisis par un lien actif (`AgendaStore.linkCalendars`), aussitôt après l'enregistrement du lien
  (`syncBusyNow`). Les demandes de rendez-vous rendent toujours occupé. Plages SANS calendrier (`cal = ''`, app d'avant le
  build 199) : comptent pour tous les liens (bug du 17.11, lien toujours libre). Marges par lien : `buffer_before_min` /
  `buffer_after_min` (0 à 240, par 5 ; écran : Aucune, 30 min, 1 h, 1 h 30, car les plages sont arrondies à 30 min) autour de tout ce qui rend occupé
  (`private.agenda_link_busy`, migration 20261117160000).
- Adresse lisible (migration 20261117170000) : `<site>/agenda/<nom>/<lien>` (app/agenda.py, `agenda_resolve` → même page,
  demande, signalement, aperçu ; le jeton n'apparaît jamais dans la page). Nom choisi une fois (`private.agenda_handles`,
  unique sur le site, 3–30, réservés `agenda_handle_reserved`, filtré comme un surnom ; `agenda_handle_set`) ; nom du lien
  `agenda_links.slug` unique pour soi (`agenda_link_set_slug`). Écran : « Adresse du lien » Lisible (défaut) / En lettres.
  `/d/<jeton>` marche toujours. Nom changé / lien arrêté : l'adresse lisible ne montre plus rien. Tests : `test_agenda.py`,
  `test_a_readable_address_agenda_name_link`, `test_links_empty_state_*`. Tests : `test_each_link_chooses_the_calendars_*`,
  `test_a_link_can_be_permanent`, `test_in_the_iphone_app_a_link_picks_iphone_calendars_*`, `AgendaTests`.
- Notification `booking_request` / `booking_cancelled` sans coordonnée ni texte libre, interrupteur
  `notification_prefs.booking_requests` (allumé) ; pastille `agenda_badge()` + signal `user:<id>`. E-mails : pas en v1,
  point d'accroche `mail_state`, statut `to_confirm` et `private.agenda_settings.double_opt_in`.
- Tests : `tests/test_agenda.py`, `tests/supabase_live/test_agenda_live.py`, `test_agenda_page_browser_live.py` (vrai
  navigateur : grille, liste, demande, réservée, acceptée).
- Écrans web (module Événements, `/agenda`, direction A validée) : semaine en jours empilés (par défaut, puis la dernière
  vue), jour avec trous « Libre · 1 h + Ajouter », mois ; `item` (titre, jour, heures ; « Plus d'options » ; « Juste pour
  moi ») ; `calendars` (« Voir ici » / « Partager », agendas .ics) ; `share` (tout décoché, groupe par groupe, le bouton
  compte les groupes) ; `free` (« Le mieux » dès 3 qui partagent, Disponible / Occupé en mots + rayures, « Les autres
  membres » grisés SANS texte ; « Organiser » → `/event/new?group&title&start&end`, « Faire voter » → `&poll=<iso,…>`) ;
  `links` (6B avant chaque lien, modèles, plages, champs Non / Facultatif / Obligatoire, aperçu) ; `requests` (Accepter,
  Refuser, Signaler → `agenda_booking_report` via ReportSheet `send`, Bloquer, Couper). Code : `lib/agenda.ts` (heure de
  Suisse, `rankDays`, `personState`, pont `nativeAgenda()` facultatif), `components/agenda/`. Entrées : « 📅 Agenda » de
  l'en-tête d'Événements et Réglages › Autres apps › Agenda (web : Settings.tsx), pastille `useAgendaBadge` (signal
  `user:<id>`). Web : plages des agendas .ics cochés → `agenda_set_busy('web')` (jamais de titre). Tests :
  `tests/test_agenda_browser.py` (base simulée), `tests/supabase_live/test_agenda_web_browser_live.py` (recette réelle).
- Avant la prod : privacy.tsx (section publique des demandes), CGU, App Privacy (e-mail), phrase EventKit, notes de revue.

## Agenda et Pronos gardés en test (décision de l'admin du 19.11)
- `agenda_enabled()` / `pronos_enabled()` (app/features.py, AGENDA_ENABLED / PRONOS_ENABLED, sinon site de test seulement) :
  éteints, `/api/account/agenda/*`, `/d/*`, `/agenda/*`, `/api/account/pronos/*`, `/prono/*` → 404 ; la page porte
  `data-agenda="off"` / `data-pronos="off"` (module : `agendaOn` / `pronosOn`, lib/features.ts : ni ligne « Autres apps »,
  ni « 📅 Agenda », ni carte Pronos de la fiche, ni bouton du groupe, ni interrupteur de notification ; leurs pages ramènent à
  l'accueil) ; iPhone : `/api/features` `agenda` / `pronos` (SettingsStore.agendaOn / pronosOn). Confettis éteints avec les Pronos.
- Leurs migrations (20261117140000-150000-160000-170000-180000-200000-210000, 20261118090000, 20261118095000 CGU) ne sont PAS
  en prod : à appliquer dans l'ordre le jour où l'admin les ouvre (aucune n'est redéfinie par une migration passée en prod
  le 19.11, sauf la contrainte content_reports_target_kind_check qu'elles complètent). Tests : `tests/test_apps_flag.py`.

## Pronos entre amis (avis f071c5f46e3d, 17.11, migration 20261117180000)
- Revue de conformité : paris AVEC argent (même payé hors de Party, TWINT, Revolut, Pot commun) = NON (Apple 5.1.1(ix),
  5.3.4, LJAr, ANJ). Seule voie : « Pronos » POUR L'HONNEUR, des points au classement du groupe. Jamais les mots pari / mise
  / pot / cagnotte / cote / gain à l'écran, aucun champ d'enjeu, aucun lien de paiement, Pot commun ou bar à côté, jamais
  de pièces de Zicou, jamais de prono sur l'alcool. La base refuse montants, devises, mise, tournée, TWINT… (`private.prono_text`).
- Tout par fonctions `prono_*` (schéma private, aucun accès direct). Réponses CACHÉES par la base (organisateur et admins
  compris) jusqu'au dévoilement : à la fin (`reveal = 'close'`) ou avec le résultat (`'result'`) ; réponse libre : toujours
  à la fin. Avant : on voit seulement QUI a joué. Après la 1re réponse : question et choix figés, fin déplaçable, Annuler.
- Qui joue : un de MES groupes (jamais Membres Vendredi Party), les participants d'un événement (« Pronos de la soirée »),
  des personnes croisées (`private.prono_known`), un lien `/prono/<jeton>` (connexion SMS, profil complet, CGU).
  Créateur : tout membre au profil complet + CGU ; il joue aussi. Types : choix (2–8), nombre (le plus proche), libre
  (l'organisateur coche), une personne. Points 1–10 choisis par l'organisateur ; classement par groupe, remise à zéro par qui
  gère le groupe. L'IA ne crée jamais de prono.
- Blocage : jamais dans le prono de l'autre ni vu ni notifié. Signaler : `prono` (report_content) et `prono_answer`
  (`prono_report_answer`, cible « <prono>:<auteur> ») ; « Masquer » cache le prono / la réponse.
- Notifications `prono_new`, `prono_result`, `prono_due` (pg_cron `pronos-tick`, à l'organisateur) ; interrupteur
  `notification_prefs.pronos` ; toucher → `/?tab=events&prono=<id>` (écran natif dans l'app iPhone).
- Web : `/pronos` (Réglages › Autres apps), `/prono/new`, `/prono/<id>`, `/group/<id>/pronos` (liste + classement),
  `/prono-invite/<jeton>`, carte sur la fiche. iPhone : écrans NATIFS (`ios/Party/Pronos/`, relais
  `POST /api/account/pronos/rpc`, app/pronos.py, photos signées) ouverts par `PartyNative.pronos` (open / list / create).
- Avant la prod : CGU (« aucun enjeu d'argent ni de boisson »), privacy.tsx, notes de revue Apple + compte démo dans une
  version acceptée AVANT l'ouverture, questionnaire d'âge relu (Gambling Non, Simulated Gambling None).
- Tests : `tests/test_pronos.py`, `tests/supabase_live/test_pronos_live.py`, `test_pronos_browser_live.py` (vrai
  navigateur), `PronosTests`, recette `ios/PartyUITests/RecettePronosUITests.swift` (Release + serveur local + base de TEST).

## Pronos v2 et confettis (ex-patates) (demande du 18.11, migration 20261118090000, CGU 2026-11-18)
- Les « patates » sont devenues des « confettis 🎊 » (décision de l'admin du 18.11) : TEXTE visible seulement, règles
  identiques. Les noms de code restent les anciens noms internes et ne se renomment jamais : `patates`, `patates_on`,
  `patates_enabled`, `PATATES_ENABLED`, `PronoPatates`, `PatateBadge`, `potato`, `harvest`, `compost`, `prono-patates-*`…
  La réaction stockée en base reste la valeur '🥔' (contrainte de `prono_react`) ; l'écran montre 🎊 (« Réaction confettis »).
- Argent réel (même « 5 balles » réglées à côté, même déguisé en confettis) : JAMAIS (Apple 5.1.1(ix) / 5.3.4, LJAr). Les
  confettis : monnaie pour rire, gratuits, jamais achetables / vendables / échangeables / transférables / convertibles,
  aucun lot, aucun lien avec Zicou, le bar, les billets, Pot commun. Revue : scratchpad pronos-v2/conformite-patates.md.
- Un sac par personne ET par terrain (groupe `g:` ou soirée `e:`) ; 100 au départ, remonte à 100 chaque lundi 0 h (heure de
  Suisse) s'il est plus bas, jamais cumulé ; 0 à 20 🎊 par prono ; partage de la piste au plus fort reste (somme nulle, JAMAIS
  de cote fixe) ; rendus si unanimes / personne / un seul lanceur / annulé / contestation gagnée ; versés 12 h après le
  résultat (contestation, vote 24 h) par `pronos-tick`. Saison = confettis ramassés ce mois-ci ; historique du sac à soi seul.
- Vocabulaire à l'écran : lancer, la piste, ramasser (« Tu ramasses »), au balai, ton sac, rendus (accords au MASCULIN) ;
  JAMAIS pari, mise, miser, cote, gain, cagnotte, jackpot, balles, CHF / €, ni coin / jeton / pièce pour les confettis (les
  pièces sont à Zicou) ; anglais (notes de revue) : « Confetti (free, valueless play tokens) », jamais « coins » ; aucune
  chance ni multiplicateur avant le dévoilement ; confettis animés seulement si juste. Rappel « Les confettis n'ont aucune
  valeur… » sous chaque sac (`NO_VALUE`, `PronoPatates.noValue`).
- Deux interrupteurs : serveur `patates_enabled()` (PATATES_ENABLED, sinon site de test seulement ; `/api/features`
  « patates ») ET base `private.prono_settings.patates_enabled` (éteint par défaut, allumé sur TEST). Prod : allumer
  seulement après une version iOS acceptée qui décrit les confettis (Notes for Review), questionnaire d'âge « Simulated
  Gambling » Frequent (18+), CGU 2026-11-18 en prod.
- Types : choice, yesno, overunder (ligne en demi-unité), number (« sans dépasser »), when (« C'est arrivé ! »), person,
  text, majority (« Devine ce que pense la bande », tranché seul), award (Trophée de la soirée : 8 catégories POSITIVES
  fermées, ≥ 3 votants, on se retire, jamais de confettis). 21 modèles `prono_templates()` (jamais d'alcool).
- Graphisme « Néon club » (maquettes pronos-v2/maquettes) : web `components/pronos/Kit.tsx` (+ list/, create/, play/,
  reveal/, board/), iPhone `ios/Party/Pronos/PronoKit.swift` (+ PronoRevealView). Le dévoilement web s'ouvre dans un `Modal`
  (sinon la fiche passait par-dessus) ; iPhone : `PronosStore.call` lit `/api/features` au premier appel.
- Tests : `tests/supabase_live/test_pronos_v2_live.py`, `test_pronos_browser_live.py` (recette réelle avec confettis),
  `tests/test_pronos_v2.py`, `tests/test_compliance_pronos.py`, `PronosTests`, recette `RecettePronosUITests` (Release).

## Discussions v2 (18.11, migrations 20261118120000 / 20261118121000)
- Qui écrit à qui : la BASE décide (`private.dm_link` → 'direct' / 'request' / 'none', `chat_link` pour les écrans).
  Direct : conversation acceptée, groupe en commun HORS Membres Vendredi Party, événement NON public en commun, organisateur
  ↔ personne qui a répondu à SON événement. Demande : VP seul en commun, même événement public, contact du répertoire,
  recherche. Aucun : blocage (deux sens), compte inactif, profil / CGU manquants, « Demandes de message : Personne ».
  L'app ne fait que proposer ; jamais de suggestion « tout le site » ni de recherche par numéro.
- Listes « Nouveau message » (`chat_people_search`, `chat_people_suggestions`) : `private.dm_link_listed` = même lien SANS
  les CGU de qui cherche (migration 20261119090000) ; écrire garde `dm_link` → feuille des CGU. Sinon, à chaque nouvelle
  version des CGU, la recherche était vide pour tous (retour du 19.11). Test : `test_discussions_recherche_cgu_live.py`.
- Demande de message (`open_direct_chat`, `direct_chats.status`) : UN message texte, sans photo, vocal, lien ni numéro
  (garde `guard_direct_message`, `request_pending`) ; Accepter / Supprimer / Bloquer / Signaler ; l'expéditeur n'est
  jamais prévenu d'un refus. Plafonds : 10 nouvelles / 24 h, 30 en attente (`limit`) ; devinette de numéro : 20 échecs
  / 24 h. Refusée : effacée aussitôt ; ignorée : 30 jours (`chat-requests-tick`). Notification `message_request`
  (« … veut t'écrire », sans contenu, une fois) + interrupteur `notification_prefs.message_requests` (web + iPhone).
- Réglages (`chat_prefs`, `chat_prefs_get` / `chat_prefs_set`) : « Demandes de message » Tout membre / Personne et
  « Confirmations de lecture » (réciproques) dans Réglages › Confidentialité, web (`settings/privacy.tsx`) et iPhone
  (`ChatPrefsSection`). « écrit… » = signal en direct, jamais en base ; ni Vu ni écrit… dans une demande ou avec un bloqué.
- Root : ne lit JAMAIS les messages directs, les demandes ni les groupes privés (`member_groups.private_chat`, créés par
  « Nouveau message », `create_chat_group`) ; il lit les autres groupes (dit dans privacy.tsx et les CGU). Jamais VP privé.
- iPhone : tout passe par `POST /api/account/chats/rpc` (app/chat_rpc.py, liste blanche RELAY, mêmes erreurs que
  pronos/rpc, terms_required → 403). Toute nouvelle fonction publique des Discussions = ajoutée à RELAY.
- Mini-profil (`member_mini`) au toucher d'un nom ou d'une photo PARTOUT (web `useMiniProfile().open`, iPhone natif),
  « Envoyer un message » désactivé avec la raison si 'none'. « Déjà vu N fois » = soirées PASSÉES où les deux étaient
  présents (Présent, organisation, billet scanné), sous `can_see_event`, calculé à l'affichage, jamais stocké.
- Fichiers : signaler un message avec photo / vocal le copie dans `moderation-evidence` (modérateurs seuls, effacé avec le
  signalement) ; case « Joindre les 10 messages précédents » décochée ; « Masquer » prévient l'auteur (`content_hidden`,
  motif + contestation) ; fichiers orphelins de `chat-photos` / `group-photos` effacés par le serveur (6 h) ; photos et
  vocaux 90 jours ; messages directs jusqu'à la suppression du compte de l'un des deux.
- Textes : CGU 2026-11-18 « Messages directs et demandes » et politique « Discussions et messages directs » (web = iPhone,
  mot pour mot) ; phrase Contacts (project.yml) avec les suggestions ; notes de revue (section DISCUSSIONS, 2 comptes de
  démo). Tests : `tests/test_compliance_discussions.py`, `tests/supabase_live/test_discussions_v2_live.py`,
  `tests/test_chat_rpc.py`, `tests/test_discussions_moderation.py`.

## Discussions v2 « Néon club » (demande du 18.11, migrations 20261118120000 et 20261118121000)
- Contrat complet : scratchpad de la session (discussions/contrat.md) ; règles de la base : qui écrit à qui = `private.dm_link`
  (direct / request / none), JAMAIS décidé par l'app. Demande de message : un seul message texte, 10 par jour, 30 en attente,
  purge `chat-requests-tick` ; accepter / supprimer / signaler / bloquer. Groupes privés (`member_groups.private_chat`).
- Mini-profil (`member_mini`) : « Jamais rencontré » / « Déjà vu N fois » = soirées PASSÉES vécues ensemble
  (`private.met_events`, sous `can_see_event`), les 3 plus récentes ; à venir ensemble, groupes en commun.
- « Envoyer un message » depuis tout profil ; « Nouveau message » (une personne → direct, plusieurs → nouveau groupe).
- Web : supabase direct (`/chats`, `/chats/new`, `/chats/requests`, `/chats/archived`) ; iPhone : écrans natifs
  (ios/Party/Chats/List, People, Conversation) par le relais `POST /api/account/chats/rpc` (app/chat_rpc.py, liste blanche).
  Pastille de l'onglet : `chat_badge`. `direct_chats` n'est PAS dans la publication temps réel : demandes suivies par le
  signal `user:<id>` (`direct_chat_changed`) ; ne jamais l'ajouter à un `useRealtime`.
- Tests : `tests/test_chats_*_browser.py`, `tests/test_chat_rpc.py`, `tests/test_compliance_discussions.py`,
  `tests/supabase_live/test_discussions_v2_live.py`, `test_discussions_moderation_live.py`, recette réelle
  `test_discussions_v2_browser_live.py`, iOS `ChatsListTests`, `ChatsPeopleTests`, `ConversationV2Tests`.
- Avant la prod : correctif D1 (les admins lisaient photos et vocaux des messages directs), clé vault `storage_secret_key`,
  compte démo « Apple-test 2 », représentant UE, notes de revue Apple.
