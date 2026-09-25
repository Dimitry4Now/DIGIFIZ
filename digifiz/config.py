"""Static configuration.

Nothing here touches pygame, so this module is safe to import from tools and
tests. The display is created explicitly in :mod:`digifiz.app`.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = ROOT / "images"
FONT_DIR = ROOT / "fonts"
INTRO_DIR = IMAGE_DIR / "intro"
ODO_FILE = ROOT / "odo.txt"

PROJECT_NAME = "Digifiz Dashboard"

# The artwork is authored at this size. Every coordinate in layout.py is in
# this space, and everything is scaled once at load time to fit the real
# display. Changing the panel means changing nothing but the display mode.
LOGICAL_SIZE = (1920, 720)

# The data arrives at 2-20 Hz, so there is nothing to gain from drawing faster.
# Frames with no state change are skipped entirely, see app.run().
FPS = 30

NEON_YELLOW = (236, 253, 147)  # speedometer
NEON_GREEN = (145, 213, 89)  # lower gauges, clock, odometer
DARK_GREY = (9, 52, 50)  # unlit seven-segment backplate
BLACK = (0, 0, 0)
DEBUG_TEXT = (255, 255, 255)

FONT_FILE = FONT_DIR / "DSEG7Classic-Bold.ttf"
FONT_LARGE = 174  # speedometer
FONT_MEDIUM = 94  # clock, MFA, fuel
FONT_SMALL = 67  # odometer


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


#: mqtt (default), demo, serial or obd. See digifiz.sources.build_source.
SOURCE = _env("DIGIFIZ_SOURCE", "mqtt")

MQTT_HOST = _env("DIGIFIZ_MQTT_HOST", "localhost")
MQTT_PORT = int(_env("DIGIFIZ_MQTT_PORT", "1883"))
MQTT_CLIENT_ID = _env("DIGIFIZ_MQTT_CLIENT_ID", "digifiz-dash")
TOPIC_PREFIX = _env("DIGIFIZ_TOPIC_PREFIX", "")

SERIAL_PORT = _env("DIGIFIZ_SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUD = int(_env("DIGIFIZ_SERIAL_BAUD", "115200"))

OBD_PORT = _env("DIGIFIZ_OBD_PORT", "")

#: BCM pin number for a physical MFA mode button, or empty for none.
MFA_BUTTON_PIN = _env("DIGIFIZ_MFA_BUTTON_PIN", "")

#: A value older than this is drawn as stale rather than as current truth.
STALE_AFTER = float(_env("DIGIFIZ_STALE_AFTER", "5.0"))

#: Odometer writes are debounced to protect the SD card.
ODO_WRITE_INTERVAL = float(_env("DIGIFIZ_ODO_WRITE_INTERVAL", "30.0"))

INTRO_ENABLED = _env_bool("DIGIFIZ_INTRO", False)
INTRO_FPS = float(_env("DIGIFIZ_INTRO_FPS", "25"))
#: Seconds to dissolve from the last intro frame into the dash.
INTRO_FADE = float(_env("DIGIFIZ_INTRO_FADE", "0.5"))

DEMO_SCENARIO = _env("DIGIFIZ_SCENARIO", "drive")
