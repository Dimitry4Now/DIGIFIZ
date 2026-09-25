#!/usr/bin/env python3
"""Publish simulated sensor data to an MQTT broker.

This is the main way to develop the dash without any hardware. It publishes to
exactly the topics the dash subscribes to, in engineering units, using the same
generators the in-process demo source uses.

    python tools/mqtt_sim.py --scenario drive --rate 20 --verbose
    python tools/mqtt_sim.py --scenario warnings --broker 192.168.2.200
    python tools/mqtt_sim.py --once            # one snapshot, then exit
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import paho.mqtt.client as mqtt  # noqa: E402

from digifiz import simulation  # noqa: E402
from digifiz.signals import BY_KEY, INDICATOR_TOPICS  # noqa: E402


def topic_for(key: str, prefix: str) -> str:
    if key in BY_KEY:
        topic = BY_KEY[key].topic
    elif key in INDICATOR_TOPICS:
        topic = INDICATOR_TOPICS[key]
    else:
        raise KeyError(key)
    return f"{prefix.rstrip('/')}/{topic}" if prefix else topic


def format_value(key: str, value: float | bool) -> str:
    """Engineering units on the wire. The dash does the scaling."""
    if isinstance(value, bool):
        return "1" if value else "0"
    decimals = BY_KEY[key].decimals if key in BY_KEY else 0
    return f"{value:.{decimals}f}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--scenario",
        default="drive",
        choices=sorted(simulation.names()),
        help="which drive cycle to publish (default: %(default)s)",
    )
    parser.add_argument("--broker", default="localhost", help="broker host")
    parser.add_argument("--port", type=int, default=1883, help="broker port")
    parser.add_argument(
        "--rate", type=float, default=20.0, help="publishes per second (default: %(default)s)"
    )
    parser.add_argument("--topic-prefix", default="", help="prefix every topic")
    parser.add_argument(
        "--duration", type=float, help="stop after this many seconds (default: forever)"
    )
    parser.add_argument(
        "--once", action="store_true", help="publish one snapshot and exit"
    )
    parser.add_argument("--retain", action="store_true", help="publish with retain set")
    parser.add_argument("--verbose", action="store_true", help="print what is published")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scenario = simulation.build(args.scenario)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="digifiz-sim")
    try:
        client.connect(args.broker, args.port, keepalive=30)
    except OSError as exc:
        print(
            f"cannot reach broker at {args.broker}:{args.port}: {exc}\n"
            "Is mosquitto running? (sudo systemctl start mosquitto)",
            file=sys.stderr,
        )
        return 1
    client.loop_start()
    print(f"publishing {args.scenario} to {args.broker}:{args.port} at {args.rate:g} Hz")

    interval = 1.0 / args.rate if args.rate > 0 else 0.05
    started = time.monotonic()
    published = 0
    try:
        while True:
            sample = scenario.step(0.0 if args.once else interval)
            for key, value in sample.items():
                client.publish(
                    topic_for(key, args.topic_prefix),
                    format_value(key, value),
                    qos=0,
                    retain=args.retain,
                )
                published += 1
            if args.verbose:
                print(
                    "  ".join(
                        f"{key}={format_value(key, value)}" for key, value in sample.items()
                    )
                )
            if args.once:
                break
            if args.duration and time.monotonic() - started >= args.duration:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        # Give paho a moment to flush the last batch before dropping the socket.
        time.sleep(0.2)
        client.loop_stop()
        client.disconnect()

    elapsed = time.monotonic() - started
    print(f"published {published} messages in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
