#!/usr/bin/env bash
# Record a take of the dash for sharing: a terminal opens, the intro frames are
# extracted, the dash runs on the demo source and is stopped with Ctrl+C. The
# raw capture is then framed by render_demo.sh, which sits next to this script.
#
#   ./record_demo.sh                          # digifiz_demo_1080p.mp4
#   ./record_demo.sh ~/Videos/demo.mp4 14     # output, seconds of dash
#
# The dash is run from this repository; DIGIFIZ_DIR points at another checkout.
#
# Needs an X11 session with ffmpeg, xdotool, wmctrl and gnome-terminal. Every
# other window is minimised for the take and restored afterwards, and the
# keyboard is driven throughout, so leave the machine alone until it finishes.
#
# The intro is re-extracted at the recording size, replacing whatever is in
# images/intro/ in that checkout.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="${DIGIFIZ_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
[ -f "$PROJECT/main.py" ] || { echo "no DIGIFIZ checkout at $PROJECT" >&2; exit 1; }

OUT="${1:-digifiz_demo_1080p.mp4}"
RUN_SECONDS="${2:-14}"
W=1366
H=768

export DISPLAY="${DISPLAY:-:0}"

for tool in ffmpeg xdotool wmctrl xwininfo xprop gnome-terminal; do
  command -v "$tool" >/dev/null || { echo "need $tool" >&2; exit 1; }
done
[ "${XDG_SESSION_TYPE:-x11}" = "x11" ] || { echo "needs an X11 session" >&2; exit 1; }

read -r SCREEN_W SCREEN_H <<<"$(xdotool getdisplaygeometry)"
X0=$(( (SCREEN_W - W) / 2 ))
Y0=$(( (SCREEN_H - H) / 2 ))

WORK="$(mktemp -d)"
RAW="$WORK/raw_recording.mp4"

RECORD_PID=""
MINIMISED=()
TERM_WID=""
ACTIVE_BEFORE="$(xdotool getactivewindow 2>/dev/null || true)"

cleanup() {
  [ -n "$RECORD_PID" ] && kill -2 "$RECORD_PID" 2>/dev/null && wait "$RECORD_PID" 2>/dev/null
  [ -n "$TERM_WID" ] && wmctrl -ic "$TERM_WID" 2>/dev/null
  for wid in "${MINIMISED[@]}"; do
    xdotool windowmap "$wid" 2>/dev/null
    wmctrl -ia "$wid" 2>/dev/null
  done
  [ -n "$ACTIVE_BEFORE" ] && xdotool windowactivate "$ACTIVE_BEFORE" 2>/dev/null
  rm -rf "$WORK"
}
trap cleanup EXIT

window_ids() { wmctrl -l | awk '{print $1}'; }

# The window that was not there when BEFORE was taken.
new_window() { comm -13 <(sort <<<"$1") <(window_ids | sort) | head -1; }

# Client area as "x y w h". xwininfo is used because xdotool reports a
# position that counts the decoration offset twice under Cinnamon.
client_rect() {
  xwininfo -id "$1" | awk '
    /Absolute upper-left X/ {x=$NF} /Absolute upper-left Y/ {y=$NF}
    /^ *Width/ {w=$NF} /^ *Height/ {h=$NF} END {print x, y, w, h}'
}

# The client area grown by the title bar and borders: what is actually seen.
visible_rect() {
  local x y w h l=0 r=0 t=0 b=0 extents
  read -r x y w h <<<"$(client_rect "$1")"
  extents="$(xprop -id "$1" _NET_FRAME_EXTENTS 2>/dev/null | grep -oE '[0-9]+, [0-9]+, [0-9]+, [0-9]+')"
  [ -n "$extents" ] && IFS=', ' read -r l r t b <<<"$extents"
  echo "$((x - l)) $((y - t)) $((w + l + r)) $((h + t + b))"
}

