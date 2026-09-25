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


def test_every_input_walks_the_same_order():
    """The keyboard, a GPIO button, MQTT and serial all call cycle_mfa(), so
    checking the order once covers all of them."""
    expected = [mode.key for mode in mfa.MODES]

    from_button = DashState()
    from_button.apply({"mfa_next": 0})  # the button sits released at startup
    seen = [from_button.mfa_mode.key]
    for _ in range(len(mfa.MODES) - 1):
        # A button toggling 0/1, the way a GPIO or Arduino input arrives.
        from_button.apply({"mfa_next": 1})  # pressed
        from_button.apply({"mfa_next": 0})  # released
        seen.append(from_button.mfa_mode.key)

    from_keyboard = DashState()
    typed = [from_keyboard.mfa_mode.key]
    for _ in range(len(mfa.MODES) - 1):
        from_keyboard.cycle_mfa()
        typed.append(from_keyboard.mfa_mode.key)

    assert typed == expected
    assert seen == expected


def test_button_counter_also_steps_one_mode_per_press():
    """An Arduino that sends a press count rather than 0/1 edges."""
    state = DashState()
    state.apply({"mfa_next": 0})
    for count in range(1, 4):
        state.apply({"mfa_next": count})
    assert state.mfa_mode.key == mfa.MODES[3].key


def test_holding_the_button_does_not_race_ahead():
    state = DashState()
    state.apply({"mfa_next": 0})
    state.apply({"mfa_next": 1})
    first = state.mfa_index
    for _ in range(20):  # the input stays high while the button is held
        state.apply({"mfa_next": 1})
    assert state.mfa_index == first


def test_absolute_mode_selection():
    """A rotary switch reporting a position rather than a button."""
    state = DashState()
    state.apply({"mfa_mode": "oil_temp"})
    assert state.mfa_mode.key == "oil_temp"
    state.apply({"mfa_mode": 1})
    assert state.mfa_mode.key == mfa.MODES[1].key
    state.apply({"mfa_mode": 99})  # wraps rather than crashing
    assert state.mfa_mode.key == mfa.MODES[99 % len(mfa.MODES)].key
    state.apply({"mfa_mode": "nonsense"})  # ignored, mode unchanged
    assert state.mfa_mode.key == mfa.MODES[99 % len(mfa.MODES)].key
