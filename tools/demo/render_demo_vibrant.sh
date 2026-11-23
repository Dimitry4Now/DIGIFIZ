#!/usr/bin/env bash
# Frame a raw screen recording for sharing: cut out the window, round its
# corners, drop a shadow under it and centre it on a vivid 1920x1080 gradient,
# the soft blobs-of-colour kind a macOS wallpaper has. The result has no audio
# stream.
#
#   ./render_demo_vibrant.sh raw_recording.mp4                       # 1366x768 window
#   ./render_demo_vibrant.sh raw_recording.mp4 demo.mp4 1366x768
#   RADIUS=2 ./render_demo_vibrant.sh raw_recording.mp4      # barely rounded
#
# The window is taken from the centre of the recording, which is where
# record_sweep_demo.sh puts it.
set -euo pipefail

RAW="${1:?usage: render_demo_vibrant.sh RAW [OUT] [WIDTHxHEIGHT]}"
OUT="${2:-digifiz_sweep_demo_1080p.mp4}"
SIZE="${3:-1366x768}"
W="${SIZE%x*}"
H="${SIZE#*x}"

CANVAS_W=1920
CANVAS_H=1080
RADIUS="${RADIUS:-18}"
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

# The gradient: blobs of colour, each weighted by a gaussian of the distance
# to its centre and blended. "x y r g b" with x and y as fractions of the canvas.
BLOBS=(
  "0.05 0.10  88  60 255"   # violet, top left
  "0.95 0.05 255  70 165"   # pink, top right
  "1.00 0.95 255 150  55"   # orange, bottom right
  "0.00 1.00  20 170 255"   # sky blue, bottom left
  "0.50 0.55 150  60 240"   # purple, behind the window
)
SPREAD=0.42
WEIGHTS="" RED="" GREEN="" BLUE=""
for blob in "${BLOBS[@]}"; do
  read -r bx by br bg bb <<<"$blob"
  weight="exp(-(pow(X/W-$bx,2)+pow(Y/H-$by,2))/$SPREAD/$SPREAD)"
  WEIGHTS+="+$weight"; RED+="+$br*$weight"; GREEN+="+$bg*$weight"; BLUE+="+$bb*$weight"
done

# Drawn small and scaled up, since it is smooth anyway, with a little noise so
# the encoder does not turn it into bands. The window's blurred silhouette goes
# on top as a shadow.
ffmpeg -loglevel error -y \
  -f lavfi -i "color=black:s=$((CANVAS_W / 4))x$((CANVAS_H / 4)),format=rgb24,geq=r='(0$RED)/(0$WEIGHTS)':g='(0$GREEN)/(0$WEIGHTS)':b='(0$BLUE)/(0$WEIGHTS)'" \
  -i "$WORK/mask.png" \
  -f lavfi -i "color=black:s=${CANVAS_W}x${CANVAS_H}" \
  -filter_complex "
    [0:v]scale=${CANVAS_W}:${CANVAS_H}:flags=bicubic,noise=alls=4:allf=u[gradient];
    [1:v]format=gray,pad=${CANVAS_W}:${CANVAS_H}:${X0}:$((Y0 + SHADOW_DROP)):black,
      gblur=sigma=${SHADOW_BLUR},lutyuv=y='val*0.65'[alpha];
    [2:v][alpha]alphamerge[shadow];
    [gradient][shadow]overlay=0:0,format=rgb24" \
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
