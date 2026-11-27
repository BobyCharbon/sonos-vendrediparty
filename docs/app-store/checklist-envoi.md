# Checklist d'envoi à Apple — Vendredi Party 1.0.0

À cocher dans l'ordre, dans App Store Connect (appstoreconnect.apple.com › Apps › Vendredi Party, id 6827221948,
`ch.bobycharbon.party`). Textes prêts : `fiche-app-store.md` (fiche), `notes-for-review.md` (notes + guide joint),
`tutoriel-reviewer-fr.md` (relecture en français).

## 1. Avant tout : la production

### Plan de mise en prod du 27.11 (lot `develop` 03357b5c ; topo : `topo-version-apple-27-11.md`)

- [x] `20261127090000` (présences : suppression du compte d'un organisateur) : **DÉJÀ EN PROD le 27.11**
      (`2026-11-27-presences-suppression-compte-apply.sql`).
- [x] `20261126150000` (présences sans compte) : **DÉJÀ EN PROD le 27.11**
      (`2026-11-26-presences-sans-compte-apply.sql`). Il a réécrit `event_changed`, `event_guest_list`, `apply_waitlist`,
      `event_attendance`, `public_event`, `chat_event_cards` et étendu `invite_preview`.
- [ ] Fichiers restants, **dans cet ordre**, par `python3 supabase/tools/apply_prod.py supabase/prod/<fichier>-apply.sql` :
      1. `2026-11-23-recherche-numero` (20261123090000)
      2. `2026-11-23-reglages-groupe-admin` (20261123110000)
      3. `2026-11-26-recherche-personnes-1h` (20261126100000)
      4. `2026-11-26-invitation-pot-commun` (20261126120000)
      5. `2026-11-26-pot-cgu-signaler` (20261126130000)
      6. `2026-11-26-pot-paiement-geste` (20261126140000)
      7. `2026-11-26-pot-filtre-paiement-purge` (20261126160000)
      8. puis `2026-11-26-demo-nettoyage` (20261126110000, données de la démo)
      9. puis `2026-11-27-coorganisateurs-apercu-groupe` (20261127100000 : `co_organizer_suggestions` et
         `group_invite_preview` réécrites EN ENTIER, aucune ancre ; d'après le contrôle du 27.11). Ancres de la prod
         PAS revérifiées pour ce fichier (aucune `position(…)` à vérifier) ; dans le dépôt, aucun des fichiers 1 à 8 ne
         touche ces deux fonctions (vérifié le 27.11).
      10. `2026-11-27-suppression-blocage` (20261127110000) : **PRÊT** (fichiers apply + rollback dans `supabase/prod/`,
         testés sur TEST le 27.11 ; aucune fonction commune avec les fichiers 1 à 9 : n'importe quel ordre). Blocage qui
         empêche d'être noté présent ou ajouté en co-organisateur ; suppression du compte d'un membre de l'équipe qui a
         validé l'événement d'un autre ; plus de trace du compte supprimé (qui amène quoi, groupes d'un événement, photo de groupe). Sans lui en prod : retirer de B4.5 / B7 du guide (et du tutoriel 3.5) la phrase
      11. `2026-11-27-blocage-suite` (20261127120000) : **PRÊT**, à appliquer EN DERNIER (après 2, 5 et 10 : ils redéfinissent
         `join_group_by_link` / créent `guard_coorganizer_block`). Blocage avec le créateur d'un événement ou d'un groupe,
         co-organisateurs retirés par un blocage, lien de groupe et ancien lien d'événement refusés en blocage, plus « et photo ».
         sur « noté présent » par une personne bloquée, puis régénérer le PDF.
- [ ] **Revérifier les ancres contre la prod avant d'appliquer** (150000 a réécrit event_changed, event_guest_list,
      apply_waitlist, event_attendance, public_event, chat_event_cards, invite_preview).
      **Fait le 27.11 en LECTURE SEULE** (`sbq.py prod`, `pg_get_functiondef` de la prod ; photo du 27.11, à refaire si
      quoi que ce soit est appliqué entre-temps) :
      - les **32 ancres** des fichiers 1 à 7 (`position(…)` / `replace(…)` : my_groups_overview, invite_preview, les 7
        `tc_*` de pot-cgu, report_snapshot, moderation_hide, notify_new_report, notify_content_hidden, report_content,
        moderation_copy_evidence, tc_group_json, tc_event_sync, tc_create, tc_join, moderate_tc_text, event_pay_info,
        expire_chat_photos, contrainte `content_reports_target_kind_check` ('pet_word')) sont **toutes présentes, une fois
        chacune**, et **aucune n'est déjà appliquée** (aucune marque « déjà fait » en prod) ;
      - parmi les 7 fonctions de 150000, **seule `invite_preview` est touchée**, par ancre (`'allow_maybe', ev.allow_maybe,`),
        et cette ancre est **toujours là** après 150000 ; **aucun fichier ne réécrit en entier** une des 7 ;
      - les fonctions réécrites EN ENTIER par 1 à 3 (search_phone, 24 fonctions des groupes, group_people_search) ne sont
        touchées ni par 150000 ni par les migrations du 25.11 en prod ;
      - quand deux fichiers touchent la même chose (report_snapshot, moderation_hide, notify_new_report, contrainte
        'pet_word', tc_create, tc_join), le 1er garde l'ancre dont le 2e a besoin : l'ordre 5 puis 6 tient ;
      - `join_group_by_link` / `join_event_by_link` : le texte « prénom, surnom et photo) » est là (remplacement facultatif) ;
      - `demo-nettoyage` : ses conditions de départ sont **toujours vraies** (bar de la démo : 3 articles, 5 lignes de
        journal, aucune commande ; Apple-test « Absent » au Paintball du 19.11 ; billets de la démo encore éteints).
      **Résultat : aucun souci d'ancre, rien à corriger.**
- [ ] Puis redéployer les fonctions **send-push** et **send-web-push** (dernière version de `develop` / `main`).

- [ ] **Refus 1.4.3 (25.11)** : branche `fix-143` en prod ; avec l'User-Agent « PartyStore », l'écran Jeux n'a ni « 🍻 Alcool »,
      ni gorgée ni « ⭐ Mode points », ni Pyramide / Je n'ai jamais / Qui de nous ? / Roulette / Beer pong / Biskit /
      Purify Test / Casino / Blackjack, ni mode Hot / Mix, ni thème WTF ; un code de Pyramide créée sur le web répond 403 ;
      la barre d'onglets n'a pas « Musique » ; Jeux › Code à 6 chiffres ouvre la soirée Musique ; `/api/features` répond `bar: false` à l'app
      App Store (et à tout appel natif `X-Party-Native: ios` en prod) ; `supabase/prod/2026-11-25-demo-sans-alcool-apply.sql`
      appliqué ; fonction `send-push` redéployée (aucune notification du bar vers l'app App Store). Tour 2 : avec « PartyStore »,
      `/api/features` répond aussi `pronos: false`, `agenda: false`, `patates: false` (même si le site les allume) ;
      `https://party.bobycharbon.ch/support` répond 200 ; `/events/terms?app=ios` et `/events/privacy?app=ios`, ouvertes dans
      Safari, n'ont ni bar, ni alcool, ni Pronos.
- [ ] Code de la soirée Musique à **6 chiffres** : l'actuel code de prod a encore 4 chiffres (gardé sur le web) ; l'hôte
      tire un nouveau code (Admin de la soirée › Nouveau code) avant l'envoi, sinon l'app ne peut pas rejoindre la soirée
      par le champ Code (4 chiffres = un jeu ; le QR marche toujours). Si une soirée Musique reste ouverte pendant toute la
      revue, ajouter « Music demo code: XXXXXX » aux notes (moins de 4 000 caractères) ; sinon les notes disent qu'elle exige
      un hôte avec Sonos.
- [ ] Profil de l'admin (auteur du message privé de démo) : son surnom contient U+F8FF (logo Apple sur un iPhone) et 🇨🇭 ;
      le renommer (« Boby ») dans l'app avant l'envoi, ou appliquer `supabase/prod/2026-11-25-surnom-sans-logo-apply.sql`
      (accord de l'admin ; il refuse de finir s'il reste un U+F8FF).
- [ ] Tour 3 (25.11) : `supabase/prod/2026-11-25-cgu-apply.sql` appliqué AVEC le déploiement (CGU du 25 novembre 2026,
      celles qu'affichent la web et le nouveau build ; remplace le fichier du 18.11) ; un billet ajouté à Cartes montre
      « Contact » au dos ; avec « PartyStore », `/api/purity/leaderboard` répond 404 et « Mes stats de jeu » n'a que
      Méninges ; « Partager › Party » (nouveau build) ne propose que « Créer l'événement ».
- [ ] NOUVEAU build Release compilé depuis `main` après la fusion de `fix-143` (jamais le 216 : ses CGU, sa confidentialité,
      ses stats Purify, son action rapide Musique, ses emojis 🍻 🍷 et son extension de partage Musique sont dans le binaire).
- [ ] Captures 6,9" et Duo et vidéo d'aperçu REFAITES sur ce build (barre sans Musique, capture 09 = Méninges ou
      Discussions, aucune boisson) ; sinon supprimer la vidéo d'aperçu dans App Store Connect.
- [ ] Tour 4 (25.11) : `2026-11-25-surnom-sans-logo-apply.sql` retire aussi U+F8FF des 27 notifications déjà envoyées
      et (tour 7) des 3 noms du Pot commun (`tc_members`, dont « Cobalt Project Paintball ») ; contrôle : 0 ligne
      `notifications` / `tc_members` avec chr(63743). Son retour arrière ne remet PAS les notifications (leur texte n'entre
      jamais dans le dépôt public) ; ~~vidéo Musique jointe~~ : abandonnée le 26.11 (les notes ne promettent plus de
      vidéo, « see attached video » retiré) ; le jour de l'envoi, valider dans l'heure toute proposition d'Apple-test (les événements publics passent par la
      modération) ; PDF du guide régénéré (partie B).
- [ ] Tour 5 (25.11) : AUCUNE version tvOS (app Apple TV « Party », même identifiant) jointe à l'envoi de la 1.0.0 iOS :
      elle affiche encore « 🍻 Boit », « 🍺 gorgées » et « Un shot » (ios/PartyTV, binaire). Avant toute version tvOS : nouveau
      build qui cache ces lignes. Retirer Apple-test du « Cobalt Project Paintball » (vrai événement, vraies personnes) :
      il ne garde que la démo et « Démo Apple ». Vérifier où est hébergé le serveur (IP chez Orange France) : la confidentialité
      dit désormais « chez l'éditeur, en France » ; si c'est faux, corriger privacy.tsx et SignInView.swift avant l'envoi.
      Vidéo Musique : abandonnée, « see attached video » retiré des notes le 26.11 (test `test_round_four_review_notes_*`
      adapté). Nouveau build : Pronos, Agenda, Zicou et bar éteints dans l'app quoi que dise le
      serveur ; Pot commun « Rembourser » ; Apple TV sans ligne « Boit » / gorgées (pour une future version tvOS).
- [ ] Tour 6 (25.11) : filtre des événements publics de l'app élargi (happy hour, afterwork, pinte, Oktoberfest, ti-punch,
      binouze, pub crawl, margarita, shooters, Ricard, Heineken, chicha, narguilé, vapoter, puff, Jäger, pils, IPA ;
      `DRINK_RE` + `storeEvents.ts`) : pendant la revue, ne valider AUCUN nouvel événement public qui parle de boisson.
      « Anniversaire de P-A, Maxou et Boby » (sondages sur l'alcool fort) : le passer « Sur invitation » ou retirer ses deux
      sondages ; « S'Beer » et « Soirée Halloween » (passés) : les archiver ou annuler ; jamais Apple-test invité à ces
      événements. Clé `storage_secret_key` à AJOUTER par l'admin dans le coffre Supabase de prod (absente au 25.11 : sans
      elle, `chat_files_gc` n'efface rien et les photos / vocaux des comptes supprimés restent, contrairement à la
      politique) ; contrôle : une ligne dans `private.chat_files_gc_runs` après le démarrage du serveur. Avis confiés à
      l'IA : le dépôt `BobyCharbon/sonos-vendrediparty` est PUBLIC ; passer le dépôt en privé, ou mettre `GITHUB_REPO` sur
      un dépôt privé à part (la politique dit seulement « copié sur GitHub »). Guide PDF régénéré au tour 6 (B2, B4.3,
      B4.4 : publication directe dans « Démo Apple », validation pour public / sur invitation ; index des jeux 4.7.4).
- [ ] Tour 7 (25.11) : `supabase/prod/2026-11-25-pot-commun-filtre-apply.sql` appliqué AVEC le déploiement (Pot commun
      filtré : noms, titres, notes ; testé sur la base de TEST). Accord IA version 3 (« publié sur GitHub, où tout le monde
      peut le lire ») : chacun le redonne avant le prochain envoi à l'IA ; si le dépôt passe en privé, le texte reste vrai
      par excès (on peut le rendre plus court plus tard, version 4). Fiche : section « ET AUSSI » de `metadata-fr.json`
      recopiée dans App Store Connect (extension Partager › Party, 4.4 ; 26.11 : plus de puce Musique / Activité en direct). Historique de
      `fix-143` réécrit le 25.11 (les 27 notifications sorties du retour arrière) : vérifier avant tout push que
      `git log -p origin/main..fix-143 -- supabase/prod/2026-11-25-surnom-sans-logo-rollback.sql | grep -c "update public.notifications"`
      vaut 0.
- [ ] Tour 8 (26.11, contrôle de la prod, textes corrigés sur develop) : notes, guide PDF, fiche, tutoriel et politique
      de confidentialité corrigés (plus de « see attached video », plus de « ✨ IA » sur la fiche, « photos and voice
      messages can be sent », plus de « mini-sondages » ni de puce Musique / Activité en direct dans la description,
      « Paying unlocks nothing » remplacé par le billet QR remis une fois le paiement confirmé, plus de « quick action »,
      « signalements lus et traités par l'éditeur sous 24 heures », « Ton avis » écrit à l'équipe de Party). Pot commun
      (décision de l'admin) : l'entrée automatique est GARDÉE (Présent à un événement avec pot = membre ; on le quitte dans Réglages › Pot commun ; « Pas présent » ne retire PAS du pot) ;
      B4.17 et la politique le disent. Politique du 26 novembre 2026 : Supabase (société américaine, données à Zurich) dans
      les transferts, empreinte des contacts plus dite « irréversible », surnoms envoyés à l'assistant IA, journal de
      connexion gardé 12 mois et recherches de personnes 1 heure. RESTE À FAIRE avant l'envoi :
      - [ ] la purge à 12 mois d'`audit.jsonl` et à 1 h de `group_search_log` est EN PLACE en prod (agent « serveur » du
            26.11) ; sinon retirer ces deux durées de la politique (web et iPhone) avant l'envoi ;
      - [ ] captures 6,9" et Duo REFAITES sur le nouveau build App Store (barre à 4 onglets, 09 = Méninges ou la Salle
            de jeux, données fictives, aucune boisson) ; ancienne vidéo d'aperçu SUPPRIMÉE dans App Store Connect
            (aucune nouvelle vidéo) ; vérifier qu'aucune ancienne image ne reste en ligne ;
      - [ ] guide PDF joint = celui du 26.11 (régénéré depuis la partie B) ; notes recopiées (3994 caractères) ;
      - [ ] clé `storage_secret_key` AJOUTÉE par l'admin dans le coffre de prod (contrôle : `private.chat_files_gc_runs`) ;
      - [ ] dépôt GitHub `BobyCharbon/sonos-vendrediparty` passé en PRIVÉ (ou `GITHUB_REPO` sur un dépôt privé à part) ;
      - [ ] nouveau build iPhone : la politique native (`SignInView.swift`) est celle du 26.11, mot pour mot la page web.
