"""Synthetic engine data.

One implementation of "plausible engine behaviour", used both by
tools/mqtt_sim.py (published over MQTT) and by the in-process demo source, so
the two can never drift apart. It replaces digifiz_imp.sh, which spawned a few
hundred mosquitto_pub processes to do the same job.
"""

from __future__ import annotations

import math
from typing import Iterable

from .signals import BY_KEY, INDICATORS

Sample = dict[str, float | bool]

#: Turn signal cadence, roughly the factory 1.5 Hz.
BLINK_HZ = 1.5


def _lag(current: float, target: float, dt: float, tau: float) -> float:
    """First-order lag, used for turbo spool and EGT thermal inertia."""
    if tau <= 0 or dt <= 0:
        return target
    alpha = 1.0 - math.exp(-dt / tau)
    return current + (target - current) * alpha


def _interpolate(keyframes: list[tuple[float, float]], t: float) -> float:
    """Linear interpolation over (time, value) keyframes, wrapping at the end."""
    period = keyframes[-1][0]
    t = t % period
    for index in range(len(keyframes) - 1):
        t0, v0 = keyframes[index]
        t1, v1 = keyframes[index + 1]
        if t0 <= t <= t1:
            span = t1 - t0
            fraction = 0.0 if span <= 0 else (t - t0) / span
            return v0 + (v1 - v0) * fraction
    return keyframes[-1][1]


def _blink(t: float, hz: float = BLINK_HZ) -> bool:
    return (t * hz) % 1.0 < 0.5


class Scenario:
    """Base class. Subclasses advance their own state in :meth:`step`."""

    name = "base"

    def __init__(self) -> None:
        self.t = 0.0
        self.values: Sample = {key: 0.0 for key in BY_KEY}
        self.values.update({name: False for name in INDICATORS})

    def step(self, dt: float) -> Sample:
        self.t += dt
        self.advance(dt)
        return dict(self.values)

    def advance(self, dt: float) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


class Idle(Scenario):
    """Warm engine, stationary, nothing wrong."""

    name = "idle"

    def advance(self, dt: float) -> None:
        self.values.update(
            rpm=850 + 25 * math.sin(self.t * 2.0),
            coolant=88.0,
            egt=180.0,
            oilpressure=32.0,
            boost=0.0,
            fuel=42.0,
            speed=0.0,
            outside_temp=18.0,
            illumination=True,
        )


class Drive(Scenario):
    """A repeating drive cycle: pull, cruise, overtake, coast down."""

    name = "drive"

    # (seconds, throttle 0..1) over a 48 second loop.
    THROTTLE = [
        (0.0, 0.05),
        (4.0, 0.85),
        (14.0, 0.55),
        (22.0, 0.30),
        (26.0, 0.95),
        (34.0, 0.40),
        (40.0, 0.00),
        (48.0, 0.05),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.rpm = 850.0
        self.boost = 0.0
        self.egt = 200.0
        self.coolant = 35.0  # starts cool and warms up
        self.speed = 0.0
        self.fuel = 48.0

    def advance(self, dt: float) -> None:
        throttle = _interpolate(self.THROTTLE, self.t)

        target_rpm = 850 + throttle * 3750
        self.rpm = _lag(self.rpm, target_rpm, dt, tau=1.2)

        # Turbo needs both throttle and revs before it makes any boost.
        spool = max(0.0, (self.rpm - 1600) / 2600)
        self.boost = _lag(self.boost, throttle * min(1.0, spool) * 22.0, dt, tau=0.8)

        self.egt = _lag(self.egt, 180 + throttle * 520, dt, tau=4.0)
        self.coolant = _lag(self.coolant, 90.0, dt, tau=90.0)
        self.speed = _lag(self.speed, throttle * 110, dt, tau=3.0)
        self.fuel = max(0.0, self.fuel - dt * (0.004 + throttle * 0.02))

        oil = 18 + (self.rpm / 5000) * 45

        turning = 30.0 <= (self.t % 48.0) < 36.0
        self.values.update(
            rpm=self.rpm,
            coolant=self.coolant,
            egt=self.egt,
            oilpressure=oil,
            boost=self.boost,
            fuel=self.fuel,
            speed=self.speed,
            outside_temp=14.0,
            illumination=True,
            rightturn=turning and _blink(self.t),
            leftturn=False,
            glow=False,
            oillight=self.rpm < 400,
            alt=self.rpm < 400,
        )


class Sweep(Scenario):
    """Every gauge driven end to end, for layout and asset checks."""

    name = "sweep"
    PERIOD = 8.0

    def advance(self, dt: float) -> None:
        phase = (self.t % self.PERIOD) / self.PERIOD
        triangle = 1.0 - abs(2.0 * phase - 1.0)
        for key, signal in BY_KEY.items():
            self.values[key] = signal.lo + (signal.hi - signal.lo) * triangle
        lit = (self.t % 2.0) < 1.0
        for name in INDICATORS:
            self.values[name] = lit


class Warnings(Scenario):
    """Each idiot lamp in turn, then all of them, so all artwork gets seen."""

    name = "warnings"
    DWELL = 0.8

    def advance(self, dt: float) -> None:
        step = int(self.t / self.DWELL) % (len(INDICATORS) + 1)
        for index, name in enumerate(INDICATORS):
            self.values[name] = step == len(INDICATORS) or index == step
        # Turn signals blink rather than sit on, like the real thing.
        if self.values["leftturn"]:
            self.values["leftturn"] = _blink(self.t)
        if self.values["rightturn"]:
            self.values["rightturn"] = _blink(self.t)
        self.values.update(
            rpm=850.0,
            coolant=95.0,
            egt=200.0,
            oilpressure=30.0,
            boost=0.0,
            fuel=4.0,  # below reserve, so the reserve lamp lights too
            speed=0.0,
            outside_temp=2.0,
        )


class ColdStart(Scenario):
    """Glow plugs, cold coolant, oil pressure lamp clearing as pressure builds."""

    name = "cold-start"

    def advance(self, dt: float) -> None:
        cranking = self.t < 1.5
        running = self.t >= 1.5
        self.values.update(
            rpm=0.0 if cranking else 900.0,
            coolant=8.0 + min(self.t, 30.0) * 0.8,
            egt=20.0 if cranking else 20 + (self.t - 1.5) * 12,
            oilpressure=0.0 if self.t < 2.5 else 34.0,
            boost=0.0,
            fuel=31.0,
            speed=0.0,
            outside_temp=-3.0,
            glow=self.t < 4.0,
            oillight=self.t < 2.5,
            alt=not running,
            illumination=True,
        )


SCENARIOS: dict[str, type[Scenario]] = {
    scenario.name: scenario
    for scenario in (Idle, Drive, Sweep, Warnings, ColdStart)
}


def names() -> Iterable[str]:
    return SCENARIOS.keys()


def build(name: str) -> Scenario:
    try:
        return SCENARIOS[name]()
    except KeyError:
        raise SystemExit(
            f"unknown scenario {name!r}; choose from {', '.join(sorted(SCENARIOS))}"
        ) from None
