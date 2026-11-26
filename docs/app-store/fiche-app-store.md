# Fiche App Store — Vendredi Party (iOS 1.0.0, français)

Textes à saisir dans App Store Connect › l'app › version 1.0.0 › Localisation **Français**. Longueurs comptées par
script le 16.11.2026. Vérifié dans le code (develop) et sur la prod en lecture seule : `/api/features` =
`compagnon: false, discussions: true, invites_v2: true, bar: true`. Rien sur Zicou, Casino, Blackjack.

## Identité

| Champ | Valeur | Source / remarque |
|---|---|---|
| Nom (30 car.) | **Vendredi Party** (14) | Choix de l'admin du 16.11 (« Party » et « Party ! » seuls sont pris, commit 1580f6a). Secours si refusé : « Party ! Événements & soirées » (28). Sous l'icône : « Party ! » (`PARTY_DISPLAY_NAME`, project.yml). |
| Sous-titre (30 car.) | **Événements, groupes et jeux** (27 ; 25.11, refus 1.4.3 : plus « soirées ») | Pour une bande d'amis (25.11 : jamais « association »). |
| Identifiant de lot | `ch.bobycharbon.party` | project.yml (Release) |
| SKU | `party-ios` | ios/README.md |
| Version | 1.0.0 | `MARKETING_VERSION` |
| Langue principale | Français | |
| Catégorie principale | **Style de vie** (Lifestyle) | Organiser ses soirées et événements entre amis. |
| Catégorie secondaire | **Divertissement** (Entertainment) | Jeux de soirée. Ne pas prendre « Jeux » (exigences et classements propres aux jeux). |
| Prix | Gratuit | Aucun achat intégré |
| Disponibilité | Les 26 pays francophones de l'App Store (décision du 09.11.2026) | Liste exacte : À VÉRIFIER dans Prix et disponibilité |
| Droits d'auteur | **© 2026 Ludovic Trombert** | Éditeur : Ludovic Trombert, développeur indépendant établi en France (25.11 : aucune association) ; nommé dans la politique de confidentialité (PrivacyView, privacy.tsx) |

## URL

| Champ | Valeur | État |
|---|---|---|
| URL de confidentialité (obligatoire) | `https://party.bobycharbon.ch/events/privacy?app=ios` | « ?app=ios » : texte de l'app App Store, sans bar, Purify Test ni Pronos (25.11). Répond 200 (16.11) ; page dessinée en JavaScript : l'ouvrir une fois dans Safari pour vérifier le texte (mis à jour le 14.11, section bar annoncée par le coordinateur : À VÉRIFIER). |
| URL d'assistance (obligatoire) | `https://party.bobycharbon.ch/support` | Page d'assistance (25.11) : contact `support@vendrediparty.ch`, éditeur établi en France, questions fréquentes, liens vers les CGU et la politique en version app (`?app=ios`). |
| URL marketing (facultative) | **Vide** | Décision du 25.11 (refus 1.4.3) : jamais vers le site, qui garde ses jeux à boire. `metadata-fr.json` l'efface. Jamais `vendrediparty.ch` (aucun site, seulement la messagerie). |

## Texte promotionnel (170 car.)

> Organise tes événements en un geste : invitations par lien, sondage de dates, billets dans Cartes, covoiturage, discussions et salle de jeux pour toute la bande.

(161 caractères ; 25.11 : plus de bar ; modifiable à tout moment sans nouvelle version.)

## Description (4 000 car.)

```text
Vendredi Party réunit tes soirées et tes événements dans une seule app, pour toutes tes soirées entre amis : on s'organise, on s'invite et on joue ensemble.

ÉVÉNEMENTS
• Crée un événement avec le formulaire, ou décris-le simplement à l'assistant IA (texte, voix ou photo d'une affiche) : il prépare la fiche, tu vérifies et tu publies.
• Choisis qui le voit : public, sur invitation ou réservé à tes groupes.
• Invite avec un lien, pour une personne ou pour plusieurs. Chacun répond Présent, Peut-être ou Absent, en un geste.
• Pas encore de date ? Lance un sondage : chacun vote Oui, Si besoin ou Non, puis tu fixes la date.
• Ajoute l'événement à ton agenda : il se met à jour tout seul si l'organisateur change quelque chose.
• Covoiturage entre participants, liste « qui amène quoi » et discussion de l'événement.
• Billets QR dans l'app Cartes d'Apple, scannés à l'entrée par l'organisateur.
• Événement payant ? Chacun paie l'organisateur directement, en dehors de l'app (lien de paiement, virement ou sur place), puis le note dans Party.

DISCUSSIONS
Discute avec tes groupes et en message privé : texte, photos, messages vocaux. Chaque événement a sa discussion, réservée à ceux qui viennent. Signaler et bloquer en un geste, conditions d'utilisation claires, signalements lus et traités par l'éditeur sous 24 heures.

JEUX
Une salle de jeux pour toute la bande : un seul code, tout le monde rejoint, on vote pour le prochain jeu et l'animateur le lance. Quiz, Président, Braquage en miniature, Néon Knockout et bien d'autres, avec le tableau des scores de la soirée. En solo, Méninges fait chauffer ta mémoire, ta logique et ta vitesse chaque jour.

ET AUSSI
• Groupes avec photo, couleur et lien d'invitation réutilisable.
• Pot commun : qui a payé quoi, qui doit combien. Si l'organisateur d'un événement en a choisi un, répondre Présent (ou y être noté Présent par l'organisateur) t'y ajoute ; tu le quittes quand tu veux.
• Notifications réglables une à une, pause en un geste.
• Ton avis, pour les membres qui y ont accès : une idée, un bug ? Écris-le directement à l'équipe de Party.
• Depuis n'importe quelle app, Partager › Party crée un événement à partir d'un lien.

Connexion simple par numéro de téléphone et code SMS, sans mot de passe. Suppression du compte directement dans l'app.

Sans publicité, sans suivi publicitaire, sans achat intégré. Réservé aux personnes de 18 ans et plus.
```

