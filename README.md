# 🎉 Vendredi Party

Webapp qui permet aux invités d'ajouter des titres à la musique de la soirée, sans compte Spotify.
À la maison, les titres entrent dans la **file Sonos** (API locale Sonos, Spotify lié au système Sonos) ;
à l'extérieur, dans la file Spotify du téléphone de l'hôte relié à une enceinte Bluetooth.

- **/** : page invités (code, prénom, recherche, ajout immédiat, aperçu de la file, messages)
- **Compte admin dans l'app** (connecté avec son numéro, droits admin) : tout se gère depuis les onglets, sans /admin —
  **Musique** : démarrer / arrêter la soirée, lecture, volume, ajout de titres, file d'attente, mode, playlists,
  enceintes, Spotify, code + QR des invités (repliable), messages, invités, bannis, notifications de l'hôte ;
  **Jeux** : parties en cours de toute la soirée (détail, rejoindre, fermer) ; **Retours** : avis des invités
  (statuts, mot pour l'invité, envoi à Claude)
- **/admin** : même gestion avec le code PIN, gardée en secours
- **/tv** : écran pour la télé (Apple TV) — titre en cours avec sa pochette, prochaines demandes et qui les a faites,
  code et QR pour entrer, événement lié, parties de jeu en cours. Réservé à l'hôte (code PIN une fois). Sur le Mac :
  ouvrir `/tv` dans Safari, Recopie de l'écran → Apple TV en **écran séparé**, puis plein écran (⌃⌘F)
- **Soirée liée à un événement** (Musique → Code et QR → « Événement de la soirée ») : les comptes notés « Présent »
  entrent dans Musique et Jeux sans code ; noté absent par l'organisateur, l'accès sans code s'arrête (le code reste)
- **Événements** : sorties du groupe, catégories/tags et abonnements, propositions,
  votes sur les dates, sondages, réponses et discussions ; connexion SMS obligatoire.

La page peut être ajoutée à l'écran d'accueil iOS/Android (icône incluse). Les icônes se
régénèrent avec `python tools/make_icons.py` (nécessite Pillow).

## Utilisation

### Party maison (file Sonos native)

1. Lance une playlist **depuis l'app Sonos** (pas via Spotify Connect / Jam) : la musique joue depuis la file Sonos.
2. Dans l'onglet **Musique** de l'app (compte admin) ou sur `/admin`, choisis **Party maison**, la même pièce
   et le mode d'insertion (juste après / équitable), puis démarre.
3. Affiche le code ou le QR (section « Code et QR pour les invités ») : les ajouts entrent dans la file Sonos.

Aucun compte Spotify à connecter dans Party : Sonos lit les titres avec le compte Spotify lié à ton système.
L'hôte peut réordonner, jouer ensuite, retirer (avec « Annuler ») et passer en mode équitable.
Le mode Spotify Connect sur Sonos (`spotify_sonos`) reste pris en charge pour une soirée déjà lancée ainsi.

### Party extérieur (Spotify → enceinte Bluetooth)

Connecte le compte Spotify Premium de l'hôte depuis les réglages, lance la musique sur
son téléphone, puis démarre **Party extérieur**. Chaque ajout d'un invité ou de l'hôte
est immédiatement envoyé à la file Spotify ; aucun envoi n'attend la fin du morceau.
Tu peux ajouter des titres, les déplacer et les retirer directement dans l'app Spotify.

Party affiche l'aperçu renvoyé par Spotify, qui peut être partiel ou légèrement retardé.
L’ordre et les suppressions se gèrent dans Spotify, en maison comme en extérieur. Les notifications de début de titre restent liées aux demandes faites dans Party.
Un titre absent de l'aperçu n'est pas considéré comme joué : l'historique des demandes
extérieures indique « envoyé à Spotify » tant que son démarrage n'a pas été observé.

Lors de la mise à jour d'une soirée extérieure, les anciennes demandes locales sont
transférées dès qu'un appareil Spotify est actif, en conservant leur ordre et sans
renvoyer celle déjà expédiée. Un transfert incertain est signalé à l'admin pour contrôle
dans Spotify ; il n'est pas automatiquement retenté.

