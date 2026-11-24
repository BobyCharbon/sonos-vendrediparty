# Album photos (avis e153dce1c115) — regard « bon sens »

Demande : une boîte de dépôt dans un groupe, photos ajoutées depuis la pellicule, qualité ORIGINALE (pas floue),
photos seulement pour l'instant.

Ce qui existe déjà et pèse sur le concept (lu dans le dépôt) :
- Discussions : photos dans `chat-photos` (8 Mo max, JPEG 0,82 recompressé sur iPhone, `ChatModels.swift:507`),
  effacées après 90 jours (« 📷 Photo expirée »). Ce n'est donc PAS un endroit pour garder.
- Souvenirs (branche `souvenirs`) : appareil jetable de la soirée, 3 photos, 1600 px, EXIF/GPS retirés, dépôt
  uniquement par le serveur avec ticket, story de 24 h, 13 mois. C'est volontairement « petit et éphémère ».
- Base = Supabase hébergé (`*.supabase.co`), serveur Party = homelab. Le stockage se paie chez Supabase, la bande
  passante d'envoi passe par la connexion de la maison si on fait transiter les fichiers par le serveur.

L'album est le troisième objet, celui qui manque : **grand, en qualité d'origine, qui dure**. Il faut le garder bien
distinct des deux autres pour que personne ne se demande « où sont les photos ? ».

---

## 1. Le concept en une phrase

**Chaque événement a son album ; la page du groupe montre les albums de ses événements, plus un album « En vrac »
du groupe pour ce qui n'a pas de soirée.**

Pourquoi pas seulement le groupe (comme l'admin l'a dit) : dans un groupe actif, 6 soirées × 150 photos = un mur
de 900 photos sans repère. L'événement est le rangement naturel (« les photos du paintball »), il porte déjà la
date, le lieu, la liste des présents. Pourquoi pas seulement l'événement : un groupe a aussi des photos sans soirée
(vacances, anniversaire hors Party) — d'où « En vrac ».

- Événement de groupe (réservé au groupe, ou qui réunit ses invités dans un groupe, `private.group_event_ids`) :
  l'album EST celui de l'événement ; la page du groupe l'affiche dans un onglet « Photos » sous forme de rangées
  « Paintball · 14 nov. · 132 photos ». Une seule copie, deux portes d'entrée. Jamais de doublon groupe/événement.