- [ ] Contrôle Apple, tour 1 (26.11, textes de soumission) : notes (3994 caractères), guide PDF (B4.3 : « Sur invitation »
      puis « Démo Apple · 2 » ; B4.14 : case « J'ai 18 ans ou plus… » vérifiée par le serveur, prénoms filtrés même changés
      en cours de partie ; B4.16 : Pot commun aussi pour qui est noté Présent par l'organisateur, dépenses et photos de
      tickets avec CGU et « Signaler » ; numérotation B4.12 corrigée) ; plus aucune Activité en direct promise (musique
      impossible à essayer sans l'hôte, 2.1) ; la Musique reste décrite, sans démo, pour ne rien cacher (2.3.1) ; aucune
      mention de Souvenirs ni de la couverture d'événement (éteints dans l'app App Store). RESTE À FAIRE avant l'envoi :
      - [ ] captures 6,9" et Duo REFAITES sur le nouveau build : les 4 onglets (**Jeux, Événements, Discussions,
            Réglages**), la 09 remplacée par **Méninges** ou la **Salle de jeux** ; aucune boisson, données fictives ;
      - [ ] vidéo d'aperçu SUPPRIMÉE dans App Store Connect (6,9" ET iPhone Duo) ;
      - [ ] clé `storage_secret_key` ajoutée dans le coffre Supabase de prod (contrôle : `private.chat_files_gc_runs`) ;
      - [ ] dépôt GitHub passé en PRIVÉ ;
      - [ ] connexion d'« Apple-test 2 » ET d'« Apple-test » testée LE JOUR de l'envoi ;
      - [ ] `supabase/prod/2026-11-26-demo-nettoyage-apply.sql` appliqué (contrôle : migration `20261126110000` en prod) ;
      - [ ] couverture de l'événement « Verknipt » vérifiée / remplacée (aucune boisson visible) ;
      - [ ] lien Shotgun de « Hard Boat » nettoyé : sans paramètre `uhandle` ni `utm_*` ;
      - [ ] App Privacy : **Payment Info** cochée (IBAN) ; manifeste : `NSPrivacyCollectedDataTypePaymentInfo` y est
            (27.11 : 17 types en tout avec Search History, voir § 6).
