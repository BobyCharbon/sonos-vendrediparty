# Visuels App Store de Vendredi Party

Tout ce qu'il faut pour la page produit de l'App Store et le partage, au même endroit. Les captures sont de vraies
captures de l'app App Store (la BETA en est la copie exacte ; simulateur, configuration Release, mêmes réglages que la
production : `/api/features` de la prod lu le 28.11.2026, `bar: false` pour l'app App Store), posées dans un fond aux
couleurs de Party avec un titre. Données de démonstration inventées (aucune vraie personne, aucun visage), base de TEST
seulement. Refaites le 28.11.2026 (question 9 de l'admin) sur develop 9f359e26 : quatre onglets (Jeux, Événements,
Discussions, Réglages), jamais l'onglet Musique (il n'existe qu'après un code de soirée à 6 chiffres).

Jamais à l'écran : onglet Musique, bar, boisson, emoji 🍻🍺🥃🍸🍹🍷, jeu caché de l'app (`HIDDEN_GAMES` d'app/store_app.py :
Casino, Blackjack, Beer pong, Biskit, Purify, Pyramide, Je n'ai jamais, Qui de nous ?, Roulette, Tu me connais ?, Le Masque),
Zicou, Agenda, Pronos, confettis, Souvenirs, couverture IA, « ✨ IA » de la fiche, prénom tapé librement dans un jeu
(prénoms de la liste `PLAYER_NAMES` ou « Joueur N »), prix de l'app, logo Apple. Icône de l'app reprise telle quelle (`ios/Party/Assets.xcassets/AppIcon.appiconset/icon-1024.png`).

## Où les mettre dans App Store Connect

App Store Connect › Vendredi Party › version iOS › **Français** › *Aperçus et captures d'écran*.

### `captures-6.9/` : iPhone 6,9 pouces (obligatoire), 1320 × 2868, PNG sans transparence

Envoyés par `tools/appstore_submit.py screens` (ou glissés à la main) dans cet ordre (le maximum d'Apple ; les 3 premières s'affichent dans les résultats de recherche).
Copie identique dans `ios/appstore/screenshots/`, que `tools/appstore_submit.py screens <clé> <version>` envoie dans
l'ordre des noms.

| Fichier | Titre | Sous-titre | Écran montré |
|---|---|---|---|
| `01-evenements.png` | Toute la soirée sur ton téléphone | Tes événements, tes groupes et tes invitations | Événements : bulles des groupes, « Tu y vas », « On attend ta réponse » |
| `02-fiche.png` | Une fiche claire, tout est dedans | Qui vient, la date, le lieu et l’itinéraire | Fiche d'une soirée avec couverture, 10 présents · 2 peut-être |
| `03-jeux.png` | Une salle de jeux pour tout le groupe | Un code, tout le monde rejoint et on vote | Salle de jeux : code, QR, joueurs aux prénoms de la liste de l'app (Léa, Hugo, Inès, Tom, Zoé, Nathan, Chloé), « Le plus voté : Quiz » ; seuls les jeux de l'app |
| `04-discussion-evenement.png` | Discute avec ceux qui viennent | La discussion de la soirée, entre invités | Discussion native de l'événement (annonce épinglée, participants « Présent ») |
| `05-ia.png` | Décris ta soirée, l’IA prépare tout | Tu vérifies, tu invites et tu publies | « Créer avec l'IA », étape 1 « La soirée » |
| `06-sondage.png` | Fixe la date avec ta bande | Chacun vote : oui, si besoin ou non | Sondage de dates d'un week-end |
| `07-billet.png` | Ton billet dans ta poche | Un QR scanné à l’entrée par l’organisateur | Billet QR d'un événement à billets |
| `08-discussions.png` | Groupes, messages et soirées | Toutes tes conversations au même endroit | Discussions (Néon) : groupes avec emoji, couleur ou photo, messages privés, événement |
| `09-meninges.png` | Méninges, ton jeu solo | Vitesse, mémoire, logique : 5 mini-jeux par jour | Méninges (Jeux › Jeux solo) : Température, six domaines, L'Échauffement du jour |
| `10-pot-commun.png` | Les comptes sans prise de tête | Pot commun : qui a payé quoi, qui doit combien | Pot commun d'un week-end |

### `captures-duo/` : iPhone Duo, écran extérieur, 1398 × 2034, PNG sans transparence

Facultatif aujourd'hui (Apple : « Starting in April 2027, screenshots will be required for any app using the iOS 27.1 SDK
or later »). Mêmes 10 visuels, mêmes titres, dans le même ordre, faits sur le simulateur « iPhone Duo » (écran extérieur :
la barre d'onglets du système y est verticale, à droite). Copie dans `ios/appstore/screenshots-duo/`, que
`tools/appstore_submit.py screens` envoie aussi (jeu `APP_IPHONE_DUO`, anciennes captures retirées d'abord).
À savoir : sur cet écran, le grand titre « Événements » du module web passe à la ligne (« Événement / s ») ; c'est
l'écran réel de l'app, à corriger dans l'app si l'on veut une capture plus nette.

### Aperçu vidéo : aucun

L'ancien tour de l'app (25.11) montrait l'onglet Musique : il est retiré du dépôt et `tools/appstore_submit.py screens`
retire tous les aperçus vidéo de la fiche fr-FR (`appPreviews`, chaque `previewType`). `apercu.sh` reste pour en refaire
un plus tard (886 × 1920, 15 à 30 s, sans onglet Musique).

### `bannieres/` : en-têtes et partage (hors App Store Connect)

| Fichier | Taille | Usage |
|---|---|---|
| `en-tete-1920x1080.png` | 1920 × 1080 | En-tête promotionnel (site, présentation, réseaux) |
| `partage-1200x630.png` | 1200 × 630 | Image Open Graph du partage d'un lien (`og:image`) |
| `carre-1080x1080.png` | 1080 × 1080 | Publication carrée (Instagram, WhatsApp) |

Nom « Vendredi Party », sous-titre « Musique, jeux et soirées » (le sous-titre de la fiche App Store reste
« Événements, soirées et jeux », voir `docs/app-store/fiche-app-store.md`).

### `brut/` : captures brutes du simulateur (sans titre ni fond)

Les captures d'origine, 1320 × 2868 (et `brut/duo/` pour l'iPhone Duo), au cas où l'on voudrait refaire une maquette.

## Tailles exigées par Apple (vérifiées le 19.11.2026)

| Appareil | Captures | Aperçu vidéo |
|---|---|---|
| iPhone 6,9" (obligatoire) | 1320 × 2868 portrait | 886 × 1920 portrait |
| iPhone Duo, écran extérieur | 1398 × 2034 portrait | 886 × 1920 portrait |
| iPhone Duo, écran intérieur | 2007 × 2853 portrait | |

Jusqu'à 10 captures et 3 aperçus par taille ; images sans canal alpha (« Images can't include alpha channels or
transparencies ») ; aperçus de 15 à 30 secondes.

