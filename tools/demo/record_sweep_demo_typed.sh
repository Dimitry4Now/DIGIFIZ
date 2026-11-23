#!/usr/bin/env bash
# Record a take of the sweep scenario for sharing, typed the way a person
# would: uneven key timing, short hesitations, and paths finished in one go as
# if by Tab. In an already placed terminal the intro frames are extracted, then
# the dash runs with every gauge and the odometer sweeping end to end and the
# MFA stepping to its next mode every few seconds, and is stopped with Ctrl+C.
# The raw capture is then framed by render_demo_vibrant.sh, which sits next to
# this script, with the window's corners only just rounded.
#
#   ./record_sweep_demo_typed.sh                          # digifiz_sweep_typed_demo_1080p.mp4
#   ./record_sweep_demo_typed.sh ~/Videos/sweep.mp4 15 3  # output, seconds of dash,
#                                                         # seconds per MFA mode
#
# The dash is run from this repository; DIGIFIZ_DIR points at another checkout.
#
# Needs an X11 session with ffmpeg, xdotool, wmctrl and gnome-terminal. Every
# other window is minimised for the take and restored afterwards, and the
# keyboard is driven throughout, so leave the machine alone until it finishes.
# The terminal profile's transparency is switched off for the take and put back.
#
# The intro is re-extracted at the recording size, replacing whatever is in
# images/intro/ in that checkout.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="${DIGIFIZ_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
[ -f "$PROJECT/main.py" ] || { echo "no DIGIFIZ checkout at $PROJECT" >&2; exit 1; }

OUT="${1:-digifiz_sweep_typed_demo_1080p.mp4}"
DASH_SECONDS="${2:-15}"
MFA_SECONDS="${3:-3}"
# How long the intro, its dissolve and the asset load hold the dash back.
INTRO_SECONDS=4
# Corner radius of the window in the finished video, in pixels.
WINDOW_RADIUS=2
W=1366
H=768

export DISPLAY="${DISPLAY:-:0}"

for tool in ffmpeg xdotool wmctrl xwininfo xprop gnome-terminal dconf gsettings; do
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

PROFILE="$(gsettings get org.gnome.Terminal.ProfilesList default | tr -d "'")"
TRANSPARENCY_KEY="/org/gnome/terminal/legacy/profiles:/:$PROFILE/use-transparent-background"
TRANSPARENCY_BEFORE="$(dconf read "$TRANSPARENCY_KEY")"

