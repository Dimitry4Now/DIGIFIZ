import time

from digifiz import config
from digifiz.odometer import Odometer, format_file, parse


def test_parse_padded_values():
    assert parse("odo:000123\ntrip:000045\n") == (123, 45.0)


def test_trip_keeps_one_decimal():
    assert parse(format_file(10, 4.25)) == (10, 4.2)


def test_parse_tolerates_junk():
    assert parse("odo:oops\ntrip:\n") == (0, 0.0)
    assert parse("") == (0, 0.0)
    assert parse("nothing useful") == (0, 0.0)


def test_round_trip(tmp_path):
    path = tmp_path / "odo.txt"
    path.write_text(format_file(4321, 12))
    odometer = Odometer(path)
    assert (odometer.odometer, odometer.trip) == (4321, 12.0)


def test_write_is_debounced(tmp_path, monkeypatch):
    path = tmp_path / "odo.txt"
    path.write_text(format_file(0, 0))
    monkeypatch.setattr(config, "ODO_WRITE_INTERVAL", 3600.0)
    odometer = Odometer(path)

    odometer.odometer = 5
    assert odometer.maybe_write() is False  # too soon
    assert parse(path.read_text()) == (0, 0.0)

    assert odometer.maybe_write(force=True) is True
    assert parse(path.read_text()) == (5, 0.0)


def test_unchanged_value_is_not_written(tmp_path):
    path = tmp_path / "odo.txt"
    path.write_text(format_file(7, 1.0))
    odometer = Odometer(path)
    assert odometer.maybe_write(force=True) is False


def test_missing_file_starts_at_zero(tmp_path):
    odometer = Odometer(tmp_path / "absent.txt")
    assert (odometer.odometer, odometer.trip) == (0, 0.0)
