#!/bin/zsh
# Captures App Store 6,9" (1320 × 2868) de l'app iOS, une par onglet, sur le simulateur.
# Usage : ios/scripts/screenshots.sh <Party.app (build Debug simulateur)> <dossier de sortie>
# Le build Debug lit PARTY_DEBUG_JS (NativeBridge.swift) : on y choisit l'onglet ouvert au lancement.
set -euo pipefail
APP="$1"
OUT="$2"
DEVICE_NAME="${DEVICE_NAME:-iPhone 17 Pro Max}"
LOAD_SECONDS="${LOAD_SECONDS:-15}"
BUNDLE_ID="${BUNDLE_ID:-ch.bobycharbon.party}"
mkdir -p "$OUT"

UDID=$(xcrun simctl list devices available -j | /usr/bin/python3 -c "
import json, sys
name = sys.argv[1]
devices = [d for runtime in json.load(sys.stdin)['devices'].values() for d in runtime if d['name'] == name]
print(devices[0]['udid'])" "$DEVICE_NAME")
xcrun simctl boot "$UDID" 2>/dev/null || true
xcrun simctl bootstatus "$UDID" -b >/dev/null
xcrun simctl status_bar "$UDID" override --time 9:41 --batteryState charged --batteryLevel 100 \
  --wifiBars 3 --cellularBars 4 --cellularMode active
xcrun simctl install "$UDID" "$APP"

capture() {  # capture <numéro> <onglet>
  local js="localStorage.setItem('vp_tab','$2');localStorage.setItem('vp_name','Léa');localStorage.setItem('vp_install_dismissed','1')"
  SIMCTL_CHILD_PARTY_DEBUG_JS="$js" xcrun simctl launch --terminate-running-process "$UDID" "$BUNDLE_ID" >/dev/null
  sleep "$LOAD_SECONDS"
  xcrun simctl io "$UDID" screenshot "$OUT/$1-$2.png" >/dev/null
  echo "$OUT/$1-$2.png"
}

# Premier lancement à blanc : le cache web se remplit, les captures suivantes sont complètes.
capture 0 music >/dev/null && rm -f "$OUT/0-music.png"
capture 1 games
capture 2 music
capture 3 feedback
capture 4 account
