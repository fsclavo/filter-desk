"""Frequency sweep and analysis result models (backend-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray


class SweepSpacing(StrEnum):
    LINEAR = "linear"
    LOGARITHMIC = "logarithmic"


@dataclass(frozen=True, slots=True)
class SweepConfig:
    f_start_hz: float
    f_stop_hz: float
    n_points: int = 2048
    spacing: SweepSpacing = SweepSpacing.LINEAR

    def __post_init__(self) -> None:
        if self.f_start_hz <= 0.0 or self.f_stop_hz <= 0.0:
            raise ValueError("sweep frequencies must be > 0")
        if self.f_stop_hz <= self.f_start_hz:
            raise ValueError("f_stop_hz must be > f_start_hz")
        if self.n_points < 2:
            raise ValueError("n_points must be >= 2")

    def frequencies_hz(self) -> NDArray[np.floating]:
        if self.spacing == SweepSpacing.LINEAR:
            return np.linspace(self.f_start_hz, self.f_stop_hz, self.n_points)
        return np.geomspace(self.f_start_hz, self.f_stop_hz, self.n_points)


@dataclass(slots=True)
class AnalysisResult:
    """Two-port frequency-domain result independent of scikit-rf."""

    frequency_hz: NDArray[np.floating]
    s11: NDArray[np.complexfloating]
    s21: NDArray[np.complexfloating]
    s12: NDArray[np.complexfloating]
    s22: NDArray[np.complexfloating]
    zin_ohm: NDArray[np.complexfloating]
    zout_ohm: NDArray[np.complexfloating]
    z0_source_ohm: float
    z0_load_ohm: float
    backend: str = ""

    def __post_init__(self) -> None:
        n = self.frequency_hz.shape[0]
        for name in ("s11", "s21", "s12", "s22", "zin_ohm", "zout_ohm"):
            arr = getattr(self, name)
            if arr.shape[0] != n:
                raise ValueError(f"{name} length mismatch: {arr.shape[0]} vs {n}")
