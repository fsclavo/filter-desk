"""Butterworth low-pass prototype g-values."""

from __future__ import annotations

import math

from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.prototype import Prototype


def butterworth_g_values(order: int) -> tuple[float, ...]:
    """Return g0..g(n+1) for Butterworth LP prototype (ωc=1 at −3 dB)."""
    if order < 1:
        raise ValueError("order must be >= 1")
    g = [1.0]
    for k in range(1, order + 1):
        g.append(2.0 * math.sin((2 * k - 1) * math.pi / (2 * order)))
    g.append(1.0)
    return tuple(g)


def synthesize_butterworth_prototype(order: int) -> Prototype:
    return Prototype(
        family=ApproximationFamily.BUTTERWORTH,
        order=order,
        g_values=butterworth_g_values(order),
    )
