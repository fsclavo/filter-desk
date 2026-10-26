"""Fit circuit component values to a measured VNA response.

The fit minimizes the weighted magnitude error of S21 and/or S11 over the
overlap band. Complex phase is not used because a measured cable delay and
reference plane are usually not calibrated out. All tunable component values
are bounded to ``±bound_pct`` around the starting design so the result remains
a local trim, not an arbitrary re-synthesis.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares

from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.service import analyze_at_frequencies
from filterdesk.analysis.types import AnalysisResult
from filterdesk.domain.circuit import Circuit
from filterdesk.optimization.constraints import relative_bounds
from filterdesk.tuning import TunableParam, apply_values, tunable_params


class VnaTuningError(ValueError):
    """Raised when a VNA fit cannot start."""


class VnaTuningCancelled(RuntimeError):
    """Raised when a VNA fit is cancelled cooperatively."""


@dataclass(frozen=True, slots=True)
class VnaTuningConfig:
    bound_pct: float = 0.2
    max_points: int = 401
    max_nfev: int = 200
    backend: str = "abcd"
    fit_s11: bool = True
    fit_s21: bool = True
    s11_weight: float = 1.0
    s21_weight: float = 1.0
    floor_db: float = -80.0
    f_min_hz: float | None = None
    f_max_hz: float | None = None

    def __post_init__(self) -> None:
        if self.bound_pct <= 0.0:
            raise VnaTuningError("bound_pct must be > 0")
        if self.max_points < 2:
            raise VnaTuningError("max_points must be >= 2")
        if self.max_nfev < 1:
            raise VnaTuningError("max_nfev must be >= 1")
        if not self.fit_s11 and not self.fit_s21:
            raise VnaTuningError("enable S11 and/or S21 fitting")
        if self.s11_weight <= 0.0 or self.s21_weight <= 0.0:
            raise VnaTuningError("weights must be > 0")
        if self.floor_db > 0.0:
            raise VnaTuningError("floor_db must be <= 0")
        if (
            self.f_min_hz is not None
            and self.f_max_hz is not None
            and self.f_min_hz >= self.f_max_hz
        ):
            raise VnaTuningError("f_min_hz must be < f_max_hz")


@dataclass(slots=True)
class VnaTuningResult:
    success: bool
    message: str
    initial_rms_db: float
    final_rms_db: float
    initial_rms_s11_db: float
    final_rms_s11_db: float
    initial_rms_s21_db: float
    final_rms_s21_db: float
    n_evaluations: int
    refs: list[str]
    initial_values: NDArray[np.float64]
    final_values: NDArray[np.float64]
    circuit: Circuit
    frequency_hz: NDArray[np.float64]
    measured_s11_db: NDArray[np.float64]
    measured_s21_db: NDArray[np.float64]
    simulated_s11_db: NDArray[np.float64]
    simulated_s21_db: NDArray[np.float64]

    @property
    def improvement_db(self) -> float:
        return self.initial_rms_db - self.final_rms_db


def _rms(values: NDArray[np.float64]) -> float:
    return float(np.sqrt(np.mean(np.asarray(values, dtype=float) ** 2)))


def _select_points(
    measured: AnalysisResult, cfg: VnaTuningConfig
) -> NDArray[np.int_]:
    freq = np.asarray(measured.frequency_hz, dtype=float)
    if freq.ndim != 1 or freq.size < 2:
        raise VnaTuningError("measured data must have at least two frequency points")
    if not np.all(np.isfinite(freq)) or np.any(freq <= 0.0):
        raise VnaTuningError("measured frequencies must be finite and > 0")
    order = np.argsort(freq)
    freq = freq[order]
    keep = np.ones(freq.size, dtype=bool)
    if cfg.f_min_hz is not None:
        keep &= freq >= cfg.f_min_hz
    if cfg.f_max_hz is not None:
        keep &= freq <= cfg.f_max_hz
    idx = np.flatnonzero(keep)
    if idx.size < 2:
        raise VnaTuningError("fewer than two measured points in the fit band")
    if idx.size > cfg.max_points:
        picks = np.linspace(0, idx.size - 1, cfg.max_points).round().astype(int)
        idx = idx[np.unique(picks)]
    return order[idx]


def _selected_params(
    circuit: Circuit, refs: Sequence[str] | None
) -> list[TunableParam]:
    params = tunable_params(circuit)
    if refs is not None:
        wanted = set(refs)
        unknown = wanted.difference(p.ref for p in params)
        if unknown:
            raise VnaTuningError(f"unknown tunable refs: {sorted(unknown)}")
        params = [p for p in params if p.ref in wanted]
    if not params:
        raise VnaTuningError("circuit has no selected tunable components")
    return params


def fit_circuit_to_measurement(
    circuit: Circuit,
    measured: AnalysisResult,
    config: VnaTuningConfig | None = None,
    *,
    refs: Sequence[str] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> VnaTuningResult:
    """Least-squares trim of L/C/R values to a measured magnitude response."""
    cfg = config or VnaTuningConfig()
    params = _selected_params(circuit, refs)
    idx = _select_points(measured, cfg)
    freq = np.asarray(measured.frequency_hz, dtype=float)[idx]
    meas_s11 = np.maximum(mag_db(np.asarray(measured.s11)[idx]), cfg.floor_db)
    meas_s21 = np.maximum(mag_db(np.asarray(measured.s21)[idx]), cfg.floor_db)

    x0 = np.asarray([p.value for p in params], dtype=float)
    bounds = relative_bounds(x0, cfg.bound_pct)
    if np.any(bounds.upper <= bounds.lower):
        raise VnaTuningError("component bounds collapsed to zero width")

    evaluations = 0

    def residuals(x: NDArray[np.float64]) -> NDArray[np.float64]:
        nonlocal evaluations
        if cancel is not None and cancel():
            raise VnaTuningCancelled("VNA fit cancelled")
        evaluations += 1
        trial = apply_values(circuit, params, x)
        sim = analyze_at_frequencies(trial, freq, backend=cfg.backend)
        parts: list[NDArray[np.float64]] = []
        if cfg.fit_s21:
            sim_s21 = np.maximum(mag_db(sim.s21), cfg.floor_db)
            parts.append(cfg.s21_weight * (sim_s21 - meas_s21))
        if cfg.fit_s11:
            sim_s11 = np.maximum(mag_db(sim.s11), cfg.floor_db)
            parts.append(cfg.s11_weight * (sim_s11 - meas_s11))
        return np.concatenate(parts)

    def sub_rms(sim: AnalysisResult, which: str) -> tuple[float, float]:
        if which == "s11":
            sim_db = np.maximum(mag_db(sim.s11), cfg.floor_db)
            return _rms(sim_db - meas_s11), float(np.max(np.abs(sim_db - meas_s11)))
        sim_db = np.maximum(mag_db(sim.s21), cfg.floor_db)
        return _rms(sim_db - meas_s21), float(np.max(np.abs(sim_db - meas_s21)))

    initial_sim = analyze_at_frequencies(circuit, freq, backend=cfg.backend)
    initial_res = residuals(x0)
    initial_rms = _rms(initial_res)
    initial_s11_rms, _ = sub_rms(initial_sim, "s11")
    initial_s21_rms, _ = sub_rms(initial_sim, "s21")

    solution = least_squares(
        residuals,
        x0,
        bounds=(bounds.lower, bounds.upper),
        max_nfev=cfg.max_nfev,
    )
    final_x = np.asarray(solution.x, dtype=float)
    final_circuit = apply_values(circuit, params, final_x)
    final_res = residuals(final_x)
    final_rms = _rms(final_res)
    if final_rms > initial_rms:
        final_x = x0.copy()
        final_circuit = circuit
        final_res = initial_res
        final_rms = initial_rms

    final_sim = analyze_at_frequencies(final_circuit, freq, backend=cfg.backend)
    final_s11_rms, _ = sub_rms(final_sim, "s11")
    final_s21_rms, _ = sub_rms(final_sim, "s21")
    return VnaTuningResult(
        success=bool(solution.success) or final_rms <= initial_rms,
        message=str(solution.message),
        initial_rms_db=initial_rms,
        final_rms_db=final_rms,
        initial_rms_s11_db=initial_s11_rms,
        final_rms_s11_db=final_s11_rms,
        initial_rms_s21_db=initial_s21_rms,
        final_rms_s21_db=final_s21_rms,
        n_evaluations=evaluations,
        refs=[p.ref for p in params],
        initial_values=x0,
        final_values=final_x,
        circuit=final_circuit,
        frequency_hz=freq,
        measured_s11_db=meas_s11,
        measured_s21_db=meas_s21,
        simulated_s11_db=np.maximum(mag_db(final_sim.s11), cfg.floor_db),
        simulated_s21_db=np.maximum(mag_db(final_sim.s21), cfg.floor_db),
    )


__all__ = [
    "VnaTuningCancelled",
    "VnaTuningConfig",
    "VnaTuningError",
    "VnaTuningResult",
    "fit_circuit_to_measurement",
]
