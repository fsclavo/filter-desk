"""Bessel–Thomson low-pass prototype g-values."""

from __future__ import annotations

from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.prototype import Prototype
from filterdesk.domain.specs import SpecValidationError
from filterdesk.synthesis.families.tables import BESSEL_G


def bessel_g_values(order: int) -> tuple[float, ...]:
    if order not in BESSEL_G:
        raise SpecValidationError(
            f"bessel supports order 1..{max(BESSEL_G)} (got {order})"
        )
    return BESSEL_G[order]


def synthesize_bessel_prototype(order: int) -> Prototype:
    return Prototype(
        family=ApproximationFamily.BESSEL,
        order=order,
        g_values=bessel_g_values(order),
        notes="bessel mag-normalized ω_-3dB=1 (ADR-012)",
    )
