# Digifiz Dash

A faithful recreation of the VW Digifiz digital instrument cluster, built to run
fullscreen on a Raspberry Pi and driven by live sensor data.

The Digifiz is one of the best looking clusters ever fitted to a production car,
and original units are getting rare, expensive and hard to keep alive. The goal
here is to save the design: rebuild it in software, pixel for pixel, so it can
be run on a modern panel — and eventually fitted to my own project car once the
rest of the pieces come together.

Started as a fork of [GFunkbus76/Digifiz-Dash](https://github.com/gfunkbus76),
which supplied the original artwork and the idea of driving it from pygame. The
code has since been rebuilt around a package layout, a data-source abstraction,
resolution-independent rendering and a test suite.

## What it does

- Tachometer, speedometer, clock, odometer and MFA readout.
- Four aux gauges: coolant temperature, exhaust gas temperature, oil pressure
  and boost.
- Ten indicator lamps plus the fuel reserve warning.
- Resolution independent: the artwork is authored at 1920x720 and scaled once at
  startup to whatever panel it finds, letterboxed and centred. An 800x480 5 inch
  panel and a 1920x720 stretched cluster LCD both work with no code changes.
- Runs with no data at all, so the look can be worked on anywhere.

## Quick start

No hardware, no broker, one command:

```bash
python3 -m venv .venv
.venv/bin/pip install -U pip -r requirements.txt
.venv/bin/python -m digifiz.app --source demo --scenario drive --size 800x480 --debug
```

`--debug` overlays frame timing, the active source and every live value.

## Data sources

Values arrive in engineering units — rpm, °C, psi, litres, km/h — and the dash
maps them onto the artwork itself. Pick a source with `--source` or the
`DIGIFIZ_SOURCE` environment variable:

| Source | What it is |
|---|---|
| `mqtt` (default) | Subscribes to a broker. The intended path for a real install. |
| `demo` | Synthetic data generated in-process. No broker, no hardware. |
| `serial` | Reads keyed lines from an Arduino over USB serial. |
| `obd` | Polls an OBD-II adapter. Needs a car with an ECU that speaks it. |

### MQTT

Topics, all publishing plain numbers:

```
engine/rpm/state          rpm        0..5000
engine/coolant/state      °C        50..120
engine/egt/state          °C         0..500
engine/oilpressure/state  psi        0..80
engine/boost/state        psi        0..30
engine/fuel/state         litres     0..60
cabin/speed_cv/state      km/h       0..199
cabin/outside_temp/state  °C       -40..60
indicator/<name>/state    0 or 1
```

Indicator names: `illumination`, `foglight`, `defog`, `highbeam`, `leftturn`,
`rightturn`, `brakewarn`, `oillight`, `alt`, `glow`.

Run it with a broker and the simulator:

```bash
sudo apt install mosquitto mosquitto-clients
tools/run_dev.sh --scenario drive
```

Or by hand:

```bash
.venv/bin/python tools/mqtt_sim.py --scenario drive --rate 20 --verbose
.venv/bin/python -m digifiz.app --source mqtt --size 800x480 --debug
```

### Serial

One line per update, keys optional, so a sketch can send only what it has:

```
D rpm=1850 egt=430 boost=12.4 oilp=45 clt=88 fuel=32 spd=62 ind=0x1A4
```

`ind` is a bitfield over the ten indicator lamps, bit 0 first.

```bash
DIGIFIZ_SERIAL_PORT=/dev/ttyUSB0 .venv/bin/python -m digifiz.app --source serial
```

## Simulator scenarios

Used by both `--source demo` and `tools/mqtt_sim.py`:

| Scenario | What it exercises |
|---|---|
| `idle` | Warm engine, stationary. Proves idle frames are skipped. |
| `drive` | A drive cycle with turbo lag, EGT inertia and a warm-up. |
| `sweep` | Every gauge end to end. Checks all artwork and the layout. |
| `warnings` | Each lamp in turn, blinking turn signals, fuel below reserve. |
| `cold-start` | Glow plugs, cold coolant, oil pressure lamp clearing. |

## Intro animation

An optional splash plays before the dash comes up. The clip is converted to
pre-scaled PNG frames once, so nothing is decoded at runtime:

```bash
sudo apt install ffmpeg
tools/extract_intro.sh das_auto.mp4 800x480
.venv/bin/python -m digifiz.app --intro --size 800x480
```

Frames land in `images/intro/` and are not tracked, so re-run the extraction for
each panel size. Without them, `--intro` simply skips.

## Performance

The dash is built to sit quietly on a Pi rather than peg a core:

- Every image is decoded, format-converted and pre-scaled **once** at startup.
- Rendered text is cached; the dash uses very few distinct strings.
- A frame is drawn only when it would actually look different. A sensor moving
  inside one gauge step, or a rounding-identical reading, repaints nothing — at
  idle roughly 98% of frames are skipped.
- The odometer is read once and written back atomically, at most every 30
  seconds, to protect the SD card.
- Under `SDL_VIDEODRIVER=kmsdrm` it draws straight to the panel with no X11, no
  Wayland and no compositor.

## Layout

All coordinates live in `digifiz/layout.py` in 1920x720 logical space.
`Geometry` scales them to the real panel once at startup, so retargeting a
different screen never means touching drawing code.

## Raspberry Pi

See [deploy/README.md](deploy/README.md) for packages, the HDMI mode for a 5
inch panel, the KMS/DRM setup and the systemd unit.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
```

Covers unit-to-frame scaling, the MQTT and serial parsers, odometer persistence
and debounce, layout scaling at several panel sizes, the simulator staying
renderable, and the repaint gate. The renderer tests run headless on SDL's dummy
video driver.

## Layout of the repository

```
digifiz/            the dash itself
  app.py            display setup, render loop, frame pacing
  config.py         tunables and environment variables
  layout.py         every coordinate, in logical space
  assets.py         load, convert and pre-scale artwork once
  render.py         drawing and the repaint gate
  scaling.py        engineering units to artwork frames
  signals.py        the one description of every value and topic
  simulation.py     synthetic engine behaviour
  sources/          mqtt, demo, serial, obd
tools/              simulator, dev runner, intro frame extraction
deploy/             systemd unit and Raspberry Pi notes
images/, fonts/     artwork
arduino-node-red/   sketches and notes for the sensor hardware
tests/
```

## Credits

- Original project and artwork: [GFunkbus76](https://github.com/gfunkbus76),
  itself inspired by ManxGauged and miata-dash.
- Seven-segment fonts: [DSEG](https://www.keshikan.net/fonts-e.html) by Keshikan.

Not affiliated with Volkswagen. The Digifiz design is theirs; this is a tribute
to it.

## Disclaimer

Work in progress, and a hobby project. If you fit something like this to a
vehicle, it is on you to make sure it does not distract you or replace anything
safety critical, and to check your local rules. **Use at your own risk.**
