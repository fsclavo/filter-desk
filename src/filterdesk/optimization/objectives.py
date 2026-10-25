"""Compatibility re-exports; definitions live in :mod:`filterdesk.tuning`."""

from filterdesk.tuning import (
    Objective,
    PassbandRipple,
    ReturnLoss,
    StopbandAttenuation,
    combined_residuals,
    limit_residuals,
    objective_residuals,
    residual_norm,
)

__all__ = [
    "Objective",
    "PassbandRipple",
    "ReturnLoss",
    "StopbandAttenuation",
    "combined_residuals",
    "limit_residuals",
    "objective_residuals",
    "residual_norm",
]
