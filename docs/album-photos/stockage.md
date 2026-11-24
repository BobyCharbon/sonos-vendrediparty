# Album photos (avis e153dce1c115) — où et comment stocker les originaux

Lecture et mesures seulement, 24.11.2026. Rien n'a été modifié (dépôt, bases, serveur).

## 1. Ce qui existe (mesuré)

### Supabase
- Organisation « VendrediParty » : **plan FREE** (`get_organization` → `plan: free`). Les deux projets y sont :
  prod `gsuetixzobooggeaubvb` (eu-central-2, Zurich) et TEST `ewromqfsmcqsthftyhzm` (eu-west-1, Irlande).
- Quotas Free (doc Supabase, pour toute l'organisation, les deux bases ensemble) : **1 Go de stockage de fichiers**,
  **5 Go de sortie (egress) non cachée + 5 Go cachée par mois**, transformation d'images **indisponible**, fichier
  de 50 Mo au plus, projet mis en pause après inactivité, pas de sauvegarde automatique.
- Pro (25 $/mois) : 100 Go de stockage puis 0,021 $/Go ; 250 Go de sortie non cachée (puis 0,09 $/Go) + 250 Go cachée
  (puis 0,03 $/Go) ; transformations : 100 images puis **5 $ / 1000 images d'origine**.
- Ce que pèsent les compartiments aujourd'hui :
  - prod : profile-photos 21 fichiers / 4 Mo, chat-photos 8 / 0,9 Mo, group-photos 1 / 0,2 Mo ; base 52 Mo.
  - TEST : profile-photos 1263 / 78 Mo, tc-receipts 26 / 1,7 Mo, chat-photos 7 / 0,5 Mo, souvenirs 3 / 70 ko.
  - Limites actuelles : 5 Mo (profils, groupes), 8 Mo (chat-photos, accepte image/heic), souvenirs 4 Mo JPEG seul.
- Conclusion : **un seul album réaliste (30 × 20 × 8 Mo ≈ 4,8 Go) dépasse à lui seul le quota Free** (1 Go) ; la
  première soirée où chacun télécharge l'album épuise les 5 Go de sortie du mois pour TOUT Party (profils, discussions).

### Serveur maison (root@192.168.50.204, LXC Proxmox, lecture seule)
- 20 cœurs (Xeon Gold 5218R), 24 Go de RAM (4,4 utilisés), charge moyenne ~4–5 (surtout `apple-stock` à 89 % d'un cœur).
- Conteneurs Party : `vendrediparty` 218 Mo, `vendrediparty-test` 122 Mo, ~0,1 % CPU ; aucune limite CPU/RAM posée.
- Disque : `/` 196 Go, **130 utilisés, 57 Go libres (70 %)** ; NAS `PLEX` 21 To à 97 % (730 Go libres) ;
  `/transmission` 5,3 To, 995 Go libres.
- Débit montant de la connexion : **non mesuré** (aucun test lancé pour ne pas charger la ligne) ; tout passe par
  pfSense/HAProxy, un seul site, pas de CDN. Même une fibre 1 Gbit/s symétrique sert ~110 Mo/s au mieux, partagés
  avec Plex/Jellyfin, transmission, etc.

### Souvenirs (branche `souvenirs`, app/souvenirs.py + migration 20261124090000)
- Le téléphone envoie la photo brute AU SERVEUR Party (15 Mo max) ; le serveur la redresse, **réencode en JPEG
  1600 px sans métadonnées** (Pillow), demande un ticket à usage unique (`souvenir_upload_ticket`, clé
  `SOUVENIRS_SECRET`, 2 min), dépose dans le compartiment privé `souvenirs` (`<événement>/<moi>/<id>.jpg`, 4 Mo,
  RLS `souvenir_may_upload/read/drop`), puis `souvenir_take`. Affichage par liens signés courts (`/object/sign`).
  Effacement : corbeille en base + `souvenir_files_gc` (API Storage) toutes les heures.
- Ce modèle est **à l'opposé** de ce que veut l'album : il fait transiter chaque octet par le serveur maison et
  recompresse. À reprendre : le ticket délivré par la base (droits, plafonds, CGU) et la corbeille pour l'effacement ;
  à ne pas reprendre : le passage par le serveur et le réencodage.

## 2. Volume de référence

50 soirées × 30 personnes × 20 photos = **30 000 photos**. HEIC d'iPhone 2–5 Mo, JPEG 48 MP 8–15 Mo ; moyenne prise : 8 Mo.
- Stock d'originaux : **≈ 240 Go** (4,8 Go par album).
- Aperçus (faits une fois) : grille 400 px ~40 ko + écran 2048 px ~450 ko → ≈ 15 Go.
- Sortie (lecture), estimation sur la durée de vie des 50 albums :
  - grilles : 30 000 × 40 ko × 30 visiteurs ≈ 36 Go ;
  - plein écran : 30 000 × 450 ko × 10 vues ≈ 135 Go ;
  - originaux (« Télécharger » / « Tout télécharger ») : 1/3 des invités prend l'album → 50 × 10 × 4,8 Go ≈ **2,4 To**.
  C'est le téléchargement des originaux qui décide de tout : il pèse 10 fois le stock.

## 3. Les trois options

### (a) Supabase Storage, envoi direct du téléphone (TUS reprenable + RLS)
- Fonctionnement : compartiment privé `albums`, ticket en base (comme Souvenirs mais SANS clé du serveur : la règle
  RLS d'insertion vérifie `private.album_may_upload(name)` = membre de l'album, plafonds, CGU) ; le téléphone envoie
  par TUS (`/storage/v1/upload/resumable`, morceaux de 6 Mo, reprise après coupure) avec son propre jeton.
- Coût : impossible en Free. Pro obligatoire : 25 $/mois + (255 − 100) × 0,021 ≈ 3,3 $ de stockage ; sortie ≈ 2,6 To
  sur la vie des albums, concentrée les jours d'après-soirée. Mois chargé (10 albums téléchargés) ≈ 500 Go :
  (500 − 250) × 0,09 ≈ 22 $, ou ≈ 8 $ si Smart CDN cache. **≈ 30 à 60 $/mois, plafonné seulement par le
  « spend cap »** (qui coupe alors tout Party, profils et discussions compris). Transformations d'images : 30 000 ×
  5 $/1000 ≈ 150 $ si on les utilisait pour les aperçus → non.
- Charge du serveur Party : nulle (il ne voit aucun octet).
- Vitesse : bonne (Zurich pour la prod, CDN Supabase devant les liens signés).
- Sauvegarde : **aucune** pour les fichiers (les sauvegardes Supabase ne couvrent que la base) → copie à organiser.
- RGPD : tout chez un seul sous-traitant déjà déclaré ; effacement par la corbeille existante (`storage_remove`).
- Bonus indirect : passer en Pro supprime la mise en pause du projet et donne les sauvegardes quotidiennes de la base.

### (b) Disque du serveur maison
- Coût : 57 Go libres seulement → il faut un disque (2 To ≈ 80–120 CHF, une fois) + courant ; NAS déjà plein (97 %).
- Charge : chaque octet entre ET sort par FastAPI/HAProxy et par le débit montant de la maison ; 30 personnes qui
  « téléchargent tout » le dimanche = 150 Go à servir depuis la maison, en concurrence avec Plex, et le serveur
  Party (un seul processus) bloqué sur des flux de 8 Mo. C'est exactement ce que l'admin craint.
- Vitesse : limitée par le montant de la ligne, aucun cache proche des invités.
- Sauvegarde : dans la même maison (incendie, vol, panne du LXC) ; à doubler ailleurs de toute façon.
- RGPD : simple (effacement local), mais disponibilité liée à la maison.
- Verdict : non pour les originaux.

### (c) Stockage objet externe : Cloudflare R2 (S3 compatible), compartiment « juridiction UE »
- Fonctionnement : le serveur Party ne fait que SIGNER (après accord de la base, comme le ticket Souvenirs) :
  URL présignée PUT pour un fichier ≤ 100 Mo, ou envoi multipart (morceaux de 8 Mo, présignés, reprenables) ;
  lecture par URL présignée GET de courte durée. Les octets vont directement téléphone ↔ R2.
- Coût (grille publique R2) : stockage 0,015 $/Go-mois (10 Go offerts), **sortie gratuite**, écritures 4,50 $/million
  (1 M offert), lectures 0,36 $/million (10 M offerts).
  255 Go → (255 − 10) × 0,015 ≈ **3,7 $/mois** ; ~150 000 écritures (originaux + 2 aperçus + morceaux) et quelques
  millions de lectures → dans les offerts. **≈ 4 $/mois, quel que soit le nombre de téléchargements.**
  (À titre de comparaison, AWS S3 : 0,023 $/Go + 0,09 $/Go de sortie → même profil que Supabase.)
- Charge du serveur Party : quelques signatures HMAC par photo (microsecondes), aucun octet.
- Vitesse : réseau Cloudflare, rapide en Suisse ; reprise native du multipart.
- Sauvegarde : R2 n'a pas de versionnage ; copie nocturne `rclone sync --immutable` vers le partage `/transmission`
  (995 Go libres) ou un disque dédié, depuis le serveur maison (sortie R2 gratuite, entrée maison).
- RGPD : nouveau sous-traitant (Cloudflare, DPA standard, compartiment « EU jurisdiction » = données gardées dans l'UE)
  à ajouter à la politique de confidentialité, App Privacy et Data safety. Effacement : corbeille en base (même
  modèle que `souvenir_trash`) vidée par une tâche du serveur Party (la base ne sait pas signer en S3) + règle de
  cycle de vie R2 qui abandonne les envois multipart incomplets après 1 jour.
- Inconvénient : deux systèmes (droits en base, fichiers chez R2) ; la RLS ne protège plus les fichiers eux-mêmes,
  c'est le serveur qui signe après avoir demandé à la base (`album_upload_ticket`, `album_read_urls`).
- Alternative suisse à étudier si l'admin tient à des données en Suisse : stockage objet S3 d'Infomaniak (prix et
  sortie à vérifier) ; même architecture, seul le point d'accès change.

### Tableau
| | (a) Supabase Pro | (b) disque maison | (c) R2 UE |
|---|---|---|---|
| Coût / mois (30 000 photos) | 30–60 $ (pics de sortie) + plan | ~0 + disque 100 CHF | **≈ 4 $** |
| Charge serveur Party | nulle | **forte** (tous les octets) | nulle (signature) |
| Vitesse d'affichage | bonne | limitée par la ligne | bonne |
| Sauvegarde | à faire | même maison | rclone nocturne vers le NAS |
| Effacement RGPD | corbeille existante | local | corbeille + tâche serveur |
| Envoi reprenable | TUS natif | à écrire | multipart natif |

## 4. Les fichiers eux-mêmes

### Originaux gardés octet pour octet
- Acceptés : HEIC/HEIF, JPEG, PNG (captures), WebP. **ProRAW (DNG 25–75 Mo) refusé en v1** (illisible dans un
  navigateur, 6–10 fois plus lourd) ; « Photo en direct » : seulement l'image fixe ; vidéos refusées (type MIME vérifié
  par la base au ticket ET par l'en-tête signé `Content-Type`).
- Empreinte SHA-256 calculée par le téléphone et envoyée au ticket : évite les doublons (même photo deux fois) et prouve
  que le fichier n'a pas été modifié.
- Clé : `album/<album>/<auteur>/<id>.<heic|jpg|png>` ; aperçus `…/<id>.g.jpg` (grille) et `…/<id>.s.jpg` (écran).

### Position GPS : retirer sans réencoder
Le conflit n'existe pas : la position vit dans les métadonnées, pas dans les pixels.
- iPhone : `CGImageDestinationCopyImageSource` avec `kCGImageMetadataShouldExcludeGPS = true` copie l'image **sans la
  recompresser** (API d'Apple prévue pour ça, JPEG et HEIC) ; on garde date, appareil, orientation, profil couleur.
- Web : petite fonction JS qui trouve le bloc Exif (JPEG : segment APP1 ; HEIC : élément `Exif` de la boîte `meta`) et
  **efface sur place, à longueur égale**, le répertoire GPS (étiquette 0x8825 et ses valeurs remplacées par des zéros) ;
  idem pour d'éventuelles balises `exif:GPS*` en XMP. Aucun pixel touché, taille identique. À tester sur des fichiers
  de chaque iPhone/Android avant ouverture.
- Par défaut position retirée ; pas d'option « garder la position » en v1 (album partagé avec des gens qu'on ne connaît
  pas tous, Apple 5.1.2). L'empreinte SHA-256 est calculée APRÈS ce retrait.
- Contrôle : à la fin de l'envoi, le serveur peut relire les 64 premiers ko (requête Range, gratuite) pour vérifier
  l'absence de GPS ; sinon la photo reste « en attente » et n'est pas montrée.

### Aperçus légers : faits par le téléphone qui envoie
- Pas de transformation Supabase (indisponible en Free, 5 $/1000 en Pro) ni de serveur qui décode 30 000 HEIC.
- iPhone : `CGImageSourceCreateThumbnailAtIndex` (rapide, orientation appliquée) → grille 400 px JPEG q0,7 (~40 ko) et
  écran 2048 px JPEG q0,85 (~450 ko), sans métadonnées.
- Web : `createImageBitmap` + `<canvas>` (`toBlob`) ; Safari décode le HEIC, **Chrome/Android non** → pour un HEIC envoyé
  depuis Chrome : aperçu fait plus tard par le serveur Party dans une file d'attente à un seul travail à la fois
  (`pillow-heif` à ajouter ; seul Pillow est dans requirements.txt), plafonné, ou à la première ouverture par un iPhone.
- Grille = aperçu 400 px ; toucher = 2048 px ; bouton « Original » = le fichier intact. Jamais l'original dans la grille.

### Télécharger l'original et « Tout télécharger »
- Une photo : URL présignée GET avec `response-content-disposition=attachment; filename=…` (nom d'origine).
- Tout : **jamais de zip fait par le serveur** (CPU + débit).
  - iPhone natif : tâche URLSession en arrière-plan par fichier, puis `PHAssetCreationRequest.addResource(with: .photo,
    fileURL:)` → l'original arrive tel quel dans Photos (HEIC reste HEIC), progression « 312 / 600 ».
  - Web : zip fabriqué dans le navigateur, en flux, sans compression (mode « store ») à partir des URL présignées ;
    au-delà de ~2 Go ou sur iPhone Safari : par lots (« Partie 1/3 »).
- Liens présignés : durée courte (15 min), arrondie à une fenêtre fixe pour que la même photo garde la même adresse
  quelques minutes (cache du navigateur).

### Plafonds raisonnables (en base, au ticket)
- Fichier : 40 Mo (couvre JPEG 48 MP et PNG ; HEIC ~5 Mo).
- Par personne et par album : 300 photos et 3 Go.
- Par album : 3 000 photos et 25 Go.
- Par personne, tous albums : 15 Go (garde-fou contre l'usage en sauvegarde personnelle).
- Débit : 600 tickets / heure / personne.
- Stock total surveillé : alerte à l'admin au-delà de 300 Go (≈ 4,5 $/mois chez R2).

### Durée de conservation
- Album d'événement : 12 mois après l'événement ; album de groupe : 12 mois après le dernier ajout.
- 30 jours avant : notification « L'album X sera effacé le … · Tout télécharger » ; l'organisateur peut prolonger une
  fois de 12 mois.
- Effacé : sa photo par son auteur (aussitôt), l'album par son organisateur, tout ce qu'une personne a déposé à la
  suppression de son compte (cascade `author_id` → corbeille → tâche qui efface originaux ET aperçus dans l'heure,
  puis dans la sauvegarde rclone au passage suivant, `--delete-after` sous 7 jours).
- Modération (Apple 1.2) : « Signaler », masquage, blocage commun ; CGU avant le premier dépôt.

## 5. Côté appareils

### iPhone
- `PHPickerViewController` avec `configuration.preferredAssetRepresentationMode = .current` (sinon iOS convertit en
  JPEG « compatible ») et `itemProvider.loadFileRepresentation(forTypeIdentifier: UTType.image.identifier)` → fichier
  d'origine (HEIC) copié dans un dossier de l'app ; les photos « optimisées iCloud » sont téléchargées en pleine taille
  par le sélecteur. `selectionLimit = 0`, filtre `.images` (exclut vidéos).
- Préparation locale : retrait GPS sans réencodage, SHA-256, 2 aperçus.
- Envoi : `URLSession(configuration: .background(withIdentifier:))`, une `uploadTask(with:fromFile:)` par fichier ou
  par morceau (multipart), 3 en parallèle ; continue écran verrouillé ou app fermée ; réessai automatique ; tickets
  demandés par lots (50) au serveur ; « Envoyé 120 / 200 » visible sur l'album.

### Web
- `<input type="file" multiple accept="image/heic,image/heif,image/jpeg,image/png,image/webp">` : lister le HEIC
  explicitement, car Safari iOS **convertit le HEIC en JPEG** quand l'`accept` est seulement `image/*` (à vérifier sur
  appareil) ; aucun `canvas` sur l'original, aucune bibliothèque de compression.
- Envoi : `fetch(PUT)` vers l'URL présignée (ou multipart en morceaux de 8 Mo, 3 en parallèle), barre de progression,
  reprise des morceaux manquants si la page reste ouverte.

## 6. Recommandation

**Option (c) : Cloudflare R2, compartiment « juridiction UE », envoi et lecture directs par URL présignées ;
droits, plafonds et tickets dans Supabase (comme Souvenirs) ; aperçus faits par le téléphone ; copie nocturne
vers le NAS.**

Ce que ça coûte :
- **≈ 4 $/mois** pour 30 000 photos (255 Go), la sortie étant gratuite : « Tout télécharger » ne coûte rien, même
  2,4 To. Évolution : +0,015 $/Go-mois, soit ~0,07 $ par album de 4,8 Go et par mois.
- Le plan Supabase peut rester Free pour les albums (seules quelques lignes par photo en base : 30 000 lignes ≈ 15 Mo).
- Une fois : carte Cloudflare, déclaration du sous-traitant (politique, App Privacy, Data safety), place pour la copie
  (≈ 255 Go sur `/transmission` ou un disque dédié).
- Serveur maison : charge négligeable (signatures + tâche d'effacement + copie de nuit).

Pourquoi pas (a) : Supabase Pro est le chemin le plus simple (RLS et TUS natifs) mais la sortie des originaux
(0,09 $/Go au-delà de 250 Go) rend la facture imprévisible et le « spend cap » couperait tout Party. À reconsidérer
seulement si l'admin veut aussi passer en Pro pour d'autres raisons ET limite « Tout télécharger ».
Pourquoi pas (b) : tous les octets passent par la maison et le serveur Party ; 57 Go libres.

## 7. Non vérifié
- Débit montant réel de la connexion (aucun test lancé).
- Prix R2 / Supabase lus dans la documentation publique connue (Supabase vérifiée aujourd'hui par sa doc ; R2 d'après
  sa grille publique, à revérifier avant engagement).
- Comportement exact de Safari iOS avec `accept="image/heic,…"` et du retrait GPS à longueur égale dans le HEIC :
  à prouver sur appareil avant de coder.
- Consommation actuelle de sortie de l'organisation Supabase (page « Usage » non consultée).
