"""Entry point: display setup, the render loop and frame pacing."""

from __future__ import annotations

import argparse
import logging
import os
import time

import pygame

from . import config
from . import __version__
from .assets import AssetCache, intro_frame_paths, load_intro_frame
from .button import MfaButton
from .layout import Geometry
from .odometer import Odometer
from .render import Renderer
from .signals import BY_KEY, INDICATORS
from .simulation import names as scenario_names
from .sources import build_source
from .state import DashState

log = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="digifiz", description=config.PROJECT_NAME)
    parser.add_argument(
        "--source",
        default=config.SOURCE,
        choices=["mqtt", "demo", "serial", "obd"],
        help="where live values come from (default: %(default)s)",
    )
    parser.add_argument(
        "--scenario",
        default=config.DEMO_SCENARIO,
        choices=sorted(scenario_names()),
        help="which synthetic drive cycle the demo source runs",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="run in a window instead of fullscreen (the default on a desktop)",
    )
    parser.add_argument(
        "--size",
        metavar="WxH",
        help="window size, e.g. 800x480, to preview a panel you do not have",
    )
    parser.add_argument(
        "--debug", action="store_true", help="overlay frame timing and source state"
    )
    parser.add_argument(
        "--fps", type=int, default=config.FPS, help="frame cap (default: %(default)s)"
    )
    parser.add_argument(
        "--intro",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="play the intro before the dash (on by default with the demo "
        "source whenever extracted frames exist)",
    )
    parser.add_argument(
        "--selftest",
        type=float,
        nargs="?",
        const=3.0,
        default=None,
        metavar="SECONDS",
        help="sweep every gauge and light every lamp on startup, like the "
        "cluster's own bulb check (default 3 seconds when given without a value)",
    )
    parser.add_argument(
        "--mfa-cycle",
        type=float,
        metavar="SECONDS",
        help="step the MFA through its modes automatically; 0 disables "
        "(defaults to 4 seconds with the demo source, off otherwise)",
    )
    parser.add_argument(
        "--mfa-button-pin",
        type=int,
        metavar="BCM",
        default=int(config.MFA_BUTTON_PIN) if config.MFA_BUTTON_PIN else None,
        help="GPIO pin (BCM numbering) of a physical MFA mode button",
    )
    parser.add_argument(
        "--odometer", type=int, metavar="KM", help="start the odometer here"
    )
    parser.add_argument(
        "--trip", type=float, metavar="KM", help="start the trip counter here"
    )
    parser.add_argument(
        "--save-odometer",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="write distance back to odo.txt (off with the demo source, so a "
        "demo never inflates the real odometer)",
    )
    parser.add_argument(
        "--time-scale",
        type=float,
        default=1.0,
        metavar="N",
        help="run simulated time N times faster, so distance-based readings "
        "move while you watch (demo source only)",
    )
    parser.add_argument(
        "--exit-after",
        type=float,
        metavar="SECONDS",
        help="quit after this long, for benchmarking and smoke tests",
    )
    parser.add_argument("--verbose", action="store_true", help="log at DEBUG level")
    return parser.parse_args(argv)


def parse_size(raw: str) -> tuple[int, int]:
    try:
        width, height = raw.lower().split("x")
        return int(width), int(height)
    except ValueError:
        raise SystemExit(f"--size wants WxH, for example 800x480, not {raw!r}") from None


def init_display(args: argparse.Namespace) -> pygame.Surface:
    """Create the window or take over the panel.

    The original created the display as an import side effect of constants.py,
    which made import order decide the window size. It is explicit here.
    """
    pygame.init()
    pygame.mouse.set_visible(False)

    if args.size:
        size = parse_size(args.size)
        flags = pygame.DOUBLEBUF
    elif args.windowed:
        size = config.LOGICAL_SIZE
        flags = pygame.DOUBLEBUF
    else:
        # Fullscreen at the panel's own mode: no scaling by the compositor and,
        # under SDL_VIDEODRIVER=kmsdrm, no desktop session needed at all.
        size = (0, 0)
        flags = pygame.FULLSCREEN | pygame.DOUBLEBUF

    surface = pygame.display.set_mode(size, flags)
    pygame.display.set_caption(f"{config.PROJECT_NAME} {__version__}")
    return surface


def play_intro(surface: pygame.Surface, geometry: Geometry) -> None:
    """Stream pre-extracted frames. No video is decoded at runtime."""
    paths = intro_frame_paths()
    if not paths:
        log.warning(
            "no intro frames in %s - build them with "
            "tools/extract_intro.sh das_auto.mp4 %dx%d",
            config.INTRO_DIR,
            *geometry.size,
        )
        return
    log.info("intro: %d frames at %g fps", len(paths), config.INTRO_FPS)
    clock = pygame.time.Clock()
    for path in paths:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN
                and event.key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_q)
            ):
                return
        surface.blit(load_intro_frame(path, geometry), (0, 0))
        pygame.display.flip()
        clock.tick(config.INTRO_FPS)


