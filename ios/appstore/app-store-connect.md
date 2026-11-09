# App Store Connect : VendrediParty 1.0.0 (ch.bobycharbon.party)

À saisir ou à vérifier avant « Ajouter pour vérification ». Contrôlé dans le code le 09.11.2026 (develop, 99e16c1),
drapeaux de prod lus sur https://party.bobycharbon.ch/api/features : `compagnon: false`, `discussions: false`,
`invites_v2: true`.

## 1. Fiche de la version

| Champ | Valeur |
|---|---|
| Nouveautés (What's New) | **Rien** : 1.0.0 est la première version, Apple n'affiche pas ce champ. |
| Notes pour la revue (App Review Information › Notes) | Copier `ios/appstore/review-notes.txt` (3 791 caractères, limite 4 000). |
| URL d'assistance (Support URL) | `https://party.bobycharbon.ch/events/terms` (répond 200 ; le contact support@vendrediparty.ch y figure) |
| URL de confidentialité (Privacy Policy URL) | `https://party.bobycharbon.ch/events/privacy` (répond 200) |
| URL marketing | Vide. **Jamais** `vendrediparty.ch` : ce domaine n'a pas de site (aucun enregistrement A), seulement la messagerie. |
| Prix / disponibilité | Gratuit, Suisse seulement |
| Chiffrement | Aucun chiffrement propre (`ITSAppUsesNonExemptEncryption = false` dans Info.plist) |
| Contenu de tiers | Oui, avec les droits : titres et pochettes lus par les API Spotify, Deezer, YouTube, Apple Music ; lieux par Google Maps |

Les deux pages sont dessinées en JavaScript : `curl` reçoit une page sans texte, un navigateur affiche bien tout.
À ouvrir une fois dans Safari pour vérifier.

**Script d'envoi** : `tools/appstore_submit.py submit` exige `ios/appstore/whats-new-fr.txt` et envoie toujours
`whatsNew`. Pour 1.0.0, ce fichier n'existe pas (exprès) : le script s'arrêtera. Envoyer 1.0.0 à la main dans App
Store Connect, ou adapter le script (ne pas envoyer `whatsNew` à une première version) avant de le lancer.

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
| Password | Le code fixe à 6 chiffres : voir le fichier local `~/sb-work/apple/demo.txt` (ligne `code=`). Jamais dans le dépôt. |

À faire avant l'envoi :
- **Le compte est encore « Guest » en production** (lu le 09.11 : `role = guest`). Le passer en **Guest+** (Guest +
  « Écrire un avis ») : sans ça, « Ton avis », son IA et « Modifier » ne s'affichent pas, et les notes mentent.
- Guest+ n'a pas `events.publish_direct` : ses événements partent « pour validation ». Prévoir de valider (ou
  refuser) rapidement les propositions d'« Apple-test » pendant la revue.
