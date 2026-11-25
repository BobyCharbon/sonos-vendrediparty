# Checklist d'envoi à Apple — Vendredi Party 1.0.0

À cocher dans l'ordre, dans App Store Connect (appstoreconnect.apple.com › Apps › Vendredi Party, id 6827221948,
`ch.bobycharbon.party`). Textes prêts : `fiche-app-store.md` (fiche), `notes-for-review.md` (notes + guide joint),
`tutoriel-reviewer-fr.md` (relecture en français).

## 1. Avant tout : la production

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
      le renommer (« Boby ») dans l'app avant l'envoi, ou faire envoyer les messages de démo par un compte neutre.

- [ ] `https://party.bobycharbon.ch/api/features` = `compagnon: false`, `discussions: true`, `invites_v2: true`, `bar: true`, `agenda: false`, `pronos: false`, `patates: false`
      (contrôlé le 16.11.2026). Rien ne doit changer pendant la revue.
- [ ] Corrections annoncées en place et visibles en prod (les notes les décrivent) : « Bloquer » masque aussitôt les
      messages (groupes, privés, événements) et prévient les modérateurs ; bar payant seulement sur un événement non public,
      bar offert partout ; articles tabac / drogues refusés ; classements des jeux sans gorgées ; CGU « 18 ans et plus » +
      section bar / paiements ; politique de confidentialité avec une section bar.
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
- [ ] Captures 6,9" **refaites sur la prod** (celles du 26.10 sont périmées : ni Événements, ni Discussions, ni bar) :
      liste et légendes dans `fiche-app-store.md`. Ni alcool mis en avant, ni « 🍻 Alcool », ni Casino / Blackjack, ni
      Zicou, ni vraie personne sans accord. **Sans l'onglet Musique** (caché depuis le 25.11) : les captures et l'aperçu
      vidéo actuels le montrent tous, la capture 09 « musique » est à remplacer (Méninges ou une autre).
- [ ] Icône 1024 inchangée.

## 4. App Review Information

- [ ] **Sign-in required** : coché.
- [ ] **User name** : `+41 79 000 09 99` (compte « Apple-test »).
- [ ] **Password** : le code fixe à 6 chiffres (Supabase prod › Authentication › Phone › Test OTP ; le fichier
      `~/sb-work/apple/demo.txt` n'existe pas sur ce Mac : le reprendre là où il est). **Jamais dans le dépôt.**
- [ ] **Notes** : la partie A de `notes-for-review.md` (3991 caractères, limite 4 000 ; = `ios/appstore/review-notes.txt`). La recopier aussi dans
      `ios/appstore/review-notes.txt` avant d'utiliser `tools/appstore_submit.py` (il envoie ce fichier), puis lancer
      `.venv/bin/python -m pytest -q tests/test_ios_app.py -p no:cacheprovider` (la partie A contient les mots exigés).
- [ ] **Pronos, Agenda, compagnon : PAS dans cette version** (éteints sur le serveur) : les notes le disent (« Not in this version »),
      aucune section PRONOS, aucun prono de démo à préparer.
      Questionnaire : Simulated Gambling **None** tant qu'ils restent éteints.
      Aucun code de compte dans le dépôt.
- [x] **Attachment** : `guide-revue-apple.pdf` (partie B de `notes-for-review.md`, mise en page A4, refait le 20.11),
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

## 6. App Privacy (Confidentialité de l'app)

Pour chaque type : **lié à l'identité : oui · suivi : non · finalité : App Functionality seulement**. Pas de suivi
(aucun SDK tiers, pas d'ATT).

- [ ] Contact Info : **Name**, **Phone Number**
- [ ] Financial Info : **Other Financial Info** (IBAN, liens Twint / Revolut des organisateurs et du pot commun)
- [ ] Contacts : **Contacts** (empreintes chiffrées, non gardées ; déclaré par prudence ; 18.11 : aussi les suggestions
      de « Nouveau message », même type, même finalité App Functionality : **rien de neuf à cocher**, relire la description)
- [ ] User Content : **Photos or Videos**, **Audio Data** (messages vocaux des Discussions — nouveau), **Emails or Text
      Messages**, **Gameplay Content** (scores et stats de jeu), **Customer Support** (« Ton avis »), **Other User Content**
- [ ] Purchases : **Purchase History** (commandes du bar, « J'ai payé » d'un événement — nouveau)
- [ ] Identifiers : **User ID**, **Device ID**
- [ ] Usage Data : **Product Interaction**
- [ ] Diagnostics : **Other Diagnostic Data**
- [ ] Non collecté : e-mail, adresse, localisation, santé, navigation, recherche, données sensibles, crash / performance,
      publicité.
- [ ] Manifeste `ios/Party/PrivacyInfo.xcprivacy` : la copie de travail du 16.11 déclare bien les 15 types ci-dessus
      (Audio Data, Customer Support et Purchase History ajoutés, pas encore commités) : vérifier qu'ils sont dans le build
      choisi.
- [ ] Textes d'autorisation (project.yml, annoncés par le coordinateur) : Caméra « Pour scanner un QR code (code de la
      soirée, billet d'un événement, carte du bar d'un invité) et prendre une photo de profil ou d'événement. » ; Micro
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
- [ ] Après la revue : vérifier que le compte de démo existe encore et que le bar « Soirée démo » n'a pas été fermé ;
      mettre à jour `ios/appstore/app-store-connect.md` et `metadata-fr.json` (drapeaux discussions / bar allumés, Audio
      Data, Purchase History, Customer Support, Contests, URL marketing) — fichiers hors de ce dossier, non modifiés ici.

## 20.11.2026 : contrôle complet avant le nouvel envoi
- [x] En-tête (3840 × 1646) et Résultats de recherche (3840 × 2560) : `visuels/app-store-connect/` (zones sûres d'Apple).
- [x] Captures iPhone Duo (10) et vidéo d'aperçu (grand écran) déposées.
- [x] Classification par âge : nouvelles questions « Position partagée » = Non, « Rencontres et relations » = Non (18+).
- [x] Confidentialité (15 types, sans suivi), conformité (DSA déclaré ; Chine hors distribution), prix et 26 pays,
      pas de Mac ni de Vision Pro, comptes de démo et codes fixes valables jusqu'à fin 2027.
- [ ] Accessibilité de l'app : facultatif, laissé vide (ne rien déclarer sans l'avoir vérifié).