def play_selftest(
    surface: pygame.Surface,
    renderer: Renderer,
    state: DashState,
    seconds: float,
) -> None:
    """The cluster's own startup check: everything to full, then back to zero.

    Real Digifiz clusters light every segment and lamp briefly at power-up so a
    dead one is obvious. It doubles as a quick proof that every frame of every
    gauge loaded.
    """
    clock = pygame.time.Clock()
    elapsed = 0.0
    while elapsed < seconds:
        dt = clock.tick(config.FPS) / 1000.0
        elapsed += dt
        for event in pygame.event.get():
            if event.type == pygame.QUIT or event.type == pygame.KEYDOWN:
                return

        # Up for the first half, back down for the second.
        half = seconds / 2
        fraction = elapsed / half if elapsed < half else max(0.0, 2 - elapsed / half)
        for key, signal in BY_KEY.items():
            state.values[key] = signal.lo + (signal.hi - signal.lo) * fraction
        lit = fraction > 0.05
        for name in INDICATORS:
            state.indicators[name] = lit
        state.mfa_index = int(elapsed * 4) % 6

        renderer.draw(surface, state)
        pygame.display.flip()

    for key, signal in BY_KEY.items():
        state.values[key] = signal.lo
    for name in INDICATORS:
        state.indicators[name] = False


def run(args: argparse.Namespace) -> int:
    surface = init_display(args)
    geometry = Geometry.for_display(surface.get_size())
    log.info(
        "display %dx%d, scale %.3f, letterbox offset %s",
        *surface.get_size(),
        geometry.scale,
        geometry.offset,
    )

    play_it = args.intro
    if play_it is None:
        # A demo is meant to show the whole thing, so the intro plays whenever
        # it has been built. Anywhere else it is opt-in, because a cluster
        # coming up in a car should show numbers as soon as it can.
        play_it = config.INTRO_ENABLED or (
            args.source == "demo" and bool(intro_frame_paths())
        )
    if play_it:
        play_intro(surface, geometry)

    assets = AssetCache(geometry)
    renderer = Renderer(geometry, assets)
    state = DashState()
    odometer = Odometer()
    if args.odometer is not None:
        odometer.odometer = args.odometer
    if args.trip is not None:
        odometer.trip = args.trip
    state.odometer = odometer.odometer
    state.trip = float(odometer.trip)

    if args.selftest:
        play_selftest(surface, renderer, state, args.selftest)

    source = build_source(args.source, scenario=args.scenario)
    source.start()
    state.source_name = source.name

    button = None
    if args.mfa_button_pin is not None:
        button = MfaButton(args.mfa_button_pin)
        button.start()

    mfa_cycle = args.mfa_cycle
    if mfa_cycle is None:
        mfa_cycle = 4.0 if args.source == "demo" else 0.0
    mfa_timer = 0.0

    # Speeding up simulated time is what makes distance-based readings, the
    # odometer and the trip counter, actually move during a short demo.
    time_scale = max(0.1, args.time_scale) if args.source == "demo" else 1.0

    save_odometer = args.save_odometer
    if save_odometer is None:
        save_odometer = args.source != "demo"
    if not save_odometer:
        log.info("odometer is not being saved (demo distance stays out of odo.txt)")

    clock = pygame.time.Clock()
    distance = float(odometer.odometer)
    trip = float(odometer.trip)
    last_signature: tuple | None = None
    drawn = skipped = 0
    running = True
    deadline = time.monotonic() + args.exit_after if args.exit_after else None

    try:
        while running:
            dt = clock.tick(args.fps) / 1000.0
            if deadline is not None and time.monotonic() >= deadline:
                running = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif event.key in (pygame.K_m, pygame.K_RIGHT):
                        state.cycle_mfa()
                        mfa_timer = 0.0
                    elif event.key == pygame.K_LEFT:
                        state.cycle_mfa(-1)
                        mfa_timer = 0.0

            state.apply(source.drain())

            if button is not None:
                for _ in range(button.drain()):
                    state.cycle_mfa()
                    mfa_timer = 0.0

            if mfa_cycle:
                mfa_timer += dt
                if mfa_timer >= mfa_cycle:
                    mfa_timer = 0.0
                    state.cycle_mfa()

            # Distance from speed: km/h for dt seconds.
            travelled = state.values["speed"] * dt * time_scale / 3600.0
            distance += travelled
            trip += travelled
            state.trip = trip
            whole = int(distance)
            if whole != state.odometer:
                state.odometer = whole
                odometer.odometer = whole
            odometer.trip = trip
            if save_odometer:
                odometer.maybe_write()

            # Everything below this line is the expensive part. A frame that
            # would look identical to the last one is not drawn at all, so a
            # sensor wobbling within one gauge step costs nothing.
            signature = renderer.signature(state)
            if signature == last_signature and not args.debug:
                skipped += 1
                continue
            last_signature = signature

            renderer.draw(surface, state)
            if args.debug:
                renderer.draw_debug(
                    surface,
                    state,
                    [
                        f"{clock.get_fps():5.1f} fps   frame {dt * 1000:5.1f} ms",
                        f"drawn {drawn}  skipped {skipped}",
                        f"source {source.status}",
                        f"scale {geometry.scale:.3f}  assets {assets.load_seconds:.2f}s",
                        "  ".join(
                            f"{key}={value:.0f}" for key, value in state.values.items()
                        ),
                    ],
                )
            pygame.display.flip()
            state.dirty = False
            drawn += 1
    finally:
        if button is not None:
            button.stop()
        source.stop()
        if save_odometer:
            odometer.maybe_write(force=True)
        pygame.quit()

    log.info(
        "drew %d frames, skipped %d (%.0f%% of frames needed no redraw)",
        drawn,
        skipped,
        100.0 * skipped / max(1, drawn + skipped),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    started = time.monotonic()
    try:
        return run(args)
    except KeyboardInterrupt:
        log.info("interrupted after %.1fs", time.monotonic() - started)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
