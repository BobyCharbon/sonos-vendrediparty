# Fiche App Store — Party entre amis (iOS 1.0.0, français)

Textes à saisir dans App Store Connect › l'app › version 1.0.0 › Localisation **Français**. Longueurs comptées par
script le 16.11.2026. Vérifié dans le code (develop) et sur la prod en lecture seule : `/api/features` =
`compagnon: false, discussions: true, invites_v2: true, bar: true`. Rien sur Zicou, Casino, Blackjack.

## Identité

| Champ | Valeur | Source / remarque |
|---|---|---|
| Nom (30 car.) | **Party entre amis** (16) | Déjà choisi (commit 1580f6a : « Party » et « Party ! » sont pris). Sous l'icône : « Party » (`PARTY_DISPLAY_NAME`, project.yml). |
| Sous-titre (30 car.) | **Soirées, invitations et jeux** (28) | |
| Identifiant de lot | `ch.bobycharbon.party` | project.yml (Release) |
| SKU | `party-ios` | ios/README.md |
| Version | 1.0.0 | `MARKETING_VERSION` |
| Langue principale | Français | |
| Catégorie principale | **Style de vie** (Lifestyle) | Organiser ses soirées et événements entre amis. |
| Catégorie secondaire | **Divertissement** (Entertainment) | Jeux de soirée, musique. Ne pas prendre « Jeux » (exigences et classements propres aux jeux). |
| Prix | Gratuit | Aucun achat intégré |
| Disponibilité | Les 26 pays francophones de l'App Store (décision du 09.11.2026) | Liste exacte : À VÉRIFIER dans Prix et disponibilité |
| Droits d'auteur | **© 2026 Ludovic Trombert** | Éditeur nommé dans la politique de confidentialité (PrivacyView, privacy.tsx) |

## URL

