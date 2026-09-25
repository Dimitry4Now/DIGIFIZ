"""Entry point: display setup, the render loop and frame pacing."""

from __future__ import annotations

import argparse
import logging
import os
import time

import pygame

from . import config
from . import __version__
from .assets import AssetCache, load_intro_frames
from .layout import Geometry
from .odometer import Odometer
from .render import Renderer
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
        "--intro", action="store_true", help="play the intro frames before the dash"
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
    """Blit pre-extracted frames. No video decoding happens at runtime."""
    frames = load_intro_frames(geometry)
    if not frames:
        log.info("no intro frames in %s, skipping", config.INTRO_DIR)
        return
    clock = pygame.time.Clock()
    for frame in frames:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN
                and event.key in (pygame.K_ESCAPE, pygame.K_SPACE)
            ):
                return
        surface.blit(frame, (0, 0))
        pygame.display.flip()
        clock.tick(config.INTRO_FPS)


def run(args: argparse.Namespace) -> int:
    surface = init_display(args)
    geometry = Geometry.for_display(surface.get_size())
    log.info(
        "display %dx%d, scale %.3f, letterbox offset %s",
        *surface.get_size(),
        geometry.scale,
        geometry.offset,
    )

    if args.intro or config.INTRO_ENABLED:
        play_intro(surface, geometry)

    assets = AssetCache(geometry)
    renderer = Renderer(geometry, assets)
    state = DashState()
    odometer = Odometer()
    state.odometer = odometer.odometer
    state.tripometer = odometer.trip

    source = build_source(args.source, scenario=args.scenario)
    source.start()
    state.source_name = source.name

    clock = pygame.time.Clock()
    distance = float(odometer.odometer)
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
                elif event.type == pygame.KEYDOWN and event.key in (
                    pygame.K_ESCAPE,
                    pygame.K_q,
                ):
                    running = False

            state.apply(source.drain())

            # Distance from speed: km/h for dt seconds. The odometer only goes
            # dirty when the whole-kilometre value changes.
            distance += state.values["speed"] * dt / 3600.0
            whole = int(distance)
            if whole != state.odometer:
                state.odometer = whole
                odometer.odometer = whole
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
        source.stop()
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
