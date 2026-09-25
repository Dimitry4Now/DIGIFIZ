from digifiz.state import DashState


def test_apply_sets_values_and_dirty():
    state = DashState()
    state.dirty = False
    state.apply({"rpm": 1200})
    assert state.values["rpm"] == 1200
    assert state.dirty is True


def test_unchanged_value_leaves_state_clean():
    state = DashState()
    state.apply({"rpm": 1200})
    state.dirty = False
    state.apply({"rpm": 1200})
    assert state.dirty is False


def test_indicators_are_booleans():
    state = DashState()
    state.apply({"glow": 1})
    assert state.indicators["glow"] is True


def test_unknown_keys_are_ignored():
    state = DashState()
    state.apply({"warp_core": 9000})
    assert "warp_core" not in state.values


def test_junk_value_does_not_raise():
    state = DashState()
    state.apply({"rpm": "not a number"})
    assert state.values["rpm"] == 0.0


def test_fuel_reserve_threshold():
    state = DashState()
    state.apply({"fuel": 20})
    assert state.fuel_reserve is False
    state.apply({"fuel": 6})
    assert state.fuel_reserve is True


def test_never_seen_value_is_not_reported_as_stale_forever():
    state = DashState()
    assert state.age("rpm") == float("inf")
    state.apply({"rpm": 100})
    assert state.age("rpm") < 1.0
