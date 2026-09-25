"""Renderer tests. They need a real pygame display, so they use SDL's dummy
video driver and run headless."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from digifiz.assets import AssetCache  # noqa: E402
from digifiz.layout import Geometry  # noqa: E402
from digifiz.render import Renderer  # noqa: E402
from digifiz.signals import BY_KEY  # noqa: E402
from digifiz.state import DashState  # noqa: E402


@pytest.fixture(scope="module")
def renderer():
    pygame.init()
    surface = pygame.display.set_mode((800, 480))
    geometry = Geometry.for_display(surface.get_size())
    yield surface, Renderer(geometry, AssetCache(geometry))
    pygame.quit()


def test_draw_does_not_raise_across_the_whole_range(renderer):
    surface, renders = renderer
    state = DashState()
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        for key, signal in BY_KEY.items():
            state.values[key] = signal.lo + (signal.hi - signal.lo) * fraction
        for name in state.indicators:
            state.indicators[name] = fraction > 0.5
        renders.draw(surface, state)


def test_signature_ignores_movement_inside_one_gauge_step(renderer):
    surface, renders = renderer
    state = DashState()
    state.apply({"rpm": 1500})
    before = renders.signature(state)
    state.apply({"rpm": 1520})  # same 100 rpm frame
    assert renders.signature(state) == before


def test_signature_changes_on_a_new_gauge_step(renderer):
    surface, renders = renderer
    state = DashState()
    state.apply({"rpm": 1500})
    before = renders.signature(state)
    state.apply({"rpm": 1650})
    assert renders.signature(state) != before


def test_signature_changes_when_a_lamp_lights(renderer):
    surface, renders = renderer
    state = DashState()
    before = renders.signature(state)
    state.apply({"glow": 1})
    assert renders.signature(state) != before


def test_text_surfaces_are_cached(renderer):
    surface, renders = renderer
    first = renders.text("large", "88", (255, 255, 255))
    second = renders.text("large", "88", (255, 255, 255))
    assert first is second


def test_assets_are_prescaled_to_the_display(renderer):
    surface, renders = renderer
    scale = renders.geometry.scale
    # background.png is authored at the logical size.
    assert renders.assets.background.get_width() == round(1920 * scale)
