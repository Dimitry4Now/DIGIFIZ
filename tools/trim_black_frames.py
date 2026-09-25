#!/usr/bin/env python3
"""Drop the black run-in and run-out from an extracted frame sequence.

Clips usually open and close on black. Played before the dash that reads as a
dead screen rather than as part of the animation, so the flat frames at each
end are removed and the rest renumbered.

    python tools/trim_black_frames.py images/intro
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

#: Mean channel value below this counts as a black frame.
BLACK_LEVEL = 1.0

#: Black frames kept at each end, so the cut is not jarring.
KEEP_PADDING = 2


def brightness(path: Path) -> float:
    colour = pygame.transform.average_color(pygame.image.load(str(path)))
    return sum(colour[:3]) / 3.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=Path("images/intro"))
    parser.add_argument(
        "--level", type=float, default=BLACK_LEVEL, help="black threshold, 0-255"
    )
    parser.add_argument(
        "--padding", type=int, default=KEEP_PADDING, help="black frames to keep"
    )
    args = parser.parse_args(argv)

    pygame.init()
    paths = sorted(args.directory.glob("frame_*.png"))
    if not paths:
        print(f"no frames in {args.directory}", file=sys.stderr)
        return 1

    levels = [brightness(path) for path in paths]
    lit = [index for index, value in enumerate(levels) if value > args.level]
    if not lit:
        print("every frame is black, nothing to trim", file=sys.stderr)
        return 1

    first = max(0, lit[0] - args.padding)
    last = min(len(paths) - 1, lit[-1] + args.padding)
    if first == 0 and last == len(paths) - 1:
        print(f"{len(paths)} frames, nothing to trim")
        return 0

    kept = paths[first : last + 1]
    for path in paths[:first] + paths[last + 1:]:
        path.unlink()

    # Renumber through temporary names so a rename never lands on a file that
    # has not been moved yet.
    for index, path in enumerate(kept):
        path.rename(path.with_name(f"tmp_{index:04d}.png"))
    for index in range(len(kept)):
        temporary = args.directory / f"tmp_{index:04d}.png"
        temporary.rename(args.directory / f"frame_{index:04d}.png")

    dropped = len(paths) - len(kept)
    print(
        f"trimmed {dropped} black frames "
        f"({len(paths)} -> {len(kept)}, {len(kept) / 25:.1f}s at 25 fps)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
