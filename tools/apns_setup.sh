#!/bin/bash
# Mise en service des notifications natives (APNs) une fois la clé créée sur developer.apple.com
# (Certificates, Identifiers & Profiles › Keys › « + » › Apple Push Notifications service).
# Usage (sur le Mac mini) : tools/apns_setup.sh ~/Downloads/AuthKey_XXXXXXXXXX.p8 [--prod]
#   - base de TEST : secrets de la fonction send-push (événements → app Party BETA) ;
#   - --prod : base de PRODUCTION aussi (app VendrediParty) et déploiement de send-push en prod. À lancer seulement
#     quand l'admin l'a décidé (règle CLAUDE.md).
# La clé n'est jamais affichée : elle part dans les secrets Supabase, et sur une ligne dans le presse-papiers pour
# la variable APNS_KEY_P8 des deux stacks Dockhand (party et partytest), avec APNS_KEY_ID affiché ci-dessous.
set -euo pipefail

KEY_FILE="${1:?Chemin du fichier AuthKey_XXXXXXXXXX.p8}"
PROD="${2:-}"
TEST_REF="ewromqfsmcqsthftyhzm"
PROD_REF="gsuetixzobooggeaubvb"
TEAM_ID="GS2B6GA9JA"
CLI="npx --yes supabase@2.58.5"

[ -f "$KEY_FILE" ] || { echo "Fichier introuvable : $KEY_FILE" >&2; exit 1; }
grep -q "BEGIN PRIVATE KEY" "$KEY_FILE" || { echo "Ce fichier n'est pas une clé .p8" >&2; exit 1; }
KEY_ID="$(basename "$KEY_FILE" .p8 | sed 's/^AuthKey_//')"
[[ "$KEY_ID" =~ ^[A-Z0-9]{10}$ ]] || { echo "Identifiant de clé illisible dans le nom du fichier ($KEY_ID)" >&2; exit 1; }
SUPABASE_ACCESS_TOKEN="$(cat ~/.config/supabase-claude/token)"
export SUPABASE_ACCESS_TOKEN
ONE_LINE="$(tr -d '\n' < "$KEY_FILE")"

set_secrets() {  # set_secrets <projet> <identifiant de l'app>
  $CLI secrets set --project-ref "$1" APNS_KEY_P8="$ONE_LINE" APNS_KEY_ID="$KEY_ID" APNS_TEAM_ID="$TEAM_ID" APNS_TOPIC="$2" > /dev/null
  echo "✓ Secrets APNs posés sur le projet $1 ($2)"
}

set_secrets "$TEST_REF" "ch.bobycharbon.party.beta"
if [ "$PROD" = "--prod" ]; then
  set_secrets "$PROD_REF" "ch.bobycharbon.party"
  (cd "$(dirname "$0")/.." && $CLI functions deploy send-push --project-ref "$PROD_REF" --use-api > /dev/null)
  echo "✓ Fonction send-push déployée en production"
fi

printf '%s' "$ONE_LINE" | pbcopy
echo
echo "Clé copiée dans le presse-papiers (une ligne). Dans Dockhand, pour les stacks « party » ET « partytest » :"
echo "  APNS_KEY_P8 = (coller)"
echo "  APNS_KEY_ID = $KEY_ID"
echo "puis « Redéployer ». Garde le fichier .p8 en lieu sûr (Apple ne le redonne jamais)."
