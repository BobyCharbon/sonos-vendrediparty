#!/bin/sh
# Mise à jour du serveur Party (avis eb710b132330) : tout le monde lit « Mise à jour en cours » pendant le redémarrage,
# au lieu d'une erreur. Usage, depuis le Mac de l'admin : deploy/update.sh prod   (ou test)
#   1. télécharge la nouvelle image (le serveur tourne encore) ;
#   2. affiche « Mise à jour en cours » à tout le monde (python -m app.notice deploy, dans le serveur qui tourne) ;
#   3. laisse 5 s aux téléphones pour le voir, puis redémarre ;
#   4. le serveur revenu efface ce message tout seul ; s'il n'a pas redémarré (même image), on l'efface ici.
# Une annonce posée par l'admin dans les Réglages est gardée. Sans ce script (redéploiement depuis Dockhand), l'app
# affiche quand même « Mise à jour en cours » dès que le serveur ne répond plus (réponse 502 / 503 / 504).
set -eu

case "${1:-}" in
  prod) stack=vendrediparty ;;
  test) stack=vendrediparty-test ;;
  *) echo "Usage : deploy/update.sh prod|test" >&2; exit 2 ;;
esac

ssh proxmox "pct exec 125 -- docker exec -e PORT=8090 -w /app/data/stacks/Docker/$stack dockhand sh -c '
  set -e
  docker compose -p $stack pull -q
  docker exec $stack python -m app.notice deploy || echo \"(message de mise à jour pas affiché : ancienne version)\"
  sleep 5
  docker compose -p $stack up -d
  sleep 3
  docker exec $stack python -m app.notice done >/dev/null 2>&1 || true
'"
echo "Mise à jour de $stack terminée."
