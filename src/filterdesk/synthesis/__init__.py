"""Synthesis package."""

from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.specs import FilterSpec
from filterdesk.synthesis.api import SynthesisResult, synthesize
from filterdesk.synthesis.order_estimate import (
    OrderEstimateError,
    OrderEstimateResult,
    estimate_minimum_order,
    supports_order_estimation,
)

__all__ = [
    "OrderEstimateError",
    "OrderEstimateResult",
    "SynthesisResult",
    "estimate_minimum_order",
    "supports_order_estimation",
    "synthesis_note",
    "synthesize",
]


def synthesis_note(spec: FilterSpec) -> str | None:
    """Human-readable caveat for a synthesized design, if any."""
    if (
        spec.family == ApproximationFamily.CHEBYSHEV_TYPE_I
        and spec.order % 2 == 0
    ):
        return (
            "Even-order Chebyshev I uses the classical equal-ripple "
            "prototype with an ideal output transformer (ADR-017); it "
            "matches the textbook response and values."
        )
    return None
