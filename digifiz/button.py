"""A physical MFA button wired to a Raspberry Pi GPIO pin.

This is one of several ways to change mode, and like all of them it ends up
calling DashState.cycle_mfa(), so every input follows the one order defined in
mfa.MODES:

- this button, on a GPIO pin
- a button on the Arduino, sending ``mfabtn=`` over serial
- an MQTT publish to ``cabin/mfa_next/state``
- the m and arrow keys
- the --mfa-cycle timer

Wiring: one side of the button to the GPIO pin, the other to ground. The
internal pull-up is enabled by default, so no external resistor is needed.
"""

from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)

#: Ignore further edges for this long after a press. Cheap buttons bounce for
#: a few milliseconds; a cluster button pressed while driving does not need to
#: repeat faster than this.
BOUNCE_SECONDS = 0.08


class MfaButton:
    """Counts presses on a GPIO pin, drained by the render loop."""

    def __init__(self, pin: int, pull_up: bool = True) -> None:
        self.pin = pin
        self.pull_up = pull_up
        self._lock = threading.Lock()
        self._presses = 0
        self._button = None
        self.available = False
        self.last_error: str | None = None

    def start(self) -> None:
        try:
            from gpiozero import Button  # imported lazily: Pi hardware only
        except Exception as exc:
            self.last_error = f"gpiozero unavailable ({exc})"
            log.warning(
                "MFA button on pin %s is disabled: %s "
                "(install it with: pip install gpiozero lgpio)",
                self.pin,
                exc,
            )
            return
        try:
            self._button = Button(
                self.pin, pull_up=self.pull_up, bounce_time=BOUNCE_SECONDS
            )
        except Exception as exc:
            self.last_error = str(exc)
            log.error("cannot claim GPIO %s for the MFA button: %s", self.pin, exc)
            return
        self._button.when_pressed = self._on_press
        self.available = True
        log.info("MFA button on GPIO %s", self.pin)

    def _on_press(self) -> None:
        # Runs on gpiozero's own thread, so only touch the counter.
        with self._lock:
            self._presses += 1

    def drain(self) -> int:
        """How many presses happened since the last call."""
        with self._lock:
            presses = self._presses
            self._presses = 0
            return presses

    def stop(self) -> None:
        if self._button is not None:
            try:
                self._button.close()
            except Exception:  # pragma: no cover - shutdown is best effort
                pass
            self._button = None
        self.available = False
