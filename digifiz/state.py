"""Live dash state, in engineering units."""

from __future__ import annotations

import time

from . import config, mfa
from .signals import INDICATORS, BY_KEY, FUEL_RESERVE_LITRES


class DashState:
    """Everything the renderer needs, plus a dirty flag to skip idle frames.

    Values are kept in engineering units; conversion to frame indices happens
    in the renderer so the state stays independent of the artwork.
    """

    def __init__(self) -> None:
        self.values: dict[str, float] = {key: 0.0 for key in BY_KEY}
        self.values["coolant"] = BY_KEY["coolant"].lo
        self.updated: dict[str, float] = {}
        self.indicators: dict[str, bool] = {name: False for name in INDICATORS}
        self.odometer = 0
        self.trip = 0.0
        self.mfa_index = mfa.DEFAULT_INDEX
        self.dirty = True
        self.source_name = "none"

    def apply(self, updates: dict[str, object]) -> None:
        """Merge a batch of updates from a data source.

        Keys may be signal names or indicator names. Unknown keys are ignored
        so a source can be ahead of the dash without breaking it.
        """
        now = time.monotonic()
        for key, raw in updates.items():
            if key in self.values:
                try:
                    value = float(raw)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
                if value != self.values[key]:
                    self.dirty = True
                self.values[key] = value
                self.updated[key] = now
            elif key in self.indicators:
                value_bool = bool(raw)
                if value_bool != self.indicators[key]:
                    self.dirty = True
                self.indicators[key] = value_bool
                self.updated[key] = now

    def age(self, key: str) -> float:
        """Seconds since ``key`` last changed, or ``inf`` if never seen."""
        stamp = self.updated.get(key)
        return float("inf") if stamp is None else time.monotonic() - stamp

    def is_stale(self, key: str) -> bool:
        return self.age(key) > config.STALE_AFTER

    @property
    def mfa_mode(self) -> mfa.Mode:
        return mfa.MODES[self.mfa_index]

    def cycle_mfa(self, step: int = 1) -> None:
        self.mfa_index = mfa.next_index(self.mfa_index, step)
        self.dirty = True

    def mfa_value(self) -> float:
        """The number the active MFA mode displays. The clock is drawn by the
        renderer from the system time, so it has no numeric value here."""
        mode = self.mfa_mode
        if mode.source == "trip":
            return self.trip
        return self.values.get(mode.source, 0.0)

    @property
    def fuel_reserve(self) -> bool:
        return self.values["fuel"] <= FUEL_RESERVE_LITRES
