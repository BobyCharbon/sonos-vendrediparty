# App Store Connect : VendrediParty 1.0.0 (ch.bobycharbon.party)

À saisir ou à vérifier avant « Ajouter pour vérification ». Contrôlé dans le code le 09.11.2026 (develop, 99e16c1),
drapeaux de prod lus sur https://party.bobycharbon.ch/api/features : `compagnon: false`, `discussions: true`,
`invites_v2: true`. **Mis à jour le 16.11.2026** : `discussions: true` en production ; `bar: false` pour l'app App Store
(« PartyStore », refus 1.4.3, 25.11 ; le web garde le bar) ; dossier complet et
à jour dans `docs/app-store/` (checklist-envoi.md fait foi pour App Privacy et le questionnaire d'âge).

## 1. Fiche de la version

| Champ | Valeur |
|---|---|
| Nouveautés (What's New) | **Rien** : 1.0.0 est la première version, Apple n'affiche pas ce champ. |
| Notes pour la revue (App Review Information › Notes) | Copier `ios/appstore/review-notes.txt` (3977 caractères, limite 4 000 ; à jour au 27.11.2026 (contrôle Apple, tour 5 : Pour ou contre sur les dilemmes de Party, « Plus tard » = Méninges seul, moyens de paiement des membres ajoutés d'office, numéro d'Apple-test 2) ; tour 3 : billet de démo à se remettre soi-même par « Remettre à tous les présents » ; tour 2 : « Mes amis dans Party », Activité en direct facultative de la Musique, Souvenirs dans « Not in this version », moyens de paiement du Pot commun cachés par défaut et « Signaler ») ; avant : 19.11.2026 : Discussions v2, groupes et discussion d'événement natifs (réservée à Présent / Peut-être) ; « Not in this version » : Pronos, Agenda, compagnon, Souvenirs, jamais ouverts par ce build). |
| URL d'assistance (Support URL) | `https://party.bobycharbon.ch/support` (page d'assistance : contact support@vendrediparty.ch, éditeur, questions fréquentes ; 25.11) |
| URL de confidentialité (Privacy Policy URL) | `https://party.bobycharbon.ch/events/privacy?app=ios` (texte de l'app App Store, sans bar ni Pronos ; 25.11) |
| URL marketing | Vide. **Jamais** `vendrediparty.ch` : ce domaine n'a pas de site (aucun enregistrement A), seulement la messagerie. |
| Prix / disponibilité | Gratuit, les 26 pays francophones de l’App Store (décision du 09.11.2026) |
| Chiffrement | Aucun chiffrement propre (`ITSAppUsesNonExemptEncryption = false` dans Info.plist) |
| Contenu de tiers | Oui, avec les droits : titres et pochettes lus par les API Spotify, Deezer, YouTube, Apple Music ; lieux par Google Maps |

Les deux pages sont dessinées en JavaScript : `curl` reçoit une page sans texte, un navigateur affiche bien tout.
À ouvrir une fois dans Safari pour vérifier.

**Script d'envoi** : `tools/appstore_submit.py submit` (workflow « App Store », mode submit) n'envoie pas de « Nouveautés » pour une première version. Il exige que le compte de démo soit déjà saisi dans App Store Connect (section 3).

## 2. Contact pour la revue (App Review Information › Contact)

À vérifier dans App Store Connect (le script le reprend de la revue précédente, rien n'est dans le dépôt) :
- Prénom, nom : la personne joignable pendant la revue.
- Téléphone : un numéro qui répond vraiment (format +41…).
- E-mail : support@vendrediparty.ch. Le domaine a bien un serveur de messagerie (MX `mta-gw.infomaniak.ch`) :
  s'envoyer un mail de test et vérifier qu'il arrive.

## 3. Sign-in information (compte de démo)

| Champ | Valeur |
|---|---|
| Sign-in required | Oui |
| User name | `+41 79 000 09 99` (compte « Apple-test ») |
| Password | Le code fixe à 6 chiffres : Supabase prod › Authentication › Providers › Phone › Test OTP. Jamais dans le dépôt. |

À faire avant l'envoi :
- Fait le 09.11 (prod) : « Apple-test » est **Guest+**, profil complet (prénom Apple, nom Review, photo neutre « AR »). La photo de profil est facultative depuis le 09.11.
- Guest+ n'a pas `events.publish_direct`, mais depuis les groupes libres (22.11) un événement réservé à un de ses
  groupes (« Démo Apple ») est publié aussitôt, sans validation du site. Seuls un événement public, Membres Vendredi
  Party ou « Sur invitation » sans groupe partent « pour validation » : prévoir de valider (ou refuser) rapidement ces
  propositions d'« Apple-test » pendant la revue.
- Vérifier que le code fixe marche encore en production (connexion sur un iPhone avec l'app App Store/TestFlight) et
  que le plafond mensuel de l'IA n'est pas atteint.
- Facultatif mais utile : la Musique (sans onglet dans l'app App Store depuis le 25.11) ne s'essaie qu'avec une soirée en
  cours, par Jeux › Code (6 chiffres). Si une soirée tourne pendant la revue, on peut ajouter son code dans les notes (une ligne).

## 4. Classification par âge (questionnaire d'Apple, version 2025)

Résultat attendu : **18+** (Apple calcule 16+ avec ces réponses : cocher « Override to Higher Age Rating : 18+ », `metadata-fr.json` › `ageRatingOverrideV2`). Libellés anglais d'App Store Connect (ils peuvent varier un peu).

| Question | Réponse | Pourquoi |
|---|---|---|
| Parental Controls | Non | Aucun contrôle parental dans l'app |
| Age Assurance | Non | Pas de vérification d'âge (la note 18+ suffit) |
| Unrestricted Web Access | Non | La vue web ne charge que party.bobycharbon.ch (+ connexion Spotify, Supabase) ; tout autre lien part dans Safari (`AppConfig.isInternal`) |
| User-Generated Content | Oui | Événements, sondages, photos, profils, avis, titres demandés |
| Messaging and Chat | Oui | « Discussion » de chaque événement, messages à l'hôte (Musique) |
| Advertising | Non | Aucune publicité |
| Profanity or Crude Humor | Peu fréquent / léger | Textes écrits par les membres ; dans l'app App Store, plus de questions « hot » ni de « Trou du cul » (Président : « Dernier ») |
| Horror/Fear Themes | Aucun | |
| Alcohol, Tobacco, or Drug Use or References | **Peu fréquent / léger** (25.11) | Refus Apple 1.4.3 : aucun jeu à boire, gorgée, bar ni Purify Test dans l'app App Store (app/store_app.py) ; restent de rares mentions écrites par les membres |
| Mature or Suggestive Themes | Fréquent / intense | Gardé par prudence (app 18+) : contenus des membres, dilemmes de Pour ou contre ; les questions « hot », le thème WTF et le Purify Test sont absents de l'app App Store depuis le 25.11 |
| Medical or Treatment Information | Aucun | |
| Health or Wellness Topics | Aucun | |
| Sexual Content or Nudity | Peu fréquent / léger | Gardé par prudence : textes des membres ; aucune image (Purify et mode hot absents de l'app App Store) |
| Graphic Sexual Content and Nudity | Aucun | |
| Cartoon or Fantasy Violence | Peu fréquent / léger | Néon Knockout (« Éjecte » les autres de l'arène), Braquage en miniature (cambriolage de musée, sans arme) |
| Realistic Violence | Aucun | |
| Prolonged Graphic or Sadistic Realistic Violence | Aucun | |
| Guns or Other Weapons | Aucun | |
| Simulated Gambling | **Aucun** (19.11) | Pronos et confettis ÉTEINTS dans cette version (PRONOS_ENABLED / PATATES_ENABLED absents en prod) ; Casino et Blackjack absents de l'app App Store. Passer à « Fréquent » dans la version qui ouvrira les confettis (voir plus bas). |
| Contests | **Fréquent** (16.11) | Quiz, classements entre joueurs (définition Apple « compete for rankings… trivia ») ; aucun tirage ni prix |
| Gambling (argent réel) | Non | Aucun argent réel ni lot dans l'app |
| Loot Boxes | Non | Coffres de Zicou absents (bêta seulement) |

Si Apple calcule moins que 18+, choisir 18+ (classification plus élevée) : la description et les notes disent 18+.
**À refaire avant** d'ouvrir en production iOS : Zicou (tirages, coffres, concours → Contests / Loot Boxes), Casino ou
Blackjack dans l'app App Store (Simulated Gambling), le Bar de la soirée (commandes de boissons), une publicité, un
accès web libre, une vérification d'âge. Les Discussions (chat) sont déjà déclarées (Messaging and Chat : Oui).

**Pronos et confettis : PAS dans cette version (décision de l'admin du 19.11 : gardés en test).** Le jour où ils
ouvriront, dans une version revue et dans cet ordre : questionnaire Simulated Gambling **Fréquent** ; section PRONOS dans
les notes (confettis sans valeur, partage de la piste, plafonds) ; App Privacy (Gameplay Content avec les Pronos) ; CGU
2026-11-18 en prod ; version **acceptée** ; seulement ensuite PRONOS_ENABLED / PATATES_ENABLED en production. Même chose
pour l'Agenda (phrase du calendrier à remettre à jour, App Privacy pour les demandes de rendez-vous).

## 5. Confidentialité de l'app (App Privacy)

Réponse générale : **des données sont collectées** ; **aucune n'est utilisée pour le suivi (tracking)** ; aucune
publicité, aucun SDK d'analyse. Pour chaque type ci-dessous : **lié à l'identité : oui**, **suivi : non**,
**finalité : App Functionality seulement**.

| Catégorie App Store Connect | Type | Ce que c'est dans Party | Dans PrivacyInfo.xcprivacy ? |
|---|---|---|---|
| Contact Info | Name | Prénom, nom, surnom du compte | oui |
| Contact Info | Phone Number | Connexion par SMS | oui |
| Financial Info | **Payment Info** | IBAN et titulaire du compte (organisateur, Pot commun) : coordonnées de paiement (26.11) | oui (`NSPrivacyCollectedDataTypePaymentInfo`, déjà dans le manifeste) ; à cocher dans App Store Connect |
| Financial Info | Other Financial Info | Liens Twint/PayPal/Revolut de l'organisateur et du Pot commun | oui |
| Contacts | Contacts | Empreintes chiffrées des numéros du répertoire comparées (rien n'est gardé) | oui (prudent : non stocké, donc facultatif, mais le garder est plus sûr) |
| User Content | Photos or Videos | Photo de profil, d'événement, ticket du Pot commun, captures données à l'IA | oui |
| User Content | Emails or Text Messages | Messages de la Discussion d'un événement, messages à l'hôte | oui |
| User Content | Other User Content | Événements, sondages, votes, avis (et leurs modifications), titres demandés, dépenses | oui |
| User Content | **Gameplay Content** | Scores et stats de jeu liés au compte (Mes stats de jeu : Méninges, Quiz) | oui (ajouté le 09.11) |
| Identifiers | User ID | Identifiant du compte | oui |
| Identifiers | Device ID | Identifiant d'invité tiré au hasard, jeton de notifications APNs, inscription Wallet | oui |
| Usage Data | Product Interaction | Journal d'usage de l'IA (plafond mensuel), journal admin | oui |
| Diagnostics | **Other Diagnostic Data** | Modèle de l'appareil, version d'iOS et de l'app joints à chaque avis (« Ton avis ») | oui (ajouté le 14.11) |
| User Content | **Audio Data** | Messages vocaux des Discussions | oui (16.11) |
| User Content | **Customer Support** | « Ton avis » (idées, bugs) | oui (16.11) |
| Purchases | **Purchase History** | « J'ai payé » d'un événement (et commandes du bar, sur le web seulement) | oui (16.11) |
| Search History | **Search History** | Recherches de personnes (« Ajouter quelqu'un » à un groupe, numéro exact ou nom) gardées 1 h pour limiter les abus ; texte tapé dans la recherche d'un lieu (envoyé à Google Places) | oui (27.11, `NSPrivacyCollectedDataTypeSearchHistory`, lot 6 iPhone) |

Pas collecté (à laisser décoché) : e-mail, adresse postale, localisation (aucun CoreLocation ; les adresses d'événement
et la ville du covoiturage sont du contenu), santé, historique de navigation, données sensibles (les profils par catégorie de Purify Test ne sont jamais gardés,
`purity.scrub`),
Crash Data / Performance Data, publicité.

**27.11.2026, fait foi** : le manifeste déclare exactement **17 types** : les 16 ci-dessous + **Search History**
(recherches de personnes gardées 1 h, texte d'une recherche de lieu envoyé à Google Places ; lié à l'identité, sans
suivi, App Functionality ; `NSPrivacyCollectedDataTypeSearchHistory`, ajouté par le lot 6 iPhone, commit d7d4fddf).
Cocher exactement ces 17 dans App Store Connect et vérifier qu'ils sont dans le build choisi.

**26.11.2026 (contrôle Apple, tour 2)** : le manifeste `ios/Party/PrivacyInfo.xcprivacy` déclare
exactement **16 types**, tous liés à l'identité, sans suivi, pour le fonctionnement de l'app : Phone Number, Name,
Photos or Videos, Contacts, Emails or Text Messages, Other User Content, Gameplay Content, User ID, Device ID, Product
Interaction, Other Diagnostic Data, Other Financial Info, **Payment Info**, Audio Data, Purchase History, Customer
Support (remplacé le 27.11 par les 17 ci-dessus ; le tableau les reprend tous). Historique :

**État au 14.11.2026** : le manifeste `ios/Party/PrivacyInfo.xcprivacy` déclare exactement ces 12 types (Phone,
Name, Photos, Contacts, Emails/Text, Other User Content, Gameplay Content, User ID, Device ID, Product Interaction,
Other Diagnostic Data, Other Financial Info), tous liés à l'identité, sans suivi, pour le fonctionnement de l'app.
Cocher **exactement** les mêmes dans App Store Connect (**Other Diagnostic Data est à cocher en plus**, 14.11).
**16.11.2026** : + Audio Data (vocaux des Discussions), Purchase History (commandes du bar liées au compte), Customer
Support (« Ton avis ») : 15 types le 16.11 (historique ; 17 depuis le 27.11, voir plus haut).
L'écran natif Réglages › Confidentialité est daté du 14 novembre 2026 comme la politique web, et l'accord IA s'y
retire (« IA de Party ») pour tous les comptes.

## 6. Description, sous-titre, mots-clés

Je n'ai pas pu les lire (ils ne sont que dans App Store Connect). À contrôler à la main. Ne **jamais** y mettre :
- Zicou, Compagnon, mascotte, collection, coffre, échange d'objets (bêta seulement) ;
- Casino, Blackjack, roulette, mise, jetons, pari, jackpot (masqués dans l'app App Store) ;
- gorgées, shot, boire, alcool, « jeux à boire », Beer pong, « Je n'ai jamais » en vedette (ne pas pousser à boire, 1.4.3) ;
- billets payants, « paiement dans l'app », « achète » (rien ne se paie dans l'app) ;
- noms de marques dans les mots-clés : Spotify, Sonos, YouTube, Twint, Apple Music, Claude (2.3.7) ;
- « gratuit », prix, classement des stores, mots-clés de concurrents.

Peut y être : soirées entre amis, événements, invitations, sondage de dates, discussions (allumées en prod depuis le
16.11), quiz, jeux de soirée, Méninges, pot commun, notifications, Wallet, assistant pour créer un événement. Plus de
file musicale ni de Purify Test (absents de l'app App Store depuis le 25.11).

## 7. Captures

- Aucune capture du mode gorgées, de la catégorie « 🍻 Alcool », de Pyramide ou Beer pong, ni de Casino/Blackjack.
- Aucun Zicou (onglet, bulle, widget) : compiler les captures avec le site de production (compagnon éteint).
- Les captures en place (26.10 et 25.11) montrent l'onglet Musique et l'ancienne liste des jeux : **toutes à refaire
  sur le nouveau build App Store** (26.11), avec les 4 onglets de l'app : **Jeux, Événements, Discussions, Réglages**.
  La capture 09 est remplacée par **Méninges** ou la **Salle de jeux**. Aucune catégorie « 🍻 Alcool », aucun jeu retiré.
- **Vidéo d'aperçu** (6,9" et iPhone Duo) : à **supprimer** dans App Store Connect (elle montre l'ancienne app).
- Le workflow `ios-screenshots.yml` compile en Debug AVEC la condition BETA (Souvenirs, Pronos, Agenda, Zicou compilés) :
  ne pas utiliser son artefact. Captures faites avec le binaire App Store sans BETA : `PARTY_SWIFT_CONDITIONS=` et
  `PARTY_BUNDLE_SUFFIX=` (variante STORE), commande complète dans `docs/app-store/checklist-envoi.md` (contrôle Apple, tour 3).

## 8. Apple TV

L'app Apple TV (`ios/PartyTV`) a le même identifiant `ch.bobycharbon.party` : elle appartient au même
enregistrement App Store (achat universel). `appstore_submit.py` n'envoie que la plateforme iOS : pas de version
tvOS dans cette soumission. Les notes le disent en une ligne. Ne pas créer de version tvOS sans ses propres notes.
