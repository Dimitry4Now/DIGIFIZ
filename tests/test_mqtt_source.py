from types import SimpleNamespace

from digifiz.signals import BY_KEY, INDICATOR_TOPICS
from digifiz.sources.mqtt_source import MqttSource, parse_payload


def message(topic: str, payload: bytes) -> SimpleNamespace:
    return SimpleNamespace(topic=topic, payload=payload)


def test_parse_payload():
    assert parse_payload(b"12.5") == 12.5
    assert parse_payload(b" 42 ") == 42.0
    assert parse_payload(b"ON") == 1.0
    assert parse_payload(b"false") == 0.0
    assert parse_payload(b"") is None
    assert parse_payload(b"nonsense") is None
    assert parse_payload(b"\xff\xfe") is None


def test_numeric_topic_reaches_drain():
    source = MqttSource()
    source._on_message(None, None, message(BY_KEY["rpm"].topic, b"2400"))
    assert source.drain() == {"rpm": 2400.0}


def test_indicator_topic_becomes_bool():
    source = MqttSource()
    source._on_message(None, None, message(INDICATOR_TOPICS["glow"], b"1"))
    assert source.drain() == {"glow": True}


def test_junk_payload_is_dropped_not_raised():
    source = MqttSource()
    source._on_message(None, None, message(BY_KEY["rpm"].topic, b"oops"))
    assert source.drain() == {}


def test_unknown_topic_is_ignored():
    source = MqttSource()
    source._on_message(None, None, message("some/other/thing", b"1"))
    assert source.drain() == {}


def test_prefix_is_stripped():
    source = MqttSource(prefix="bus")
    source._on_message(None, None, message(f"bus/{BY_KEY['speed'].topic}", b"75"))
    assert source.drain() == {"speed": 75.0}


def test_drain_keeps_only_the_newest_value():
    source = MqttSource()
    for value in (b"1000", b"2000", b"3000"):
        source._on_message(None, None, message(BY_KEY["rpm"].topic, value))
    assert source.drain() == {"rpm": 3000.0}
    assert source.drain() == {}


def test_subscribes_once_to_explicit_topics():
    calls = []

    class FakeClient:
        def subscribe(self, topics):
            calls.append(topics)

    source = MqttSource()
    source._on_connect(FakeClient(), None, None, 0)
    assert len(calls) == 1
    subscribed = [topic for topic, _qos in calls[0]]
    assert "#" not in subscribed
    assert BY_KEY["rpm"].topic in subscribed
    assert len(subscribed) == len(BY_KEY) + len(INDICATOR_TOPICS)
