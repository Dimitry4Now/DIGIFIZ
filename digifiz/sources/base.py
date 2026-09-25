"""The interface every data source implements."""

from __future__ import annotations

import threading


class DataSource:
    """Collects updates off the render thread and hands them over in batches.

    Sources run their own I/O (network or serial) on a background thread and
    only ever touch ``_pending`` under the lock. The render loop calls
    :meth:`drain`, which never blocks on I/O, so a hung broker or an unplugged
    Arduino cannot stall the dash.
    """

    name = "base"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, float | bool] = {}
        self.connected = False
        self.last_error: str | None = None

    def start(self) -> None:
        """Begin collecting. Must not block for longer than a connect attempt."""

    def stop(self) -> None:
        """Release resources. Safe to call even if start() failed."""

    def publish(self, key: str, value: float | bool) -> None:
        """Called from the source's own thread to record the newest value."""
        with self._lock:
            self._pending[key] = value

    def publish_many(self, updates: dict[str, float | bool]) -> None:
        with self._lock:
            self._pending.update(updates)

    def drain(self) -> dict[str, float | bool]:
        """Return and clear the newest value per key since the last call."""
        with self._lock:
            if not self._pending:
                return {}
            batch = self._pending
            self._pending = {}
            return batch

    @property
    def status(self) -> str:
        if self.last_error:
            return f"{self.name}: {self.last_error}"
        return f"{self.name}: {'connected' if self.connected else 'offline'}"
