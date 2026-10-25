"""Derivative-free limit optimizer over tunable component values (FR-P4)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import (
    differential_evolution,
    dual_annealing,
    least_squares,
    minimize,
)

from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig
from filterdesk.domain.circuit import Circuit
from filterdesk.domain.overlays import LimitRegion
from filterdesk.optimization.constraints import relative_bounds
from filterdesk.optimization.objectives import (
    Objective,
    combined_residuals,
    residual_norm,
)
from filterdesk.optimization.variables import apply_values, tunable_params


class OptimizeMethod(StrEnum):
    LEAST_SQUARES = "least_squares"
    NELDER_MEAD = "nelder_mead"
    DIFFERENTIAL_EVOLUTION = "differential_evolution"
    DUAL_ANNEALING = "dual_annealing"


class OptimizationError(ValueError):
    """Raised when an optimization run cannot start."""


class OptimizationCancelled(RuntimeError):
    """Raised when a running optimization is cancelled cooperatively."""


@dataclass(frozen=True, slots=True)
class OptimizationConfig:
    method: OptimizeMethod = OptimizeMethod.LEAST_SQUARES
    bound_pct: float = 0.2
    max_iter: int = 200
    backend: str = "abcd"
    seed: int | None = None
    objectives: tuple[Objective, ...] = ()

    def __post_init__(self) -> None:
        if self.bound_pct < 0.0:
            raise OptimizationError("bound_pct must be >= 0")
        if self.max_iter < 1:
            raise OptimizationError("max_iter must be >= 1")


@dataclass(slots=True)
class OptimizationResult:
    method: OptimizeMethod
    success: bool
    message: str
    initial_cost: float
    final_cost: float
    n_evaluations: int
    refs: list[str]
    initial_values: NDArray[np.float64]
    final_values: NDArray[np.float64]
    circuit: Circuit

    @property
    def improvement(self) -> float:
        return self.initial_cost - self.final_cost


def optimize_circuit(
    circuit: Circuit,
    sweep: SweepConfig,
    limits: list[LimitRegion],
    config: OptimizationConfig | None = None,
    *,
    cancel: Callable[[], bool] | None = None,
) -> OptimizationResult:
    """Minimise limit violations by tuning component values within ``bound_pct``.

    Uses the residual vector from :func:`limit_residuals`: least-squares
    minimizes its 2-norm; Nelder–Mead minimizes the squared norm.
    """
    cfg = config or OptimizationConfig()
    params = tunable_params(circuit)
    if not params:
        raise OptimizationError("circuit has no tunable components")
    active = [lim for lim in limits if lim.enabled]
    objectives = list(cfg.objectives)
    if not active and not objectives:
        raise OptimizationError("no enabled limit regions or objectives to optimize")

    x0 = np.asarray([p.value for p in params], dtype=float)
    bounds = relative_bounds(x0, cfg.bound_pct)
    evaluations = 0

    def residuals(x: NDArray[np.float64]) -> NDArray[np.float64]:
        nonlocal evaluations
        if cancel is not None and cancel():
            raise OptimizationCancelled("optimization cancelled")
        evaluations += 1
        trial = apply_values(circuit, params, x)
        result = analyze_circuit(trial, sweep, backend=cfg.backend)
        return combined_residuals(result, active, objectives)

    def scalar(x: NDArray[np.float64]) -> float:
        r = residuals(x)
        return float(np.sum(r * r))

    initial_cost = residual_norm(residuals(x0))

    if cfg.method == OptimizeMethod.LEAST_SQUARES:
        solution = least_squares(
            residuals,
            x0,
            bounds=(bounds.lower, bounds.upper),
            max_nfev=cfg.max_iter,
        )
        final_x = np.asarray(solution.x, dtype=float)
        success = bool(solution.success)
        message = str(solution.message)
    elif cfg.method == OptimizeMethod.DIFFERENTIAL_EVOLUTION:
        de = differential_evolution(
            scalar,
            bounds=list(zip(bounds.lower.tolist(), bounds.upper.tolist(), strict=True)),
            maxiter=cfg.max_iter,
            seed=cfg.seed,
            polish=True,
            tol=1e-8,
        )
        final_x = np.asarray(de.x, dtype=float)
        success = bool(de.success)
        message = str(de.message)
    elif cfg.method == OptimizeMethod.DUAL_ANNEALING:
        da = dual_annealing(
            scalar,
            bounds=list(zip(bounds.lower.tolist(), bounds.upper.tolist(), strict=True)),
            maxiter=cfg.max_iter,
            seed=cfg.seed,
        )
        final_x = np.asarray(da.x, dtype=float)
        success = bool(da.success)
        message = str(da.message)
    else:
        nm = minimize(
            scalar,
            x0,
            method="Nelder-Mead",
            bounds=list(zip(bounds.lower.tolist(), bounds.upper.tolist(), strict=True)),
            options={"maxiter": cfg.max_iter},
        )
        final_x = np.asarray(nm.x, dtype=float)
        success = bool(nm.success)
        message = str(nm.message)

    final_circuit = apply_values(circuit, params, final_x)
    final_cost = residual_norm(
        combined_residuals(
            analyze_circuit(final_circuit, sweep, backend=cfg.backend),
            active,
            objectives,
        )
    )

    # Never return a result worse than the nominal starting point (global methods
    # such as dual annealing can otherwise finish below the initial quality).
    if final_cost > initial_cost:
        final_x = x0.copy()
        final_circuit = circuit
        final_cost = initial_cost

    return OptimizationResult(
        method=cfg.method,
        success=success,
        message=message,
        initial_cost=initial_cost,
        final_cost=final_cost,
        n_evaluations=evaluations,
        refs=[p.ref for p in params],
        initial_values=x0,
        final_values=final_x,
        circuit=final_circuit,
    )


__all__ = [
    "OptimizeMethod",
    "OptimizationCancelled",
    "OptimizationConfig",
    "OptimizationError",
    "OptimizationResult",
    "optimize_circuit",
]
