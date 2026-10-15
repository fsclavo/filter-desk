"""Gaussian low-pass prototype g-values (finite-order approximation)."""

from __future__ import annotations

from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.prototype import Prototype
from filterdesk.domain.specs import SpecValidationError
from filterdesk.synthesis.families.tables import GAUSSIAN_G


def gaussian_g_values(order: int) -> tuple[float, ...]:
    if order not in GAUSSIAN_G:
        raise SpecValidationError(
            f"gaussian supports order 1..{max(GAUSSIAN_G)} (got {order})"
        )
    return GAUSSIAN_G[order]


def synthesize_gaussian_prototype(order: int) -> Prototype:
    return Prototype(
        family=ApproximationFamily.GAUSSIAN,
        order=order,
        g_values=gaussian_g_values(order),
        notes="gaussian finite-order ladder approx, ω_-3dB=1 (ADR-012)",
    )
