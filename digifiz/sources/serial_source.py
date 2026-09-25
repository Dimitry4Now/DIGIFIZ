"""Direct Arduino serial source.

Unproven until the hardware exists, but the line parser is pure and tested, so
the only unknown left is the wiring.

Wire format, one line per update, keys optional so a sketch can send only what
it has and adding a sensor never breaks the parser:

    D rpm=1850 egt=430 boost=12.4 oilp=45 clt=88 fuel=32 spd=62 ind=0x1A4

``ind`` is a bitfield over signals.INDICATORS, bit 0 being the first lamp.
"""

from __future__ import annotations

import logging
import threading
import time

from .. import config
from ..signals import INDICATORS
from .base import DataSource

log = logging.getLogger(__name__)

#: Short wire keys mapped onto dash signal keys.
FIELD_MAP = {
    "rpm": "rpm",
    "egt": "egt",
    "boost": "boost",
    "oilp": "oilpressure",
    "clt": "coolant",
    "fuel": "fuel",
    "spd": "speed",
    "oat": "outside_temp",
}


def parse_line(line: str) -> dict[str, float | bool]:
    """Decode one wire line. Unknown keys and junk fields are skipped."""
    line = line.strip()
    if not line:
        return {}
    fields = line.split()
    if fields and fields[0] == "D":
        fields = fields[1:]
    updates: dict[str, float | bool] = {}
    for field in fields:
        if "=" not in field:
            continue
        key, _, raw = field.partition("=")
        key = key.strip().lower()
        raw = raw.strip()
        if key == "ind":
            bits = _parse_int(raw)
            if bits is None:
                continue
            for index, name in enumerate(INDICATORS):
                updates[name] = bool(bits & (1 << index))
            continue
        signal_key = FIELD_MAP.get(key)
        if signal_key is None:
            continue
        try:
            updates[signal_key] = float(raw)
        except ValueError:
            continue
    return updates


def _parse_int(raw: str) -> int | None:
    try:
        return int(raw, 16) if raw.lower().startswith("0x") else int(raw)
    except ValueError:
        return None


class SerialSource(DataSource):
    name = "serial"

    def __init__(self, port: str | None = None, baud: int | None = None) -> None:
        super().__init__()
        self.port = port or config.SERIAL_PORT
        self.baud = baud or config.SERIAL_BAUD
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="serial", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        import serial  # imported here so pyserial stays an optional dependency

        backoff = 1.0
        while not self._stop.is_set():
            try:
                with serial.Serial(self.port, self.baud, timeout=1) as link:
                    self.connected = True
                    self.last_error = None
                    backoff = 1.0
                    log.info("serial open on %s at %d baud", self.port, self.baud)
                    self._read_forever(link)
            except Exception as exc:
                self.connected = False
                self.last_error = str(exc)
                log.warning("serial %s: %s, retrying in %.0fs", self.port, exc, backoff)
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 16.0)

    def _read_forever(self, link) -> None:
        while not self._stop.is_set():
            raw = link.readline()
            if not raw:
                continue  # timeout, the Arduino may just be quiet
            try:
                line = raw.decode("utf-8", errors="replace")
            except Exception:
                continue
            updates = parse_line(line)
            if updates:
                self.publish_many(updates)
