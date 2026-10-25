"""Elliptic / Cauer approximation prototype."""

from __future__ import annotations

from scipy import signal

from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.prototype import Prototype
from filterdesk.synthesis.cauer_extract import extract_cauer_arms_from_zpk


def synthesize_elliptic_prototype(
    order: int, passband_ripple_db: float, stopband_attenuation_db: float
) -> Prototype:
    """Normalized elliptic LP: passband edge ω'=1, Ap / As in dB."""
    if order < 2:
        raise ValueError("elliptic requires order >= 2")
    if order % 2 == 0:
        raise ValueError(
            "even-order elliptic needs a transformer or unequal terminations; "
            "use an odd order"
        )
    if passband_ripple_db <= 0.0:
        raise ValueError("passband_ripple_db must be > 0")
    if stopband_attenuation_db <= 0.0:
        raise ValueError("stopband_attenuation_db must be > 0")
    if stopband_attenuation_db <= passband_ripple_db:
        raise ValueError("stopband_attenuation_db must exceed passband_ripple_db")
    z, p, k = signal.ellipap(order, passband_ripple_db, stopband_attenuation_db)
    arms = extract_cauer_arms_from_zpk(z, p, float(k))
    return Prototype(
        family=ApproximationFamily.ELLIPTIC,
        order=order,
        arms=arms,
        passband_ripple_db=passband_ripple_db,
        stopband_attenuation_db=stopband_attenuation_db,
        notes=(
            "omega_p=1 rad/s ripple edge; Z0'=1 ohm; equal-R Cauer "
            "(even order via |S21| fit)"
        ),
    )
