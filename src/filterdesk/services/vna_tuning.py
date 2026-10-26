"""Fit circuit component values to a measured VNA response.

The default fit minimizes the weighted magnitude error of S21 and/or S11 over
the overlap band. Phase fitting is opt-in: it adds a shared reference-plane
delay plus one phase offset per measured S-parameter, because an uncalibrated
cable delay otherwise dominates the phase error. All component values are
bounded around the starting design (local, wide or multi-start global) so the
result remains a trim, not an arbitrary re-synthesis.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares

from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.service import analyze_at_frequencies
from filterdesk.analysis.types import AnalysisResult
from filterdesk.domain.circuit import Circuit
from filterdesk.optimization.constraints import Bounds, relative_bounds
from filterdesk.tuning import TunableParam, apply_values, tunable_params


class VnaTuningError(ValueError):
    """Raised when a VNA fit cannot start."""


class VnaTuningCancelled(RuntimeError):
    """Raised when a VNA fit is cancelled cooperatively."""


class VnaBoundMode(StrEnum):
    """Component search box around the nominal design."""

    LOCAL = "local"
    WIDE = "wide"
    GLOBAL = "global"


_WIDE_BOUNDS = (0.5, 2.0)
_GLOBAL_BOUNDS = (0.2, 5.0)


@dataclass(frozen=True, slots=True)
class VnaTuningConfig:
    bound_pct: float = 0.2
    bound_mode: VnaBoundMode | str = VnaBoundMode.LOCAL
    max_points: int = 401
    max_nfev: int = 200
    global_starts: int = 6
    backend: str = "abcd"
    fit_s11: bool = True
    fit_s21: bool = True
    s11_weight: float = 1.0
    s21_weight: float = 1.0
    floor_db: float = -80.0
    fit_phase: bool = False
    phase_weight: float = 1.0
    phase_min_db: float = -40.0
    max_delay_ns: float = 1000.0
    f_min_hz: float | None = None
    f_max_hz: float | None = None

    def __post_init__(self) -> None:
        if self.bound_pct <= 0.0:
            raise VnaTuningError("bound_pct must be > 0")
        try:
            VnaBoundMode(str(self.bound_mode))
        except ValueError as exc:
            raise VnaTuningError(f"unknown bound_mode {self.bound_mode!r}") from exc
        if self.max_points < 2:
            raise VnaTuningError("max_points must be >= 2")
        if self.max_nfev < 1:
            raise VnaTuningError("max_nfev must be >= 1")
        if self.global_starts < 1:
            raise VnaTuningError("global_starts must be >= 1")
        if not self.fit_s11 and not self.fit_s21:
            raise VnaTuningError("enable S11 and/or S21 fitting")
        if self.s11_weight <= 0.0 or self.s21_weight <= 0.0:
            raise VnaTuningError("weights must be > 0")
        if self.floor_db > 0.0:
            raise VnaTuningError("floor_db must be <= 0")
        if self.fit_phase and self.phase_weight <= 0.0:
            raise VnaTuningError("phase_weight must be > 0")
        if self.fit_phase and self.phase_min_db > 0.0:
            raise VnaTuningError("phase_min_db must be <= 0")
        if self.fit_phase and self.max_delay_ns <= 0.0:
            raise VnaTuningError("max_delay_ns must be > 0")
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
    bound_mode: VnaBoundMode = VnaBoundMode.LOCAL
    delay_s: float | None = None
    phase_s11_deg: float | None = None
    phase_s21_deg: float | None = None
    n_starts: int = 1
    holdout_rms_db: float | None = None
    holdout_rms_s11_db: float | None = None
    holdout_rms_s21_db: float | None = None
    holdout_points: int = 0
    quality_notes: tuple[str, ...] = ()

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


def _component_bounds(
    x0: NDArray[np.float64], cfg: VnaTuningConfig
) -> Bounds:
    mode = VnaBoundMode(str(cfg.bound_mode))
    if mode is VnaBoundMode.LOCAL:
        return relative_bounds(x0, cfg.bound_pct)
    low, high = _WIDE_BOUNDS if mode is VnaBoundMode.WIDE else _GLOBAL_BOUNDS
    return Bounds(lower=x0 * low, upper=x0 * high)


def _estimate_phase_model(
    freq: NDArray[np.float64],
    measured: NDArray[np.complexfloating],
    simulated: NDArray[np.complexfloating],
    cfg: VnaTuningConfig,
) -> tuple[float, float]:
    """Return an initial ``(delay_ns, phase_deg)`` from measured/simulated phase."""
    valid = (
        (np.abs(measured) > 0.0)
        & (np.abs(simulated) > 0.0)
        & (mag_db(measured) >= cfg.phase_min_db)
    )
    if np.count_nonzero(valid) < 3:
        return 0.0, 0.0
    ratio = measured[valid] / simulated[valid]
    phase = np.unwrap(np.angle(ratio))
    f = freq[valid]
    slope, intercept = np.polyfit(f - f.mean(), phase, 1)
    delay_ns = float(
        np.clip(
            -slope / (2.0 * math.pi) * 1e9,
            -cfg.max_delay_ns,
            cfg.max_delay_ns,
        )
    )
    phase_deg = float(np.degrees(np.angle(np.exp(1j * intercept))))
    return delay_ns, phase_deg


def _nuisance_initial(
    freq: NDArray[np.float64],
    measured_s11: NDArray[np.complexfloating],
    measured_s21: NDArray[np.complexfloating],
    simulated: AnalysisResult,
    cfg: VnaTuningConfig,
) -> tuple[float, float, float]:
    """Initial delay (ns), S21 phase (deg), S11 phase (deg)."""
    if not cfg.fit_phase:
        return 0.0, 0.0, 0.0
    primary = measured_s21 if cfg.fit_s21 else measured_s11
    primary_sim = simulated.s21 if cfg.fit_s21 else simulated.s11
    delay_ns, _ = _estimate_phase_model(freq, primary, primary_sim, cfg)
    delay_rad = 2.0 * math.pi * freq * delay_ns * 1e-9

    def offset(
        measured: NDArray[np.complexfloating], sim: NDArray[np.complexfloating]
    ) -> float:
        ratio = measured * np.conj(sim) * np.exp(1j * delay_rad)
        return float(np.degrees(np.angle(np.nanmedian(ratio))) if ratio.size else 0.0)

    phase_s21 = offset(measured_s21, simulated.s21) if cfg.fit_s21 else 0.0
    phase_s11 = offset(measured_s11, simulated.s11) if cfg.fit_s11 else 0.0
    return delay_ns, phase_s21, phase_s11


def _make_starts(
    component_x0: NDArray[np.float64],
    components_bounds: Bounds,
    nuisance_x0: NDArray[np.float64],
    nuisance_bounds: Bounds,
    cfg: VnaTuningConfig,
    mode: VnaBoundMode,
) -> list[NDArray[np.float64]]:
    starts = [np.concatenate([component_x0, nuisance_x0])]
    if mode is not VnaBoundMode.GLOBAL or cfg.global_starts <= 1:
        return starts
    rng = np.random.default_rng(0)
    lo = np.log(components_bounds.lower)
    hi = np.log(components_bounds.upper)
    for _ in range(cfg.global_starts - 1):
        comps = np.exp(rng.uniform(lo, hi))
        starts.append(np.concatenate([comps, nuisance_x0]))
    return starts


def fit_circuit_to_measurement(
    circuit: Circuit,
    measured: AnalysisResult,
    config: VnaTuningConfig | None = None,
    *,
    refs: Sequence[str] | None = None,
    holdout: AnalysisResult | None = None,
    cancel: Callable[[], bool] | None = None,
) -> VnaTuningResult:
    """Trim L/C/R values to a measured response (magnitude, optional phase).

    ``holdout`` is evaluated only after fitting; it is never used to choose
    component values.
    """
    cfg = config or VnaTuningConfig()
    mode = VnaBoundMode(str(cfg.bound_mode))
    params = _selected_params(circuit, refs)
    idx = _select_points(measured, cfg)
    freq = np.asarray(measured.frequency_hz, dtype=float)[idx]
    meas_s11_c = np.asarray(measured.s11, dtype=np.complex128)[idx]
    meas_s21_c = np.asarray(measured.s21, dtype=np.complex128)[idx]
    meas_s11 = np.maximum(mag_db(meas_s11_c), cfg.floor_db)
    meas_s21 = np.maximum(mag_db(meas_s21_c), cfg.floor_db)

    component_x0 = np.asarray([p.value for p in params], dtype=float)
    components_bounds = _component_bounds(component_x0, cfg)
    if np.any(components_bounds.upper <= components_bounds.lower):
        raise VnaTuningError("component bounds collapsed to zero width")

    initial_sim = analyze_at_frequencies(circuit, freq, backend=cfg.backend)
    delay_ns, phase_s21_deg, phase_s11_deg = _nuisance_initial(
        freq, meas_s11_c, meas_s21_c, initial_sim, cfg
    )
    n_components = len(params)
    if cfg.fit_phase:
        nuisance_x0 = np.asarray(
            [delay_ns, phase_s21_deg, phase_s11_deg], dtype=float
        )
        nuisance_bounds = Bounds(
            lower=np.asarray([-cfg.max_delay_ns, -180.0, -180.0]),
            upper=np.asarray([cfg.max_delay_ns, 180.0, 180.0]),
        )
    else:
        nuisance_x0 = np.empty(0, dtype=float)
        nuisance_bounds = Bounds(
            lower=np.empty(0, dtype=float), upper=np.empty(0, dtype=float)
        )
    starts = _make_starts(
        component_x0, components_bounds, nuisance_x0, nuisance_bounds, cfg, mode
    )
    evaluations = 0

    def residuals(x: NDArray[np.float64]) -> NDArray[np.float64]:
        nonlocal evaluations
        if cancel is not None and cancel():
            raise VnaTuningCancelled("VNA fit cancelled")
        evaluations += 1
        components = x[:n_components]
        delay = x[n_components] if cfg.fit_phase else 0.0
        phi21 = x[n_components + 1] if cfg.fit_phase and cfg.fit_s21 else 0.0
        phi11 = x[n_components + 2] if cfg.fit_phase and cfg.fit_s11 else 0.0
        trial = apply_values(circuit, params, components)
        sim = analyze_at_frequencies(trial, freq, backend=cfg.backend)
        parts: list[NDArray[np.float64]] = []
        if cfg.fit_s21:
            sim_s21 = np.maximum(mag_db(sim.s21), cfg.floor_db)
            parts.append(cfg.s21_weight * (sim_s21 - meas_s21))
        if cfg.fit_s11:
            sim_s11 = np.maximum(mag_db(sim.s11), cfg.floor_db)
            parts.append(cfg.s11_weight * (sim_s11 - meas_s11))
        if cfg.fit_phase:
            delay_rad = 2.0 * math.pi * freq * delay * 1e-9
            if cfg.fit_s21:
                aligned = sim.s21 * np.exp(1j * (math.radians(phi21) - delay_rad))
                mask = meas_s21 >= cfg.phase_min_db
                if np.any(mask):
                    diff = np.angle(meas_s21_c[mask] * np.conj(aligned[mask]))
                    parts.append(cfg.phase_weight * diff)
            if cfg.fit_s11:
                aligned = sim.s11 * np.exp(1j * (math.radians(phi11) - delay_rad))
                mask = meas_s11 >= cfg.phase_min_db
                if np.any(mask):
                    diff = np.angle(meas_s11_c[mask] * np.conj(aligned[mask]))
                    parts.append(cfg.phase_weight * diff)
        return np.concatenate(parts)

    def sub_rms(sim: AnalysisResult, which: str) -> tuple[float, float]:
        if which == "s11":
            sim_db = np.maximum(mag_db(sim.s11), cfg.floor_db)
            return _rms(sim_db - meas_s11), float(np.max(np.abs(sim_db - meas_s11)))
        sim_db = np.maximum(mag_db(sim.s21), cfg.floor_db)
        return _rms(sim_db - meas_s21), float(np.max(np.abs(sim_db - meas_s21)))

    initial_res = residuals(np.concatenate([component_x0, nuisance_x0]))
    initial_rms = _rms(initial_res)
    initial_s11_rms, _ = sub_rms(initial_sim, "s11")
    initial_s21_rms, _ = sub_rms(initial_sim, "s21")

    all_bounds = Bounds(
        lower=np.concatenate([components_bounds.lower, nuisance_bounds.lower]),
        upper=np.concatenate([components_bounds.upper, nuisance_bounds.upper]),
    )
    best_x: NDArray[np.float64] | None = None
    best_cost = math.inf
    best_solution = None
    for start in starts:
        solution = least_squares(
            residuals,
            start,
            bounds=(all_bounds.lower, all_bounds.upper),
            max_nfev=cfg.max_nfev,
            x_scale=1.0,
        )
        cost = _rms(residuals(solution.x))
        if cost < best_cost:
            best_cost = cost
            best_x = np.asarray(solution.x, dtype=float)
            best_solution = solution

    assert best_x is not None and best_solution is not None
    final_x = best_x[:n_components]
    final_circuit = apply_values(circuit, params, final_x)
    final_res = residuals(best_x)
    final_rms = _rms(final_res)
    if final_rms > initial_rms:
        final_x = component_x0.copy()
        final_circuit = circuit
        final_res = initial_res
        final_rms = initial_rms
        best_cost = initial_rms
        best_x = np.concatenate([component_x0, nuisance_x0])

    final_sim = analyze_at_frequencies(final_circuit, freq, backend=cfg.backend)
    final_s11_rms, _ = sub_rms(final_sim, "s11")
    final_s21_rms, _ = sub_rms(final_sim, "s21")
    delay_s = float(best_x[n_components] * 1e-9) if cfg.fit_phase else None
    phase_s21 = (
        float(best_x[n_components + 1]) if cfg.fit_phase and cfg.fit_s21 else None
    )
    phase_s11 = (
        float(best_x[n_components + 2]) if cfg.fit_phase and cfg.fit_s11 else None
    )
    holdout_rms = holdout_s11 = holdout_s21 = None
    holdout_points = 0
    if holdout is not None:
        h_idx = _select_points(holdout, cfg)
        h_freq = np.asarray(holdout.frequency_hz, dtype=float)[h_idx]
        h_s11 = np.maximum(
            mag_db(np.asarray(holdout.s11, dtype=np.complex128)[h_idx]),
            cfg.floor_db,
        )
        h_s21 = np.maximum(
            mag_db(np.asarray(holdout.s21, dtype=np.complex128)[h_idx]),
            cfg.floor_db,
        )
        h_sim = analyze_at_frequencies(final_circuit, h_freq, backend=cfg.backend)
        h_s11_sim = np.maximum(mag_db(h_sim.s11), cfg.floor_db)
        h_s21_sim = np.maximum(mag_db(h_sim.s21), cfg.floor_db)
        holdout_rms = _rms(
            np.concatenate((h_s11_sim - h_s11, h_s21_sim - h_s21))
        )
        holdout_s11 = _rms(h_s11_sim - h_s11)
        holdout_s21 = _rms(h_s21_sim - h_s21)
        holdout_points = int(h_freq.size)

    quality: list[str] = []
    if final_rms > 3.0:
        quality.append(f"high fit RMS ({final_rms:.2f} dB)")
    for index, (param, value) in enumerate(zip(params, final_x, strict=True)):
        lo = components_bounds.lower[index]
        hi = components_bounds.upper[index]
        if value <= lo * 1.001 or value >= hi * 0.999:
            quality.append(f"{param.ref} at bound")
    if (
        cfg.fit_phase
        and delay_s is not None
        and abs(delay_s) >= cfg.max_delay_ns * 0.999e-9
    ):
        quality.append("delay at bound")
    if holdout_rms is not None and holdout_rms > max(3.0, final_rms * 2.0):
        quality.append("holdout much worse than fit")

    return VnaTuningResult(
        success=bool(best_solution.success) or final_rms <= initial_rms,
        message=str(best_solution.message),
        initial_rms_db=initial_rms,
        final_rms_db=final_rms,
        initial_rms_s11_db=initial_s11_rms,
        final_rms_s11_db=final_s11_rms,
        initial_rms_s21_db=initial_s21_rms,
        final_rms_s21_db=final_s21_rms,
        n_evaluations=evaluations,
        refs=[p.ref for p in params],
        initial_values=component_x0,
        final_values=final_x,
        circuit=final_circuit,
        frequency_hz=freq,
        measured_s11_db=meas_s11,
        measured_s21_db=meas_s21,
        simulated_s11_db=np.maximum(mag_db(final_sim.s11), cfg.floor_db),
        simulated_s21_db=np.maximum(mag_db(final_sim.s21), cfg.floor_db),
        bound_mode=mode,
        delay_s=delay_s,
        phase_s11_deg=phase_s11,
        phase_s21_deg=phase_s21,
        n_starts=len(starts),
        holdout_rms_db=holdout_rms,
        holdout_rms_s11_db=holdout_s11,
        holdout_rms_s21_db=holdout_s21,
        holdout_points=holdout_points,
        quality_notes=tuple(quality),
    )


__all__ = [
    "VnaBoundMode",
    "VnaTuningCancelled",
    "VnaTuningConfig",
    "VnaTuningError",
    "VnaTuningResult",
    "fit_circuit_to_measurement",
]
