# Checklist d'envoi à Apple — Party entre amis 1.0.0

À cocher dans l'ordre, dans App Store Connect (appstoreconnect.apple.com › Apps › Party entre amis, id 6827221948,
`ch.bobycharbon.party`). Textes prêts : `fiche-app-store.md` (fiche), `notes-for-review.md` (notes + guide joint),
`tutoriel-reviewer-fr.md` (relecture en français).

## 1. Avant tout : la production

- [ ] `https://party.bobycharbon.ch/api/features` = `compagnon: false`, `discussions: true`, `invites_v2: true`, `bar: true`
      (contrôlé le 16.11.2026). Rien ne doit changer pendant la revue.
- [ ] Corrections annoncées en place et visibles en prod (les notes les décrivent) : « Bloquer » masque aussitôt les
      messages (groupes, privés, événements) et prévient les modérateurs ; bar payant seulement sur un événement non public,
      bar offert partout ; articles tabac / drogues refusés ; classements des jeux sans gorgées ; CGU « 18 ans et plus » +
      section bar / paiements ; politique de confidentialité avec une section bar.
- [ ] Données de démo prêtes en prod (encadré « À FAIRE AVANT ENVOI » de `notes-for-review.md`) : « Soirée démo »
      (Apple-test invité, bar ouvert, articles sans alcool), groupe « Démo Apple » avec des messages, un message privé,
      si possible « Démo Apple · Sondage ».
- [ ] Le jour de l'envoi : se connecter avec le compte de démo sur un iPhone (app TestFlight du build choisi) et refaire
      le parcours « TRY IT » des notes : connexion, « Soirée démo » (réponse, billet, bar), Discussions › « Démo Apple »,
      Jeux › Créer une salle › Quiz, Méninges.
- [ ] AUCUNE mise en prod, maintenance ou migration pendant la revue (24-48 h, plus si Apple pose une question).
- [ ] Plafond mensuel de l'IA loin d'être atteint (Réglages › Administration › Assistant IA).

## 2. Build et version

- [ ] Dernier build TestFlight **compilé depuis `main`** (site de production), configuration Release, **pas le build 7**
      du 26.10. Build « traité » (Processing terminé) dans TestFlight.
- [ ] Version **1.0.0** (`MARKETING_VERSION`), build choisi dans la section « Build » de la version.
- [ ] Export compliance : `ITSAppUsesNonExemptEncryption = false` dans Info.plist → aucune question (HTTPS du système
      seulement). Si App Store Connect la pose quand même : « Non » au chiffrement propre.
- [ ] Notifications : le build App Store doit être signé avec l'entitlement `aps-environment` = `production` (le fichier
      project.yml contient `development` ; l'export App Store le remplace normalement) — **À VÉRIFIER** une fois : une
      notification reçue sur l'app TestFlight.
- [ ] Appareils : iPhone seulement (sur iPad, mode compatible) ; iOS 16 minimum.

## 3. Fiche de la version (localisation Français)

