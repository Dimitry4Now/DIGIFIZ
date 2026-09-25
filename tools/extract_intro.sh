#!/usr/bin/env bash
# Turn an intro clip into pre-scaled PNG frames, once, so the dash never has to
# decode video at runtime. This is what replaced the opencv-python dependency.
#
#   tools/extract_intro.sh das_auto.mp4 1920x720
set -euo pipefail

VIDEO="${1:?usage: extract_intro.sh VIDEO [WIDTHxHEIGHT]}"
SIZE="${2:-1920x720}"
OUT="images/intro"

command -v ffmpeg >/dev/null || { echo "ffmpeg not installed" >&2; exit 1; }

mkdir -p "$OUT"
rm -f "$OUT"/frame_*.png
ffmpeg -loglevel error -i "$VIDEO" -vf "scale=${SIZE/x/:}:flags=lanczos" \
  "$OUT/frame_%04d.png"
echo "wrote $(ls "$OUT"/frame_*.png | wc -l) frames to $OUT at $SIZE"
