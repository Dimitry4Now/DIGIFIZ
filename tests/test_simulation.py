import pytest

from digifiz import simulation
from digifiz.scaling import frame_for
from digifiz.signals import BY_KEY, INDICATORS


@pytest.mark.parametrize("name", sorted(simulation.names()))
def test_every_sample_is_renderable(name):
    """Scenarios may leave a gauge's range - a cold engine is below the coolant
    gauge's lowest mark - but every sample must still map onto a real frame."""
    scenario = simulation.build(name)
    for _ in range(2000):  # 100 seconds at 20 Hz, past every scenario's loop
        sample = scenario.step(0.05)
        for key, value in sample.items():
            if key in BY_KEY:
                signal = BY_KEY[key]
                assert isinstance(value, float)
                assert value == value  # not NaN
                if signal.frames:
                    assert 0 <= frame_for(signal, value) < signal.frames
            else:
                assert key in INDICATORS
                assert isinstance(value, bool)


@pytest.mark.parametrize("name", sorted(simulation.names()))
def test_speed_and_rpm_are_never_negative(name):
    scenario = simulation.build(name)
    for _ in range(500):
        sample = scenario.step(0.05)
        assert sample["rpm"] >= 0
        assert sample["speed"] >= 0


@pytest.mark.parametrize("name", sorted(simulation.names()))
def test_every_key_is_present(name):
    sample = simulation.build(name).step(0.05)
    assert set(BY_KEY) <= set(sample)
    assert set(INDICATORS) <= set(sample)


def test_sweep_reaches_both_ends():
    scenario = simulation.build("sweep")
    seen = []
    for _ in range(400):
        seen.append(scenario.step(0.05)["rpm"])
    assert min(seen) < 100
    assert max(seen) > 4900


def test_warnings_lights_every_lamp():
    scenario = simulation.build("warnings")
    lit = set()
    for _ in range(1000):
        sample = scenario.step(0.05)
        lit.update(name for name in INDICATORS if sample[name])
    assert lit == set(INDICATORS)


def test_unknown_scenario_is_a_clean_error():
    with pytest.raises(SystemExit):
        simulation.build("nope")
