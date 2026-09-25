"""The single description of every value the dash can display.

This table is the contract between the data sources, the simulator, the
scaling code and the renderer. Node-RED used to hold the unit-to-frame-index
mapping in its range nodes; it lives here now so it can be tested.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    """One numeric value, in engineering units.

    ``frames`` is the number of artwork frames for gauges drawn from a PNG
    sequence, or ``None`` for values drawn as text.
    """

    key: str
    topic: str
    unit: str
    lo: float
    hi: float
    frames: int | None = None
    decimals: int = 0


#: Aux gauges (coolant, EGT, oil pressure, boost) all share images/gauges/aux*.png.
AUX_FRAMES = 20

#: images/rpm/RPM 000.png .. RPM 5000.png, one frame per 100 rpm.
RPM_FRAMES = 51

SIGNALS: tuple[Signal, ...] = (
    Signal("rpm", "engine/rpm/state", "rpm", 0, 5000, RPM_FRAMES),
    Signal("coolant", "engine/coolant/state", "C", 50, 120, AUX_FRAMES),
    Signal("egt", "engine/egt/state", "C", 0, 500, AUX_FRAMES),
    Signal("oilpressure", "engine/oilpressure/state", "psi", 0, 80, AUX_FRAMES),
    Signal("boost", "engine/boost/state", "psi", 0, 30, AUX_FRAMES, decimals=1),
    Signal("fuel", "engine/fuel/state", "L", 0, 60),
    Signal("speed", "cabin/speed_cv/state", "km/h", 0, 199),
    Signal("outside_temp", "cabin/outside_temp/state", "C", -40, 60),
)

BY_KEY: dict[str, Signal] = {s.key: s for s in SIGNALS}
BY_TOPIC: dict[str, Signal] = {s.topic: s for s in SIGNALS}

#: The ten idiot lamps, in the order their artwork is numbered (ind0..ind9).
INDICATORS: tuple[str, ...] = (
    "illumination",
    "foglight",
    "defog",
    "highbeam",
    "leftturn",
    "rightturn",
    "brakewarn",
    "oillight",
    "alt",
    "glow",
)

INDICATOR_TOPICS: dict[str, str] = {
    name: f"indicator/{name}/state" for name in INDICATORS
}
TOPIC_TO_INDICATOR: dict[str, str] = {v: k for k, v in INDICATOR_TOPICS.items()}

#: Factory reserve light comes on at 7 litres, it is derived not published.
FUEL_RESERVE_LITRES = 7.0


def all_topics(prefix: str = "") -> list[str]:
    """Every topic the dash subscribes to, in publish order."""
    topics = [s.topic for s in SIGNALS] + list(INDICATOR_TOPICS.values())
    if prefix:
        return [f"{prefix.rstrip('/')}/{t}" for t in topics]
    return topics


def strip_prefix(topic: str, prefix: str = "") -> str:
    """Remove an optional topic prefix so table lookups still work."""
    if not prefix:
        return topic
    head = prefix.rstrip("/") + "/"
    return topic[len(head):] if topic.startswith(head) else topic
