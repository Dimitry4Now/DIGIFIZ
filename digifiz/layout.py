"""Every on-screen position, in 1920x720 logical coordinates.

Positions came from the original constants.py and the literal coordinates that
were scattered through draw_indicators(). They are scaled to the real display
once, by Geometry, so no per-frame arithmetic is needed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import LOGICAL_SIZE

RPM = (135, 5)
RPM_LABEL = (135, 5)

# The four aux gauges share one image sequence, only the x position differs.
AUX = {
    "coolant": (1481, 105),
    "egt": (1599, 105),
    "oilpressure": (1711, 105),
    "boost": (1822, 105),
}

CLOCK = (555, 620)
ODOMETER_RIGHT = (395, 678)
MFA_BACKGROUND = (1021, 563)
MFA_TEMP_RIGHT = (1435, 668)
FUEL_RIGHT = (1717, 667)
SPEEDO_RIGHT = (1247, 305)
FUEL_RESERVE = (1795, 616)

#: Idiot lamp slots, in the ind0..ind9 order of signals.INDICATORS.
INDICATOR_SLOTS = (
    (45, 460),
    (185, 460),
    (325, 460),
    (465, 460),
    (605, 460),
    (1220, 460),
    (1360, 460),
    (1500, 460),
    (1640, 460),
    (1780, 460),
)


@dataclass(frozen=True)
class Geometry:
    """Maps logical coordinates onto the real display, letterboxed and centred."""

    size: tuple[int, int]
    scale: float
    offset: tuple[int, int]

    @classmethod
    def for_display(cls, size: tuple[int, int]) -> "Geometry":
        logical_w, logical_h = LOGICAL_SIZE
        width, height = size
        scale = min(width / logical_w, height / logical_h)
        offset = (
            int((width - logical_w * scale) // 2),
            int((height - logical_h * scale) // 2),
        )
        return cls(size=size, scale=scale, offset=offset)

    def point(self, logical: tuple[int, int]) -> tuple[int, int]:
        """Scale a logical point into display coordinates."""
        return (
            int(logical[0] * self.scale) + self.offset[0],
            int(logical[1] * self.scale) + self.offset[1],
        )

    def length(self, value: float) -> int:
        return int(value * self.scale)

    def font_size(self, logical_size: int) -> int:
        return max(8, int(logical_size * self.scale))
