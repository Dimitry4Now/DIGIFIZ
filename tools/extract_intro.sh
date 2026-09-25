#!/usr/bin/env bash
# Turn an intro clip into pre-scaled PNG frames, once, so the dash never has to
# decode video at runtime. This is what replaced the opencv-python dependency.
#
#   tools/extract_intro.sh das_auto.mp4 800x480
#
# Extract at the size of the panel you will run on: the frames are blitted
# straight to the screen with no scaling.
set -euo pipefail

cd "$(dirname "$0")/.."

VIDEO="${1:?usage: extract_intro.sh VIDEO [WIDTHxHEIGHT]}"
SIZE="${2:-1920x720}"
WIDTH="${SIZE%x*}"
HEIGHT="${SIZE#*x}"
OUT="images/intro"

[ -f "$VIDEO" ] || { echo "no such video: $VIDEO" >&2; exit 1; }

mkdir -p "$OUT"
rm -f "$OUT"/frame_*.png

if command -v ffmpeg >/dev/null; then
  ffmpeg -loglevel error -i "$VIDEO" \
    -vf "scale=${WIDTH}:${HEIGHT}:flags=lanczos" "$OUT/frame_%04d.png"
elif command -v gst-launch-1.0 >/dev/null; then
  # GStreamer is already on most desktop installs, so ffmpeg is not required.
  gst-launch-1.0 -q filesrc location="$VIDEO" ! decodebin ! videoconvert \
    ! videoscale ! "video/x-raw,width=${WIDTH},height=${HEIGHT}" \
    ! pngenc ! multifilesink location="$OUT/frame_%04d.png" 2>/dev/null
else
  echo "need ffmpeg or gst-launch-1.0: sudo apt install ffmpeg" >&2
  exit 1
fi

COUNT=$(ls "$OUT"/frame_*.png 2>/dev/null | wc -l)
[ "$COUNT" -gt 0 ] || { echo "extraction produced no frames" >&2; exit 1; }
echo "wrote $COUNT frames to $OUT at ${WIDTH}x${HEIGHT}"
