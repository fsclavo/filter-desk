"""Monte-Carlo tolerance engine for ladder LC circuits (FR-P3 core)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.limits_eval import evaluate_limits
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig
from filterdesk.domain.circuit import (
    Circuit,
    Element,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealResistor,
    IdealSeriesLC,
    NonIdealCapacitor,
    NonIdealInductor,
)
from filterdesk.domain.overlays import LimitRegion


class ToleranceDistribution(StrEnum):
    UNIFORM = "uniform"
    NORMAL = "normal"


@dataclass(frozen=True, slots=True)
class MonteCarloConfig:
    """Tolerance sweep configuration.

    ``tolerance_pct`` is the relative tolerance in percent: uniform is ±tol;
    normal uses it as one standard deviation (sigma = tol/100).
    """

    n_trials: int = 1000
    tolerance_pct: float = 1.0
    distribution: ToleranceDistribution = ToleranceDistribution.UNIFORM
    seed: int | None = None
    backend: str = "abcd"

    def __post_init__(self) -> None:
        if self.n_trials < 1:
            raise ValueError("n_trials must be >= 1")
        if self.tolerance_pct < 0.0:
            raise ValueError("tolerance_pct must be >= 0")


@dataclass(slots=True)
class MonteCarloResult:
    frequency_hz: NDArray[np.float64]
    s21_db_min: NDArray[np.float64]
    s21_db_max: NDArray[np.float64]
    s21_db_p05: NDArray[np.float64]
    s21_db_p50: NDArray[np.float64]
    s21_db_p95: NDArray[np.float64]
    s11_db_min: NDArray[np.float64]
    s11_db_max: NDArray[np.float64]
    yield_fraction: float | None
    passes: int
    n_trials: int
    config: MonteCarloConfig

    @property
    def s21_spread_db(self) -> NDArray[np.float64]:
        """Envelope width (max − min) in dB at each frequency."""
        return np.asarray(self.s21_db_max - self.s21_db_min, dtype=np.float64)

    @property
    def max_spread_db(self) -> float:
        return float(np.max(self.s21_spread_db))


def _draw_factor(
    rng: np.random.Generator,
    tolerance_pct: float,
    distribution: ToleranceDistribution,
) -> float:
    if tolerance_pct == 0.0:
        return 1.0
    frac = tolerance_pct / 100.0
    if distribution == ToleranceDistribution.UNIFORM:
        return float(1.0 + rng.uniform(-frac, frac))
    return float(1.0 + rng.normal(0.0, frac))


def perturb_circuit(
    circuit: Circuit,
    rng: np.random.Generator,
    config: MonteCarloConfig,
) -> Circuit:
    """Return a copy with each reactive/R nominal value scaled independently."""
    tol = config.tolerance_pct
    dist = config.distribution

    def f() -> float:
        return _draw_factor(rng, tol, dist)

    elements: list[Element] = []
    for el in circuit.elements:
        if isinstance(el, IdealInductor):
            elements.append(replace(el, value_h=el.value_h * f()))
        elif isinstance(el, IdealCapacitor):
            elements.append(replace(el, value_f=el.value_f * f()))
        elif isinstance(el, IdealResistor):
            elements.append(replace(el, value_ohm=el.value_ohm * f()))
        elif isinstance(el, (IdealSeriesLC, IdealParallelLC)):
            elements.append(
                replace(el, value_h=el.value_h * f(), value_f=el.value_f * f())
            )
        elif isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
            elements.append(
                replace(
                    el,
                    series_l_h=el.series_l_h * f(),
                    series_c_f=el.series_c_f * f(),
                    parallel_l_h=el.parallel_l_h * f(),
                    parallel_c_f=el.parallel_c_f * f(),
                )
            )
        elif isinstance(el, NonIdealInductor):
            elements.append(replace(el, value_h=el.value_h * f()))
        elif isinstance(el, NonIdealCapacitor):
            elements.append(replace(el, value_f=el.value_f * f()))
        else:
            elements.append(el)
    return replace(circuit, elements=elements)


def _run_trials(
    circuit: Circuit,
    sweep: SweepConfig,
    config: MonteCarloConfig,
    active_limits: list[LimitRegion],
) -> tuple[NDArray[np.float64], NDArray[np.float64], int]:
    rng = np.random.default_rng(config.seed)
    n = sweep.n_points
    s21 = np.empty((config.n_trials, n), dtype=np.float64)
    s11 = np.empty((config.n_trials, n), dtype=np.float64)
    passes = 0
    for i in range(config.n_trials):
        trial = perturb_circuit(circuit, rng, config)
        result = analyze_circuit(trial, sweep, backend=config.backend)
        s21[i, :] = mag_db(result.s21)
        s11[i, :] = mag_db(result.s11)
        if active_limits:
            verdicts = evaluate_limits(result, active_limits)
            if all(v is not False for v in verdicts.values()):
                passes += 1
    return s21, s11, passes


def run_monte_carlo(
    circuit: Circuit,
    sweep: SweepConfig,
    config: MonteCarloConfig,
    *,
    limits: list[LimitRegion] | None = None,
) -> MonteCarloResult:
    """Run ``config.n_trials`` perturbed analyses and summarise the response."""
    active = [lim for lim in (limits or []) if lim.enabled]
    s21, s11, passes = _run_trials(circuit, sweep, config, active)
    perc = np.percentile(s21, [5, 50, 95], axis=0)
    yield_fraction = passes / config.n_trials if active else None

    return MonteCarloResult(
        frequency_hz=np.asarray(sweep.frequencies_hz(), dtype=np.float64),
        s21_db_min=np.asarray(np.min(s21, axis=0), dtype=np.float64),
        s21_db_max=np.asarray(np.max(s21, axis=0), dtype=np.float64),
        s21_db_p05=np.asarray(perc[0], dtype=np.float64),
        s21_db_p50=np.asarray(perc[1], dtype=np.float64),
        s21_db_p95=np.asarray(perc[2], dtype=np.float64),
        s11_db_min=np.asarray(np.min(s11, axis=0), dtype=np.float64),
        s11_db_max=np.asarray(np.max(s11, axis=0), dtype=np.float64),
        yield_fraction=yield_fraction,
        passes=passes,
        n_trials=config.n_trials,
        config=config,
    )
