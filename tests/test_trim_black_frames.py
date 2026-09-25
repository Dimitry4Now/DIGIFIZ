import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import trim_black_frames  # noqa: E402


def write_frames(directory: Path, pattern: str) -> None:
    """``pattern`` is one character per frame: ``.`` black, ``#`` lit."""
    pygame.init()
    directory.mkdir(parents=True, exist_ok=True)
    for index, character in enumerate(pattern):
        surface = pygame.Surface((16, 16))
        surface.fill((0, 0, 0) if character == "." else (200, 200, 200))
        pygame.image.save(surface, str(directory / f"frame_{index:04d}.png"))


def frame_count(directory: Path) -> int:
    return len(list(directory.glob("frame_*.png")))


def test_trims_both_ends_keeping_padding(tmp_path):
    write_frames(tmp_path, "....####....")
    assert trim_black_frames.main([str(tmp_path), "--padding", "1"]) == 0
    # Four lit frames plus one black frame of padding at each end.
    assert frame_count(tmp_path) == 6


def test_frames_are_renumbered_from_zero(tmp_path):
    write_frames(tmp_path, "...###...")
    trim_black_frames.main([str(tmp_path), "--padding", "0"])
    names = sorted(path.name for path in tmp_path.glob("frame_*.png"))
    assert names == ["frame_0000.png", "frame_0001.png", "frame_0002.png"]


def test_nothing_to_trim_leaves_the_sequence_alone(tmp_path):
    write_frames(tmp_path, "####")
    assert trim_black_frames.main([str(tmp_path), "--padding", "0"]) == 0
    assert frame_count(tmp_path) == 4


def test_all_black_is_an_error_not_a_wipe(tmp_path):
    write_frames(tmp_path, "....")
    assert trim_black_frames.main([str(tmp_path)]) == 1
    assert frame_count(tmp_path) == 4


def test_missing_directory_is_an_error(tmp_path):
    assert trim_black_frames.main([str(tmp_path / "absent")]) == 1
