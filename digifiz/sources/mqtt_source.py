"""MQTT source, the primary data path.

The original code called client.subscribe("#") and 18 message_callback_add()
calls from inside the render loop, roughly 120 times a second. Everything here
is registered exactly once, in on_connect, so it also survives a reconnect
without the loop's help.
"""

from __future__ import annotations

import logging

import paho.mqtt.client as mqtt

from .. import config
from ..signals import (
    BY_TOPIC,
    TOPIC_TO_CONTROL,
    TOPIC_TO_INDICATOR,
    all_topics,
    strip_prefix,
)
from .base import DataSource

log = logging.getLogger(__name__)


def parse_payload(raw: bytes) -> float | None:
    """A numeric payload, or None if it is junk. Never raises."""
    try:
        text = raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        return None
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        # Tolerate the booleans a flow might publish for indicator topics.
        lowered = text.lower()
        if lowered in {"true", "on"}:
            return 1.0
        if lowered in {"false", "off"}:
            return 0.0
        return None


class MqttSource(DataSource):
    name = "mqtt"

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        prefix: str | None = None,
    ) -> None:
        super().__init__()
        self.host = host or config.MQTT_HOST
        self.port = port if port is not None else config.MQTT_PORT
        self.prefix = prefix if prefix is not None else config.TOPIC_PREFIX
        self._warned: set[str] = set()
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=config.MQTT_CLIENT_ID
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=16)

    def start(self) -> None:
        try:
            self.client.connect_async(self.host, self.port, keepalive=30)
            self.client.loop_start()
        except OSError as exc:  # pragma: no cover - needs a broken host
            self.last_error = str(exc)
            log.error("cannot reach broker %s:%s: %s", self.host, self.port, exc)

    def stop(self) -> None:
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:  # pragma: no cover - shutdown is best effort
            pass

    # paho callbacks, all running on the network thread.

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            self.last_error = f"connect refused ({reason_code})"
            log.error("broker refused connection: %s", reason_code)
            return
        self.connected = True
        self.last_error = None
        # Subscribe to the explicit topic list, once, rather than to "#".
        topics = [(topic, 0) for topic in all_topics(self.prefix)]
        client.subscribe(topics)
        log.info("connected to %s:%s, %d topics", self.host, self.port, len(topics))

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = False
        if reason_code:
            self.last_error = f"disconnected ({reason_code})"
            log.warning("broker disconnected: %s, paho will retry", reason_code)

    def _on_message(self, client, userdata, message):
        topic = strip_prefix(message.topic, self.prefix)
        value = parse_payload(message.payload)
        if value is None:
            self._warn_once(topic, f"unparseable payload {message.payload!r}")
            return
        if topic in BY_TOPIC:
            self.publish(BY_TOPIC[topic].key, value)
        elif topic in TOPIC_TO_INDICATOR:
            self.publish(TOPIC_TO_INDICATOR[topic], value >= 0.5)
        elif topic in TOPIC_TO_CONTROL:
            self.publish(TOPIC_TO_CONTROL[topic], value)
        else:
            self._warn_once(topic, "topic is not on the dash")

    def _warn_once(self, topic: str, reason: str) -> None:
        if topic not in self._warned:
            self._warned.add(topic)
            log.warning("%s: %s", topic, reason)
