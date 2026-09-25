"""Drawing the dash.

All text goes through a surface cache. The original re-rasterised every string
every frame, including the 174px speedometer glyphs, and drew the clock twice.
"""

from __future__ import annotations

from datetime import datetime

import pygame

from . import config, layout
from .assets import AssetCache
from .layout import Geometry
from .scaling import frame_for
from .signals import BY_KEY, INDICATORS
from .state import DashState


def _dim(color: tuple[int, int, int], factor: float = 0.35) -> tuple[int, int, int]:
    return tuple(int(channel * factor) for channel in color)  # type: ignore[return-value]


class Renderer:
    def __init__(self, geometry: Geometry, assets: AssetCache) -> None:
        self.geometry = geometry
        self.assets = assets
        self.fonts = {
            "large": self._font(config.FONT_LARGE),
            "medium": self._font(config.FONT_MEDIUM),
            "small": self._font(config.FONT_SMALL),
        }
        self._text_cache: dict[tuple[str, str, tuple[int, int, int]], pygame.Surface] = {}
        self.debug_font = pygame.font.Font(None, geometry.font_size(48))
        # The unlit seven-segment backplate never changes.
        self.clock_backplate = self.text("medium", "00:00", config.DARK_GREY)

    def _font(self, logical_size: int) -> pygame.font.Font:
        return pygame.font.Font(
            str(config.FONT_FILE), self.geometry.font_size(logical_size)
        )

    def text(
        self, font_key: str, value: str, color: tuple[int, int, int]
    ) -> pygame.Surface:
        """A rendered string, cached. The dash uses very few distinct strings."""
        key = (font_key, value, color)
        surface = self._text_cache.get(key)
        if surface is None:
            surface = self.fonts[font_key].render(value, True, color)
            self._text_cache[key] = surface
        return surface

    def _blit_midright(
        self,
        target: pygame.Surface,
        surface: pygame.Surface,
        logical_point: tuple[int, int],
    ) -> pygame.Rect:
        rect = surface.get_rect()
        rect.midright = self.geometry.point(logical_point)
        return target.blit(surface, rect)

    def _color(
        self, state: DashState, key: str, color: tuple[int, int, int]
    ) -> tuple[int, int, int]:
        """Dim a value that was live and has since gone stale."""
        age = state.age(key)
        if age != float("inf") and age > config.STALE_AFTER:
            return _dim(color)
        return color

    def signature(self, state: DashState) -> tuple:
        """Everything that is actually visible, as a comparable value.

        Comparing this instead of a plain dirty flag means a value that moved
        but still lands on the same gauge frame or the same rounded digits does
        not trigger a repaint. Engine idle wobble, for instance, redraws nothing.
        """
        frames = tuple(
            frame_for(BY_KEY[key], state.values[key])
            for key in ("rpm", "coolant", "egt", "oilpressure", "boost")
        )
        digits = (
            int(round(state.values["speed"])),
            int(round(state.values["fuel"])),
            state.odometer,
            state.mfa_index,
            self.mfa_text(state),
        )
        stale = tuple(
            state.age(key) > config.STALE_AFTER
            for key in ("speed", "fuel", state.mfa_mode.source)
        )
        lamps = tuple(state.indicators[name] for name in INDICATORS)
        return (
            frames,
            digits,
            stale,
            lamps,
            state.fuel_reserve,
            datetime.now().strftime("%H:%M"),
        )

    def draw(self, target: pygame.Surface, state: DashState) -> None:
        target.fill(config.BLACK)
        target.blit(self.background_position(), self.geometry.point((0, 0)))
        self._draw_rpm(target, state)
        self._draw_aux(target, state)
        self._draw_indicators(target, state)
        self._draw_clock(target)
        self._draw_mfa(target, state)
        self._draw_numbers(target, state)

    def background_position(self) -> pygame.Surface:
        return self.assets.background

    def _draw_rpm(self, target: pygame.Surface, state: DashState) -> None:
        index = frame_for(BY_KEY["rpm"], state.values["rpm"])
        target.blit(self.assets.rpm_frames[index], self.geometry.point(layout.RPM))

    def _draw_aux(self, target: pygame.Surface, state: DashState) -> None:
        for key, position in layout.AUX.items():
            index = frame_for(BY_KEY[key], state.values[key])
            target.blit(self.assets.aux_frames[index], self.geometry.point(position))

    def _draw_indicators(self, target: pygame.Surface, state: DashState) -> None:
        for slot, name in enumerate(INDICATORS):
            if state.indicators[name]:
                target.blit(
                    self.assets.indicators[slot],
                    self.geometry.point(layout.INDICATOR_SLOTS[slot]),
                )
        lamp = (
            self.assets.fuel_reserve_on
            if state.fuel_reserve
            else self.assets.fuel_reserve_off
        )
        target.blit(lamp, self.geometry.point(layout.FUEL_RESERVE))

    def _draw_clock(self, target: pygame.Surface) -> None:
        position = self.geometry.point(layout.CLOCK)
        target.blit(self.clock_backplate, position)
        now = datetime.now().strftime("%H:%M")
        target.blit(self.text("medium", now, config.NEON_GREEN), position)

    def _draw_mfa(self, target: pygame.Surface, state: DashState) -> None:
        mode = state.mfa_mode
        target.blit(
            self.assets.mfa_modes[mode.key], self.geometry.point(layout.MFA_BACKGROUND)
        )
        color = self._color(state, mode.source, config.NEON_GREEN)
        self._blit_midright(
            target, self.text("medium", self.mfa_text(state), color),
            layout.MFA_TEMP_RIGHT,
        )

    @staticmethod
    def mfa_text(state: DashState) -> str:
        """The digits for the active MFA mode."""
        mode = state.mfa_mode
        if mode.source == "clock":
            return datetime.now().strftime("%H:%M")
        value = state.mfa_value()
        return f"{value:.{mode.decimals}f}" if mode.decimals else str(int(round(value)))

    def _draw_numbers(self, target: pygame.Surface, state: DashState) -> None:
        speed = str(int(round(state.values["speed"])))
        self._blit_midright(
            target,
            self.text("large", speed, self._color(state, "speed", config.NEON_YELLOW)),
            layout.SPEEDO_RIGHT,
        )
        fuel = str(int(round(state.values["fuel"])))
        self._blit_midright(
            target,
            self.text("medium", fuel, self._color(state, "fuel", config.NEON_GREEN)),
            layout.FUEL_RIGHT,
        )
        self._blit_midright(
            target,
            self.text("small", f"{state.odometer:06d}", config.NEON_GREEN),
            layout.ODOMETER_RIGHT,
        )

    def draw_debug(
        self, target: pygame.Surface, state: DashState, lines: list[str]
    ) -> None:
        y = 4
        for line in lines:
            surface = self.debug_font.render(line, True, config.DEBUG_TEXT)
            shadow = self.debug_font.render(line, True, config.BLACK)
            target.blit(shadow, (5, y + 1))
            target.blit(surface, (4, y))
            y += surface.get_height()
