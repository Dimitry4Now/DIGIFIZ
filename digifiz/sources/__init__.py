"""Data sources. Every source implements the DataSource interface in base.py."""

from __future__ import annotations

from .base import DataSource


def build_source(name: str, scenario: str | None = None) -> DataSource:
    """Instantiate a source by name, importing only what is needed.

    Keeping the imports lazy means the optional pyserial and obd dependencies
    are not required to run the dash over MQTT or in demo mode.
    """
    name = name.strip().lower()
    if name == "mqtt":
        from .mqtt_source import MqttSource

        return MqttSource()
    if name == "demo":
        from .demo_source import DemoSource

        return DemoSource(scenario)
    if name == "serial":
        from .serial_source import SerialSource

        return SerialSource()
    if name == "obd":
        from .obd_source import ObdSource

        return ObdSource()
    raise SystemExit(
        f"unknown DIGIFIZ_SOURCE {name!r}; choose from mqtt, demo, serial, obd"
    )


__all__ = ["DataSource", "build_source"]
