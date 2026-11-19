#!/bin/zsh
# Captures brutes du simulateur 6,9" pour les visuels App Store (voir docs/app-store/visuels/README.md).
# Usage : tools/appstore_visuels/captures.sh <UDID du simulateur> <port du serveur local> <dossier brut> [étapes] [test]
#   étapes : events,event,eventchat,poll,ticket,chats,chat,pot,ia,games,music (défaut) ; groups (page du groupe) en plus ; test : testCaptures (défaut) ou testApercu
# Prérequis : serveur Party local sur la base de TEST (drapeaux de la prod), données de demo_data.py.
set -euo pipefail
HERE=${0:A:h}
ROOT=${HERE:h:h}
UDID="$1"; PORT="$2"; OUT="${3:A}"; STEPS="${4:-events,event,eventchat,poll,ticket,chats,chat,pot,ia,games,music}"; TEST="${5:-testCaptures}"
mkdir -p "$OUT"
xcrun simctl boot "$UDID" 2>/dev/null || true
xcrun simctl bootstatus "$UDID" -b >/dev/null
# Barre d'état propre (jamais une fausse barre dessinée : c'est celle du simulateur).
xcrun simctl status_bar "$UDID" override --time 9:41 --batteryState charged --batteryLevel 100 \
  --cellularBars 4 --wifiBars 3 --cellularMode active
cd "$ROOT/ios"
xcodegen >/dev/null
TEST_RUNNER_VISUELS_DIR="$OUT" TEST_RUNNER_VISUELS_ONLY="$STEPS" \
TEST_RUNNER_VISUELS_JS="$(cat "$HERE/demo_only.js")" \
TEST_RUNNER_VISUELS_HOST_DEMO="$(cat "$HERE/host_demo.json")" \
TEST_RUNNER_VISUELS_AI_DRAFT="$(cat "$HERE/ia_draft.json")" \
TEST_RUNNER_VISUELS_AI_SAID="Soirée karaoké chez moi le samedi 12 décembre à 20 h, avenue de la Gare 21 à Sion. Chacun amène un dessert !" \
TEST_RUNNER_VISUELS_SERVER="http://127.0.0.1:$PORT" \
xcodebuild test -project Party.xcodeproj -scheme Party -configuration Release -destination "id=$UDID" \
  -derivedDataPath "${DERIVED_DATA:-/tmp/party-visuels-dd}" ENABLE_TESTABILITY=YES PARTY_SWIFT_CONDITIONS=E2E_HOOKS \
  PARTY_BASE_URL="http://127.0.0.1:$PORT" "-only-testing:PartyUITests/VisuelsAppStoreUITests/$TEST" > "$OUT.log" 2>&1 \
  || { grep -E "error:" "$OUT.log" | tail -5; exit 1; }
ls -l "$OUT"