- [ ] Nom : **Party entre amis** · Sous-titre : **Soirées, invitations et jeux**.
- [ ] Texte promotionnel, description, mots-clés : copiés de `fiche-app-store.md`.
- [ ] Nouveautés : rien (1re version, Apple n'affiche pas ce champ).
- [ ] URL d'assistance : `https://party.bobycharbon.ch/events/terms` · URL de confidentialité :
      `https://party.bobycharbon.ch/events/privacy` (ouvertes une fois dans Safari) · URL marketing : décider (site Party
      ou vide, jamais `vendrediparty.ch`).
- [ ] Droits d'auteur : `© 2026 Ludovic Trombert`.
- [ ] Catégories : Style de vie / Divertissement.
- [ ] Captures 6,9" **refaites sur la prod** (celles du 26.10 sont périmées : ni Événements, ni Discussions, ni bar) :
      liste et légendes dans `fiche-app-store.md`. Ni alcool mis en avant, ni « 🍻 Alcool », ni Casino / Blackjack, ni
      Zicou, ni vraie personne sans accord.
- [ ] Icône 1024 inchangée.

## 4. App Review Information

- [ ] **Sign-in required** : coché.
- [ ] **User name** : `+41 79 000 09 99` (compte « Apple-test »).
- [ ] **Password** : le code fixe à 6 chiffres (Supabase prod › Authentication › Phone › Test OTP ; le fichier
      `~/sb-work/apple/demo.txt` n'existe pas sur ce Mac : le reprendre là où il est). **Jamais dans le dépôt.**
- [ ] **Notes** : la partie A de `notes-for-review.md` (3 807 caractères, limite 4 000). La recopier aussi dans
      `ios/appstore/review-notes.txt` avant d'utiliser `tools/appstore_submit.py` (il envoie ce fichier), puis lancer
      `.venv/bin/python -m pytest -q tests/test_ios_app.py -p no:cacheprovider` (la partie A contient les mots exigés).
- [ ] **Attachment** : la partie B de `notes-for-review.md` en PDF, sans l'encadré « À FAIRE » (le champ pièce jointe
      d'App Review Information : À VÉRIFIER qu'il est proposé ; sinon, mettre le guide sur une page et donner son lien
      dans les notes).
- [ ] **Contact** : prénom, nom, téléphone qui répond vraiment pendant la revue (+41…), e-mail `support@vendrediparty.ch`
      (s'envoyer un message de test) — **À FOURNIR** (rien dans le dépôt).

## 5. Classification par âge (questionnaire) → **18+**

- [ ] Parental Controls : Non · Age Assurance : Non
- [ ] Unrestricted Web Access : Non (seul le site de Party s'ouvre dans l'app ; le reste part dans Safari)
- [ ] User-Generated Content : Oui · Messaging and Chat : Oui · Social Media : Non · Advertising : Non
- [ ] Profanity or Crude Humor : Infrequent/Mild
- [ ] Horror/Fear Themes : None
- [ ] Alcohol, Tobacco, or Drug Use or References : **Frequent/Intense** (jeux à boire facultatifs, bar de la soirée)
- [ ] Mature or Suggestive Themes : **Frequent/Intense**
- [ ] Medical or Treatment Information : None · Health or Wellness Topics : None
- [ ] Sexual Content or Nudity : Infrequent/Mild · Graphic Sexual Content and Nudity : None
- [ ] Cartoon or Fantasy Violence : Infrequent/Mild · Realistic Violence : None · Prolonged Graphic or Sadistic Realistic
      Violence : None · Guns or Other Weapons : None
- [ ] Simulated Gambling : **None** (Casino et Blackjack absents de l'app App Store) · Gambling : Non · Loot Boxes : Non
- [ ] Contests : **Frequent/Intense** (choix du coordinateur du 16.11 : parties en compétition, classements et tableau de la
      soirée ; l'ancien `app-store-connect.md` disait « None ». Aucun lot ni tirage. La note reste 18+ dans les deux cas.)
- [ ] Résultat affiché : 18+. Si Apple calcule moins, choisir 18+.

## 6. App Privacy (Confidentialité de l'app)

Pour chaque type : **lié à l'identité : oui · suivi : non · finalité : App Functionality seulement**. Pas de suivi
(aucun SDK tiers, pas d'ATT).

- [ ] Contact Info : **Name**, **Phone Number**
- [ ] Financial Info : **Other Financial Info** (IBAN, liens Twint / Revolut des organisateurs et du pot commun)
- [ ] Contacts : **Contacts** (empreintes chiffrées, non gardées ; déclaré par prudence)
- [ ] User Content : **Photos or Videos**, **Audio Data** (messages vocaux des Discussions — nouveau), **Emails or Text
      Messages**, **Gameplay Content**, **Customer Support** (« Ton avis » — nouveau), **Other User Content**
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
- [ ] Droits sur le contenu : « contient du contenu de tiers » = Oui, avec les droits (titres et pochettes lus par les API
      de musique, lieux par Google).
- [ ] Contrats « Apps gratuites » acceptés (Business) par le titulaire du compte.

## 8. Envoi

- [ ] « Ajouter pour vérification » › « Soumettre ». Publication : manuelle (conseillé) pour choisir le moment.
- [ ] Pendant la revue : surveiller l'e-mail et le Resolution Center ; valider vite les propositions d'Apple-test ;
      répondre en anglais, poliment, avec des captures si besoin.
- [ ] Après la revue : vérifier que le compte de démo existe encore et que le bar « Soirée démo » n'a pas été fermé ;
      mettre à jour `ios/appstore/app-store-connect.md` et `metadata-fr.json` (drapeaux discussions / bar allumés, Audio
      Data, Purchase History, Customer Support, Contests, URL marketing) — fichiers hors de ce dossier, non modifiés ici.
