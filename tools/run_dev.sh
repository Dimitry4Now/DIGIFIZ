#!/usr/bin/env bash
# Start everything needed to see the dash running on a development machine:
# a broker, the simulator, and the dash itself. Cleans up on exit.
#
#   tools/run_dev.sh                       # drive cycle, windowed
#   tools/run_dev.sh --scenario warnings
#   tools/run_dev.sh --scenario sweep --size 800x480
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON=".venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"

SCENARIO="drive"
RATE="20"
SIZE="800x480"
EXTRA=()

while [ $# -gt 0 ]; do
  case "$1" in
    --scenario) SCENARIO="$2"; shift 2 ;;
    --rate)     RATE="$2"; shift 2 ;;
    --size)     SIZE="$2"; shift 2 ;;
    *)          EXTRA+=("$1"); shift ;;
  esac
done

# Start a broker only if nothing is already listening on 1883.
BROKER_PID=""
if ! (exec 3<>/dev/tcp/127.0.0.1/1883) 2>/dev/null; then
  if command -v mosquitto >/dev/null; then
    echo "starting mosquitto on 1883"
    mosquitto -p 1883 >/tmp/digifiz-mosquitto.log 2>&1 &
    BROKER_PID=$!
    sleep 0.5
  else
    echo "mosquitto not installed: sudo apt install mosquitto mosquitto-clients" >&2
    echo "falling back to the in-process demo source" >&2
    exec "$PYTHON" -m digifiz.app --source demo --scenario "$SCENARIO" \
      --size "$SIZE" --windowed --debug "${EXTRA[@]+"${EXTRA[@]}"}"
  fi
fi

SIM_PID=""
cleanup() {
  [ -n "$SIM_PID" ] && kill "$SIM_PID" 2>/dev/null || true
  [ -n "$BROKER_PID" ] && kill "$BROKER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$PYTHON" tools/mqtt_sim.py --scenario "$SCENARIO" --rate "$RATE" &
SIM_PID=$!

"$PYTHON" -m digifiz.app --source mqtt --size "$SIZE" --debug "${EXTRA[@]+"${EXTRA[@]}"}"