Longueur : 2 408 caractères (limite 4 000 ; 26.11 : sans mini-sondages ni soirée Musique ; Pot commun : aussi noté Présent par l'organisateur). Aucun nom de marque tierce, aucun mot sur l'alcool, Zicou, Casino ou Blackjack.
« Sur place » est décrit sans promesse : les billets n'existent que si l'organisateur les allume. 26.11 : ni « mini-sondages »
(les comptes de démo ne peuvent pas en créer) ni soirée Musique / Activité en direct (impossible à essayer sans l'hôte) ;
modération = « signalements lus et traités par l'éditeur sous 24 heures » ; « Ton avis » écrit à l'équipe de Party. Refus 1.4.3 (25.11) : plus de bar dans la fiche ni dans l'app App Store.

## Mots-clés (100 car.)

```text
fête,soirée,événement,invitation,sondage,quiz,anniversaire,covoiturage,billet,groupe
```

(96 caractères ; 25.11 : « apéro » retiré, refus 1.4.3 ; sans espaces ; ni « party » ni « vendredi », déjà dans le nom ; aucune marque : ni Spotify, Sonos, YouTube, Twint, Revolut,
Claude, Apple — règle 2.3.7 ; aucun mot d'alcool.)

## Nouveautés de cette version

Version 1.0.0 = **première version** : Apple n'affiche pas ce champ (et `tools/appstore_submit.py` ne l'envoie pas).
Texte prêt pour la prochaine version (1.0.1), à mettre dans `ios/appstore/whats-new-fr.txt` le moment venu :

```text
• Discussions : tes groupes et tes messages privés, avec photos et messages vocaux.
• Paiement d'un événement plus clair : lien de paiement, billetterie ou sur place.
• Corrections et améliorations.
```

## Captures d'écran à faire

iPhone seulement (`TARGETED_DEVICE_FAMILY: 1`) : **6,9 pouces (1320 × 2868)**, de 3 à 10 captures, sur la PRODUCTION
(compagnon éteint) avec un compte de démo et des **données fictives** (aucun vrai nom, numéro ou visage sans accord).
Les captures en place (25.11, et celles du 26.10) montrent encore l'onglet Musique : **à refaire sur le nouveau build App Store** (26.11) (ni Événements, ni Discussions,
ni bar) et **sans l'onglet Musique**, caché dans l'app App Store depuis le 25.11. Règle 2.3.8 : captures adaptées à tous les publics même pour une app 18+ → **aucune boisson alcoolisée, aucune
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
| 7 | Discussion de l'événement (messages fictifs) | Fiche › Discussion | Toute la soirée se prépare ici |
| 8 | Discussions : une conversation de groupe fictive | Onglet Discussions | Discute avec tes groupes |
| 9 | Salle de jeux (tuiles d'« Ambiance » / « Jeux de cartes ») ou une question de Quiz | Jeux › Créer une salle | Une salle de jeux pour toute la bande |
| 10 | Méninges (Faire chauffer) | Jeux › Méninges | Fais chauffer tes méninges |

Aperçu vidéo : **aucun** pour cet envoi (26.11 : l'ancien, `docs/app-store/visuels/apercu/`, montre l'onglet Musique ;
le supprimer dans App Store Connect, 6,9 pouces et Duo). Icône 1024 × 1024 sans transparence : en place
(`ios/Party/Assets.xcassets/AppIcon.appiconset/icon-1024.png`, vérifiée : 1024 px, pas de canal alpha) ; ne jamais la changer.
