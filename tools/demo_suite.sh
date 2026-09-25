#!/usr/bin/env bash
# The full walk-through: startup check, then every scenario in turn, with the
# MFA stepping through its modes and the odometer running fast enough to watch.
#
#   tools/demo_suite.sh                 # 800x480, 15 seconds per scenario
#   tools/demo_suite.sh 1920x720 25
set -euo pipefail

cd "$(dirname "$0")/.."

SIZE="${1:-800x480}"
SECONDS_EACH="${2:-15}"

PYTHON=".venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"

# A starting odometer that looks like a car with history, and simulated time
# running 30x so kilometres actually tick over while you watch.
ODOMETER=214778
TIME_SCALE=30

# Extract the intro once, if it has not been done for this size yet.
if ! compgen -G "images/intro/frame_*.png" >/dev/null && [ -f das_auto.mp4 ]; then
  if command -v ffmpeg >/dev/null; then
    tools/extract_intro.sh das_auto.mp4 "$SIZE"
  else
    echo "ffmpeg not installed, so no intro: sudo apt install ffmpeg"
  fi
fi

INTRO=""
compgen -G "images/intro/frame_*.png" >/dev/null && INTRO="--intro"

FIRST=1
for SCENARIO in cold-start idle drive sweep warnings; do
  echo "--- $SCENARIO"
  # The intro and the bulb check only belong at the very start.
  EXTRA=()
  if [ "$FIRST" = "1" ]; then
    [ -n "$INTRO" ] && EXTRA+=("$INTRO")
    EXTRA+=(--selftest 3)
    FIRST=0
  fi
  "$PYTHON" -m digifiz.app \
    --source demo --scenario "$SCENARIO" --size "$SIZE" \
    --odometer "$ODOMETER" --time-scale "$TIME_SCALE" \
    --mfa-cycle 3 --debug --exit-after "$SECONDS_EACH" \
    "${EXTRA[@]+"${EXTRA[@]}"}"
done

echo "done"
