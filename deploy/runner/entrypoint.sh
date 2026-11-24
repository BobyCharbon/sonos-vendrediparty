#!/bin/bash
# Premier démarrage : enregistre le runner avec RUNNER_TOKEN (jeton d'enregistrement, valable 1 h) et garde son
# identité dans /runner-state. Démarrages suivants : reprend cette identité, sans jeton.
set -euo pipefail
cd /home/runner
STATE=/runner-state
for f in .runner .credentials .credentials_rsaparams; do
  if [ -f "$STATE/$f" ]; then cp "$STATE/$f" .; fi
done
if [ ! -f .runner ]; then
  if [ -z "${RUNNER_TOKEN:-}" ]; then
    echo "Runner pas encore enregistré : relancer avec RUNNER_TOKEN=… (voir deploy/runner/README.md)" >&2
    exit 1
  fi
  ./config.sh --unattended --replace \
    --url "${REPO_URL:-https://github.com/BobyCharbon/sonos-vendrediparty}" --token "$RUNNER_TOKEN" \
    --name "${RUNNER_NAME:-party-linux}" --labels party-linux --work /home/runner/_work
  cp .runner .credentials .credentials_rsaparams "$STATE/"
fi
exec ./run.sh
