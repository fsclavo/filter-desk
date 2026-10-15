"""Statistical helpers for Monte-Carlo tolerance results (FR-P3)."""

from __future__ import annotations

import math


def wilson_interval(
    passes: int, trials: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (default 95%)."""
    if trials <= 0:
        raise ValueError("trials must be > 0")
    p = passes / trials
    denom = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denom
    margin = (
        z * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)) / denom
    )
    lo = max(0.0, center - margin)
    hi = min(1.0, center + margin)
    return lo, hi


def yield_fraction(passes: int, trials: int) -> float:
    if trials <= 0:
        raise ValueError("trials must be > 0")
    return passes / trials
