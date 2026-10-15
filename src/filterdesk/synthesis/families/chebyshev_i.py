"""Chebyshev Type I low-pass prototype g-values."""

from __future__ import annotations

import math

from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.prototype import Prototype


def chebyshev_epsilon(passband_ripple_db: float) -> float:
    if passband_ripple_db <= 0.0:
        raise ValueError("passband_ripple_db must be > 0")
    return math.sqrt(10.0 ** (0.1 * passband_ripple_db) - 1.0)


def chebyshev_type_i_g_values(
    order: int, passband_ripple_db: float
) -> tuple[float, ...]:
    """Return g0..g(n+1) for Chebyshev Type I LP prototype.

    Normalization: ωc = 1 at the **ripple edge** (ADR-006).
    Uses γ = sinh(β/n) with β = asinh(1/ε) — see docs/math/chebyshev_type_i.md.
    """
    if order < 1:
        raise ValueError("order must be >= 1")
    eps = chebyshev_epsilon(passband_ripple_db)
    beta = math.asinh(1.0 / eps)
    gamma = math.sinh(beta / order)
    g: list[float] = [1.0]
    for k in range(1, order + 1):
        a_k = math.sin((2 * k - 1) * math.pi / (2 * order))
        if k == 1:
            g.append(2.0 * a_k / gamma)
        else:
            a_km1 = math.sin((2 * (k - 1) - 1) * math.pi / (2 * order))
            b_km1 = gamma * gamma + math.sin((k - 1) * math.pi / order) ** 2
            g.append(4.0 * a_km1 * a_k / (b_km1 * g[k - 1]))
    if order % 2 == 1:
        g.append(1.0)
    else:
        g.append((1.0 / math.tanh(beta / 4.0)) ** 2)
    return tuple(g)


def synthesize_chebyshev_i_prototype(
    order: int, passband_ripple_db: float
) -> Prototype:
    eps = chebyshev_epsilon(passband_ripple_db)
    return Prototype(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        order=order,
        g_values=chebyshev_type_i_g_values(order, passband_ripple_db),
        epsilon=eps,
        passband_ripple_db=passband_ripple_db,
    )
