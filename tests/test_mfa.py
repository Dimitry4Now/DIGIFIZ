import os
from collections import Counter

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from digifiz import mfa  # noqa: E402
from digifiz.assets import AssetCache  # noqa: E402
from digifiz.layout import Geometry  # noqa: E402
from digifiz.render import Renderer  # noqa: E402
from digifiz.signals import BY_KEY  # noqa: E402
from digifiz.state import DashState  # noqa: E402


@pytest.fixture(scope="module")
def renderer():
    pygame.init()
    pygame.display.set_mode((800, 480))
    geometry = Geometry.for_display((800, 480))
    yield Renderer(geometry, AssetCache(geometry))
    pygame.quit()


@pytest.fixture(scope="module")
def native_assets(renderer):
    return AssetCache(Geometry.for_display((1920, 720)))


def test_every_mode_has_a_value_to_show():
    for mode in mfa.MODES:
        assert mode.source == "clock" or mode.source in BY_KEY or mode.source == "trip"


def test_chips_do_not_overlap():
    rects = [pygame.Rect(mode.chip) for mode in mfa.MODES]
    for index, rect in enumerate(rects):
        for other in rects[index + 1:]:
            assert not rect.colliderect(other)


def test_cycling_wraps_all_the_way_round():
    state = DashState()
    start = state.mfa_index
    for _ in range(len(mfa.MODES)):
        state.cycle_mfa()
    assert state.mfa_index == start


def test_cycling_backwards():
    state = DashState()
    state.cycle_mfa(-1)
    assert state.mfa_index == (mfa.DEFAULT_INDEX - 1) % len(mfa.MODES)


def test_one_surface_per_mode(renderer):
    assert set(renderer.assets.mfa_modes) == {mode.key for mode in mfa.MODES}


def test_only_the_active_chip_is_lit(native_assets):
    """Checked at native resolution: scaling blends chip edges, which would
    make colour sampling on a small panel meaningless."""
    for mode in mfa.MODES:
        surface = native_assets.mfa_modes[mode.key]
        for other in mfa.MODES:
            color = _dominant_color(surface, pygame.Rect(other.chip))
            expected = mfa.CHIP_LIT if other.key == mode.key else mfa.CHIP_UNLIT
            assert color == expected, f"{mode.key}: {other.key} was {color}"


def _dominant_color(surface, rect):
    """The chip's background: the colour covering most of its rectangle.

    Sampling a single pixel is unreliable because the chips have rounded,
    antialiased borders and glyphs across the middle.
    """
    counts = Counter()
    for y in range(rect.y + 2, rect.bottom - 2):
        for x in range(rect.x + 2, rect.right - 2):
            counts[surface.get_at((x, y))[:3]] += 1
    return counts.most_common(1)[0][0]


def test_mode_text_formatting(renderer):
    state = DashState()
    state.apply({"consumption": 7.44, "avg_speed": 63.2, "oil_temp": 104.4})
    state.trip = 142.63

    state.mfa_index = mfa.MODES.index(mfa.BY_KEY["consumption"])
    assert renderer.mfa_text(state) == "7.4"

    state.mfa_index = mfa.MODES.index(mfa.BY_KEY["avg_speed"])
    assert renderer.mfa_text(state) == "63"

    state.mfa_index = mfa.MODES.index(mfa.BY_KEY["trip"])
    assert renderer.mfa_text(state) == "142.6"

    state.mfa_index = mfa.MODES.index(mfa.BY_KEY["clock"])
    assert ":" in renderer.mfa_text(state)


def test_signature_changes_with_the_mode(renderer):
    state = DashState()
    before = renderer.signature(state)
    state.cycle_mfa()
    assert renderer.signature(state) != before


def test_cycle_order_starts_at_the_clock_and_loops():
    assert [mode.key for mode in mfa.MODES] == [
        "clock",
        "trip",
        "consumption",
        "avg_speed",
        "oil_temp",
        "outside_temp",
    ]
    assert mfa.MODES[mfa.DEFAULT_INDEX].key == "clock"

    state = DashState()
    order = [state.mfa_mode.key]
    for _ in range(len(mfa.MODES) - 1):
        state.cycle_mfa()
        order.append(state.mfa_mode.key)
    assert order == [mode.key for mode in mfa.MODES]

    state.cycle_mfa()
    assert state.mfa_mode.key == "clock"