# place WID RECT_FUNCTION: nudge the window until that rectangle's top-left
# corner sits on the crop's, so any overshoot is trimmed off the far edges.
place() {
  local wid="$1" rect="$2" ax=$X0 ay=$Y0 vx vy dx dy
  for _ in 1 2 3 4; do
    xdotool windowmove "$wid" "$ax" "$ay"
    sleep 0.25
    read -r vx vy _ _ <<<"$("$rect" "$wid")"
    dx=$((X0 - vx)); dy=$((Y0 - vy))
    [ "$dx" -eq 0 ] && [ "$dy" -eq 0 ] && break
    ax=$((ax + dx)); ay=$((ay + dy))
  done
}

type_line() {
  xdotool type --clearmodifiers --delay 55 "$1"
  sleep 0.4
  xdotool key Return
}

# Clear the desktop, and park the pointer where the crop will not see it.
for wid in $(window_ids); do
  xprop -id "$wid" _NET_WM_WINDOW_TYPE | grep -qE 'DESKTOP|DOCK' && continue
  xprop -id "$wid" _NET_WM_STATE | grep -q HIDDEN && continue
  xdotool windowminimize "$wid" && MINIMISED+=("$wid")
done
xdotool mousemove $((SCREEN_W - 20)) $((SCREEN_H - 20))
sleep 1

ffmpeg -loglevel error -y -an -f x11grab -draw_mouse 1 -framerate 30 \
  -video_size "${SCREEN_W}x${SCREEN_H}" -i "$DISPLAY.0" \
  -c:v libx264 -preset ultrafast -pix_fmt yuv420p "$RAW" </dev/null &
RECORD_PID=$!
sleep 1.5

# SDL_VIDEO_WINDOW_POS makes the dash open where the crop is, rather than
# jumping there on camera.
BEFORE="$(window_ids)"
gnome-terminal --working-directory="$HOME" -- env SDL_VIDEO_WINDOW_POS="$X0,$Y0" bash
for _ in $(seq 40); do
  TERM_WID="$(new_window "$BEFORE")"
  [ -n "$TERM_WID" ] && break
  sleep 0.25
done
[ -n "$TERM_WID" ] || { echo "terminal never appeared" >&2; exit 1; }

# Terminals resize in whole character cells, so grow until the crop is covered.
read -r _ _ vw vh <<<"$(visible_rect "$TERM_WID")"
read -r _ _ cw ch <<<"$(client_rect "$TERM_WID")"
rw=$((W - (vw - cw))); rh=$((H - (vh - ch)))
for _ in 1 2 3 4 5 6; do
  xdotool windowsize "$TERM_WID" "$rw" "$rh"
  sleep 0.3
  read -r _ _ vw vh <<<"$(visible_rect "$TERM_WID")"
  [ "$vw" -ge "$W" ] && [ "$vh" -ge "$H" ] && break
  [ "$vw" -lt "$W" ] && rw=$((rw + W - vw + 4))
  [ "$vh" -lt "$H" ] && rh=$((rh + H - vh + 4))
done
place "$TERM_WID" visible_rect
xdotool windowactivate --sync "$TERM_WID"
xdotool key --clearmodifiers ctrl+l
sleep 1

type_line "cd $PROJECT"
sleep 0.8
type_line "tools/extract_intro.sh das_auto.mp4 ${W}x${H}"
sleep 1
for _ in $(seq 300); do
  pgrep -f 'extract_intro.sh|trim_black_frames' >/dev/null || break
  sleep 0.3
done
sleep 1.2

BEFORE="$(window_ids)"
type_line ".venv/bin/python main.py --source demo --windowed --size ${W}x${H}"
APP_WID=""
for _ in $(seq 60); do
  APP_WID="$(new_window "$BEFORE")"
  [ -n "$APP_WID" ] && break
  sleep 0.25
done
[ -n "$APP_WID" ] || { echo "dash window never appeared" >&2; exit 1; }
xdotool windowactivate "$APP_WID"
place "$APP_WID" client_rect

# The intro takes the first few seconds of this.
sleep "$RUN_SECONDS"

xdotool windowactivate --sync "$TERM_WID"
sleep 0.3
xdotool key --clearmodifiers ctrl+c
sleep 2

kill -2 "$RECORD_PID"
wait "$RECORD_PID"
RECORD_PID=""

"$HERE/render_demo.sh" "$RAW" "$OUT" "${W}x${H}"
