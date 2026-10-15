"""Variable bounds for the optimizer (FR-P4)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class Bounds:
    lower: NDArray[np.float64]
    upper: NDArray[np.float64]


def relative_bounds(
    values: NDArray[np.floating] | list[float], bound_pct: float
) -> Bounds:
    """Symmetric ``±bound_pct`` relative box around the nominal values."""
    if bound_pct < 0.0:
        raise ValueError("bound_pct must be >= 0")
    x0 = np.asarray(values, dtype=float)
    lower = np.maximum(x0 * (1.0 - bound_pct), np.finfo(float).tiny)
    upper = x0 * (1.0 + bound_pct)
    return Bounds(lower=lower, upper=upper)
