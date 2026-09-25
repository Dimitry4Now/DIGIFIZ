"""Image loading.

Every surface is loaded once, converted to the display format and pre-scaled to
the real panel size. The original loaded a PNG from disk on every value change
and never converted it, so each blit paid a per-pixel format conversion on top
of a decode; that was the single largest cost in the old render loop.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from pathlib import Path

import pygame

from . import config, mfa
from .layout import Geometry
from .signals import AUX_FRAMES, INDICATORS, RPM_FRAMES

log = logging.getLogger(__name__)


#: How many surfaces a full load produces, used for progress reporting.
TOTAL_SURFACES = RPM_FRAMES + AUX_FRAMES + len(INDICATORS) + len(mfa.MODES) + 3


class AssetCache:
    """Every surface the dash draws, loaded once.

    Loading can be driven a step at a time (:meth:`load_progressively`) so it
    can happen during the intro instead of as a pause after it.
    """

    def __init__(self, geometry: Geometry, load: bool = True) -> None:
        self.geometry = geometry
        self.background: pygame.Surface | None = None
        self.rpm_frames: list[pygame.Surface] = []
        self.aux_frames: list[pygame.Surface] = []
        self.indicators: list[pygame.Surface] = []
        self.mfa_modes: dict[str, pygame.Surface] = {}
        self.fuel_reserve_on: pygame.Surface | None = None
        self.fuel_reserve_off: pygame.Surface | None = None
        self.ready = False
        self.load_seconds = 0.0
        self._started = 0.0
        if load:
            self.load()

    def load(self) -> None:
        """Load everything now."""
        for _ in self.load_progressively():
            pass

    def load_progressively(self) -> Iterator[float]:
        """Load one surface per step, yielding progress from 0.0 to 1.0.

        The caller decides how much time to spend per step, which is what lets
        the intro play at full frame rate while the dash loads behind it.
        """
        if self.ready:
            return
        self._started = time.monotonic()
        done = 0

        self.background = self._load("background.png")
        done += 1
        yield done / TOTAL_SURFACES

        # Each frame already carries the bar's track and scale, so there is no
        # separate label to blit over it.
        for index in range(RPM_FRAMES):
            self.rpm_frames.append(self._load(f"rpm/RPM {index * 100:03d}.png"))
            done += 1
            yield done / TOTAL_SURFACES

        for index in range(AUX_FRAMES):
            self.aux_frames.append(self._load(f"gauges/aux{index}.png"))
            done += 1
            yield done / TOTAL_SURFACES

        for index in range(len(INDICATORS)):
            self.indicators.append(self._load(f"indicators/ind{index}.png"))
            done += 1
            yield done / TOTAL_SURFACES

        self.fuel_reserve_on = self._load("indicators/fuelResOn.png")
        self.fuel_reserve_off = self._load("indicators/fuelResOff.png")
        done += 2
        yield done / TOTAL_SURFACES

        for key, surface in self._mfa_mode_surfaces():
            self.mfa_modes[key] = surface
            done += 1
            yield done / TOTAL_SURFACES

        self.ready = True
        self.load_seconds = time.monotonic() - self._started
        log.info(
            "loaded %d surfaces at scale %.3f in %.2fs",
            self.count,
            self.geometry.scale,
            self.load_seconds,
        )

    @property
    def count(self) -> int:
        return (
            len(self.rpm_frames)
            + len(self.aux_frames)
            + len(self.indicators)
            + len(self.mfa_modes)
            + 3
        )

    def _mfa_mode_surfaces(self) -> Iterator[tuple[str, pygame.Surface]]:
        """One MFA surface per mode, with only that mode's chip lit.

        The artwork ships with the ambient temperature chip lit. Every chip is
        a flat colour, so the lit and unlit colours can simply be swapped: the
        whole panel is dimmed once, then the active chip is lit back up.
        """
        # Recolour at native resolution, then scale, so the swap is exact.
        base = pygame.image.load(
            str(config.IMAGE_DIR / "indicators/MFA_temp.png")
        ).convert_alpha()
        _replace_color(base, mfa.CHIP_LIT, mfa.CHIP_UNLIT)

        for mode in mfa.MODES:
            surface = base.copy()
            _replace_color(
                surface, mfa.CHIP_UNLIT, mfa.CHIP_LIT, area=pygame.Rect(mode.chip)
            )
            yield mode.key, self._scaled(surface)

    def _scaled(self, surface: pygame.Surface) -> pygame.Surface:
        scale = self.geometry.scale
        if abs(scale - 1.0) <= 1e-6:
            return surface
        width = max(1, int(round(surface.get_width() * scale)))
        height = max(1, int(round(surface.get_height() * scale)))
        return pygame.transform.smoothscale(surface, (width, height))

    def _load(self, relative: str) -> pygame.Surface:
        path = config.IMAGE_DIR / relative
        return self._scaled(pygame.image.load(str(path)).convert_alpha())


def _replace_color(
    surface: pygame.Surface,
    old: tuple[int, int, int],
    new: tuple[int, int, int],
    area: pygame.Rect | None = None,
) -> None:
    """Swap one flat colour for another, optionally only inside ``area``."""
    target = surface.subsurface(area) if area else surface
    pixels = pygame.PixelArray(target)
    pixels.replace(old, new)
    pixels.close()


def intro_frame_paths() -> list[Path]:
    """Pre-extracted intro frames, in order. Empty if the intro is not built."""
    if not config.INTRO_DIR.is_dir():
        return []
    return sorted(config.INTRO_DIR.glob("frame_*.png"))


def load_intro_frame(path: Path, geometry: Geometry) -> pygame.Surface:
    """One intro frame, decoded on demand.

    Frames are streamed from disk rather than all held in memory: a few seconds
    of full-screen video is hundreds of MB as surfaces, and decoding one PNG
    costs a few milliseconds, which fits inside the frame budget. Extract them
    at the panel's own size (tools/extract_intro.sh) so nothing is scaled here.
    """
    surface = pygame.image.load(str(path)).convert()
    if surface.get_size() != geometry.size:
        surface = pygame.transform.smoothscale(surface, geometry.size)
    return surface