- [ ] **Contrôle du 27.11 (textes, lot 6) — LE JOUR DE L'ENVOI** :
      - [ ] sur la base de TEST, avec un compte jetable : faire TRY IT 1 à 3 de la partie A (Présent à un événement +
            billet remis, événement « Sur invitation » d'un groupe publié, message + « Signaler » dans un groupe) ET créer
            un pot (Réglages › Pot commun › Nouveau pot commun, une dépense), puis **supprimer ce compte pour de vrai**
            (Réglages › Gérer mon compte › Supprimer mon compte) : la suppression doit passer, sans message de connexion ;
      - [ ] code fixe d'« Apple-test 2 » vérifié en s'y connectant (B2 dit « same fixed code as the first demo account ») ;
      - [ ] manifeste du build choisi : **17 types**, `NSPrivacyCollectedDataTypeSearchHistory` compris (§ 6) ; sinon
            l'ajouter avant l'archive, ou retirer Search History d'App Store Connect et de `app-store-connect.md` § 5 ;
      - [ ] `20261127110000` (suppression-blocage) en prod : sinon retirer du guide (B4.5, B7) et du tutoriel (3.5) la phrase
            « noté présent / ajouté en co-organisateur » par une personne bloquée, et régénérer le PDF ;
      - [ ] `20261127100000` en prod (co-organisateurs liés, aperçu d'un lien de groupe : B4.5, B7) ;
      - [ ] feuille « Signaler » : contact support@vendrediparty.ch et « 24 h » visibles (web : contact après l'envoi ;
            iPhone : « Traité sous 24 h · support@ », lot 6 iPhone d7d4fddf) ; sinon corriger B7 et régénérer le PDF ;
      - [ ] politique de confidentialité du **27 novembre 2026** (web et nouveau build, mot pour mot) ; guide PDF du 27.11 joint ;
      - [ ] `docs/app-store/topo-version-apple-27-11.md` relu (commits depuis 03357b5c).
- [ ] **Contrôle Apple, tour 2 (26.11) — LE JOUR DE L'ENVOI**, dans cet ordre :
      - [ ] se connecter avec **Apple-test** ET **Apple-test 2** (app TestFlight du build choisi) ; « Demandes (1) » visible
            chez Apple-test ;
      - [ ] dates de la démo : « Soirée démo Vendredi Party » le **12.12** (encore à venir), demande de message
            d'Apple-test 2 purgée vers le **20.12** (30 jours sans réponse) : si l'envoi glisse près de ces dates,
            REFAIRE la soirée (nouvelle date) et la demande avant d'envoyer ;
      - [ ] dépôt GitHub passé en **PRIVÉ** (ou `GITHUB_REPO` sur un dépôt privé à part) ;
      - [ ] App Privacy : les **17 types** du manifeste cochés (Search History compris), ni plus ni moins (§ 6 et `ios/appstore/app-store-connect.md` § 5) ;
      - [ ] clé `storage_secret_key` ajoutée dans le coffre Supabase de prod (contrôle : une ligne dans
            `private.chat_files_gc_runs`) ;
      - [ ] captures 6,9" et Duo refaites : les **4 onglets** (Jeux, Événements, Discussions, Réglages), **rien de vrai**
            (données fictives, aucune vraie personne), **rien d'alcool**, rien qui contredise la note (contenu
            présentable à tout public, comme pour une app 4+) ; ancienne **vidéo d'aperçu SUPPRIMÉE** (6,9" et Duo) ;
      - [ ] **nettoyage de la démo appliqué** (`supabase/prod/2026-11-26-demo-nettoyage-apply.sql`, migration `20261126110000`
            en prod) ; Billets QR allumés sur la Soirée démo (`tickets_enabled = true`), AUCUN billet remis d'avance : la partie A,
            B2 et B4.10 disent à Apple de répondre Présent puis « Remettre à tous les présents » (sinon corriger les
            trois et régénérer le PDF) ;
      - [ ] migrations **20261123090000**, **20261123110000**, **20261126100000**, **20261126110000**, **20261126120000**,
            **20261126130000**, **20261126140000**, **20261126150000** (déjà là le 27.11), **20261126160000**, **20261127090000**
            (déjà là le 27.11), **20261127100000** et, s'il est prêt, **20261127110000** en prod
            (`select version from supabase_migrations.schema_migrations where version like '2026112%'`) ; ordre : plan du 27.11 en haut ;
      - [ ] fonctions **send-push** ET **send-web-push** redéployées (dernière version de develop / main) ;
      - [ ] avant toute archive locale : `xcodegen` dans `ios/` (sinon le projet Xcode garde l'ancien manifeste et les
            anciens fichiers) ;
      - [ ] notes (3994 caractères) recopiées dans App Store Connect = `ios/appstore/review-notes.txt` ; guide PDF du
            tour 2 joint (B4.4 sans sous-liste, « Mes amis dans Party », Activité en direct facultative, Pot commun aux
            moyens de paiement cachés par défaut, « Signaler le groupe », Souvenirs dans « Not in this version »).
- [ ] **Contrôle Apple, tour 3 (26.11, textes de soumission)** :
      - [ ] Soirée démo : se connecter avec Apple-test, répondre **Présent**, carte **Billets QR** › **Remettre à tous
            les présents** › carte **Ton billet** et badge « Ajouter à l'app Cartes Apple » visibles (partie A TRY IT 1,
            B2, B4.10) ;
      - [ ] « Apple-test 2 » : le guide dit « same fixed code as the first demo account » : le VÉRIFIER en se
            connectant avec ce numéro et le code d'Apple-test le jour de l'envoi (sinon corriger B2 et régénérer le PDF) ;
      - [ ] captures 6,9" et Duo faites avec le binaire App Store, SANS la condition BETA. Le workflow
            `.github/workflows/ios-screenshots.yml` compile en Debug avec `PARTY_SWIFT_CONDITIONS=BETA` (Souvenirs,
            Pronos, Agenda, Zicou compilés) : ne PAS prendre son artefact. Sur le Mac, depuis `ios/` :
            ```
            xcodegen
            xcodebuild build -project Party.xcodeproj -scheme Party -configuration Debug \
              -sdk iphonesimulator -destination 'generic/platform=iOS Simulator' -derivedDataPath /tmp/PartyStore \
              CODE_SIGNING_ALLOWED=NO PARTY_SWIFT_CONDITIONS= PARTY_BUNDLE_SUFFIX= \
              PARTY_HOST=party.bobycharbon.ch PARTY_DISPLAY_NAME=Party ASSETCATALOG_COMPILER_APPICON_NAME=AppIcon
            cd .. && BUNDLE_ID=ch.bobycharbon.party ios/scripts/screenshots.sh \
              /tmp/PartyStore/Build/Products/Debug-iphonesimulator/Party.app <dossier des captures>
            ```
            `PARTY_SWIFT_CONDITIONS=` retire BETA (reste seulement DEBUG, qui ne sert qu'à `PARTY_DEBUG_JS`, le choix
            de l'onglet par le script) ; `PARTY_BUNDLE_SUFFIX=` donne la variante **STORE** (`AppConfig.storeLocked`,
            textes d'autorisation de l'App Store). Pour des captures à la main : mêmes réglages avec
            `-configuration Release` (`Release-iphonesimulator/Party.app`), en touchant soi-même les écrans ;
      - [ ] ce qu'elles montrent : la barre à **4 onglets** (Jeux, Événements, Discussions, Réglages), les **10 écrans**
            de `fiche-app-store.md` (09 = **Méninges** ou la **Salle de jeux**), comptes et données **fictifs** ; RIEN
            d'alcool, de Casino / Blackjack, de Zicou, de Souvenirs, de Pronos ni d'Agenda ; tout présentable comme pour
            une app **4+** (2.3.8) ;
      - [ ] **vidéo d'aperçu SUPPRIMÉE** dans App Store Connect (6,9" ET iPhone Duo), aucune nouvelle vidéo.
