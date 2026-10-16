"""Transmit harmonic readout (Phase 12).

For a transmit filter, reports ``|S21|`` at the harmonics ``2·f0 …`` and the
suppression relative to the fundamental, i.e. how much the filter attenuates each
harmonic versus the wanted signal.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.types import AnalysisResult


class HarmonicError(ValueError):
    """Raised when harmonics cannot be computed."""


@dataclass(frozen=True, slots=True)
class Harmonic:
    order: int
    frequency_hz: float
    s21_db: float
    suppression_db: float


@dataclass(frozen=True, slots=True)
class HarmonicReport:
    fundamental_hz: float
    fundamental_s21_db: float
    harmonics: tuple[Harmonic, ...]

    @property
    def min_suppression_db(self) -> float:
        return min((h.suppression_db for h in self.harmonics), default=0.0)

    @property
    def worst_order(self) -> int | None:
        if not self.harmonics:
            return None
        return min(self.harmonics, key=lambda h: h.suppression_db).order


def compute_harmonics(
    result: AnalysisResult,
    fundamental_hz: float,
    *,
    max_order: int = 5,
) -> HarmonicReport:
    """Report |S21| and suppression at harmonics of ``fundamental_hz``."""
    if fundamental_hz <= 0.0:
        raise HarmonicError("fundamental_hz must be > 0")
    if max_order < 2:
        raise HarmonicError("max_order must be >= 2")
    f = np.asarray(result.frequency_hz, dtype=float)
    if f.size == 0:
        raise HarmonicError("empty analysis")
    s21_db = np.asarray(mag_db(result.s21), dtype=float)
    f_max = float(np.max(f))

    idx_f0 = int(np.argmin(np.abs(f - fundamental_hz)))
    f0_db = float(s21_db[idx_f0])

    harmonics: list[Harmonic] = []
    for order in range(2, max_order + 1):
        target = fundamental_hz * order
        if target > f_max:
            break
        idx = int(np.argmin(np.abs(f - target)))
        db = float(s21_db[idx])
        harmonics.append(
            Harmonic(
                order=order,
                frequency_hz=float(f[idx]),
                s21_db=db,
                suppression_db=f0_db - db,
            )
        )
    return HarmonicReport(
        fundamental_hz=fundamental_hz,
        fundamental_s21_db=f0_db,
        harmonics=tuple(harmonics),
    )


__all__ = ["Harmonic", "HarmonicError", "HarmonicReport", "compute_harmonics"]