- Vérifier que le code fixe marche encore en production (connexion sur un iPhone avec l'app App Store/TestFlight) et
  que le plafond mensuel de l'IA n'est pas atteint.
- Facultatif mais utile : la Musique ne s'essaie qu'avec une soirée en cours (code à 4 chiffres). Si une soirée tourne
  pendant la revue, on peut ajouter son code dans les notes (une ligne).

## 4. Classification par âge (questionnaire d'Apple, version 2025)

Résultat attendu : **18+**. Libellés anglais d'App Store Connect (ils peuvent varier un peu).

| Question | Réponse | Pourquoi |
|---|---|---|
| Parental Controls | Non | Aucun contrôle parental dans l'app |
| Age Assurance | Non | Pas de vérification d'âge (la note 18+ suffit) |
| Unrestricted Web Access | Non | La vue web ne charge que party.bobycharbon.ch (+ connexion Spotify, Supabase) ; tout autre lien part dans Safari (`AppConfig.isInternal`) |
| User-Generated Content | Oui | Événements, sondages, photos, profils, avis, titres demandés |
| Messaging and Chat | Oui | « Discussion » de chaque événement, messages à l'hôte (Musique) |
| Advertising | Non | Aucune publicité |
| Profanity or Crude Humor | Peu fréquent / léger | Questions « hot » de « Je n'ai jamais », « Qui de nous ? », Président (« … ou Trou du cul ») |
| Horror/Fear Themes | Aucun | |
| Alcohol, Tobacco, or Drug Use or References | **Fréquent / intense** | Catégorie « 🍻 Alcool » (Beer pong, Biskit Royal, Je n'ai jamais, Qui de nous ?, Roulette, Purify Test), mode gorgées de Pyramide, Quiz, Qui est le plus… ; catégorie Drogues de Purify Test |
| Mature or Suggestive Themes | Fréquent / intense | Questions « hot », Purify Test (🔞 Adultes) |
| Medical or Treatment Information | Aucun | |
| Health or Wellness Topics | Aucun | |
| Sexual Content or Nudity | Peu fréquent / léger | Questions écrites (Purify « Au lit », mode hot), aucune image |
| Graphic Sexual Content and Nudity | Aucun | |
| Cartoon or Fantasy Violence | Peu fréquent / léger | Néon Knockout (« Éjecte » les autres de l'arène), Braquage en miniature (cambriolage de musée, sans arme) |
| Realistic Violence | Aucun | |
| Prolonged Graphic or Sadistic Realistic Violence | Aucun | |
| Guns or Other Weapons | Aucun | |
| Simulated Gambling | **Aucun** | Casino et Blackjack masqués et refusés par le serveur dans l'app App Store (`STORE_APP_MARK`). « Roulette » = roue de prénoms, sans mise. À garder ainsi. |
| Contests | Aucun | Aucun concours ni tirage (Zicou éteint) |
| Gambling (argent réel) | Non | |
| Loot Boxes | Non | Coffres de Zicou absents (bêta seulement) |

## 5. Confidentialité de l'app (App Privacy)

Réponse générale : **des données sont collectées** ; **aucune n'est utilisée pour le suivi (tracking)** ; aucune
publicité, aucun SDK d'analyse. Pour chaque type ci-dessous : **lié à l'identité : oui**, **suivi : non**,
**finalité : App Functionality seulement**.

| Catégorie App Store Connect | Type | Ce que c'est dans Party | Dans PrivacyInfo.xcprivacy ? |
|---|---|---|---|
| Contact Info | Name | Prénom, nom, surnom du compte | oui |
| Contact Info | Phone Number | Connexion par SMS | oui |
| Financial Info | Other Financial Info | IBAN, titulaire, liens Twint/PayPal/Revolut de l'organisateur et du Pot commun | oui |
| Contacts | Contacts | Empreintes chiffrées des numéros du répertoire comparées (rien n'est gardé) | oui (prudent : non stocké, donc facultatif, mais le garder est plus sûr) |
| User Content | Photos or Videos | Photo de profil, d'événement, ticket du Pot commun, captures données à l'IA | oui |
| User Content | Emails or Text Messages | Messages de la Discussion d'un événement, messages à l'hôte | oui |
| User Content | Other User Content | Événements, sondages, votes, avis (et leurs modifications), titres demandés, dépenses | oui |
| User Content | **Gameplay Content** | Scores et stats de jeu liés au compte (Mes stats de jeu : Méninges, Purify Test, Quiz) | **non → à ajouter** |
| Identifiers | User ID | Identifiant du compte | oui |
| Identifiers | Device ID | Identifiant d'invité tiré au hasard, jeton de notifications APNs, inscription Wallet | oui |
| Usage Data | Product Interaction | Journal d'usage de l'IA (plafond mensuel), journal admin | oui |

Pas collecté (à laisser décoché) : e-mail, adresse postale, localisation (aucun CoreLocation ; les adresses d'événement
sont du contenu), santé, historique de navigation, historique de recherche (la recherche de titres n'est pas
gardée), données sensibles (les profils par catégorie de Purify Test ne sont jamais gardés, `purity.scrub`), audio
(la dictée est faite par Apple ; les messages vocaux n'existent que dans Discussions, éteintes), diagnostics, publicité.

**Écarts entre le manifeste et la réalité** (pour l'agent qui corrige `ios/Party/PrivacyInfo.xcprivacy`) :
1. **Gameplay Content manque** : les scores et stats de jeu sont gardés avec le compte.
2. **Purchase History, à trancher** : le statut « Payé » d'une place et les dépenses du Pot commun sont gardés avec le
   compte. Lecture prudente : le déclarer (Purchase History, App Functionality). Sinon, considérer que « Other
   Financial Info » + « Other User Content » le couvrent. Choisir, puis mettre le même dans le manifeste et ici.
3. Le texte du micro (`NSMicrophoneUsageDescription`) dit « ou t'enregistrer » : l'enregistrement (messages vocaux)
   n'est atteignable que dans Discussions, éteintes en production. Sans gravité, mais à reformuler à la prochaine
   version si Discussions reste éteint.
4. Le manifeste ne déclare plus `AudioData` : juste (rien n'est envoyé en audio dans l'app App Store).

Autres écarts de textes vus en passant (pas dans App Store Connect, mais un examinateur peut les lire) :
- L'écran natif **Réglages › Confidentialité** (`PrivacyView`, SignInView.swift) affiche « Mise à jour du 19 octobre
  2026 » et ne parle ni de l'IA (Anthropic), ni de GitHub, ni de Wallet, alors que la politique web est du
  9 novembre 2026. Il ne contient pas non plus de lien vers la politique complète.
- La politique web dit qu'on retire l'accord IA « dans Réglages › Confidentialité » ; dans l'app iPhone, cet endroit
  n'a pas de ligne IA : le retrait est dans **Réglages › Ton avis › Retirer mon accord** (c'est ce que disent la feuille
  d'accord et les notes). Un compte Guest (sans « Écrire un avis ») ne trouve donc aucun endroit pour retirer son accord.

## 6. Description, sous-titre, mots-clés

Je n'ai pas pu les lire (ils ne sont que dans App Store Connect). À contrôler à la main. Ne **jamais** y mettre :
- Zicou, Compagnon, mascotte, collection, coffre, échange d'objets (bêta seulement) ;
- Casino, Blackjack, roulette, mise, jetons, pari, jackpot (masqués dans l'app App Store) ;
- gorgées, shot, boire, alcool, « jeux à boire », Beer pong, « Je n'ai jamais » en vedette (ne pas pousser à boire, 1.4.3) ;
- Discussions, messages privés, messages vocaux (éteints en production) ;
- billets payants, « paiement dans l'app », « achète » (rien ne se paie dans l'app) ;
- noms de marques dans les mots-clés : Spotify, Sonos, YouTube, Twint, Apple Music, Claude (2.3.7) ;
- « gratuit », prix, classement des stores, mots-clés de concurrents.

Peut y être : soirées entre amis, événements, invitations, sondage de dates, file musicale de la soirée, quiz, jeux
de soirée, Purify Test, pot commun, notifications, Wallet, assistant pour créer un événement.

## 7. Captures

- Aucune capture du mode gorgées, de la catégorie « 🍻 Alcool », de Pyramide ou Beer pong, ni de Casino/Blackjack.
- Aucun Zicou (onglet, bulle, widget) : compiler les captures avec le site de production (compagnon éteint).
- Les captures en place datent du 26.10 (workflow « App iOS → captures App Store », onglets Jeux, Musique, Ton avis,
  Réglages). La capture **Jeux** montre la liste des jeux : vérifier que l'en-tête « 🍻 Alcool » n'y apparaît pas
  (c'est la 2e catégorie, juste sous « Chaque jour ») ; sinon la refaire en faisant défiler jusqu'à « Ambiance » ou
  « Jeux 3D ».
- Le workflow compile en Debug (condition BETA présente) : sans conséquence tant que le site de production a
  `compagnon: false`, mais vérifier qu'aucune bulle de Zicou n'apparaît.

## 8. Apple TV

L'app Apple TV (`ios/PartyTV`) a le même identifiant `ch.bobycharbon.party` : elle appartient au même
enregistrement App Store (achat universel). `appstore_submit.py` n'envoie que la plateforme iOS : pas de version
tvOS dans cette soumission. Les notes le disent en une ligne. Ne pas créer de version tvOS sans ses propres notes.
