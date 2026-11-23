#!/usr/bin/env bash
# Frame a raw screen recording for sharing: cut out the window, round its
# corners, drop a shadow under it and centre it on a dark 1920x1080 canvas.
# The result has no audio stream.
#
#   ./render_demo.sh raw_recording.mp4                       # 1366x768 window
#   ./render_demo.sh raw_recording.mp4 demo.mp4 1366x768
#
# The window is taken from the centre of the recording, which is where
# record_demo.sh puts it.
set -euo pipefail

RAW="${1:?usage: render_demo.sh RAW [OUT] [WIDTHxHEIGHT]}"
OUT="${2:-digifiz_demo_1080p.mp4}"
SIZE="${3:-1366x768}"
W="${SIZE%x*}"
H="${SIZE#*x}"

CANVAS_W=1920
CANVAS_H=1080
RADIUS=18
SHADOW_DROP=16
SHADOW_BLUR=28

[ -f "$RAW" ] || { echo "no such recording: $RAW" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "need ffmpeg: sudo apt install ffmpeg" >&2; exit 1; }

X0=$(( (CANVAS_W - W) / 2 ))
Y0=$(( (CANVAS_H - H) / 2 ))

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# The mask and the backdrop never change, so they are drawn once as stills
# rather than recomputed with geq on every frame.
EDGE_X="min(X,W-1-X)"
EDGE_Y="min(Y,H-1-Y)"
ffmpeg -loglevel error -y -f lavfi \
  -i "color=black:s=${W}x${H},format=gray,geq=lum='if(lt($EDGE_X,$RADIUS)*lt($EDGE_Y,$RADIUS),if(lte(hypot($RADIUS-$EDGE_X,$RADIUS-$EDGE_Y),$RADIUS),255,0),255)'" \
  -frames:v 1 "$WORK/mask.png"

# A dark gradient with the window's blurred silhouette laid on it as a shadow.
ffmpeg -loglevel error -y \
  -f lavfi -i "color=c=0x1e1e2e:s=${CANVAS_W}x${CANVAS_H},format=rgb24,geq=r='30-13*Y/H+10*X/W':g='30-13*Y/H':b='46-19*Y/H+14*X/W'" \
  -i "$WORK/mask.png" \
  -f lavfi -i "color=black:s=${CANVAS_W}x${CANVAS_H}" \
  -filter_complex "
    [1:v]format=gray,pad=${CANVAS_W}:${CANVAS_H}:${X0}:$((Y0 + SHADOW_DROP)):black,
      gblur=sigma=${SHADOW_BLUR},lutyuv=y='val*0.6'[alpha];
    [2:v][alpha]alphamerge[shadow];
    [0:v][shadow]overlay=0:0,format=rgb24" \
  -frames:v 1 "$WORK/backdrop.png"

# The looped stills never end on their own, so the recording sets the length.
DURATION="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$RAW")"

ffmpeg -loglevel error -y -an -i "$RAW" \
  -loop 1 -i "$WORK/mask.png" -loop 1 -i "$WORK/backdrop.png" \
  -filter_complex "
    [0:v]crop=${W}:${H}:(in_w-${W})/2:(in_h-${H})/2,format=rgba[window];
    [1:v]format=gray[mask];
    [window][mask]alphamerge[app];
    [2:v][app]overlay=${X0}:${Y0}:shortest=1,format=yuv420p" \
  -t "$DURATION" -r 30 -c:v libx264 -crf 18 -an -movflags +faststart "$OUT"

echo "wrote $OUT"