- [ ] Connexion testée avec « Apple-test 2 » (jamais connecté en prod au 25.11) et « Apple-test » le jour de l'envoi.
- [ ] App Store Connect › Business : adresse du compte développeur en France (Segny) et statut DSA (non-commerçant) à jour.

- [ ] `https://party.bobycharbon.ch/api/features` = `compagnon: false`, `discussions: true`, `invites_v2: true`, `bar: true` (web ; `false` avec « PartyStore »), `agenda: false`, `pronos: false`, `patates: false`
      (contrôlé le 16.11.2026). Rien ne doit changer pendant la revue.
- [ ] Corrections annoncées en place et visibles en prod (les notes les décrivent) : « Bloquer » masque aussitôt les
      messages (groupes, privés, événements) et prévient les modérateurs ; bar payant seulement sur un événement non public,
      bar offert partout ; articles tabac / drogues refusés ; classements des jeux sans gorgées ; CGU « 18 ans et plus » +
      section paiements (la section bar et celle de la confidentialité n'apparaissent que sur le web, jamais avec
      `?app=ios` ni dans le nouveau build).
- [ ] Données de démo prêtes en prod (encadré « À FAIRE AVANT ENVOI » de `notes-for-review.md`) : « Soirée démo »
      (Apple-test invité, aucun article alcoolisé ni texte « commander au bar »), groupe « Démo Apple » avec des messages, un message privé,
      si possible « Démo Apple · Sondage ».
