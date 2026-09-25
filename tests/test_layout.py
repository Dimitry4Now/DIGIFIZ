from digifiz.config import LOGICAL_SIZE
from digifiz.layout import AUX, INDICATOR_SLOTS, Geometry
from digifiz.signals import INDICATORS


def test_native_panel_is_unscaled():
    geometry = Geometry.for_display(LOGICAL_SIZE)
    assert geometry.scale == 1.0
    assert geometry.offset == (0, 0)
    assert geometry.point((100, 200)) == (100, 200)


def test_small_panel_letterboxes_vertically():
    geometry = Geometry.for_display((800, 480))
    assert round(geometry.scale, 4) == round(800 / 1920, 4)
    assert geometry.offset == (0, 90)
    assert geometry.point((0, 0)) == (0, 90)
    assert geometry.point((1920, 720)) == (800, 390)


def test_content_never_leaves_the_display():
    for size in ((800, 480), (1280, 720), (1920, 720), (1024, 600)):
        geometry = Geometry.for_display(size)
        right, bottom = geometry.point(LOGICAL_SIZE)
        assert right <= size[0]
        assert bottom <= size[1]


def test_fonts_stay_legible_when_scaled_down():
    geometry = Geometry.for_display((800, 480))
    assert geometry.font_size(174) >= 60
    assert geometry.font_size(67) >= 20


def test_one_slot_per_indicator():
    assert len(INDICATOR_SLOTS) == len(INDICATORS)
    assert set(AUX) == {"coolant", "egt", "oilpressure", "boost"}
