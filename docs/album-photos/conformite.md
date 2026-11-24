# Album photo partagé (« boîte de dépôt ») — revue de conformité avant conception (avis e153dce1c115, 24.11.2026)

Verdict : **OUI À CONDITION DE** — ❌ pas conforme en l'état d'une conception « brute » : 6 points 🔴 à intégrer dès la conception.

Sources lues : CLAUDE.md (conformité, groupes, Souvenirs dans la copie de travail `scratchpad/souvenirs/CLAUDE.md` l. 802+),
`ios/project.yml` l. 70-74 (textes Caméra / Photos), `web/events/src/app/privacy.tsx`, `docs/app-store/checklist-envoi.md`
(18+, UGC Oui, App Privacy « Photos or Videos », DSA non-commerçant), `docs/app-store/notes-for-review.md`,
`ios/Party/Chats/ChatModels.swift:507` et `web/events/src/lib/chats.ts:229` (photos de discussion ré-encodées en JPEG
→ EXIF perdus par effet de bord ; l'album en qualité originale perd cette protection).

## Différence décisive avec les Souvenirs
Souvenirs : 1600 px, JPEG, EXIF/GPS retirés par le serveur (`app/souvenirs.py`), dépôt par ticket serveur seulement.
Album : **original** gardé → le fichier contient GPS (domicile !), heure exacte, modèle d'appareil, parfois numéro de série,
XMP/IPTC de lieu. C'est LE risque nouveau.

## 🔴 Obligatoire

1. **Lieu retiré des originaux, sans perte de qualité** — RGPD art. 5(1)(c) et 25, nLPD art. 6 al. 2-3 et 7
   (minimisation, protection par défaut), Apple 5.1.1(i)/(iii).
   Le GPS d'une photo prise chez soi révèle l'adresse à tout le groupe, puis à quiconque reçoit le fichier téléchargé.
   Correction : dépôt UNIQUEMENT par le serveur (même modèle que Souvenirs : ticket à usage unique, aucun dépôt direct
   dans le compartiment) ; le serveur retire sans ré-encoder (exiftool ou équivalent, JPEG et HEIC) : EXIF GPS, XMP/IPTC
   de lieu, numéros de série ; garde date de prise de vue et orientation. Test : un original avec GPS ressort sans GPS,
   pixels identiques (même hash des données image). Ne jamais compter sur PhotosPicker ni Safari pour retirer le lieu.

2. **Contenu des utilisateurs (Apple 1.2, Google Play UGC, DSA art. 16)** : avant la 1re photo, CGU acceptées
   (`terms_required`) ; « Signaler » sur chaque photo (type `album_photo`, motifs habituels + `my_image`) qui la **masque
   aussitôt** pour tous ; « Bloquer » commun à l'app qui cache les photos dans les deux sens ; modération sous 24 h
   (« Masquer » efface fichier compris, « Classer » remet) ; contact publié (support@ déjà en place).
   Filtre automatique d'images : **pas obligatoire** (Apple exige « une méthode de filtrage », qui est ici : cercle fermé
   + téléphone vérifié + CGU + masquage immédiat sur signalement ; DSA art. 8 : aucune obligation de surveillance
   générale ; nLPD rien). Voir 🟠 pour le conseillé.

3. **Qui voit et télécharge : le cercle fermé seulement** — Apple 5.1.1/5.1.2, RGPD art. 5(1)(b)(f), CC art. 28 (droit
   à l'image). Groupe : ses membres actuels (jamais Membres Vendredi Party : trop large, des centaines d'inconnus) ;
   événement : Présent / Peut-être / organisation (comme `souvenir_circle`), jamais la liste d'attente ni un visiteur
   d'un lien public. Lecture et téléchargement par liens signés courts (10 min), jamais d'adresse publique ni de lien
   de partage de l'album. Bloqués exclus ; quitter le groupe / « Pas présent » = plus d'accès. Option allumée par qui
   gère le groupe / l'organisation, **éteinte par défaut**, jamais allumée par l'IA (hors schéma ai_events / ai_event_edit).
   Événement public : déconseillé de l'ouvrir (cercle d'inconnus) ; si oui, même cercle Présent/Peut-être.

4. **« Je suis sur la photo »** — RGPD art. 17 et 21, nLPD art. 30-32, CC art. 28. OUI sous forme de motif de
   signalement `my_image` « Je suis sur la photo et je ne veux pas qu'elle soit montrée » : masquée aussitôt, seule la
   modération peut la remettre (comme Souvenirs). Une personne hors de l'app (pas membre) doit pouvoir le demander par
   le contact publié (DSA art. 16 : « toute personne »). **NON** à l'identification de personnes (étiquettes de noms) et
   **NON** à toute reconnaissance faciale (donnée biométrique, RGPD art. 9, nLPD art. 5 let. c) : ne pas concevoir.

5. **Suppression et durée** — Apple 5.1.1(v), RGPD art. 5(1)(e)/17, nLPD art. 6 al. 4.
   L'auteur supprime ses photos à tout moment ; suppression du compte = toutes ses photos de tous les albums, fichiers
   compris (corbeille vidée par la base, comme `souvenir_trash`) ; album d'événement effacé avec l'événement ; durée
   écrite et appliquée par pg_cron (proposition : album d'événement 13 mois après la fin, comme Souvenirs ; album de
   groupe tant que le groupe existe, l'auteur parti : ses photos restent seulement si c'est écrit, sinon partent avec lui).
   Groupe supprimé = album supprimé.