- [ ] Le jour de l'envoi : se connecter avec le compte de démo sur un iPhone (app TestFlight du build choisi) et refaire
      le parcours « TRY IT » des notes : connexion, « Soirée démo » (réponse, qui vient, discussion), Discussions › « Démo Apple »,
      Jeux › Créer une salle › Quiz, Méninges.
- [ ] AUCUNE mise en prod, maintenance ou migration pendant la revue (24-48 h, plus si Apple pose une question).
- [ ] Plafond mensuel de l'IA loin d'être atteint (Réglages › Administration › Assistant IA).

## 2. Build et version

- [ ] **NOUVEAU build** compilé depuis `main` après la fusion de `fix-143` (site de production), configuration Release ;
      **jamais le build 216** (ses CGU, sa confidentialité, ses stats Purify, sa phrase caméra, ses emojis 🍻 🍷 et son action
      rapide Musique sont écrits dans le binaire), ni le build 7 du 26.10. Build « traité » (Processing terminé) dans TestFlight.
- [ ] Version **1.0.0** (`MARKETING_VERSION`), build choisi dans la section « Build » de la version.
- [ ] Export compliance : `ITSAppUsesNonExemptEncryption = false` dans Info.plist → aucune question (HTTPS du système
      seulement). Si App Store Connect la pose quand même : « Non » au chiffrement propre.
