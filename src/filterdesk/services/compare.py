"""Compare a simulated response against imported/measured data.

Both inputs are :class:`AnalysisResult` objects (2-port S-parameters). The two
frequency grids rarely coincide, so the measured magnitude traces are
interpolated onto the simulated grid restricted to the overlapping band. The
result carries aligned dB traces plus scalar goodness-of-fit metrics.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.types import AnalysisResult


class CompareError(Exception):
    """Raised when two results cannot be aligned for comparison."""


def _sorted_trace(
    frequency_hz: NDArray[np.floating],
    s: NDArray[np.complexfloating],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    f = np.asarray(frequency_hz, dtype=np.float64)
    db = np.asarray(mag_db(s), dtype=np.float64)
    order = np.argsort(f, kind="stable")
    return f[order], db[order]


@dataclass(frozen=True, slots=True)
class CompareResult:
    """Aligned simulated vs measured magnitude response over the overlap band."""

    frequency_hz: NDArray[np.float64]
    s21_db_sim: NDArray[np.float64]
    s21_db_mea: NDArray[np.float64]
    s11_db_sim: NDArray[np.float64]
    s11_db_mea: NDArray[np.float64]

    @property
    def n_points(self) -> int:
        return int(self.frequency_hz.shape[0])

    @property
    def f_min_hz(self) -> float:
        return float(self.frequency_hz[0])

    @property
    def f_max_hz(self) -> float:
        return float(self.frequency_hz[-1])

    def s21_db_error(self) -> NDArray[np.float64]:
        return np.asarray(self.s21_db_sim - self.s21_db_mea, dtype=np.float64)

    def s11_db_error(self) -> NDArray[np.float64]:
        return np.asarray(self.s11_db_sim - self.s11_db_mea, dtype=np.float64)

    @property
    def s21_db_rms_error(self) -> float:
        return float(np.sqrt(np.mean(self.s21_db_error() ** 2)))

    @property
    def s21_db_max_error(self) -> float:
        return float(np.max(np.abs(self.s21_db_error())))

    @property
    def s11_db_rms_error(self) -> float:
        return float(np.sqrt(np.mean(self.s11_db_error() ** 2)))

    @property
    def s11_db_max_error(self) -> float:
        return float(np.max(np.abs(self.s11_db_error())))

    def summary(self) -> str:
        return (
            f"{self.n_points} points, "
            f"{self.f_min_hz:.6g}-{self.f_max_hz:.6g} Hz | "
            f"S21 err RMS={self.s21_db_rms_error:.3f} dB "
            f"max={self.s21_db_max_error:.3f} dB | "
            f"S11 err RMS={self.s11_db_rms_error:.3f} dB "
            f"max={self.s11_db_max_error:.3f} dB"
        )


def compare_results(
    simulated: AnalysisResult,
    measured: AnalysisResult,
) -> CompareResult:
    """Align `measured` onto the `simulated` grid over their overlap band."""
    sim_f = np.asarray(simulated.frequency_hz, dtype=np.float64)
    mea_f = np.asarray(measured.frequency_hz, dtype=np.float64)
    if sim_f.shape[0] < 2:
        raise CompareError("simulated result needs at least 2 points")
    if mea_f.shape[0] < 2:
        raise CompareError("measured result needs at least 2 points")

    f_min = max(float(sim_f.min()), float(mea_f.min()))
    f_max = min(float(sim_f.max()), float(mea_f.max()))
    if not f_max > f_min:
        raise CompareError("simulated and measured frequency ranges do not overlap")

    mask = (sim_f >= f_min) & (sim_f <= f_max)
    grid = sim_f[mask]
    if grid.shape[0] < 2:
        raise CompareError("fewer than 2 simulated points inside the overlap")

    mea_sorted_f, mea_s21_db = _sorted_trace(mea_f, measured.s21)
    _, mea_s11_db = _sorted_trace(mea_f, measured.s11)
    log_grid = np.log10(grid)
    # Extrapolation is disabled by construction (grid is inside the overlap),
    # but clamp the log inputs anyway to keep np.interp well defined.
    mea_s21 = np.interp(log_grid, np.log10(mea_sorted_f), mea_s21_db)
    mea_s11 = np.interp(log_grid, np.log10(mea_sorted_f), mea_s11_db)

    sim_s21_db = np.asarray(mag_db(simulated.s21), dtype=np.float64)[mask]
    sim_s11_db = np.asarray(mag_db(simulated.s11), dtype=np.float64)[mask]

    return CompareResult(
        frequency_hz=np.ascontiguousarray(grid, dtype=np.float64),
        s21_db_sim=np.ascontiguousarray(sim_s21_db),
        s21_db_mea=np.ascontiguousarray(mea_s21),
        s11_db_sim=np.ascontiguousarray(sim_s11_db),
        s11_db_mea=np.ascontiguousarray(mea_s11),
    )


@dataclass(frozen=True, slots=True)
class MeasuredAtFrequency:
    """Interpolated measured values at one cursor frequency."""

    frequency_hz: float
    s21_db: float
    s11_db: float
    vswr: float
    phase_s21_deg: float


def wrap_degrees(value: float) -> float:
    """Wrap an angle to (-180, 180]."""
    wrapped = (float(value) + 180.0) % 360.0 - 180.0
    return 180.0 if wrapped == -180.0 else wrapped


def measured_at_frequency(
    measured: AnalysisResult,
    frequency_hz: float,
) -> MeasuredAtFrequency | None:
    """Interpolate measured complex S11/S21 onto ``frequency_hz``.

    Returns ``None`` when the cursor is outside the measured band. The phase is
    interpolated from the unwrapped measured S21 phase so a 360° wrap does not
    create a bogus linear interpolation.
    """
    f = np.asarray(measured.frequency_hz, dtype=float)
    if f.size < 2 or not np.isfinite(frequency_hz):
        return None
    order = np.argsort(f, kind="stable")
    f_sorted = f[order]
    target = float(frequency_hz)
    if target < f_sorted[0] or target > f_sorted[-1]:
        return None
    s11 = np.asarray(measured.s11, dtype=np.complex128)[order]
    s21 = np.asarray(measured.s21, dtype=np.complex128)[order]
    log_f = np.log10(np.maximum(f_sorted, 1e-30))
    log_target = float(np.log10(max(target, 1e-30)))
    s11_i = complex(
        np.interp(log_target, log_f, s11.real),
        np.interp(log_target, log_f, s11.imag),
    )
    s21_i = complex(
        np.interp(log_target, log_f, s21.real),
        np.interp(log_target, log_f, s21.imag),
    )
    phase_unwrapped = np.degrees(np.unwrap(np.angle(s21)))
    phase_i = float(np.interp(log_target, log_f, phase_unwrapped))
    gamma = min(abs(s11_i), 0.999999999)
    vswr_i = (1.0 + gamma) / (1.0 - gamma)
    return MeasuredAtFrequency(
        frequency_hz=target,
        s21_db=float(20.0 * np.log10(max(abs(s21_i), 1e-15))),
        s11_db=float(20.0 * np.log10(max(abs(s11_i), 1e-15))),
        vswr=float(vswr_i),
        phase_s21_deg=phase_i,
    )


__all__ = [
    "CompareError",
    "CompareResult",
    "MeasuredAtFrequency",
    "compare_results",
    "measured_at_frequency",
    "wrap_degrees",
]
