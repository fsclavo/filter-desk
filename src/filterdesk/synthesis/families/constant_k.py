"""Constant-k image-parameter ladder sections."""

from __future__ import annotations

from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.prototype import NormalizedArm, Prototype


def synthesize_constant_k_prototype(order: int) -> Prototype:
    """Constant-k low-pass mid-series cascade (Z0'=1, image ωc'=1).

    ``order`` is the number of T-sections. Cascaded mid-series prototype:

    - ``order`` shunt capacitors of value 2
    - ``order + 1`` series inductors (ends = 1, internal = 2)
    """
    if order < 1:
        raise ValueError("order must be >= 1")
    arms: list[NormalizedArm] = []
    for i in range(order + 1):
        L = 1.0 if i in (0, order) else 2.0
        arms.append(NormalizedArm(kind="series_L", value=L))
        if i < order:
            arms.append(NormalizedArm(kind="shunt_C", value=2.0))
    return Prototype(
        family=ApproximationFamily.CONSTANT_K,
        order=order,
        arms=tuple(arms),
        notes="image-parameter constant-k mid-series; omega_c=1; Z0'=1",
    )
