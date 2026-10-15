"""Chebyshev Type II (inverse Chebyshev) Cauer prototype."""

from __future__ import annotations

from scipy import signal

from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.prototype import Prototype
from filterdesk.synthesis.cauer_extract import extract_cauer_arms_from_zpk


def synthesize_chebyshev_ii_prototype(
    order: int, stopband_attenuation_db: float
) -> Prototype:
    """Normalized Type II LP: stopband edge at ω'=1, min attenuation As (dB)."""
    if order < 1:
        raise ValueError("chebyshev_type_ii requires order >= 1")
    if stopband_attenuation_db <= 0.0:
        raise ValueError("stopband_attenuation_db must be > 0")
    z, p, k = signal.cheb2ap(order, stopband_attenuation_db)
    arms = extract_cauer_arms_from_zpk(
        z, p, float(k), reflection_zeros_at_origin=True
    )
    return Prototype(
        family=ApproximationFamily.CHEBYSHEV_TYPE_II,
        order=order,
        arms=arms,
        stopband_attenuation_db=stopband_attenuation_db,
        notes="omega_s=1 rad/s stopband edge; Z0'=1 ohm; equal-R Cauer",
    )
