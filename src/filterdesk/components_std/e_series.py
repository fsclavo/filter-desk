"""Preferred number (E-series) tables per IEC 60063 (E6–E96).

Values are the normalized base values within one decade (1.00 … 9.76). Multiply
by a power of ten to obtain the actual component value.
"""

from __future__ import annotations

import math
from enum import StrEnum


class ESeries(StrEnum):
    E6 = "E6"
    E12 = "E12"
    E24 = "E24"
    E48 = "E48"
    E96 = "E96"


_E_SERIES_BASE: dict[ESeries, tuple[float, ...]] = {
    ESeries.E6: (1.0, 1.5, 2.2, 3.3, 4.7, 6.8),
    ESeries.E12: (1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2),
    ESeries.E24: (
        1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
        3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1,
    ),
    ESeries.E48: (
        1.00, 1.05, 1.10, 1.15, 1.21, 1.27, 1.33, 1.40, 1.47, 1.54,
        1.62, 1.69, 1.78, 1.87, 1.96, 2.05, 2.15, 2.26, 2.37, 2.49,
        2.61, 2.74, 2.87, 3.01, 3.16, 3.32, 3.48, 3.65, 3.83, 4.02,
        4.22, 4.42, 4.64, 4.87, 5.11, 5.36, 5.62, 5.90, 6.19, 6.49,
        6.81, 7.15, 7.50, 7.87, 8.25, 8.66, 9.09, 9.53,
    ),
    ESeries.E96: (
        1.00, 1.02, 1.05, 1.07, 1.10, 1.13, 1.15, 1.18, 1.21, 1.24,
        1.27, 1.30, 1.33, 1.37, 1.40, 1.43, 1.47, 1.50, 1.54, 1.58,
        1.62, 1.65, 1.69, 1.74, 1.78, 1.82, 1.87, 1.91, 1.96, 2.00,
        2.05, 2.10, 2.15, 2.21, 2.26, 2.32, 2.37, 2.43, 2.49, 2.55,
        2.61, 2.67, 2.74, 2.80, 2.87, 2.94, 3.01, 3.09, 3.16, 3.24,
        3.32, 3.40, 3.48, 3.57, 3.65, 3.74, 3.83, 3.92, 4.02, 4.12,
        4.22, 4.32, 4.42, 4.53, 4.64, 4.75, 4.87, 4.99, 5.11, 5.23,
        5.36, 5.49, 5.62, 5.76, 5.90, 6.04, 6.19, 6.34, 6.49, 6.65,
        6.81, 6.98, 7.15, 7.32, 7.50, 7.68, 7.87, 8.06, 8.25, 8.45,
        8.66, 8.87, 9.09, 9.31, 9.53, 9.76,
    ),
}


def base_values(series: ESeries | str) -> tuple[float, ...]:
    """Normalized preferred values within one decade (ascending)."""
    key = ESeries(series)
    return _E_SERIES_BASE[key]


def e_series_values(
    series: ESeries | str, *, decades: int = 7, low_decade: int = 0
) -> tuple[float, ...]:
    """All preferred values over ``decades`` decades, starting at ``10**low_decade``."""
    if decades < 1:
        raise ValueError("decades must be >= 1")
    base = base_values(series)
    values: list[float] = []
    for decade in range(low_decade, low_decade + decades):
        factor = 10.0 ** decade
        values.extend(v * factor for v in base)
    return tuple(values)


def nearest_e_series(value: float, series: ESeries | str) -> float:
    """Nearest E-series value to ``value`` (geometric/log distance).

    Values must be > 0 (component magnitudes). Works across any decade.
    """
    if value <= 0.0:
        raise ValueError("value must be > 0")
    base = base_values(series)
    decade = math.floor(math.log10(value))
    log_value = math.log10(value)
    best = base[0] * 10.0 ** (decade - 1)
    best_err = math.inf
    for d in (decade - 1, decade, decade + 1):
        factor = 10.0 ** d
        for b in base:
            candidate = b * factor
            err = abs(math.log10(candidate) - log_value)
            if err < best_err:
                best_err = err
                best = candidate
    return best
