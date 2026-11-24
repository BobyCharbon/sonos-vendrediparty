#!/bin/sh
# Copie de nuit des photos Souvenirs vers le NAS (procédure : deploy/souvenirs-nas.md). À lancer sur l'hôte Docker
# (192.168.50.204) par /etc/cron.d/party-souvenirs-nas. Miroir exact : --delete retire du NAS ce que Party a effacé
# (auteur, organisation, modération, compte, 13 mois, story sans enregistrement), au plus tard la nuit suivante.
# Usage : souvenirs-nas.sh <dossier souvenirs du volume Docker> <dossier du NAS>
set -eu
SRC="${1:?dossier source}"
DEST="${2:?dossier du NAS}"
STAMP="$SRC/.derniere-copie-nas"

[ -d "$SRC" ] || { echo "Souvenirs : $SRC absent (aucune photo encore)" >&2; exit 0; }
# Jamais vers le disque local si le partage du NAS n'est pas monté (sinon --delete viderait un dossier vide).
mountpoint -q "$(dirname "$DEST")" || mountpoint -q "$DEST" || { echo "Souvenirs : NAS non monté ($DEST)" >&2; exit 1; }
mkdir -p "$DEST"

# CIFS : ni propriétaire ni droits (-rt), horloge à 2 s près ; fichiers en cours d'écriture (*.tmp) ignorés.
rsync -rt --delete --modify-window=2 --exclude '*.tmp' --exclude '.derniere-copie-nas' "$SRC/" "$DEST/"

# Lue par l'admin (Réglages › Serveur : « dernière copie NAS : … »).
date -Iseconds > "$STAMP"