- [ ] Notifications : le build App Store doit être signé avec l'entitlement `aps-environment` = `production` (le fichier
      project.yml contient `development` ; l'export App Store le remplace normalement) — **À VÉRIFIER** une fois : une
      notification reçue sur l'app TestFlight.
- [ ] Appareils : iPhone seulement (sur iPad, mode compatible) ; iOS 16 minimum.

## 3. Fiche de la version (localisation Français)

- [ ] Nom : **Vendredi Party** · Sous-titre : **Événements, groupes et jeux**.
- [ ] Texte promotionnel, description, mots-clés : copiés de `fiche-app-store.md`.
- [ ] Nouveautés : rien (1re version, Apple n'affiche pas ce champ).
- [ ] URL d'assistance : `https://party.bobycharbon.ch/support` · URL de confidentialité :
      `https://party.bobycharbon.ch/events/privacy?app=ios` (ouvertes une fois dans Safari) · URL marketing : **vide** (décision du 25.11 :
      jamais vers le site et ses jeux, jamais `vendrediparty.ch` ; `metadata-fr.json` l'efface).
- [ ] Droits d'auteur : `© 2026 Ludovic Trombert`.
- [ ] Catégories : Style de vie / Divertissement.
- [ ] Captures 6,9" **refaites sur la prod avec le nouveau build** (celles du 25.11 et du 26.10 sont périmées) :
      liste et légendes dans `fiche-app-store.md`. Ni alcool mis en avant, ni « 🍻 Alcool », ni Casino / Blackjack, ni
      Zicou, ni vraie personne sans accord. **Sans l'onglet Musique** (caché depuis le 25.11) : les captures et l'aperçu
      vidéo actuels le montrent tous, la capture 09 « musique » est à remplacer (Méninges ou une autre). Aperçu vidéo :
      le SUPPRIMER (26.11 : aucune vidéo pour cet envoi).
- [ ] Icône 1024 inchangée.

## 4. App Review Information

- [ ] **Sign-in required** : coché.
- [ ] **User name** : `+41 79 000 09 99` (compte « Apple-test »).
- [ ] **Password** : le code fixe à 6 chiffres (Supabase prod › Authentication › Phone › Test OTP ; le fichier
      `~/sb-work/apple/demo.txt` n'existe pas sur ce Mac : le reprendre là où il est). **Jamais dans le dépôt.**
- [ ] **Notes** : la partie A de `notes-for-review.md` (3994 caractères, contrôle Apple tour 2, limite 4 000 ; = `ios/appstore/review-notes.txt`). La recopier aussi dans
      `ios/appstore/review-notes.txt` avant d'utiliser `tools/appstore_submit.py` (il envoie ce fichier), puis lancer
      `.venv/bin/python -m pytest -q tests/test_ios_app.py -p no:cacheprovider` (la partie A contient les mots exigés).
- [ ] **Pronos, Agenda, compagnon : PAS dans cette version** (jamais ouverts par ce build, quoi que dise le serveur) : les notes le disent (« Not in this version »),
      aucune section PRONOS, aucun prono de démo à préparer.
      Questionnaire : Simulated Gambling **None** tant qu'ils restent éteints.
      Aucun code de compte dans le dépôt.
- [ ] **Attachment** : `guide-revue-apple.pdf` (partie B de `notes-for-review.md`, mise en page A4, refait le 27.11 :
      présences à la main / sans compte en B4.5 ; à JOINDRE DE NOUVEAU, l'ancien du 26.11 est périmé),
      envoyé par `tools/appstore_submit.py attach` (workflow « App iOS → revue App Store », mode attach).
- [ ] **Contact** : prénom, nom, téléphone qui répond vraiment pendant la revue (+41…), e-mail `support@vendrediparty.ch`
      (s'envoyer un message de test) — **À FOURNIR** (rien dans le dépôt).

- [x] **Discussions v2 (18.11)** (fait le 20.11 : `supabase/prod/2026-11-20-demo-apple-test-2-apply.sql`, code fixe
      ajouté dans Test OTP) : la section DISCUSSIONS des notes (demandes de message, « Nouveau message », groupes
      privés non lus par l'administration, mini-profil, Signaler / Bloquer). **Deux comptes de démo** : « Apple-test » et
      « Apple-test 2 » (second numéro à code fixe, Supabase › Test OTP ; son numéro dans le guide PDF, son code saisi
      seulement dans App Store Connect ; jamais dans le dépôt), sans groupe ni événement privé en commun, avec une demande
      de message en attente d'« Apple-test 2 » vers « Apple-test » (encadré « À FAIRE », point 4 bis, de `notes-for-review.md`).
- [ ] Phrase Contacts (project.yml, `NSContactsUsageDescription`) : « … et te les proposer quand tu écris un nouveau
      message » — à vérifier dans le build choisi (Réglages iOS › Party › Contacts).

## 5. Classification par âge (questionnaire) → **18+**

- [ ] Parental Controls : Non · Age Assurance : Non
- [ ] Unrestricted Web Access : Non (seul le site de Party s'ouvre dans l'app ; le reste part dans Safari)
- [ ] User-Generated Content : Oui · Messaging and Chat : Oui · Social Media : Non · Advertising : Non
- [ ] Profanity or Crude Humor : Infrequent/Mild
- [ ] Horror/Fear Themes : None
- [ ] Alcohol, Tobacco, or Drug Use or References : **Infrequent/Mild** (25.11, refus 1.4.3 : plus aucun jeu à boire, ni
      gorgée, ni bar, ni Purify Test dans l'app App Store ; restent de rares mentions écrites par les membres)
- [ ] Mature or Suggestive Themes : **Frequent/Intense**
- [ ] **Override to Higher Age Rating : 18+** (Apple calcule 16+ avec ces réponses ; CGU et notes disent 18+ :
      `metadata-fr.json` › `ageRatingOverrideV2: EIGHTEEN_PLUS`, à contrôler à l'écran, sinon cocher à la main)
- [ ] Medical or Treatment Information : None · Health or Wellness Topics : None
- [ ] Sexual Content or Nudity : Infrequent/Mild · Graphic Sexual Content and Nudity : None
- [ ] Cartoon or Fantasy Violence : Infrequent/Mild · Realistic Violence : None · Prolonged Graphic or Sadistic Realistic
      Violence : None · Guns or Other Weapons : None
- [ ] Simulated Gambling : **None** (19.11 : Pronos et confettis éteints dans cette version ; Casino et Blackjack absents de
      l'app App Store) · Gambling : **Non** (aucun argent réel ni lot)
      · Loot Boxes : Non
- [ ] Contests : **Frequent/Intense** (choix du coordinateur du 16.11 : parties en compétition, classements et tableau de la
      soirée ; l'ancien `app-store-connect.md` disait « None ». Aucun lot ni tirage. La note reste 18+ dans les deux cas.)
- [ ] Résultat affiché : 18+. Si Apple calcule moins, choisir 18+.
- [ ] Tour 4 (25.11) : Profanity, Sexual Content et Cartoon Violence sont aussi dans `metadata-fr.json` (Infrequent/Mild,
      envoyés par `tools/appstore_submit.py`) : relire à l'écran qu'ils ne sont pas restés à « None ».

## 6. App Privacy (Confidentialité de l'app)

Pour chaque type : **lié à l'identité : oui · suivi : non · finalité : App Functionality seulement**. Pas de suivi
(aucun SDK tiers, pas d'ATT).

- [ ] Contact Info : **Name**, **Phone Number**
- [ ] Financial Info : **Payment Info** (IBAN et titulaire : organisateurs et pot commun ; 26.11) et **Other Financial
      Info** (liens Twint / Revolut / PayPal)
- [ ] Contacts : **Contacts** (empreintes chiffrées, non gardées ; déclaré par prudence ; 18.11 : aussi les suggestions
      de « Nouveau message », même type, même finalité App Functionality : **rien de neuf à cocher**, relire la description)
- [ ] User Content : **Photos or Videos**, **Audio Data** (messages vocaux des Discussions — nouveau), **Emails or Text
      Messages**, **Gameplay Content** (scores et stats de jeu), **Customer Support** (« Ton avis »), **Other User Content**
- [ ] Purchases : **Purchase History** (« J'ai payé » d'un événement ; commandes du bar sur le web seulement)
- [ ] Identifiers : **User ID**, **Device ID**
- [ ] Usage Data : **Product Interaction**
- [ ] Diagnostics : **Other Diagnostic Data**
- [ ] Search History : **Search History** (27.11 : recherches de personnes gardées 1 h ; texte d'une recherche de lieu
      envoyé à Google Places)
- [ ] Non collecté : e-mail, adresse, localisation, santé, navigation, données sensibles, crash / performance,
      publicité.
- [ ] Manifeste `ios/Party/PrivacyInfo.xcprivacy` (27.11) : **17 types**, exactement ceux ci-dessus (Name,
      Phone Number, Payment Info, Other Financial Info, Contacts, Photos or Videos, Audio Data, Emails or Text Messages,
      Gameplay Content, Customer Support, Other User Content, Purchase History, User ID, Device ID, Product Interaction,
      Other Diagnostic Data, **Search History**) : cocher les mêmes 17 dans App Store Connect, vérifier qu'ils sont dans le
      build choisi (`NSPrivacyCollectedDataTypeSearchHistory` : lot 6 iPhone, commit d7d4fddf, à fusionner avec ces textes).
- [ ] Textes d'autorisation (project.yml, annoncés par le coordinateur) : Caméra (`PARTY_USAGE_CAMERA_STORE`) « Pour scanner un QR
      code (code de la soirée ou d'un jeu, billet) ou un ticket du Pot commun, et prendre une photo de profil,
      d'événement, de groupe ou à envoyer dans une discussion. » (B8 du guide dit la même chose) ; Micro
      « Seulement quand tu touches le micro : pour enregistrer un message vocal dans une discussion, ou dicter un texte. »
      — À VÉRIFIER dans le build choisi.

## 7. Prix, disponibilité, statut

- [ ] Gratuit ; 26 pays francophones (liste à contrôler dans Prix et disponibilité).
- [ ] Statut **DSA** (Business › Digital Services Act) : déclarer **non-commerçant** (app gratuite, sans activité
      commerciale) ; sans déclaration, pas de distribution en France, Belgique et Luxembourg.
- [x] **Représentant légal dans l'UE** (décision de l'admin du 19.11) : Ludovic Trombert, établi en France (01), nommé
      dans la politique de confidentialité (web et iPhone, section UE) avec l'adresse et support@vendrediparty.ch.
      **25.11** : l'éditeur est établi en France, donc dans l'UE : aucun représentant à désigner ; la politique dit
      « éditeur établi en France », autorité de contrôle CNIL (le PFPDT pour les personnes en Suisse). Texte iPhone aligné
      (prochain build).
- [ ] Droits sur le contenu : « contient du contenu de tiers » = Oui, avec les droits (titres et pochettes lus par les API
      de musique, lieux par Google).
- [ ] Contrats « Apps gratuites » acceptés (Business) par le titulaire du compte.

## 7 bis. Pronos et confettis : plus tard, dans une version revue

- [ ] Pas dans cette version (19.11). Le jour où ils ouvrent : questionnaire Simulated Gambling **Frequent**, section
      PRONOS dans les notes, App Privacy (Gameplay Content avec les Pronos), CGU 2026-11-18 en prod, version **acceptée**,
      PUIS seulement PRONOS_ENABLED / PATATES_ENABLED en production (jamais avant).

## 8. Envoi

- [ ] « Ajouter pour vérification » › « Soumettre ». Publication : manuelle (conseillé) pour choisir le moment.
- [ ] Pendant la revue : surveiller l'e-mail et le Resolution Center ; valider vite les propositions d'Apple-test ;
      répondre en anglais, poliment, avec des captures si besoin.
- [ ] Après la revue : vérifier que le compte de démo et la « Soirée démo » existent encore ;
      mettre à jour `ios/appstore/app-store-connect.md` et `metadata-fr.json` (drapeaux discussions / bar allumés, Audio
      Data, Purchase History, Customer Support, Contests, URL marketing) — fichiers hors de ce dossier, non modifiés ici.

## 20.11.2026 : contrôle complet avant le nouvel envoi
- [x] En-tête (3840 × 1646) et Résultats de recherche (3840 × 2560) : `visuels/app-store-connect/` (zones sûres d'Apple).
- [ ] Captures iPhone Duo (10) : à REFAIRE sur le nouveau build (barre sans Musique, 25.11) ; vidéo d'aperçu (grand écran) : à SUPPRIMER (26.11).
- [x] Classification par âge : nouvelles questions « Position partagée » = Non, « Rencontres et relations » = Non (18+).
- [x] Confidentialité (15 types, sans suivi), conformité (DSA déclaré ; Chine hors distribution), prix et 26 pays,
      pas de Mac ni de Vision Pro, comptes de démo et codes fixes valables jusqu'à fin 2027.
- [ ] Accessibilité de l'app : facultatif, laissé vide (ne rien déclarer sans l'avoir vérifié).