### Anciennes soirées Sonos natives (jusqu’à leur arrêt)

- **À la suite** : chaque demande passe après celles déjà en attente (premier arrivé, premier servi, celles de l'hôte comprises), avant la suite de la playlist. L'hôte garde ⏫ pour faire passer un titre juste après celui en cours.
- **Équitable** : les demandes passent avant ta playlist, un titre par invité à tour de rôle
  (A, A, A, B, C, B → A B C A B A).

Les doublons (titre déjà dans la file à venir) sont refusés.

### Code d'accès invités

La page invités est protégée par un code à 4 chiffres, affiché dans `/admin` avec un QR code
qui l'inclut (scanner = entrer directement). **🔄 Nouveau code** en génère un autre et
déconnecte tous les invités. Les essais sont limités : 5 échecs → IP bloquée 15 min,
30 échecs au total en 10 min → tout le monde bloqué 10 min.

Derrière un reverse proxy (HAProxy), renseigne `FORWARDED_ALLOW_IPS` avec l'IP du proxy pour que
l'app voie la vraie IP des invités (limitation des essais et bannissements).

### Modération

- Les retraits de titres se font dans Spotify. Les anciennes sessions Sonos natives conservent leurs boutons de retrait.
- Depuis `/admin`, section « Invités » : **⏸ 10 min** (blocage temporaire), **⛔** (bannissement,
  conservé d'une soirée à l'autre). La purge **🗑** reste disponible pour les anciennes files Sonos natives.
  Le blocage vise l'identifiant du navigateur **et** l'IP du téléphone.

## Configuration

### Comptes et événements

Le module `web/events` reprend le client Vendredi Party et utilise le **même projet
Supabase**, ses comptes, ses événements et son fournisseur SMS Twilio. Aucune migration
de données ni nouvelle inscription n'est nécessaire. Le changement de site demande
une première connexion SMS sur Party ; la session y est ensuite conservée.

Le code/QR de musique et la connexion d'un téléphone aux jeux restent indépendants
du compte des événements. Les droits de membre et d'admin des événements sont contrôlés
par Supabase Auth et les politiques de la base, jamais par le code musique.

Les paramètres publics Supabase se trouvent dans `web/events/app.config.js` et peuvent
être remplacés à la construction avec `EXPO_PUBLIC_SUPABASE_URL` et
`EXPO_PUBLIC_SUPABASE_ANON_KEY`. Seules l'URL et la clé **publique** doivent être
présentes dans le client. Les secrets Twilio restent dans Supabase.

Les notifications d'événements sont consultables dans **Activité** et peuvent être
reçues par Web Push après activation sur chaque navigateur. **Mon profil → Notifications**
permet de choisir les nouveaux événements (tous, abonnements catégorie/tag, aucun),
les changements, sondages, rappels, discussions et alertes d'organisation. Une catégorie
OU un tag abonné suffit. Une sourdine par événement reste disponible.

Les **annonces admin sont obligatoires**, indépendantes des abonnements, des sourdines
et du bouton d'alertes facultatives. Elles restent lisibles après lecture et après la
purge des notifications à 90 jours. Le navigateur et le téléphone gardent la maîtrise
de leur permission push. Les heures silencieuses du groupe reportent aussi les annonces.
Sur iPhone/iPad, ajouter la webapp à l'écran d'accueil depuis Safari avant l'activation.

La page `/admin#events` intègre également les événements. Son code PIN musique ne
donne aucun droit Supabase : l'administration du groupe nécessite son compte SMS admin.
Un clic sur une notification ouvre la fiche ou l'activité dans l'onglet Événements.

Les abonnements Web Push d'événements utilisent la portée `/events/`, distincte de
la musique (`/`) et de l'admin musique (`/admin`). Ils sont liés à la session SMS et
sont retirés à la déconnexion. Les préférences et droits sont revérifiés avant envoi.
Voir [supabase/README.md](supabase/README.md) pour le service d'envoi et son déploiement.

La webapp est le seul livrable actuel. Expo sert à construire les pages web réutilisées ;
aucun build iOS/Android ni compte EAS n'est requis.

```bash
cp .env.example .env   # puis remplis les valeurs
```

**Spotify** : crée une app Web API sur <https://developer.spotify.com/dashboard>, copie
le Client ID / Secret, puis enregistre la Redirect URI de ton déploiement :
`https://partytest.bobycharbon.ch/api/spotify/callback` pour le test,
`https://party.bobycharbon.ch/api/spotify/callback` pour le site principal.

**SONOS_IP** : l'IP de n'importe quelle enceinte. Requis si le serveur n'est pas sur le même
sous-réseau que les Sonos (la découverte multicast ne traverse pas les VLAN).

**PARTY_PUBLIC_URL** : l'origine HTTPS de ce déploiement, utilisée pour les QR codes
et le retour de connexion Spotify. Par défaut : `https://party.bobycharbon.ch`.
La stack de test définit `https://partytest.bobycharbon.ch` ; enregistrer également
`https://partytest.bobycharbon.ch/api/spotify/callback` dans les Redirect URIs Spotify
et connecter le compte depuis l'admin du site de test. Les deux sites conservent leurs
sessions séparément. L'ancienne variable `PUBLIC_URL` n'est pas utilisée.

## Lancer

### En local (dev)

Construire d'abord les pages d'événements avec Node 22.23.3 :

```bash
cd web/events
npm ci
npm run typecheck
npm run lint
npm run build
cd ../..
```

Puis lancer le serveur :

```bash
uv venv && uv pip install -r requirements.txt
set -a; source .env; set +a
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

En local, définir `EVENTS_WEB_DIR` avec le chemin absolu de `web/events/dist` pour
servir le module. Dans l'image Docker, il est automatiquement copié dans
`app/events-web`. Les routes du module sont sous `/events/` et restent sur la même
origine que Party. Un build absent renvoie une erreur 503 explicite.

### Docker en local

```bash
docker compose up -d --build
```

Le conteneur utilise `network_mode: host`. L'état de la soirée est conservé dans `./data`.

### Production (serveur Docker, mises à jour par Git)

1. Chaque push sur `main` lance les tests, puis publie l'image
   `ghcr.io/bobycharbon/sonos-vendrediparty:latest` (GitHub Actions).
2. Sur le serveur, la stack `deploy/docker-compose.yml` utilise cette image (port `8090` par défaut,
   l'agent Edge de Portainer occupant souvent le 8000). Renseigne `ADMIN_PIN`, `SPOTIFY_CLIENT_ID`
   et `SPOTIFY_CLIENT_SECRET` dans les variables de la stack.
3. Dockhand détecte la nouvelle image : mise à jour en un clic ou automatique.

Les pushes sur `develop` publient le tag `:develop` utilisé par
`https://partytest.bobycharbon.ch`. Le build Docker vérifie les types et le lint du
client, puis inclut son export web dans la même image que le serveur. Une mise à jour
de cette image actualise donc ensemble les onglets Musique, Jeux et Événements.

L'image est privée : le serveur doit être connecté à `ghcr.io` avec un token GitHub `read:packages`.

## App iOS

`ios/` contient l'app native (Swift, WKWebView) qui affiche ce site à l'identique de l'app
installée depuis Safari. Étapes de construction, notifications et publication : [ios/README.md](ios/README.md).

## Tests

```bash
uv pip install pytest && .venv/bin/python -m pytest -q
```

Les parcours navigateur des événements nécessitent le build web et Playwright :

```bash
uv pip install playwright httpx
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest -q tests/test_events_web.py tests/test_events_browser.py
```

Ces parcours simulent Supabase et Twilio, sans SMS ni modification de données réelles.
Ils couvrent les indicatifs suisse/français, la connexion obligatoire, l'attente
d'approbation, la liste, la fiche et la réponse à un événement à plusieurs largeurs.