## Les refaire

Tout est dans `tools/appstore_visuels/` :

| Fichier | Rôle |
|---|---|
| `demo_assets.py` | Dessine les images de démonstration (photo de profil de Léa, couvertures d'événements, photo de groupe) : emoji sur dégradés, aucune photo de banque d'images. |
| `demo_data.py` | Crée (`create`) puis efface (`clean`) les données de démonstration sur la base de **TEST** (jamais la prod) : 12 personnes inventées, 5 événements, 4 groupes, messages, billet, pot commun. Une seule transaction qui efface les notifications qu'elle crée : aucun vrai membre de la base de test n'est prévenu. |
| `demo_only.js` | Injecté par `PARTY_DEBUG_JS` (build de recette `E2E_HOOKS` seulement, jamais l'App Store) : sur la liste, ne garde que les événements de démonstration (la base de TEST est partagée avec les recettes). Il ne cache plus rien d'autre : la salle de jeux est celle que le serveur sert à l'app. |
| `ia_draft.json` | Fiche figée de « Créer avec l'IA » (`PARTY_DEBUG_AI_EVENT`) : la vraie fenêtre de l'app, sans appel à l'IA. |
| `captures.sh` | Lance `ios/PartyUITests/VisuelsAppStoreUITests.swift` (Release) sur un simulateur : captures brutes, chacune avec son arbre d'accessibilité (`.txt`) ; le test échoue si un onglet Musique est à l'écran. |
| `apercu.sh` | Filme le simulateur pendant `testApercu` et produit l'aperçu 886 × 1920 (ffmpeg). |
| `maquettes.py` | Pose chaque capture dans sa maquette (titre, fond, téléphone) et dessine les bannières (Playwright / Chromium, police Bricolage Grotesque de Party). |

Étapes (depuis la racine du dépôt, avec `.venv`) :

```sh
# 1. Module Événements construit contre la base de TEST, puis serveur local avec les drapeaux de la prod
cd web/events && EXPO_PUBLIC_SUPABASE_URL=https://ewromqfsmcqsthftyhzm.supabase.co \
  EXPO_PUBLIC_SUPABASE_ANON_KEY="$(cat ~/.config/supabase-claude/test-publishable-key)" \
  npx expo export -p web --clear --output-dir /tmp/visuels-dist && cd ../..
# (post-traitement de web/events/scripts/postbuild.mjs sur /tmp/visuels-dist/index.html)
SUPABASE_URL=https://ewromqfsmcqsthftyhzm.supabase.co SUPABASE_ANON_KEY="$(cat ~/.config/supabase-claude/test-publishable-key)" \
  DATA_DIR=/tmp/visuels-data EVENTS_WEB_DIR=/tmp/visuels-dist PARTY_PUBLIC_URL=http://127.0.0.1:8741 \
  COMPAGNON_ENABLED=0 DISCUSSIONS_ENABLED=1 BAR_ENABLED=1 INVITES_V2_ENABLED=1 AGENDA_ENABLED=0 PRONOS_ENABLED=0 PATATES_ENABLED=0 \
  SOUVENIRS_ENABLED=0 COVERS_ENABLED=0 \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8741 --lifespan off &
# 2. Images et données de démonstration (base de TEST)
.venv/bin/python tools/appstore_visuels/demo_assets.py /tmp/visuels-assets
.venv/bin/python tools/appstore_visuels/demo_data.py create /tmp/visuels-assets
# 3. Simulateurs dédiés (jamais ceux des autres sessions ; le 28.11 : 237DCBCD « iPhone 18 Pro Max » et 95B164DA « iPhone Duo »)
xcrun simctl create "Party Visuels 6.9" "iPhone 17 Pro Max"      # → UDID 6,9"
xcrun simctl create "Party Visuels Duo" com.apple.CoreSimulator.SimDeviceType.iPhone-Duo \
  com.apple.CoreSimulator.SimRuntime.iOS-27-2-iPhone19-4         # → UDID Duo
tools/appstore_visuels/captures.sh <UDID 6,9"> 8741 docs/app-store/visuels/brut
tools/appstore_visuels/captures.sh <UDID Duo> 8741 docs/app-store/visuels/brut/duo
# 4. Maquettes, bannières, copie dans ios/appstore/screenshots(-duo)/
.venv/bin/python tools/appstore_visuels/maquettes.py docs/app-store/visuels/brut docs/app-store/visuels/brut/duo
# 5. (Plus d'aperçu vidéo pour l'instant ; apercu.sh <UDID 6,9"> 8741 <dossier> le referait.)
# 6. Toujours effacer les données de démonstration
.venv/bin/python tools/appstore_visuels/demo_data.py clean
```

La spectatrice « Léa » se connecte avec le numéro de test 079 000 02 10 (code fixe de la base de TEST). Changer un titre :
`SHOTS` dans `maquettes.py`. Changer un écran : `VisuelsAppStoreUITests.swift`.
