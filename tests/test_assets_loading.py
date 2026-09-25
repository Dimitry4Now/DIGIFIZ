import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from digifiz.assets import TOTAL_SURFACES, AssetCache  # noqa: E402
from digifiz.layout import Geometry  # noqa: E402
from digifiz.signals import AUX_FRAMES, INDICATORS, RPM_FRAMES  # noqa: E402


@pytest.fixture(scope="module")
def display():
    pygame.init()
    pygame.display.set_mode((800, 480))
    yield Geometry.for_display((800, 480))
    pygame.quit()


def test_progressive_load_reports_progress_and_finishes(display):
    assets = AssetCache(display, load=False)
    assert assets.ready is False

    progress = list(assets.load_progressively())
    assert assets.ready is True
    assert progress == sorted(progress)
    assert progress[0] > 0
    assert progress[-1] == pytest.approx(1.0)
    assert len(progress) <= TOTAL_SURFACES


def test_progressive_load_produces_everything(display):
    assets = AssetCache(display, load=False)
    assets.load()
    assert len(assets.rpm_frames) == RPM_FRAMES
    assert len(assets.aux_frames) == AUX_FRAMES
    assert len(assets.indicators) == len(INDICATORS)
    assert assets.background is not None
    assert assets.fuel_reserve_on is not None
    assert assets.count == TOTAL_SURFACES


def test_loading_twice_is_a_no_op(display):
    assets = AssetCache(display)
    frames = list(assets.rpm_frames)
    assert list(assets.load_progressively()) == []
    assert assets.rpm_frames == frames


def test_can_be_loaded_a_step_at_a_time(display):
    """This is what lets the intro play while the dash loads behind it."""
    assets = AssetCache(display, load=False)
    loader = assets.load_progressively()
    for _ in range(5):
        next(loader)
    assert assets.ready is False
    assert assets.background is not None  # the first steps really did work
    for _ in loader:
        pass
    assert assets.ready is True
