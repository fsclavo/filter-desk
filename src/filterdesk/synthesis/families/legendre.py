"""Legendre (Papoulis / Optimum-L) low-pass prototype g-values."""

from __future__ import annotations

from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.prototype import Prototype
from filterdesk.domain.specs import SpecValidationError
from filterdesk.synthesis.families.tables import LEGENDRE_G


def legendre_g_values(order: int) -> tuple[float, ...]:
    if order not in LEGENDRE_G:
        raise SpecValidationError(
            f"legendre supports order 2..{max(LEGENDRE_G)} (got {order})"
        )
    return LEGENDRE_G[order]


def synthesize_legendre_prototype(order: int) -> Prototype:
    return Prototype(
        family=ApproximationFamily.LEGENDRE,
        order=order,
        g_values=legendre_g_values(order),
        notes="papoulis/legendre monotonic, ω_-3dB≈1 (ADR-012)",
    )
