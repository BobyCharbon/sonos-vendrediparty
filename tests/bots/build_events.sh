#!/bin/sh
# Construit le module Événements de HEAD (develop) branché sur la base de TEST, hors de web/events/dist
# (utilisé par d'autres tests) : sources exportées par git archive dans $1/src, module dans $1/events-dist.
# Usage : sh tests/bots/build_events.sh <dossier de travail>
set -e
WORK="${1:?dossier de travail}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
rm -rf "$WORK/src" "$WORK/events-dist"
mkdir -p "$WORK/src"
git -C "$REPO" archive HEAD | tar -x -C "$WORK/src"
ln -s "$REPO/web/events/node_modules" "$WORK/src/web/events/node_modules"
cd "$WORK/src/web/events"
EXPO_PUBLIC_SUPABASE_URL=https://ewromqfsmcqsthftyhzm.supabase.co \
EXPO_PUBLIC_SUPABASE_ANON_KEY="$(cat "$HOME/.config/supabase-claude/test-publishable-key")" \
  npx expo export --platform web --output-dir "$WORK/events-dist" --clear  # sans --clear, le cache de Metro a servi d'anciennes pages
# Même retouche que scripts/postbuild.mjs, appliquée à la copie du banc (le script d'origine écrit dans web/events/dist).
sed "s#new URL('../dist/index.html', import.meta.url)#'$WORK/events-dist/index.html'#" scripts/postbuild.mjs > "$WORK/postbuild.mjs"
node "$WORK/postbuild.mjs"
grep -q 'id="app-shell"' "$WORK/events-dist/index.html"
# Garde-fou : le banc ne parle JAMAIS à la base de production (un cache périmé l'a déjà fait viser).
if grep -rq gsuetixzobooggeaubvb "$WORK/events-dist"; then echo "ERREUR : le module vise la base de PRODUCTION" >&2; exit 1; fi
grep -rq ewromqfsmcqsthftyhzm "$WORK/events-dist" || { echo "ERREUR : le module ne vise pas la base de TEST" >&2; exit 1; }
echo "Module prêt : $WORK/events-dist (sources : $WORK/src, commit $(git -C "$REPO" rev-parse --short HEAD))"
