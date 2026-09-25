"""Engineering units to artwork frame indices."""

from __future__ import annotations

from .signals import Signal


def clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


def frame_for(signal: Signal, value: float) -> int:
    """Map ``value`` onto a frame index for ``signal``'s PNG sequence.

    Values outside the signal's declared range clamp to the end frames rather
        than raising, because a sensor glitch must not take the cluster down.
    """
    if signal.frames is None:
        raise ValueError(f"signal {signal.key!r} has no frame sequence")
    span = signal.hi - signal.lo
    if span <= 0:
        return 0
    fraction = (clamp(value, signal.lo, signal.hi) - signal.lo) / span
    return int(round(fraction * (signal.frames - 1)))


def fraction_for(signal: Signal, value: float) -> float:
    """``value`` as 0.0-1.0 across the signal's range, clamped."""
    span = signal.hi - signal.lo
    if span <= 0:
        return 0.0
    return (clamp(value, signal.lo, signal.hi) - signal.lo) / span
