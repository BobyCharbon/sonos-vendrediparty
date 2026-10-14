# 🎉 Vendredi Party

Webapp locale qui permet aux invités d'ajouter des titres Spotify dans la **file Sonos**,
sans compte : la lecture passe par le compte Spotify lié à ton système Sonos.

- **/** : page invités (prénom, recherche, ajout, file à venir)
- **/admin** : démarrer/arrêter la soirée, choisir la pièce, mode d'insertion, QR code, retirer un titre, passer

## Utilisation

1. Lance une playlist **depuis l'app Sonos** (pas via Spotify Connect / Jam) → la musique joue depuis la file Sonos (crossfade OK).
2. Ouvre `/admin`, choisis la pièce, le mode, puis **Démarrer la soirée**.
3. Affiche le QR code : les invités ajoutent leurs titres.

### Modes d'insertion (modifiable en cours de soirée)

- **Juste après** : chaque ajout passe juste après le titre en cours.
- **Équitable** : les demandes passent avant ta playlist, un titre par invité à tour de rôle
  (A, A, A, B, C, B → A B C A B A).

Les doublons (titre déjà dans la file à venir) sont refusés.

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

**PUBLIC_URL** : l'adresse que les invités doivent ouvrir (encodée dans le QR code).

## Lancer

### En local (dev)

```bash
uv venv && uv pip install -r requirements.txt
set -a; source .env; set +a
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker (Proxmox LXC, NAS…)

```bash
docker compose up -d --build
```

Le conteneur utilise `network_mode: host`. L'état de la soirée est conservé dans `./data`.

## Tests

```bash
uv pip install pytest && .venv/bin/python -m pytest -q
```
