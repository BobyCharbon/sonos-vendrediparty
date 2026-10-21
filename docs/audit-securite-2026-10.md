# Audit sécurité & stabilité — octobre 2026

Audit de la branche `develop` (app FastAPI exposée sur `partytest.bobycharbon.ch`),
mené via tests navigateur réels (viewport iPhone) + deux revues de code ciblées
(sécurité et correctness/async). Ce document liste **ce qui a été corrigé** et
**ce qui reste à décider/implémenter**.

## Déjà corrigé (branche `develop`)

Crashs (HTTP 500) atteignables **sans authentification depuis Internet**, plus
quelques courses de concurrence. Voir le commit « durcir les entrées hostiles »
et `tests/test_hardening.py`.

- PIN/cookie non-ASCII → `hmac.compare_digest(str, str)` levait `TypeError`. Helper `_eq()` qui compare les octets.
- `/events/%00` (octet nul) → `Path.resolve` levait `ValueError` → désormais 404.
- Erreurs `httpx` (Spotify/Sonos/Supabase) non gérées → 500. Gestionnaire global → 502 propre, sans fuite de détail.
- `quiz.configure` : un thème non-texte levait `TypeError`.
- Flood `names` de la Roulette (boucle O(n²) qui fige le worker) → champs listes/texte de `GameAction` bornés (`Field(max_length=…)`).
- Courses sur les dicts de parties : `del` → `pop(.., None)`, itération sur copies, `save()` ré-essayé brièvement (plus de 500 « dictionary changed size during iteration »).
- **Reprise du siège animateur** : le siège `host`/`leads` ne peut plus être repris par simple prénom (voir finding 1 ci-dessous — correctif minimal appliqué).

## À décider / implémenter plus tard

### 1. Reprise de siège par pseudo (HIGH) — partiellement traité
Derrière le NAT d'une soirée, tous les invités partagent une IP publique. La
reprise de place (`reclaim_seat`) se base sur « même prénom + même IP (ou place
hors-ligne) ». L'IP ne prouve donc pas l'identité : un invité peut reprendre la
place (points, rôle, mot secret) d'un homonyme.
- **Fait** : le siège de l'animateur et des leads est désormais protégé (le pire cas : prise de contrôle end/ban/launch).
- **Reste** : les sièges des joueurs normaux restent reprenables par homonyme. Correctif complet = **jeton secret par siège** émis au `join`, stocké côté client, exigé pour toute reprise. Supprime la dépendance au prénom/IP. À valider sur plusieurs vrais téléphones (change le comportement testé de `test_rejoin`).

### 2. `/api/events` (SSE) diffuse les codes de partie (MEDIUM)
Le flux non authentifié renvoie `games_stamp()` = `"code:version,…"`. Les codes
à 4 chiffres sont le seul secret d'accès aux jeux ; les diffuser permet de les
énumérer (et alimente le finding 1). Pas de plafond de connexions non plus.
- **Fix** : ne pas mettre les codes en clair (hash par viewer, ou flux par code), exiger `require_viewer` pour la partie musique, plafonner les connexions par IP + durée de vie max. Nécessite un changement client+serveur coordonné.

### 3. Élévation admin SSO = cookie partagé et éternel (MEDIUM)
`account_admin` pose le même cookie `HMAC("admin:"+ADMIN_PIN)` pour tous les
admins ; pas d'identité par utilisateur, pas d'expiration, valide jusqu'au
changement de PIN/secret. Un admin rétrocédé/banni dans Supabase garde l'accès ;
un cookie volé reste valide indéfiniment ; aucune traçabilité.
- **Fix** : jeton signé par session `{uid, iat, exp}` (ex. 12 h), re-vérification périodique de `my_permissions`.

### 4. Limiteur PIN : verrouillages et force brute (MEDIUM)
- Le verrou **global** est un levier de déni de service : un attaquant peut bloquer `/api/admin/login` (ou le join invité) pour tout le monde, y compris le vrai admin.
- En mode non-cooldown (invité), le compteur par IP ne décroît jamais → un invité peut finir verrouillé sur toute la soirée à cause de fautes de frappe espacées.
- `_ips` n'est jamais purgé (croissance mémoire).
- PIN à 4 chiffres + `.env.example` = `1234` : force brute réaliste sur un service laissé tourner (seul le verrou global limite ; contournable en IPv6 par /64).
- **Fix** : PIN admin long (≥10 car. alphanum), pénalités par IP escaladées plutôt qu'un verrou global, clé de limiteur par /64 IPv6, privilégier le SSO Supabase, purge TTL de `_ips`.

