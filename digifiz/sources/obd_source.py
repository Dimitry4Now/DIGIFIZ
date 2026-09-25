"""OBD-II source.

Only useful on a vehicle with an ECU that speaks OBD-II, roughly 1996 and
later. The Digifiz project's own target is a 1976 bus with a mechanical AAZ
diesel, which has no ECU at all, so this is here for a newer car and stays a
thin adapter until someone has one to test against.
"""

from __future__ import annotations

import logging
import threading

from .. import config
from .base import DataSource

log = logging.getLogger(__name__)

#: OBD-II command name -> dash signal key. Speed and coolant arrive in metric.
COMMAND_MAP = {
    "RPM": "rpm",
    "SPEED": "speed",
    "COOLANT_TEMP": "coolant",
    "AMBIANT_AIR_TEMP": "outside_temp",
    "FUEL_LEVEL": "fuel",
    "INTAKE_PRESSURE": "boost",
}

POLL_INTERVAL = 0.25


class ObdSource(DataSource):
    name = "obd"

    def __init__(self, port: str | None = None) -> None:
        super().__init__()
        self.port = port or config.OBD_PORT or None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="obd", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            import obd  # imported lazily, python-OBD is an optional extra
        except ImportError:
            self.last_error = "python-OBD not installed (pip install obd)"
            log.error("%s", self.last_error)
            return

        connection = obd.OBD(self.port) if self.port else obd.OBD()
        if not connection.is_connected():
            self.last_error = "no OBD-II adapter responding"
            log.error("%s", self.last_error)
            return
        self.connected = True

        commands = {
            key: getattr(obd.commands, name)
            for name, key in COMMAND_MAP.items()
            if hasattr(obd.commands, name)
        }
        while not self._stop.is_set():
            for key, command in commands.items():
                response = connection.query(command)
                if response.is_null() or response.value is None:
                    continue
                try:
                    self.publish(key, float(response.value.magnitude))
                except (AttributeError, TypeError, ValueError):
                    continue
            self._stop.wait(POLL_INTERVAL)
        connection.close()
