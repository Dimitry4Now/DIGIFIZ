#!/usr/bin/env python3
"""Compose a 1280x720 YouTube thumbnail: the dash on the vivid gradient used
for the demo videos, under a title set in the cluster's own segment font.

    .venv/bin/python tools/demo/make_thumbnail.py DASH.png OUT.png

DASH.png is a frame of the dash with the letterbox cut off, for example:

    ffmpeg -ss 42 -i demo.mp4 -frames:v 1 -vf crop=1366:514:277:283 dash.png

Needs pygame-ce, which the DIGIFIZ virtualenv already has.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

PROJECT = Path(os.environ.get("DIGIFIZ_DIR", Path(__file__).resolve().parents[2]))
SEGMENT_FONT = PROJECT / "fonts" / "DSEG14Classic-Regular.ttf"
SANS_FONT = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"

WIDTH, HEIGHT = 1280, 720
NEON = (190, 255, 90)

# The same blobs as render_demo_vibrant.sh: (x, y) as fractions, then colour.
BLOBS = [
    (0.05, 0.10, (88, 60, 255)),
    (0.95, 0.05, (255, 70, 165)),
    (1.00, 0.95, (255, 150, 55)),
    (0.00, 1.00, (20, 170, 255)),
    (0.50, 0.55, (150, 60, 240)),
]
SPREAD = 0.42


def gradient() -> pygame.Surface:
    # Worked out small and scaled up; it is smooth, so nothing is lost.
    small_w, small_h = WIDTH // 8, HEIGHT // 8
    small = pygame.Surface((small_w, small_h))
    for y in range(small_h):
        for x in range(small_w):
            fx, fy = x / small_w, y / small_h
            total = 0.0
            mixed = [0.0, 0.0, 0.0]
            for bx, by, colour in BLOBS:
                weight = math.exp(-((fx - bx) ** 2 + (fy - by) ** 2) / SPREAD**2)
                total += weight
                for channel in range(3):
                    mixed[channel] += colour[channel] * weight
            small.set_at((x, y), [round(value / total) for value in mixed])
    return pygame.transform.smoothscale(small, (WIDTH, HEIGHT))


def rounded(surface: pygame.Surface, radius: int) -> pygame.Surface:
    mask = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    out = surface.convert_alpha()
    out.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return out


def glow(surface: pygame.Surface, radius: int, strength: int = 2) -> pygame.Surface:
    """A soft halo from a surface's own pixels, for light that seems to bleed.

    Drawn on black and meant for additive blending, so transparent pixels add
    nothing rather than whatever colour they happen to hold.
    """
    pad = radius * 3
    lit = pygame.Surface((surface.get_width() + pad * 2, surface.get_height() + pad * 2))
    lit.fill((0, 0, 0))
    lit.blit(surface, (pad, pad))
    halo = pygame.transform.gaussian_blur(lit, radius)
    for _ in range(strength - 1):
        halo.blit(halo, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return halo


def shadow(size: tuple[int, int], radius: int, blur: int, alpha: int) -> pygame.Surface:
    pad = blur * 3
    shape = pygame.Surface((size[0] + pad * 2, size[1] + pad * 2), pygame.SRCALPHA)
    pygame.draw.rect(shape, (0, 0, 0, alpha), (pad, pad, *size), border_radius=radius)
    return pygame.transform.gaussian_blur(shape, blur)


def text(font: pygame.font.Font, words: str, colour) -> pygame.Surface:
    return font.render(words, True, colour)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 1
    dash_path, out_path = sys.argv[1], sys.argv[2]

    pygame.init()
    pygame.display.set_mode((1, 1))
    canvas = gradient()

    # A dark scrim behind the title keeps it readable on every part of the
    # gradient, and at the size YouTube shows thumbnails in a list.
    scrim = pygame.Surface((WIDTH, 300), pygame.SRCALPHA)
    for y in range(300):
        pygame.draw.line(scrim, (10, 6, 30, round(150 * (1 - y / 300) ** 1.4)), (0, y), (WIDTH, y))
    canvas.blit(scrim, (0, 0))

    # Title in the cluster's own 14-segment font, lit like the dash.
    title_font = pygame.font.Font(str(SEGMENT_FONT), 104)
    title = text(title_font, "DIGIFIZ", NEON)
    title_pos = ((WIDTH - title.get_width()) // 2, 30)
    halo = glow(title, 16, strength=1)
    halo.fill((150, 150, 150), special_flags=pygame.BLEND_RGB_MULT)
    canvas.blit(halo, (title_pos[0] - 48, title_pos[1] - 48), special_flags=pygame.BLEND_RGB_ADD)
    canvas.blit(title, title_pos)

    sub_font = pygame.font.Font(SANS_FONT, 42)
    subtitle = text(sub_font, "The VW Digifiz cluster, rebuilt in Python", (255, 255, 255))
    sub_shadow = text(sub_font, "The VW Digifiz cluster, rebuilt in Python", (0, 0, 0))
    sub_pos = ((WIDTH - subtitle.get_width()) // 2, 168)
    sub_shadow.set_alpha(140)
    canvas.blit(pygame.transform.gaussian_blur(sub_shadow.convert_alpha(), 4), (sub_pos[0] + 2, sub_pos[1] + 4))
    canvas.blit(subtitle, sub_pos)

    # The dash, on a black bezel with rounded corners, a shadow and a faint
    # glow of its own light around it.
    dash = pygame.image.load(dash_path).convert()
    dash_w = 1040
    dash = pygame.transform.smoothscale(dash, (dash_w, round(dash.get_height() * dash_w / dash.get_width())))
    bezel_pad = 14
    bezel = pygame.Surface((dash.get_width() + bezel_pad * 2, dash.get_height() + bezel_pad * 2))
    bezel.fill((0, 0, 0))
    bezel.blit(dash, (bezel_pad, bezel_pad))
    bezel = rounded(bezel, 16)

    bezel_pos = ((WIDTH - bezel.get_width()) // 2, HEIGHT - bezel.get_height() - 26)
    drop = shadow(bezel.get_size(), 16, 18, 190)
    pad = 18 * 3
    canvas.blit(drop, (bezel_pos[0] - pad, bezel_pos[1] - pad + 14))
    light = glow(dash, 22, strength=1)
    light.set_alpha(70)
    canvas.blit(light, (bezel_pos[0] + bezel_pad - 66, bezel_pos[1] + bezel_pad - 66), special_flags=pygame.BLEND_RGB_ADD)
    canvas.blit(bezel, bezel_pos)

    pygame.image.save(canvas, out_path)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
