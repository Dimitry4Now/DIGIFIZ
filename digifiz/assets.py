"""Image loading.

Every surface is loaded once, converted to the display format and pre-scaled to
the real panel size. The original loaded a PNG from disk on every value change
and never converted it, so each blit paid a per-pixel format conversion on top
of a decode; that was the single largest cost in the old render loop.
"""

from __future__ import annotations

import logging
import time

import pygame

from . import config
from .layout import Geometry
from .signals import AUX_FRAMES, INDICATORS, RPM_FRAMES

log = logging.getLogger(__name__)


class AssetCache:
    def __init__(self, geometry: Geometry) -> None:
        self.geometry = geometry
        started = time.monotonic()

        self.background = self._load("background.png")
        self.rpm_frames = [
            self._load(f"rpm/RPM {index * 100:03d}.png") for index in range(RPM_FRAMES)
        ]
        self.rpm_label = self._load("rpm/RPM.png")
        self.aux_frames = [
            self._load(f"gauges/aux{index}.png") for index in range(AUX_FRAMES)
        ]
        self.indicators = [
            self._load(f"indicators/ind{index}.png") for index in range(len(INDICATORS))
        ]
        self.fuel_reserve_on = self._load("indicators/fuelResOn.png")
        self.fuel_reserve_off = self._load("indicators/fuelResOff.png")
        self.mfa = self._load("indicators/MFA_temp.png")

        self.load_seconds = time.monotonic() - started
        log.info(
            "loaded %d surfaces at scale %.3f in %.2fs",
            self.count,
            geometry.scale,
            self.load_seconds,
        )

    @property
    def count(self) -> int:
        return len(self.rpm_frames) + len(self.aux_frames) + len(self.indicators) + 5

    def _load(self, relative: str) -> pygame.Surface:
        path = config.IMAGE_DIR / relative
        surface = pygame.image.load(str(path)).convert_alpha()
        scale = self.geometry.scale
        if abs(scale - 1.0) > 1e-6:
            width = max(1, int(round(surface.get_width() * scale)))
            height = max(1, int(round(surface.get_height() * scale)))
            surface = pygame.transform.smoothscale(surface, (width, height))
        return surface


def load_intro_frames(geometry: Geometry) -> list[pygame.Surface]:
    """Pre-extracted intro frames, empty list if none are present.

    Frames are produced once by tools/extract_intro.sh rather than decoded at
    runtime, which is what let the opencv-python dependency go away.
    """
    if not config.INTRO_DIR.is_dir():
        return []
    frames = []
    for path in sorted(config.INTRO_DIR.glob("frame_*.png")):
        surface = pygame.image.load(str(path)).convert()
        target = geometry.size
        if surface.get_size() != target:
            surface = pygame.transform.smoothscale(surface, target)
        frames.append(surface)
    return frames
