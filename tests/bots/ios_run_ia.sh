#!/bin/sh
# « Créer avec l'IA » dans l'app iPhone (Release + E2E_HOOKS : brouillon injecté par PARTY_DEBUG_AI_EVENT, sans clé
# Anthropic) contre le serveur du banc (base de TEST), sur un simulateur dédié (défaut « C2-02 iPhone »), vidéo comprise.
# Usage : sh tests/bots/ios_run_ia.sh <dossier de travail (contient src/)> <origine> build
#         BOTS_IOS_PHONE=0790000104 BOTS_IOS_DRAFT='<json>' BOTS_IOS_CASE=nom sh tests/bots/ios_run_ia.sh <dossier> <origine> <test>
#   <test> : méthode de BotsAICreationUITests (ex. testLogin, testStepOneToThree…), ou d'une autre classe du banc
#   avec BOTS_IOS_CLASS (ex. BotsMemberNotificationsUITests, BOTS_IOS_STEP=off|on|de pour testQuietHours).
set -e
WORK="${1:?dossier de travail}"; ORIGIN="${2:?origine}"; WHAT="${3:?build ou test}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUTDIR="${BOTS_IOS_OUTDIR:-$WORK/ios}"
SIM_NAME="${BOTS_IOS_SIM:-C2-02 iPhone}"
mkdir -p "$OUTDIR"
SIM=$(xcrun simctl list devices | grep "$SIM_NAME (" | head -1 | sed -E 's/.*\(([0-9A-F-]{36})\).*/\1/')
if [ -z "$SIM" ]; then SIM=$(xcrun simctl create "$SIM_NAME" "iPhone 17"); fi
xcrun simctl boot "$SIM" 2>/dev/null || true
COMMON="-project $WORK/src/ios/Party.xcodeproj -scheme Party -configuration Release -destination id=$SIM -derivedDataPath $WORK/ios-dd"
if [ "$WHAT" = build ]; then
  cp "$REPO"/tests/bots/ios/BotsAICreationUITests.swift "$REPO"/tests/bots/ios/BotsMemberNotificationsUITests.swift "$WORK/src/ios/PartyUITests/"
  sed -i '' 's/testTargets: \[PartyTests, PartyUITests\]/testTargets: [PartyUITests]/' "$WORK/src/ios/project.yml"
  (cd "$WORK/src/ios" && xcodegen generate --quiet)
  # shellcheck disable=SC2086
  xcodebuild build-for-testing $COMMON CODE_SIGNING_ALLOWED=NO PARTY_BASE_URL="$ORIGIN" \
    SWIFT_ACTIVE_COMPILATION_CONDITIONS=E2E_HOOKS > "$OUTDIR/xcodebuild-build.log" 2>&1
  echo "construit : $(tail -1 "$OUTDIR/xcodebuild-build.log")"
  exit 0
fi
CASE="${BOTS_IOS_CASE:-$WHAT}"
xcrun simctl io "$SIM" recordVideo --codec h264 --force "$OUTDIR/video-$CASE.mp4" &
REC=$!
set +e
TEST_RUNNER_BOTS_IOS_OUT="$OUTDIR/$CASE" TEST_RUNNER_BOTS_IOS_PHONE="${BOTS_IOS_PHONE:-0790000104}" \
TEST_RUNNER_BOTS_IOS_DRAFT="${BOTS_IOS_DRAFT:-}" TEST_RUNNER_BOTS_IOS_STEP="${BOTS_IOS_STEP:-}" TEST_RUNNER_BOTS_IOS_CASE="$CASE" TEST_RUNNER_BOTS_IOS_CHOICE="${BOTS_IOS_CHOICE:-invite}" \
xcodebuild test-without-building $COMMON -only-testing:"PartyUITests/${BOTS_IOS_CLASS:-BotsAICreationUITests}/$WHAT" \
  > "$OUTDIR/xcodebuild-$CASE.log" 2>&1
STATUS=$?
kill -INT $REC; wait $REC 2>/dev/null
grep "BOTS:" "$OUTDIR/xcodebuild-$CASE.log" || true
grep -E "error:|Test Case .* (passed|failed)" "$OUTDIR/xcodebuild-$CASE.log" | tail -8
echo "xcodebuild ($WHAT / $CASE) : $STATUS ; constats et vidéo dans $OUTDIR"
