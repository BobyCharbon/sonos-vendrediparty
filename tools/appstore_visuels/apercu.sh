#!/bin/zsh
# Aperçu vidéo App Store (App Preview 6,9" : 886 × 1920, 30 i/s, H.264, piste son muette, 15 à 30 s).
# Usage : tools/appstore_visuels/apercu.sh <UDID du simulateur> <port du serveur local> <dossier de sortie>
# Filme le simulateur pendant testApercu (captures.sh), coupe au début et à la fin du tour, accélère s'il le faut.
set -euo pipefail
HERE=${0:A:h}
UDID="$1"; PORT="$2"; OUT="${3:A}"
WORK=$(mktemp -d)
mkdir -p "$OUT"
xcrun simctl io "$UDID" recordVideo --codec h264 --force "$WORK/brut.mov" &
REC=$!
trap 'kill -INT $REC 2>/dev/null || true' EXIT  # la caméra s'arrête même si le tour échoue
START=$(python3 -c 'import time; print(time.time())')
"$HERE/captures.sh" "$UDID" "$PORT" "$WORK/temps" "" testApercu >/dev/null
kill -INT $REC; wait $REC || true
FROM=$(python3 -c "print(float(open('$WORK/temps/apercu-temps.txt').read().split()[0]) - $START)")
TO=$(python3 -c "print(float(open('$WORK/temps/apercu-temps.txt').read().split()[1]) - $START)")
LEN=$(python3 -c "print($TO - $FROM)")
SPEED=$(python3 -c "print(max(1.0, $LEN / 29.0))")  # 30 s au plus
# 1320 × 2868 → 886 × 1925, puis 2 px coupés en haut et 3 en bas : 886 × 1920 (format exigé).
ffmpeg -y -loglevel error -ss "$FROM" -to "$TO" -i "$WORK/brut.mov" -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 \
  -filter:v "setpts=PTS/$SPEED,fps=30,scale=886:1925,crop=886:1920:0:2,format=yuv420p" -map 0:v -map 1:a -shortest \
  -c:v libx264 -profile:v high -level 4.0 -b:v 5M -maxrate 6M -bufsize 12M -c:a aac -b:a 256k "$OUT/01-tour-de-l-app-886x1920.mp4"
ffprobe -v error -show_entries stream=width,height,r_frame_rate,codec_name -show_entries format=duration -of compact "$OUT/01-tour-de-l-app-886x1920.mp4"
rm -rf "$WORK"
