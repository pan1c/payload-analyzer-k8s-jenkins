"""Numeric statistics helpers."""
from __future__ import annotations

from statistics import mean, median, stdev
from typing import Sequence

__all__: list[str] = [
    "numeric_summary",
]


def numeric_summary(values: Sequence[float] | Sequence[int]) -> dict[str, float]:
    """
    Compute min, max, mean, median, stddev for a sequence of numbers.
    Raises ValueError if input is empty.
    """
    if not values:
        raise ValueError("'numbers' array must not be empty")
    vals = [float(v) for v in values]
    avg = mean(vals)
    return {
        "min": min(vals),
        "max": max(vals),
        "mean": avg,
        "median": median(vals),
        "stddev": stdev(vals) if len(vals) > 1 else 0.0,
    }