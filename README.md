# 🎉 Vendredi Party

Webapp locale qui permet aux invités d'ajouter des titres Spotify dans la **file Sonos**,
sans compte : la lecture passe par le compte Spotify lié à ton système Sonos.

- **/** : page invités (code, prénom, recherche, ajout, file à venir, message pour l'hôte)
- **/admin** : démarrer/arrêter la soirée, choisir la pièce, mode d'insertion, code + QR code,
  messages des invités, file d'attente complète modifiable (⏫ jouer ensuite, ⬆⬇ déplacer,
  ▶︎ jouer maintenant, ✕ retirer), invités présents et modération

La page peut être ajoutée à l'écran d'accueil iOS/Android (icône incluse). Les icônes se
régénèrent avec `python tools/make_icons.py` (nécessite Pillow).

## Utilisation

1. Lance une playlist **depuis l'app Sonos** (pas via Spotify Connect / Jam) → la musique joue depuis la file Sonos (crossfade OK).
2. Ouvre `/admin`, choisis la pièce, le mode, puis **Démarrer la soirée**.
3. Affiche le QR code : les invités ajoutent leurs titres.

### Party extérieur (Spotify → enceinte Bluetooth)

Connecte le compte Spotify Premium de l'hôte depuis les réglages, lance la musique sur
son téléphone, puis démarre **Party extérieur**. Chaque ajout d'un invité ou de l'hôte
est immédiatement envoyé à la file Spotify ; aucun envoi n'attend la fin du morceau.
Tu peux ajouter des titres, les déplacer et les retirer directement dans l'app Spotify.

Party affiche l'aperçu renvoyé par Spotify, qui peut être partiel ou légèrement retardé.
Les commandes de réorganisation, suppression et le mode équitable sont réservés au mode
maison. Les notifications de début de titre restent liées aux demandes faites dans Party.
Un titre absent de l'aperçu n'est pas considéré comme joué : l'historique des demandes
extérieures indique « envoyé à Spotify » tant que son démarrage n'a pas été observé.

Lors de la mise à jour d'une soirée extérieure, les anciennes demandes locales sont
transférées dès qu'un appareil Spotify est actif, en conservant leur ordre et sans
renvoyer celle déjà expédiée. Un transfert incertain est signalé à l'admin pour contrôle
dans Spotify ; il n'est pas automatiquement retenté.

### Modes d'insertion maison (modifiable en cours de soirée)

- **Juste après** : chaque ajout passe juste après le titre en cours.
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

- Chaque invité peut retirer ses propres titres encore en attente.
- Depuis `/admin`, section « Invités » : **⏸ 10 min** (blocage temporaire), **⛔** (bannissement,
  conservé d'une soirée à l'autre), **🗑** (retire ses titres en attente).
  Le blocage vise l'identifiant du navigateur **et** l'IP du téléphone.

## Configuration

```bash
cp .env.example .env   # puis remplis les valeurs
```

**Spotify** (recherche uniquement) : crée une app sur <https://developer.spotify.com/dashboard>
(Redirect URI quelconque, ex. `http://127.0.0.1/callback`, API « Web API »), copie le Client ID / Secret.

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

```bash
uv venv && uv pip install -r requirements.txt
set -a; source .env; set +a
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

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

L'image est privée : le serveur doit être connecté à `ghcr.io` avec un token GitHub `read:packages`.

## Tests

```bash
uv pip install pytest && .venv/bin/python -m pytest -q
```
