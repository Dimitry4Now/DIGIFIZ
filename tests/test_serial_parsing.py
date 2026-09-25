from digifiz.signals import INDICATORS
from digifiz.sources.serial_source import parse_line


def test_full_line():
    updates = parse_line("D rpm=1850 egt=430 boost=12.4 oilp=45 clt=88 fuel=32 spd=62")
    assert updates["rpm"] == 1850
    assert updates["boost"] == 12.4
    assert updates["oilpressure"] == 45
    assert updates["coolant"] == 88
    assert updates["speed"] == 62


def test_partial_line_is_accepted():
    assert parse_line("rpm=900") == {"rpm": 900.0}


def test_indicator_bitfield():
    updates = parse_line("D ind=0x005")
    assert updates[INDICATORS[0]] is True
    assert updates[INDICATORS[1]] is False
    assert updates[INDICATORS[2]] is True
    assert all(updates[name] is False for name in INDICATORS[3:])


def test_decimal_bitfield():
    assert parse_line("ind=3")[INDICATORS[1]] is True


def test_junk_never_raises():
    for line in ("", "   ", "garbage", "=", "rpm=", "rpm=abc", "unknown=5", "D"):
        assert isinstance(parse_line(line), dict)


def test_unknown_keys_do_not_discard_good_ones():
    assert parse_line("nonsense=1 spd=42") == {"speed": 42.0}