cleanup() {
  [ -n "$RECORD_PID" ] && kill -2 "$RECORD_PID" 2>/dev/null && wait "$RECORD_PID" 2>/dev/null
  [ -n "$TERM_WID" ] && wmctrl -ic "$TERM_WID" 2>/dev/null
  for wid in "${MINIMISED[@]}"; do
    xdotool windowmap "$wid" 2>/dev/null
    wmctrl -ia "$wid" 2>/dev/null
  done
  [ -n "$ACTIVE_BEFORE" ] && xdotool windowactivate "$ACTIVE_BEFORE" 2>/dev/null
  if [ -n "$TRANSPARENCY_BEFORE" ]; then
    dconf write "$TRANSPARENCY_KEY" "$TRANSPARENCY_BEFORE"
  else
    dconf reset "$TRANSPARENCY_KEY"
  fi
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

# A random duration between two bounds, in seconds.
between() { awk -v lo="$1" -v hi="$2" -v r="$RANDOM" 'BEGIN { printf "%.3f", lo + (hi - lo) * r / 32767 }'; }

hesitate() { sleep "$(between 0.2 0.3)"; }

# human TEXT [SLOWDOWN]: one key at a time at an uneven pace, with the odd
# hesitation between words.
human() {
  local text="$1" slowdown="${2:-1}" i char
  for ((i = 0; i < ${#text}; i++)); do
    char="${text:i:1}"
    xdotool type --clearmodifiers --delay 0 -- "$char"
    sleep "$(awk -v t="$(between 0.07 0.17)" -v s="$slowdown" 'BEGIN { print t * s }')"
    [ "$char" = " " ] && [ $((RANDOM % 2)) -eq 0 ] && hesitate
  done
}

# completed START REST: type the start of a name, then have the rest land at
# once, which is what pressing Tab looks like. Real completion is not used
# because what it does depends on the shell and on what else is in the folder.
completed() {
  human "$1"
  hesitate
  xdotool type --clearmodifiers --delay 3 -- "$2"
  hesitate
}

enter() {
  sleep "$(between 0.35 0.6)"
  xdotool key Return
}

# How much of each folder name is typed before "Tab". Anything not listed gets
# its first half.
declare -A TYPED_START=([home]=ho [Desktop]=Desk)

# completed_path /a/b/c: walk a path one completed folder at a time.
completed_path() {
  local segment start segments
  IFS=/ read -ra segments <<<"${1#/}"
  for segment in "${segments[@]}"; do
    start="${TYPED_START[$segment]:-${segment:0:$(( (${#segment} + 1) / 2 > 3 ? 3 : (${#segment} + 1) / 2 ))}}"
    human "/"
    completed "$start" "${segment:${#start}}"
  done
}

# Clear the desktop, and park the pointer where the crop will not see it.
for wid in $(window_ids); do
  xprop -id "$wid" _NET_WM_WINDOW_TYPE | grep -qE 'DESKTOP|DOCK' && continue
  xprop -id "$wid" _NET_WM_STATE | grep -q HIDDEN && continue
  xdotool windowminimize "$wid" && MINIMISED+=("$wid")
done
xdotool mousemove $((SCREEN_W - 20)) $((SCREEN_H - 20))
sleep 1

# A solid terminal, so the wallpaper does not show through the take.
dconf write "$TRANSPARENCY_KEY" false

# The terminal is opened and put in place before the camera rolls, so the take
# starts on a still window. SDL_VIDEO_WINDOW_POS does the same for the dash: it
# opens where the crop is rather than jumping there.
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

ffmpeg -loglevel error -y -an -f x11grab -draw_mouse 1 -framerate 30 \
  -video_size "${SCREEN_W}x${SCREEN_H}" -i "$DISPLAY.0" \
  -c:v libx264 -preset ultrafast -pix_fmt yuv420p "$RAW" </dev/null &
RECORD_PID=$!
sleep 1.5

human "cd"
sleep 0.5
human " "
completed_path "$PROJECT"
enter
sleep 1.2

completed "to" "ols/"
completed "ex" "tract_intro.sh "
completed "das" "_auto.mp4 "
human "${W}x${H}" 2
enter
sleep 1
for _ in $(seq 300); do
  pgrep -f 'extract_intro.sh|trim_black_frames' >/dev/null || break
  sleep 0.3
done
sleep 1.2

BEFORE="$(window_ids)"
completed ".v" "env/"
completed "b" "in/"
completed "py" "thon"
human " "
completed "ma" "in.py "
human "--source demo --scenario sweep --mfa-cycle $MFA_SECONDS --size "
human "${W}x${H}" 2
enter
APP_WID=""
for _ in $(seq 60); do
  APP_WID="$(new_window "$BEFORE")"
  [ -n "$APP_WID" ] && break
  sleep 0.25
done
[ -n "$APP_WID" ] || { echo "dash window never appeared" >&2; exit 1; }
xdotool windowactivate "$APP_WID"
place "$APP_WID" client_rect

sleep "$((INTRO_SECONDS + DASH_SECONDS))"

xdotool windowactivate --sync "$TERM_WID"
sleep 0.3
xdotool key --clearmodifiers ctrl+c
sleep 2

kill -2 "$RECORD_PID"
wait "$RECORD_PID"
RECORD_PID=""

RADIUS="$WINDOW_RADIUS" "$HERE/render_demo_vibrant.sh" "$RAW" "$OUT" "${W}x${H}"