6. **Textes et revue avant ouverture** — Apple 2.3.1(a), 2.5.19 + règle du projet.
   CGU (nouvelle version) : « ne dépose que des photos que tu as le droit de partager, avec l'accord des personnes
   visibles ; ni nudité, ni violence, ni contenu illégal ; télécharger = copie hors de Party, ne la diffuse pas sans
   accord » ; privacy.tsx : section Album (qui voit, originaux, lieu retiré, durée, suppression, signalement) ;
   Notes for Review + démo dans une version acceptée AVANT l'ouverture en prod iOS (voir plus bas).

## 🟠 Conseillé / administratif

- **Filtre automatique d'images (fortement conseillé, pas bloquant)** : classer chaque photo côté serveur avec un modèle
  open source hébergé chez nous (aucun SDK ni service tiers, sinon nouvelle déclaration de sous-traitant) ; « sensible »
  = flou + « Afficher quand même » et file de modération, jamais refus muet. Le framework Apple SensitiveContentAnalysis
  ne suffit pas seul : il ne marche que si l'utilisateur a activé l'avertissement de contenu sensible, et demande un
  droit (entitlement) spécial. Le filtre devient 🔴 si l'album s'ouvre à des événements publics.
- **Contenu illégal grave (pédopornographie)** : retrait immédiat ET signalement à fedpol / police (CP art. 197) ;
  procédure écrite pour l'admin ; ne pas « Masquer » (qui efface) avant d'avoir sécurisé ce que l'autorité demandera.
- **DSA art. 17 (exposé des motifs)** : quand la modération retire une photo, l'auteur reçoit le motif et le moyen de
  contester (manque aujourd'hui dans toute l'app : aucune notification de retrait trouvée). DSA art. 13 :
  un fournisseur hors UE qui vise l'UE doit désigner un représentant légal dans l'UE (manque pour toute l'app, risque
  d'amende faible mais réel) ; statut DSA « non-commerçant » déjà prévu dans App Store Connect.
- **Photothèque iPhone** : `PhotosPicker` (PHPicker) **sans demande d'autorisation** ni accès complet ; sélection
  multiple bornée ; `preferredItemEncoding = .current` pour recevoir l'original (HEIC) non transcodé ;
  `loadTransferable(Data)` ; jamais `PHPhotoLibrary.requestAuthorization`. Textes à préciser (5.1.1(ii)) :
  NSPhotoLibraryUsageDescription « … de discussion ou d'album » ; NSPhotoLibraryAddUsageDescription « … une photo d'un
  album que tu télécharges ». « Enregistrer dans Photos » = ajout seul (`.addOnly`).
- **App Privacy** : « Photos or Videos » déjà déclaré (lié à l'identité, fonctionnalité de l'app, pas de pistage) ;
  vérifier que « Precise Location » reste NON (vrai seulement si le point 1 est fait). Google Data safety : « Photos »
  si l'app Android devient publique (aujourd'hui non publique → nouvelle revue de toute façon).
- **Questionnaire d'âge** : déjà 18+ et « User-Generated Content : Oui » ; à relire et confirmer (règle du projet :
  à refaire pour tout nouveau contenu de joueur), sans changement attendu.
- **Notifications** « Nouvelles photos dans l'album » : regroupées (une par lot, pas une par photo), interrupteur dédié
  dans Réglages › Notifications, `may_receive_push`, blocage respecté (4.5.4).
- **Plafonds** (abus et capacité, pas une règle de store) : taille par fichier (ex. 30 Mo), nombre par personne et par
  album, débit par heure ; types acceptés JPEG/HEIC/PNG seulement, contrôle du vrai format (pas l'extension), pas de vidéo
  ni Live Photo animée.
- **Affichage web** : HEIC illisible hors Safari → vignette JPEG dérivée pour l'affichage, original au téléchargement.
- **Temps réel / données** : signal sans contenu `event:<id>` / groupe (règles du projet) ; compteur sans « qui ».

## Ce que les notes de revue doivent dire (partie A, anglais, ≤ 4 000 caractères au total)
- Où : group page › « Album » ; event page › « Album » (option turned on by the organizer).
- Qui : only current group members / event participants; nothing public; blocked users never see each other's photos.
- « Photos are picked with the system photo picker (PHPicker): no full Photo Library access is requested. Originals are
  kept, but location (GPS) and device serial metadata are removed by the server before anyone else can see them. »
- UGC : Terms before the first photo; « Signaler » on every photo hides it at once for everyone (including « I am in
  this photo and do not want it shown »); « Bloquer »; reports handled within 24 h; contact support@vendrediparty.ch.
- Suppression : author deletes any time; account deletion removes all photos; event album deleted 13 months after.
- Démo : groupe « Démo Apple » et « Soirée démo Vendredi Party » avec un album déjà rempli de 4–6 photos neutres
  (paysages, objets, aucun visage identifiable), Apple-test membre ; montrer Signaler / Bloquer.
- Pas de vidéo, aucun achat, aucune vente ou valeur attachée aux photos.

Le reste (pas d'argent, pas de récompense, pas d'alcool mis en avant) est conforme.