- Événement public ou sur invitation, sans groupe : l'album vit sur la fiche seulement.
- Ce n'est PAS une option à allumer (contrairement aux Souvenirs) : un album vide ne coûte rien et ne se voit pas
  (« Ajouter les premières photos » seulement à partir du début de l'événement). Une seule option : l'organisation
  peut le couper (`events.album_enabled`, allumé par défaut, l'IA n'y touche pas). À vérifier par `exigence-apple`.

## 2. Qui ajoute, qui voit, qui supprime

| | Album d'événement | « En vrac » du groupe |
|---|---|---|
| Ajoute | Présent / Peut-être + organisation (comme `souvenir_circle`), dès le début de l'événement, sans fin | Tout membre |
| Voit | Ceux qui voient la fiche ET ont répondu Présent/Peut-être, organisation, + membres du groupe si événement de groupe | Membres |
| Supprime | L'auteur (ses photos) ; l'organisation (n'importe laquelle) ; modération | L'auteur ; qui gère le groupe ; modération |

- Événement **public** : l'album n'est jamais public. Seuls les participants le voient (sinon n'importe qui
  regarde les photos d'une soirée privée chez quelqu'un). Pas de lien public de l'album en v1.
- Profil complet + CGU avant la 1re photo (contenu de joueur, Apple 1.2), filtre, « Signaler » (motif « Je suis sur
  la photo et je ne veux pas qu'elle soit montrée » repris des Souvenirs : masquée aussitôt), blocage dans les deux
  sens (comme Souvenirs).
- Pas de « J'aime », pas de commentaires en v1 : ça transforme l'album en deuxième discussion à modérer.
- **Auteur qui quitte le groupe** : ses photos RESTENT (c'est le souvenir de tous ; WhatsApp et Google Photos font
  pareil), il peut encore les supprimer lui-même depuis « Mes photos partagées » (Réglages) même s'il n'a plus accès
  à l'album. Le dire en une ligne au moment de quitter : « Tes 23 photos restent dans l'album. Les retirer ? ».
- **Compte supprimé** : TOUTES ses photos partent (RGPD, règle du projet « tout part avec la suppression du
  compte »). Pas de discussion.
- **Personne retirée par l'organisation / bloquée** : ses photos restent mais elle ne voit plus l'album ; bloquée :
  ses photos sont cachées à celui qui bloque (même logique que les messages).

## 3. Plafonds et durée

Ordre de grandeur réaliste : photo iPhone HEIC 1,5–3 Mo (48 MP : 5–8 Mo), JPEG Android 3–6 Mo.
Une bonne soirée à 20 personnes ≈ 150–400 photos ≈ **0,5 à 1,5 Go**. Les vidéos seraient ×20 : le « pas de vidéos »
de l'admin est juste.

Plafonds proposés (simples, affichés seulement quand on les touche) :
- **25 Mo par fichier** (couvre le 48 MP et les RAW-JPEG ; refuse le ProRAW DNG de 75 Mo : « trop lourd »).
- **300 photos par personne et par album**, **1 500 par album**, **3 Go par album**.
- Groupe : **5 000 photos** en tout (« En vrac » + albums de ses événements ne comptent qu'une fois : par album).
- Débit : 500 photos / personne / jour (frein aux abus, invisible en usage normal).

Durée : **garder tant que le groupe / l'événement existe**, avec une purge : album sans aucune ouverture depuis
**24 mois** → prévenir l'organisation (« Télécharger avant le … ») puis effacer 30 jours après. Événement supprimé :
album supprimé (après « Télécharger tout » proposé dans la confirmation). Groupe supprimé : « En vrac » supprimé.
Ne pas reprendre les 13 mois des Souvenirs : on ne dépose pas des photos d'origine pour les perdre dans un an.

**Le serveur tiendra-t-il ?** Le vrai coût est le stockage Supabase, pas le serveur Party :
- Il faut que les fichiers n'aillent PAS par le homelab : envoi direct du téléphone vers Supabase Storage
  (téléversement repris `TUS` / resumable, ticket signé par photo délivré par la base), sinon chaque photo traverse
  deux fois la connexion de la maison. Le dépôt direct a été interdit aux Souvenirs à cause de l'EXIF/GPS : voir §7.
- Prévoir un tableau « stockage utilisé » pour l'admin et un interrupteur `ALBUMS_ENABLED`, puis regarder le compteur
  après un mois de vrai usage. À vérifier par l'admin : l'offre Supabase (Free 1 Go = impossible ; Pro = 100 Go
  inclus puis payé au Go, et la sortie de données pour « Tout télécharger » est aussi comptée).
- Miniatures obligatoires (sinon la grille charge 200 × 3 Mo en 4G) : générées une fois (≈ 400 px et ≈ 2048 px),
  la grille et la visionneuse ne lisent jamais l'original ; l'original ne part qu'au « Télécharger ».

## 4. Notifications sans spammer

- Une seule notification **groupée et retardée** : la 1re photo arme un minuteur de 30 min ; à la fin, un seul
  « 📷 Ludo et 3 autres ont ajouté 47 photos · Paintball ». Nouvelle photo pendant le délai : rien de plus.
  Au plus **une par album et par 6 h**, et jamais la nuit (22 h–8 h, heure de Suisse : reportée au matin).
- Jamais à l'auteur lui-même ; jamais pendant que la personne regarde l'album.
- Interrupteur `notification_prefs.albums` (web + iPhone), `may_receive_push`, blocage respectés.
- Le lendemain de l'événement (une fois, seulement s'il y avait au moins 1 photo OU si l'organisation l'a demandé) :
  « Tu as des photos d'hier soir ? Ajoute-les à l'album » — aux Présents seulement, interrupteur à part, jamais de
  relance. C'est le moment où les gens ont la pellicule pleine.
- Pastille « 12 nouvelles » sur l'onglet Photos du groupe / la carte de la fiche (pas de push pour ça).

## 5. Lien avec les Souvenirs

Oui, mais une proposition, pas un transfert automatique :
- À la fin de la story (et sur l'écran « Mes souvenirs »), une carte « 📷 Tu as d'autres photos de la soirée ?
  Ajoute-les à l'album » → ouvre le sélecteur de la pellicule. C'est le pont naturel.
- Les photos Souvenirs elles-mêmes ne vont PAS dans l'album d'office : elles ont été prises avec une promesse
  différente (24 h, « garder » facultatif, 1600 px). Bouton « Ajouter à l'album » sur SES propres photos Souvenirs
  seulement (jamais celles des autres) — en 1600 px, c'est dit (« version Souvenirs, pas l'original »). Optionnel v2.
- Sur la fiche, ordre : Souvenirs (pendant / juste après) puis Album (après). Deux noms, deux icônes : 📸 jetable,
  🖼️ album. Ne jamais appeler l'album « Souvenirs ».

## 6. Lien avec la discussion

- Une photo envoyée dans la discussion ne va PAS dans l'album d'office : on envoie dans une discussion des captures,
  des mèmes, des photos de ticket… L'album se polluerait, et la discussion recompresse (JPEG 0,82) : l'album
  perdrait sa promesse « qualité d'origine ».
- Appui long sur une photo de la discussion → « Ajouter à l'album » (par son auteur seulement) : copie la version
  de la discussion, dit « qualité de la discussion ».
- Dans la discussion, une seule bulle système groupée par lot : « 🖼️ Ludo a ajouté 47 photos à l'album » (tapable,
  ouvre l'album à ces photos). Une par lot, jamais une par photo. Pas de notification en plus de celle du §4.
- Le sélecteur photo de la discussion propose, au-delà de 5 photos choisies : « Plutôt les mettre dans l'album ? »
  (en qualité d'origine). C'est la meilleure éducation possible, sans règle à lire.

## 7. Cas de la vraie vie

- **200 photos d'un coup en 4G** : file d'attente locale, 3 envois en parallèle, téléversement repris (TUS) : une
  coupure reprend où elle s'était arrêtée, pas depuis zéro. iPhone : `URLSession` d'arrière-plan pour continuer
  écran verrouillé ; barre « 87 / 200 · tu peux fermer l'app » ; les photos apparaissent une à une (pas d'attente
  de la fin). Option « Attendre le Wi-Fi » proposée seulement au-delà de 50 photos en données mobiles. Web : la page
  doit rester ouverte, le dire.
- **Doublons** : empreinte SHA-256 de l'original calculée sur le téléphone avant envoi ; la base refuse le même
  fichier deux fois dans un album (« 12 déjà dans l'album, ignorées ») — pas d'envoi inutile en 4G. Même photo
  envoyée par deux personnes (AirDrop) : idem. Les « presque doublons » (rafale) : pas en v1.
- **Orientation EXIF** : l'original garde sa balise d'orientation (on ne touche pas aux pixels) ; les miniatures et
  la version d'écran sont redressées à la génération (`ImageOps.exif_transpose`, déjà utilisé dans souvenirs.py).
  Bouton « Pivoter » par l'auteur = on change seulement la balise / une rotation enregistrée, jamais un réencodage.
- **GPS / EXIF** : qualité d'origine ≠ position du domicile. Retirer GPS (et numéro de série de l'appareil) SANS
  réencoder : iPhone le fait avant l'envoi (PHPicker + réécriture des métadonnées avec `CGImageDestination`,
  `kCGImageMetadataShouldExcludeGPS`, copie sans recompression) ; web/Android : `exiftool`-like côté serveur sur un
  travail en tâche de fond qui lit le fichier déposé en « quarantaine » et ne le rend visible qu'après nettoyage
  (album marque la photo `processing`). Ainsi le dépôt peut être direct vers Supabase sans laisser fuir le GPS :
  personne ne lit un fichier non nettoyé. Date de prise de vue gardée (sert au tri).
- **HEIC** : on garde le HEIC d'origine (c'est LA qualité d'origine iPhone) ; la version d'écran est en JPEG/WebP,
  lisible par Android, Windows et tous les navigateurs. Serveur : `pillow-heif` (libheif) pour lire le HEIC.
  « Télécharger » sur Android / web : proposer « Original (HEIC) » ou « Compatible (JPEG pleine taille) ».
  Attention : le sélecteur iOS convertit en JPEG par défaut dans Safari et certains pickers — iPhone app :
  `PHPickerConfiguration.preferredAssetRepresentationMode = .current` pour recevoir l'original.
- **Photos « Live » et rafales** : on ne prend que l'image fixe. Captures d'écran : acceptées (pas de tri magique).
- **Tout télécharger** : « Télécharger l'album » → le serveur prépare un ZIP (originaux, noms `2026-11-14_2213_Ludo.heic`)
  en tâche de fond, lien signé valable 24 h, notification « Ton album est prêt » ; découpé en ZIP de 2 Go. iPhone :
  « Enregistrer dans Photos » par sélection (plus naturel qu'un ZIP sur iPhone), en série, avec reprise. Limiter à
  3 ZIP par personne et par jour (sortie de données payée).
- **Photo de quelqu'un qui ne veut pas** : signalement « Je suis dessus », masquée aussitôt, l'organisation décide
  (même règle que Souvenirs).
- **Contenu illégal / nudité** : signalement + modération existante ; pas d'analyse automatique en v1 (aucun SDK tiers).
- **Photo ajoutée trois mois après** : autorisé (c'est le but). Notification groupée normale.

## 8. Idées qui le rendraient génial sans le compliquer (sans argent ni alcool)

1. **Filtre « Par personne »** : pastilles des photographes en haut de l'album (« Julie · 42 »). Retrouver « les
   photos de Julie » est la question n°1 après une soirée.
2. **Tri par heure de prise de vue, toutes personnes mêlées** (et pas par heure d'envoi) avec séparateurs
   « 21 h · 22 h · 23 h » : l'album raconte la soirée dans l'ordre, même si chacun envoie le lendemain.
3. **La couverture** : l'organisation (ou par défaut la photo la plus « vue ») devient la couverture de l'album et
   la vignette de l'événement passé dans la liste — les vieux événements deviennent beaux au lieu d'être une liste
   grise.
4. **« Ajouter depuis la pellicule » intelligent** : le sélecteur s'ouvre directement sur les photos prises
   PENDANT l'événement (début → fin + 6 h, d'après la date EXIF, lue sur le téléphone, rien envoyé), toutes
   pré-cochées sauf captures d'écran. Deux touchers pour tout envoyer. C'est LA fonction qui fera que les gens
   ajoutent vraiment leurs photos.
5. **Diaporama** : bouton ▶ plein écran, une photo toutes les 4 s, sur la TV via AirPlay (l'app a déjà un lien
   Apple TV) — parfait pour la soirée « on regarde les photos ».

## 9. Ce que je déconseille

- Un album par groupe seulement (mur ingérable) ; un album « public ».
- Mettre les photos de la discussion dans l'album d'office.
- Réencoder les originaux « pour gagner de la place » : c'est exactement le « flou » que l'admin ne veut pas.
- Faire transiter les originaux par le serveur homelab.
- Vidéos, likes, commentaires, reconnaissance de visages (données biométriques : RGPD, App Privacy, non) en v1.

## 10. Questions ouvertes pour l'admin

- Offre Supabase actuelle et budget stockage (décide des plafonds du §3).
- Album d'événement : coupable par l'organisation (proposé) ou toujours présent ?
- Durée : « tant que l'événement existe + purge après 24 mois sans ouverture » OK ?
- Avant la prod : CGU, privacy.tsx (originaux gardés, GPS retiré, durée), App Privacy (photos), notes de revue,
  NSPhotoLibraryUsageDescription (PHPicker n'en exige pas pour lire ; « Enregistrer dans Photos » exige
  NSPhotoLibraryAddUsageDescription), didacticiel (règle du 24.11), contrôle `exigence-apple`.
