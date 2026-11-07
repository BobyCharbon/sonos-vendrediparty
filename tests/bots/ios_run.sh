#!/bin/sh
# Parcours organisateur dans l'app iPhone (Release) sur un simulateur dédié « Bots iPhone 17 », contre le serveur du
# banc (base de TEST), avec enregistrement vidéo (simctl io recordVideo).
# Usage : sh tests/bots/ios_run.sh <dossier de travail (contient src/)> <origine du serveur> <session : littéral JS (chaîne JSON entre guillemets)> [titre]
# BOTS_IOS_TEST : test à lancer (défaut BotsOrganizerUITests ; ex. BotsAnnouncementsUITests/testValidatorAcceptsInActivity),
# BOTS_IOS_PHONE / BOTS_IOS_WHO : numéro (0790000101…) et nom court du bot, pour les tests qui se connectent eux-mêmes.
set -e
WORK="${1:?dossier de travail}"; ORIGIN="${2:?origine}"; SESSION="${3:?session}"; TITLE="${4:-Bot Soirée complète}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUTDIR="$WORK/bots/ios"
mkdir -p "$OUTDIR"
cp "$REPO"/tests/bots/ios/*.swift "$WORK/src/ios/PartyUITests/"
TEST="${BOTS_IOS_TEST:-BotsOrganizerUITests}"
# Copie du banc seulement : le schéma n'embarque que les tests d'interface (PartyTests utilise des aides DEBUG).
sed -i '' 's/testTargets: \[PartyTests, PartyUITests\]/testTargets: [PartyUITests]/' "$WORK/src/ios/project.yml"
(cd "$WORK/src/ios" && xcodegen generate --quiet)
SIM=$(xcrun simctl list devices | grep "Bots iPhone 17 (" | head -1 | sed -E 's/.*\(([0-9A-F-]{36})\).*/\1/')
if [ -z "$SIM" ]; then SIM=$(xcrun simctl create "Bots iPhone 17" "iPhone 17"); fi
xcrun simctl boot "$SIM" 2>/dev/null || true
xcrun simctl io "$SIM" recordVideo --codec h264 --force "$OUTDIR/video-$(echo "$TEST" | tr '/' '-').mp4" &
REC=$!
# Toujours recompiler le test du banc (sinon xcodebuild peut relancer un ancien PartyUITests-Runner).
rm -rf "$WORK/ios-dd/Build/Products/Release-iphonesimulator/PartyUITests-Runner.app" \
  "$WORK/ios-dd/Build/Intermediates.noindex/Party.build/Release-iphonesimulator/PartyUITests.build"
set +e
TEST_RUNNER_BOTS_IOS_SESSION="$SESSION" TEST_RUNNER_BOTS_IOS_OUT="$OUTDIR" TEST_RUNNER_BOTS_IOS_EVENT_TITLE="$TITLE" \
TEST_RUNNER_BOTS_IOS_PHONE="${BOTS_IOS_PHONE:-0790000103}" TEST_RUNNER_BOTS_IOS_WHO="${BOTS_IOS_WHO:-bot}" \
xcodebuild test -project "$WORK/src/ios/Party.xcodeproj" -scheme Party -configuration Release \
  -destination "id=$SIM" -derivedDataPath "$WORK/ios-dd" -only-testing:"PartyUITests/$TEST" \
  CODE_SIGNING_ALLOWED=NO PARTY_BASE_URL="$ORIGIN" > "$OUTDIR/xcodebuild-$(echo "$TEST" | tr '/' '-').log" 2>&1
STATUS=$?
kill -INT $REC; wait $REC 2>/dev/null
grep "BOTS:" "$OUTDIR/xcodebuild-$(echo "$TEST" | tr '/' '-').log" || true
echo "xcodebuild ($TEST) : $STATUS ; constats et vidéo dans $OUTDIR"
