"""The MFA display: which reading the lower centre panel is showing.

The artwork (images/indicators/MFA_temp.png) carries all six mode chips with
the ambient temperature one lit. The lit and unlit chip colours are solid, so
one surface per mode is built at load time by recolouring the chips rather than
by needing six variants of the artwork.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Chip background colours sampled from MFA_temp.png.
CHIP_LIT = (52, 151, 46)
CHIP_UNLIT = (13, 112, 69)


@dataclass(frozen=True)
class Mode:
    """One MFA reading.

    ``chip`` is the label's rectangle inside the MFA artwork, ``source`` the
    state value it displays, and ``decimals`` how it is formatted.
    """

    key: str
    label: str
    chip: tuple[int, int, int, int]
    source: str
    decimals: int = 0


MODES: tuple[Mode, ...] = (
    Mode("consumption", "L/100KM", (1, 1, 149, 47), "consumption", decimals=1),
    Mode("avg_speed", "KM/H", (157, 1, 92, 47), "avg_speed"),
    Mode("oil_temp", "oil C", (256, 1, 110, 47), "oil_temp"),
    Mode("outside_temp", "ambient C", (373, 1, 81, 47), "outside_temp"),
    Mode("trip", "KM", (1, 55, 59, 42), "trip", decimals=1),
    Mode("clock", "clock", (1, 104, 59, 42), "clock"),
)

BY_KEY = {mode.key: mode for mode in MODES}

#: The mode the dash starts in, matching the artwork's own lit chip.
DEFAULT_INDEX = MODES.index(BY_KEY["outside_temp"])


def next_index(index: int, step: int = 1) -> int:
    return (index + step) % len(MODES)