### 5. Concurrence (MEDIUM, architecturale)
Un seul worker uvicorn, état en mémoire, routes synchrones dans le pool de 40
threads. Les actions/polls de jeux hors neon/island/heist/président (quiz,
blackjack, votes, pyramide…) n'ont **pas de verrou par partie** : deux requêtes
simultanées peuvent double-compter des points, sauter une question, ou doubler
une élimination. Un Sonos/Spotify lent peut aussi figer tout le monde
(`snapshot` tient `_snap_lock` pendant l'appel réseau).
- **Garde-fous déjà en place** (sûrs) : `save()` ré-essaye la sérialisation ; `del` → `pop` ; itérations sur copies.
- **Fix complet** (non fait, risqué sans test de charge) : un verrou par code de partie autour de la séquence get→tick→action→save ; double-checked locking + cache négatif pour `snapshot` ; sortir l'appel réseau de `submit_track` du verrou ; exécuteur borné séparé pour Sonos/Spotify.

### 6. Endpoints d'écriture ouverts (MEDIUM)
- `POST /api/feedback` : limité par `guest_id` fourni par le client (contournable), store FIFO de 500 → un attaquant peut noyer les vrais retours ; déclenche `notify_admin` + `save()`.
- `POST /api/presence|games|games/{code}` : remplissent le plafond de 300 invités / 30 parties → déni de création de partie, et masquent les invités légitimes.
- **Fix** : limite par IP indépendante du `guest_id`, plafonds globaux, `require_guest` sur le feedback, purge des dicts.

### 7. Durcissements d'infrastructure (LOW) — hors code applicatif
- **HAProxy** : vérifier que `X-Forwarded-For` est bien **réécrit** (`set-header X-Forwarded-For %[src]`) et non passé tel quel, sinon tout client spoofe son IP et contourne les limiteurs. Vérifier aussi l'envoi de `X-Forwarded-Proto: https` (sinon cookies sans `Secure`).
- Conteneur en **host networking** + `--host 0.0.0.0` : le port est joignable en clair sur le LAN.
- **`/docs`, `/redoc`, `/openapi.json`** publics : exposent toute l'API admin. À désactiver en prod (ou gate par variable d'env).
- **Dockerfile** tourne en **root** ; `session.json` et `secret` écrits avec l'umask par défaut (`chmod 600` recommandé, comme `spotify_user.json`).
- Pas de CSP/X-Frame-Options/HSTS sur les pages principales (seul `/events` les pose).
- `/api/calendar.ics` non authentifié (le docstring dit « client authentifié ») : contenu de calendrier arbitraire sur un domaine de confiance (phishing). Signer le lien (HMAC) ou exiger un jeton.
- Liste de révocation d'invités plafonnée à 500 (`party.py`) : un cookie révoqué redevient valide au-delà de 500 révocations ultérieures. Scoper par epoch/nonce.
- Fuites de détail dans des messages d'erreur invités (ex. `Sonos a refusé : {e}`, `r.text[:200]` Spotify).

## Vérifié et OK
- Couverture des routes admin : tout `/api/admin/*` (sauf login/logout) est derrière `require_admin` ; routes invité derrière `require_guest`/`require_viewer`.
- Traversée de chemin `/events/{resource}` : sûre (rejet des segments `.`, `resolve()` + `is_relative_to`).
- OAuth Spotify : state serveur à usage unique (TTL 10 min), redirections internes fixes, pas d'open redirect.
- Résolution de liens : allow-list d'hôtes, `follow_redirects=False`.
- Push : allow-list des services de push.
- `SUPABASE_ANON_KEY`/`SUPABASE_URL` dans `accounts.py` : clé **publishable** (anon) publique par conception, déjà livrée au navigateur ; pas une fuite tant que RLS/grants tiennent. Aucun secret (ADMIN_PIN, secret Spotify, service_role) dans le code ou l'historique git.
- Entrées de jeu neon/island/heist : rejettent NaN/inf. Rendu client via `esc()` — pas de XSS stocké trouvé.
