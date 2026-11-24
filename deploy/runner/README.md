# Runners GitHub Actions auto-hébergés

Dépôt privé : les minutes des machines GitHub sont payantes (≈ 150 $/mois au rythme de novembre 2026). Tous les jobs
tournent donc sur deux machines de l'admin, gratuites :

| Runner | Où | Labels | Jobs |
|---|---|---|---|
| `party-mac` | Mac de l'admin, `~/actions-runner`, service launchd de la session | `self-hosted, macOS, ARM64, party-mac` | TestFlight iPhone + Apple TV, captures App Store, Android |
| `party-linux` | serveur 192.168.50.204, conteneur `party-runner`, `/opt/party-runner` (hors Dockhand) | `self-hosted, Linux, X64, party-linux` | tests, image Docker, revue App Store, correction par Claude |

Un job attend (« Queued ») tant que sa machine est éteinte ou que son runner est arrêté ; il part dès son retour.
Chaque runner fait un job à la fois. État : GitHub › Settings › Actions › Runners, ou
`gh api repos/BobyCharbon/sonos-vendrediparty/actions/runners --jq '.runners[]|[.name,.status]'`.

Sécurité : un runner auto-hébergé exécute le code des workflows du dépôt. Il est réservé à ce dépôt PRIVÉ (jamais un
dépôt public : un fork pourrait y lancer son code). `party-linux` a le socket Docker du serveur, donc l'équivalent
de root sur l'hôte ; seul le propriétaire du dépôt peut pousser ou étiqueter une issue `claude-fix`.

## Mac (`party-mac`)

Installé le 24.11.2026, runner officiel `actions/runner` v2.338.2 (osx-arm64, somme SHA-256 vérifiée).

```bash
cd ~/actions-runner
./svc.sh status            # état du service
./svc.sh stop              # arrêter (les jobs Apple attendent)
./svc.sh start             # relancer
```

- Démarre avec la session de l'admin (LaunchAgent `actions.runner.BobyCharbon-sonos-vendrediparty.party-mac`) :
  Mac allumé et session ouverte pour builder. Journaux : `~/Library/Logs/actions.runner.BobyCharbon-sonos-vendrediparty.party-mac/`.
- PATH du service : `~/actions-runner/.path` (xcodegen dans `~/.local/bin`, Homebrew) ; variables : `~/actions-runner/.env`
  (`DEVELOPER_DIR` = `/Applications/Xcode.app`, Xcode 27.2). Après une modification : `./svc.sh stop && ./svc.sh start`.
- Xcode : les workflows vérifient Xcode 27.2 (`/Applications/Xcode_27.2.app` sinon `/Applications/Xcode.app`) et ne
  changent jamais le `xcode-select` du Mac.
- Signature : aucun certificat ni trousseau sur le Mac. La clé API App Store Connect vient des secrets GitHub
  (`ASC_*`), écrite dans le dossier temporaire du job puis effacée ; la signature est gérée par Apple. Les profils que
  l'export télécharge sont effacés à la fin, ceux de l'admin restent. DerivedData : dans le dossier temporaire du job.
- Captures App Store : simulateur « Party CI » créé puis supprimé à chaque passage ; ceux de l'admin ne sont pas touchés.
- Android : il faut le SDK Android sur le Mac (pas installé au 24.11) : `brew install --cask android-commandlinetools`,
  puis, par l'admin lui-même, `sdkmanager --licenses` (licences de Google), et `ANDROID_HOME=…` dans `~/actions-runner/.env`.
- TestFlight : sur main (push) et à la demande (Actions › « App iOS → TestFlight » › Run workflow). Décocher « envoi »
  = compilation seule, rien ne part chez Apple.

Désinstaller :

```bash
cd ~/actions-runner
./svc.sh stop && ./svc.sh uninstall
./config.sh remove --token "$(gh api -X POST repos/BobyCharbon/sonos-vendrediparty/actions/runners/remove-token --jq .token)"
rm -rf ~/actions-runner
```

## Serveur (`party-linux`)

Image `party-runner:local` construite sur place depuis ce dossier : image officielle `ghcr.io/actions/actions-runner`
(version épinglée dans `Dockerfile`) + `gh` et `python3-venv`. Le runner se met à jour tout seul. Ressources
plafonnées (16 cœurs, 16 Go) pour laisser la place à la prod. Réseau Docker par défaut (pas de `network_mode: host`).
Le build de l'image Party passe par un builder buildx à part : il ne touche ni aux images ni aux conteneurs des sites.

Installation (déjà faite le 24.11.2026) :

```bash
# depuis le Mac, dans le dépôt
ssh -i ~/.ssh/homelab root@192.168.50.204 'mkdir -p /opt/party-runner/state && chown 1001:1001 /opt/party-runner/state && chmod 700 /opt/party-runner/state'
scp -i ~/.ssh/homelab deploy/runner/{Dockerfile,entrypoint.sh,docker-compose.yml} root@192.168.50.204:/opt/party-runner/
TOKEN=$(gh api -X POST repos/BobyCharbon/sonos-vendrediparty/actions/runners/registration-token --jq .token)
ssh -i ~/.ssh/homelab root@192.168.50.204 "cd /opt/party-runner && docker compose build && RUNNER_TOKEN=$TOKEN docker compose up -d"
# puis une fois enregistré, recréer sans le jeton (expiré au bout d'1 h de toute façon) :
ssh -i ~/.ssh/homelab root@192.168.50.204 'cd /opt/party-runner && docker compose up -d'
```

L'identité du runner est gardée dans `/opt/party-runner/state` : un redémarrage du conteneur ou du serveur le
reconnecte sans nouveau jeton. `DOCKER_GID` (défaut 996) = groupe de `/var/run/docker.sock` (`getent group docker`).

Sur le serveur, dans `/opt/party-runner` :

```bash
docker compose logs -f     # journal
docker compose stop        # arrêter (les jobs Linux attendent)
docker compose start       # relancer
docker builder prune --filter until=168h -f   # si le disque se remplit (cache des builds buildx)
```

Désinstaller :

```bash
cd /opt/party-runner && docker compose down && docker image rm party-runner:local
rm -rf /opt/party-runner
# puis retirer « party-linux » dans GitHub › Settings › Actions › Runners (ou :)
gh api -X DELETE repos/BobyCharbon/sonos-vendrediparty/actions/runners/$(gh api repos/BobyCharbon/sonos-vendrediparty/actions/runners --jq '.runners[]|select(.name=="party-linux").id')
```

Revenir aux machines GitHub : remettre `runs-on: ubuntu-latest` / `macos-15` / `xcode-27` dans `.github/workflows/`
(payant tant que le dépôt est privé).
