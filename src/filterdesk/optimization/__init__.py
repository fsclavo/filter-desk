"""Component-value optimization against limit regions (FR-P4)."""

from filterdesk.optimization.constraints import Bounds, relative_bounds
from filterdesk.optimization.objectives import (
    Objective,
    PassbandRipple,
    ReturnLoss,
    StopbandAttenuation,
    combined_residuals,
    limit_residuals,
    objective_residuals,
    residual_norm,
)
from filterdesk.optimization.solvers import (
    OptimizationCancelled,
    OptimizationConfig,
    OptimizationError,
    OptimizationResult,
    OptimizeMethod,
    optimize_circuit,
)
from filterdesk.optimization.variables import (
    TunableParam,
    apply_values,
    tunable_params,
)

__all__ = [
    "Bounds",
    "Objective",
    "OptimizationCancelled",
    "OptimizationConfig",
    "OptimizationError",
    "OptimizationResult",
    "OptimizeMethod",
    "PassbandRipple",
    "ReturnLoss",
    "StopbandAttenuation",
    "TunableParam",
    "apply_values",
    "combined_residuals",
    "limit_residuals",
    "objective_residuals",
    "optimize_circuit",
    "relative_bounds",
    "residual_norm",
    "tunable_params",
]
