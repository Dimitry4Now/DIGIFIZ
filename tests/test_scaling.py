from digifiz.scaling import fraction_for, frame_for
from digifiz.signals import BY_KEY, RPM_FRAMES, AUX_FRAMES


def test_rpm_endpoints():
    rpm = BY_KEY["rpm"]
    assert frame_for(rpm, 0) == 0
    assert frame_for(rpm, 5000) == RPM_FRAMES - 1
    assert frame_for(rpm, 2500) == (RPM_FRAMES - 1) // 2


def test_out_of_range_clamps_instead_of_raising():
    rpm = BY_KEY["rpm"]
    assert frame_for(rpm, -1000) == 0
    assert frame_for(rpm, 99999) == RPM_FRAMES - 1


def test_every_aux_signal_covers_its_frame_range():
    for key in ("coolant", "egt", "oilpressure", "boost"):
        signal = BY_KEY[key]
        assert signal.frames == AUX_FRAMES
        assert frame_for(signal, signal.lo) == 0
        assert frame_for(signal, signal.hi) == AUX_FRAMES - 1


def test_frames_are_monotonic_and_in_bounds():
    signal = BY_KEY["egt"]
    previous = -1
    for value in range(-50, 600, 5):
        index = frame_for(signal, value)
        assert 0 <= index < signal.frames
        assert index >= previous
        previous = index


def test_text_only_signal_has_no_frames():
    import pytest

    with pytest.raises(ValueError):
        frame_for(BY_KEY["speed"], 50)


def test_fraction_clamps():
    signal = BY_KEY["boost"]
    assert fraction_for(signal, -5) == 0.0
    assert fraction_for(signal, 99) == 1.0