| Champ | Valeur | État |
|---|---|---|
| URL de confidentialité (obligatoire) | `https://party.bobycharbon.ch/events/privacy` | Répond 200 (16.11) ; page dessinée en JavaScript : l'ouvrir une fois dans Safari pour vérifier le texte (mis à jour le 14.11, section bar annoncée par le coordinateur : À VÉRIFIER). |
| URL d'assistance (obligatoire) | `https://party.bobycharbon.ch/events/terms` | Répond 200 ; conditions d'utilisation + contact `support@vendrediparty.ch` (MX Infomaniak en place). Une vraie page « Aide / contact » serait mieux : **À FOURNIR (facultatif)**. |
| URL marketing (facultative) | `https://party.bobycharbon.ch` | Répond 200 (c'est le site de Party lui-même). `metadata-fr.json` la donne, `app-store-connect.md` dit « vide » : choisir une seule réponse (**À DÉCIDER**). Jamais `vendrediparty.ch` (aucun site, seulement la messagerie). |

## Texte promotionnel (170 car.)

> Organise tes soirées en un geste : invitations par lien, sondage de dates, billets dans Cartes, covoiturage, bar de
> la soirée et salle de jeux pour toute la bande.

(163 caractères ; modifiable à tout moment sans nouvelle version.)

## Description (4 000 car.)

```text
Party réunit tes soirées entre amis dans une seule app : on s'organise, on s'invite, on joue et on choisit la musique ensemble. C'est l'app de notre association, Vendredi Party, ouverte à tous ceux qui organisent des soirées avec leurs amis.

ÉVÉNEMENTS
• Crée un événement avec le formulaire, ou décris-le simplement à l'assistant IA (texte, voix ou photo d'une affiche) : il prépare la fiche, tu vérifies et tu publies.
• Choisis qui le voit : public, sur invitation ou réservé à tes groupes.
• Invite avec un lien, pour une personne ou pour plusieurs. Chacun répond Présent, Peut-être ou Absent, en un geste.
• Pas encore de date ? Lance un sondage : chacun vote Oui, Si besoin ou Non, puis tu fixes la date.
• Ajoute l'événement à ton agenda : il se met à jour tout seul si l'organisateur change quelque chose.
• Covoiturage entre participants, liste « qui amène quoi », mini-sondages et discussion de l'événement.
• Billets QR dans l'app Cartes d'Apple, scannés à l'entrée par l'organisateur.
• Événement payant ? Chacun paie l'organisateur directement, en dehors de l'app (lien de paiement, virement ou sur place), puis le note dans Party.

BAR DE LA SOIRÉE
L'organisateur prépare la carte des boissons servies sur place. Chacun montre son QR au comptoir et voit ce qu'il doit à l'organisateur, à rembourser entre amis. Party ne vend rien et ne touche jamais l'argent.

DISCUSSIONS
Discute avec tes groupes et en message privé : texte, photos, messages vocaux. Signaler et bloquer en un geste, conditions d'utilisation claires et modération par notre équipe.

JEUX
Une salle de jeux pour toute la bande : un seul code, tout le monde rejoint, on vote pour le prochain jeu et l'animateur le lance. Quiz, Président, Braquage en miniature, Néon Knockout et bien d'autres, avec le tableau des scores de la soirée. En solo, Méninges fait chauffer ta mémoire, ta logique et ta vitesse chaque jour.

MUSIQUE
Pendant une soirée, scanne le QR de l'hôte ou entre son code : propose tes titres, ils rejoignent la file d'attente commune. Une notification te prévient quand ton titre arrive.

ET AUSSI
• Groupes avec lien d'invitation réutilisable.
• Pot commun : qui a payé quoi, qui doit combien.
• Notifications réglables une à une, pause en un geste.
• Ton avis : une idée, un bug ? Écris-le directement aux organisateurs.

Connexion simple par numéro de téléphone et code SMS, sans mot de passe. Suppression du compte directement dans l'app.

Sans publicité, sans suivi publicitaire, sans achat intégré. Réservé aux personnes de 18 ans et plus.
```

Longueur : 2 541 caractères (limite 4 000). Aucun nom de marque tierce, aucun mot sur l'alcool, Zicou, Casino ou Blackjack.
« Sur place » et le bar sont décrits sans promesse : la musique demande une soirée en cours chez un hôte équipé ; le bar
et les billets n'existent que si l'organisateur les allume.

## Mots-clés (100 car.)

```text
fête,soirée,événement,invitation,sondage,agenda,quiz,apéro,anniversaire,covoiturage,billet
```

(90 caractères, 95 octets ; sans espaces ; ni « party », ni « amis », déjà dans le nom ; aucune marque : ni Spotify, Sonos, YouTube, Twint, Revolut,
Claude, Apple — règle 2.3.7 ; aucun mot d'alcool.)

## Nouveautés de cette version

Version 1.0.0 = **première version** : Apple n'affiche pas ce champ (et `tools/appstore_submit.py` ne l'envoie pas).
Texte prêt pour la prochaine version (1.0.1), à mettre dans `ios/appstore/whats-new-fr.txt` le moment venu :

```text
• Bar de la soirée : la carte des boissons, ton QR au comptoir et ton solde dans Cartes.
• Discussions : tes groupes et tes messages privés, avec photos et messages vocaux.
• Paiement d'un événement plus clair : lien de paiement, billetterie ou sur place.
• Corrections et améliorations.
```

## Captures d'écran à faire

iPhone seulement (`TARGETED_DEVICE_FAMILY: 1`) : **6,9 pouces (1320 × 2868)**, de 3 à 10 captures, sur la PRODUCTION
(compagnon éteint) avec un compte de démo et des **données fictives** (aucun vrai nom, numéro ou visage sans accord).
Les captures en place datent du 26.10 (Jeux, Musique, Ton avis, Réglages) : **à refaire** (ni Événements, ni Discussions,
ni bar). Règle 2.3.8 : captures adaptées à tous les publics même pour une app 18+ → **aucune boisson alcoolisée, aucune
catégorie « 🍻 Alcool », aucun 🍻, ni Casino, ni Blackjack, ni Zicou**. Le script `ios/scripts/screenshots.sh` est en
partie périmé (sa capture « 2-games-3d » vise une section cachée depuis l'accueil des Jeux du 15.11) : À VÉRIFIER / refaire
à la main sur le simulateur.

| # | Écran | Comment l'obtenir | Légende (sur la capture) |
|---|---|---|---|
| 1 | Événements, liste « À venir » | Onglet Événements, 3-4 événements fictifs | Toutes vos soirées au même endroit |
| 2 | Fiche d'un événement (date, lieu, Présent / Peut-être / Absent, « Ajouter à mon agenda ») | Toucher un événement fictif | Réponds en un geste |
| 3 | « Créer avec l'IA », étape 1 (description tapée) | Événements › ✨ Avec l'IA | Décris ta soirée, l'IA prépare tout |
| 4 | Feuille « Inviter » (Une personne / Plusieurs, lien) | Carte Invités › + Inviter | Invite avec un simple lien |
| 5 | Sondage de dates (Oui / Si besoin / Non) | Pastille Sondages › un sondage fictif | Trouvez la date ensemble |
| 6 | Ton billet (QR + badge « Ajouter à Cartes Apple ») | Événement à billets, billet remis | Ton billet dans Cartes |
| 7 | Bar de la soirée côté invité (carte **sans alcool** : sirop, jus, eau…) | Ouvrir le bar › | Le bar de la soirée, sans prise de tête |
| 8 | Discussions : une conversation de groupe fictive | Onglet Discussions | Discute avec tes groupes |
| 9 | Salle de jeux (tuiles d'« Ambiance » / « Jeux de cartes ») ou une question de Quiz | Jeux › Créer une salle | Une salle de jeux pour toute la bande |
| 10 | Musique pendant une soirée (file avec des titres) ou Méninges | Musique (soirée en cours) / Jeux › Méninges | La musique choisie par tous |

Aperçu vidéo (facultatif) : mêmes règles. Icône 1024 × 1024 sans transparence : en place
(`ios/Party/Assets.xcassets/AppIcon.appiconset/icon-1024.png`, vérifiée : 1024 px, pas de canal alpha) ; ne jamais la changer.
