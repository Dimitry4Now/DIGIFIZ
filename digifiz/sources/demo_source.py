"""In-process synthetic data, so the dash runs with no broker at all."""

from __future__ import annotations

import time

from .. import config
from ..simulation import build
from .base import DataSource


class DemoSource(DataSource):
    name = "demo"

    def __init__(self, scenario: str | None = None) -> None:
        super().__init__()
        self.scenario = build(scenario or config.DEMO_SCENARIO)
        self.name = f"demo:{self.scenario.name}"
        self._last = time.monotonic()

    def start(self) -> None:
        self.connected = True
        self._last = time.monotonic()

    def drain(self) -> dict[str, float | bool]:
        # Generated on the render thread, cheap and always current, so there is
        # no reason to spend a thread on it.
        now = time.monotonic()
        dt = now - self._last
        self._last = now
        return self.scenario.step(dt)
