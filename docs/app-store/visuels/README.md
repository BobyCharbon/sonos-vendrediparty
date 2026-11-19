# Visuels App Store de Vendredi Party

Tout ce qu'il faut pour la page produit de l'App Store et le partage, au même endroit. Les captures sont de vraies
captures de l'app (simulateur, configuration Release comme l'App Store, mêmes réglages que la production :
`compagnon: false, discussions: true, invites_v2: true, bar: true`), posées dans un fond aux couleurs de Party avec un
titre. Données de démonstration inventées (aucune vraie personne, aucun visage), base de TEST seulement.

Jamais à l'écran : Zicou, Agenda, Pronos, confettis, Casino, Blackjack, catégorie « 🍻 Alcool », boisson alcoolisée,
prix de l'app, logo Apple. Icône de l'app reprise telle quelle (`ios/Party/Assets.xcassets/AppIcon.appiconset/icon-1024.png`).

## Où les mettre dans App Store Connect

App Store Connect › Vendredi Party › version iOS › **Français** › *Aperçus et captures d'écran*.

### `captures-6.9/` : iPhone 6,9 pouces (obligatoire), 1320 × 2868, PNG sans transparence

Glisser les 10 fichiers dans cet ordre (le maximum d'Apple ; les 3 premières s'affichent dans les résultats de recherche).
Copie identique dans `ios/appstore/screenshots/`, que `tools/appstore_submit.py screens <clé> <version>` envoie dans
l'ordre des noms.

| Fichier | Titre | Sous-titre | Écran montré |
|---|---|---|---|
| `01-evenements.png` | Toute la soirée sur ton téléphone | Tes événements, tes groupes et tes invitations | Événements : bulles des groupes, « Tu y vas », « On attend ta réponse » |
| `02-fiche.png` | Une fiche claire, tout est dedans | Qui vient, la date, le lieu et l’itinéraire | Fiche d'une soirée avec couverture, 10 présents · 2 peut-être |
| `03-jeux.png` | Une salle de jeux pour tout le groupe | Un code, tout le monde rejoint et on vote | Salle de jeux : code, QR, joueurs, « Le plus voté : Quiz » |
| `04-discussion-evenement.png` | Discute avec ceux qui viennent | La discussion de la soirée, entre invités | Discussion native de l'événement (annonce épinglée, participants « Présent ») |
| `05-ia.png` | Décris ta soirée, l’IA prépare tout | Tu vérifies, tu invites et tu publies | « Créer avec l'IA », étape 1 « La soirée » |
| `06-sondage.png` | Fixe la date avec ta bande | Chacun vote : oui, si besoin ou non | Sondage de dates d'un week-end |
| `07-billet.png` | Ton billet dans ta poche | Un QR scanné à l’entrée par l’organisateur | Billet QR d'un événement à billets |
| `08-discussions.png` | Groupes, messages et soirées | Toutes tes conversations au même endroit | Discussions (Néon) : groupes avec emoji, couleur ou photo, messages privés, événement |
| `09-musique.png` | La musique de la soirée, ensemble | Chacun propose ses titres, ils rejoignent la file | « Gérer la soirée » : file d'attente avec « ajouté par » |
| `10-pot-commun.png` | Les comptes sans prise de tête | Pot commun : qui a payé quoi, qui doit combien | Pot commun d'un week-end |

### `captures-duo/` : iPhone Duo, écran extérieur, 1398 × 2034, PNG sans transparence

Facultatif aujourd'hui (Apple : « Starting in April 2027, screenshots will be required for any app using the iOS 27.1 SDK
or later »). Mêmes 10 visuels, mêmes titres, dans le même ordre, faits sur le simulateur « iPhone Duo » (écran extérieur :
la barre d'onglets du système y est verticale, à droite). Copie dans `ios/appstore/screenshots-duo/` : pas encore envoyée
par `appstore_submit.py` (il ne gère que le 6,9") ; les glisser à la main dans la rubrique iPhone Duo.
À savoir : sur cet écran, le grand titre « Événements » du module web passe à la ligne (« Événement / s ») ; c'est
l'écran réel de l'app, à corriger dans l'app si l'on veut une capture plus nette.

### `apercu/` : aperçu vidéo (App Preview), 886 × 1920, 30 i/s, H.264, 29 s, piste son muette

| Fichier | Contenu |
|---|---|
| `01-tour-de-l-app-886x1920.mp4` | Tour de l'app filmé dans le simulateur : Événements, fiche de la soirée disco (réponse, discussion), Discussions, conversation des Lucioles, Jeux. |

Même rubrique d'App Store Connect, avant les captures (jusqu'à 3 aperçus par taille ; 886 × 1920 est accepté pour le
6,9" comme pour l'iPhone Duo). Image d'affiche : à choisir dans App Store Connect. Un seul aperçu pour l'instant.

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
| `demo_only.js` | Injecté par `PARTY_DEBUG_JS` (build de recette `E2E_HOOKS` seulement, jamais l'App Store) : sur la liste, ne garde que les événements de démonstration (la base de TEST est partagée avec les recettes) et cache la catégorie « 🍻 Alcool » de la salle de jeux. |
| `host_demo.json` | État figé de « Gérer la soirée » (`PARTY_DEBUG_HOST_DEMO`) : le simulateur n'a pas d'enceinte ; titres et artistes inventés. |
| `ia_draft.json` | Fiche figée de « Créer avec l'IA » (`PARTY_DEBUG_AI_EVENT`) : la vraie fenêtre de l'app, sans appel à l'IA. |
| `captures.sh` | Lance `ios/PartyUITests/VisuelsAppStoreUITests.swift` (Release) sur un simulateur : captures brutes. |
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
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8741 --lifespan off &
# 2. Images et données de démonstration (base de TEST)
.venv/bin/python tools/appstore_visuels/demo_assets.py /tmp/visuels-assets
.venv/bin/python tools/appstore_visuels/demo_data.py create /tmp/visuels-assets
# 3. Simulateurs dédiés (jamais ceux des autres sessions)
xcrun simctl create "Party Visuels 6.9" "iPhone 17 Pro Max"      # → UDID 6,9"
xcrun simctl create "Party Visuels Duo" com.apple.CoreSimulator.SimDeviceType.iPhone-Duo \
  com.apple.CoreSimulator.SimRuntime.iOS-27-2-iPhone19-4         # → UDID Duo
tools/appstore_visuels/captures.sh <UDID 6,9"> 8741 docs/app-store/visuels/brut
tools/appstore_visuels/captures.sh <UDID Duo> 8741 docs/app-store/visuels/brut/duo
# 4. Maquettes, bannières, copie dans ios/appstore/screenshots(-duo)/
.venv/bin/python tools/appstore_visuels/maquettes.py docs/app-store/visuels/brut docs/app-store/visuels/brut/duo
# 5. Aperçu vidéo
tools/appstore_visuels/apercu.sh <UDID 6,9"> 8741 docs/app-store/visuels/apercu
# 6. Toujours effacer les données de démonstration
.venv/bin/python tools/appstore_visuels/demo_data.py clean
```

La spectatrice « Léa » se connecte avec le numéro de test 079 000 02 10 (code fixe de la base de TEST). Changer un titre :
`SHOTS` dans `maquettes.py`. Changer un écran : `VisuelsAppStoreUITests.swift`.
