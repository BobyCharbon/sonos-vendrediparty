#!/bin/sh
# Campagne 2, agent 09 : app iPhone (Release) sur le simulateur dédié « C2-09 iPhone », tests BotsVisualUITests.
# Usage : sh tests/bots/ios_visuel.sh <dossier de travail (contient src/ et bots/)> <origine> <session : littéral JS> <événement> <jeton> [test]
set -e
WORK="${1:?dossier}"; ORIGIN="${2:?origine}"; SESSION="${3:?session}"; EVENT="${4:?événement}"; TOKEN="${5:?jeton}"
TEST="${6:-BotsVisualUITests}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUTDIR="$WORK/bots/ios"
mkdir -p "$OUTDIR"
cp "$REPO"/tests/bots/ios/*.swift "$WORK/src/ios/PartyUITests/"
sed -i '' 's/testTargets: \[PartyTests, PartyUITests\]/testTargets: [PartyUITests]/' "$WORK/src/ios/project.yml"
(cd "$WORK/src/ios" && xcodegen generate --quiet)
SIM=$(xcrun simctl list devices | grep "C2-09 iPhone (" | head -1 | sed -E 's/.*\(([0-9A-F-]{36})\).*/\1/')
if [ -z "$SIM" ]; then SIM=$(xcrun simctl create "C2-09 iPhone" "iPhone 17"); fi
xcrun simctl boot "$SIM" 2>/dev/null || true
NAME=$(echo "$TEST" | tr '/' '-')
LOG="$OUTDIR/xcodebuild-$NAME.log"
xcrun simctl io "$SIM" recordVideo --codec h264 --force "$OUTDIR/video-$NAME.mp4" &
REC=$!
# Toujours recompiler le test du banc (sinon xcodebuild peut relancer un ancien PartyUITests-Runner).
rm -rf "$WORK/ios-dd/Build/Products/Release-iphonesimulator/PartyUITests-Runner.app"
set +e
TEST_RUNNER_BOTS_IOS_SESSION="$SESSION" TEST_RUNNER_BOTS_IOS_OUT="$OUTDIR" TEST_RUNNER_BOTS_IOS_EVENT="$EVENT" \
TEST_RUNNER_BOTS_IOS_TOKEN="$TOKEN" \
xcodebuild test -project "$WORK/src/ios/Party.xcodeproj" -scheme Party -configuration Release \
  -destination "id=$SIM" -derivedDataPath "$WORK/ios-dd" -only-testing:"PartyUITests/$TEST" \
  CODE_SIGNING_ALLOWED=NO PARTY_BASE_URL="$ORIGIN" > "$LOG" 2>&1
STATUS=$?
kill -INT $REC; wait $REC 2>/dev/null
grep "BOTS:" "$LOG" || true
echo "xcodebuild ($TEST) : $STATUS ; constats dans $OUTDIR"
