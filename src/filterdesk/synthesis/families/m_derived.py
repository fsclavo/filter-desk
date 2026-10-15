"""M-derived image-parameter sections."""

from __future__ import annotations

import math

from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.prototype import NormalizedArm, Prototype


def m_derived_zero_frequency(m: float) -> float:
    """Normalized frequency of m-derived attenuation peak (ω∞ / ωc)."""
    if not (0.0 < m < 1.0):
        raise ValueError("m must be in (0, 1)")
    return 1.0 / math.sqrt(1.0 - m * m)


def synthesize_m_derived_prototype(order: int, m: float) -> Prototype:
    """Shunt m-derived low-pass cascade (Z0'=1, image ωc'=1).

    ``order`` is the number of m-derived L-sections (series L + shunt series-LC).
    Series L = m; shunt series-LC uses L=(1−m²)/m, C=m so ω∞=1/√(1−m²).
    """
    if order < 1:
        raise ValueError("order must be >= 1")
    if not (0.0 < m < 1.0):
        raise ValueError("m_parameter must be in (0, 1)")

    w_inf = m_derived_zero_frequency(m)
    L_sh = (1.0 - m * m) / m
    C_sh = m
    arms: list[NormalizedArm] = []
    for _ in range(order):
        arms.append(NormalizedArm(kind="series_L", value=m))
        arms.append(NormalizedArm(kind="shunt_series_LC", L=L_sh, C=C_sh))

    for a in arms:
        if a.kind == "shunt_series_LC":
            assert a.L is not None and a.C is not None
            w = 1.0 / math.sqrt(a.L * a.C)
            if abs(w - w_inf) > 1e-9:
                raise RuntimeError("m-derived zero frequency mismatch")

    return Prototype(
        family=ApproximationFamily.M_DERIVED,
        order=order,
        arms=tuple(arms),
        m_parameter=m,
        notes=(
            f"image-parameter m-derived m={m:g}; omega_inf'={w_inf:.6g}; Z0'=1"
        ),
    )
