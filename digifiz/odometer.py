"""Odometer persistence.

The original read and parsed odo.txt inside the render loop, once per frame.
This reads it once at startup and writes back only when the value changed, at
most once every config.ODO_WRITE_INTERVAL seconds, because the file lives on an
SD card in a vehicle that gets its power cut without a shutdown.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from . import config

log = logging.getLogger(__name__)


def parse(text: str) -> tuple[int, int]:
    """Read ``odo:``/``trip:`` lines. Missing or malformed values become 0."""
    odometer = trip = 0
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("odo:"):
            odometer = _to_int(line[4:], "odo")
        elif line.startswith("trip:"):
            trip = _to_int(line[5:], "trip")
    return odometer, trip


def _to_int(raw: str, label: str) -> int:
    try:
        return int(float(raw.strip()))
    except ValueError:
        log.warning("odo.txt: %s value %r is not a number, using 0", label, raw)
        return 0


def format_file(odometer: int, trip: int) -> str:
    return f"odo:{odometer}\ntrip:{trip}\n"


class Odometer:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else config.ODO_FILE
        self.odometer, self.trip = self._read()
        self._written = (self.odometer, self.trip)
        self._last_write = time.monotonic()

    def _read(self) -> tuple[int, int]:
        try:
            return parse(self.path.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            log.warning("cannot read %s (%s), starting from zero", self.path, exc)
            return 0, 0

    def maybe_write(self, force: bool = False) -> bool:
        """Persist if the value changed and the debounce window has passed."""
        current = (self.odometer, self.trip)
        if current == self._written:
            return False
        now = time.monotonic()
        if not force and now - self._last_write < config.ODO_WRITE_INTERVAL:
            return False
        self._write(current)
        return True

    def _write(self, current: tuple[int, int]) -> None:
        # Write to a temporary file and replace, so a power cut mid-write
        # cannot leave a truncated odometer behind.
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temp.write_text(format_file(*current), encoding="utf-8")
            os.replace(temp, self.path)
        except OSError as exc:
            log.error("cannot write %s: %s", self.path, exc)
            return
        self._written = current
        self._last_write = time.monotonic()
