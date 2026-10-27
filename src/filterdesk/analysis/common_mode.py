"""Common-mode choke estimates (separate from the differential 2-port)."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from filterdesk.domain.circuit import BalunSpec


class CommonModeError(ValueError):
    """Raised when a common-mode estimate is not applicable."""


@dataclass(frozen=True, slots=True)
class CommonModePoint:
    frequency_hz: float
    impedance_ohm: complex
    attenuation_db: float


@dataclass(frozen=True, slots=True)
class CommonModeReport:
    z0_ohm: float
    points: tuple[CommonModePoint, ...]
    model: str = "series choke, ideal inductance"


def common_mode_sweep(
    balun: BalunSpec,
    frequencies_hz: list[float] | np.ndarray,
    *,
    z0_ohm: float | None = None,
) -> CommonModeReport:
    """Estimate ``Zcm(f)`` and series-choke common-mode attenuation.

    This is deliberately separate from the differential filter 2-port.  It uses
    ``2*pi*f*Lm`` when the magnetizing inductance is available, otherwise the
    scalar ``common_mode_impedance_ohm`` as a constant fallback.
    """
    if balun.kind != "choke":
        raise CommonModeError("common-mode sweep is defined for choke baluns")
    z0 = float(balun.z_unbalanced_ohm if z0_ohm is None else z0_ohm)
    if z0 <= 0.0:
        raise CommonModeError("common-mode reference impedance must be > 0")
    freqs = np.asarray(frequencies_hz, dtype=float)
    if freqs.ndim != 1 or freqs.size == 0 or np.any(freqs <= 0.0):
        raise CommonModeError("frequencies must be a non-empty positive 1-D array")
    if balun.magnetizing_inductance_h <= 0.0 and balun.common_mode_impedance_ohm <= 0.0:
        raise CommonModeError("no common-mode impedance/inductance available")

    points: list[CommonModePoint] = []
    for freq in freqs:
        if balun.magnetizing_inductance_h > 0.0:
            zcm = 1j * 2.0 * math.pi * float(freq) * balun.magnetizing_inductance_h
        else:
            zcm = complex(balun.common_mode_impedance_ohm)
        s21 = 2.0 * z0 / (2.0 * z0 + zcm)
        attenuation = -20.0 * math.log10(max(abs(s21), 1e-15))
        points.append(CommonModePoint(float(freq), zcm, attenuation))
    return CommonModeReport(z0_ohm=z0, points=tuple(points))


__all__ = [
    "CommonModeError",
    "CommonModePoint",
    "CommonModeReport",
    "common_mode_sweep",
]
