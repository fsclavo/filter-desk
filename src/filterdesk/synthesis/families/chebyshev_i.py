"""Chebyshev Type I low-pass prototype g-values.

Both odd and even orders use the classical closed-form g-values. For even
orders the load/source ratio ``g(n+1) = coth²(β/2)`` is unequal; FilterDesk
realizes it with an ideal output transformer (ADR-017), so no modified
prototype is needed.
"""

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
    """Return g0..g(n+1) for the classical Chebyshev Type I LP prototype.

    Normalization: ωc = 1 at the **ripple edge** (ADR-006). For even orders
    ``g(n+1) = coth²(β/2)`` is the classical load/source ratio.
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
        g.append((1.0 / math.tanh(beta / 2.0)) ** 2)
    return tuple(g)


def synthesize_chebyshev_i_prototype(
    order: int, passband_ripple_db: float
) -> Prototype:
    eps = chebyshev_epsilon(passband_ripple_db)
    g_values = chebyshev_type_i_g_values(order, passband_ripple_db)
    if order % 2 == 0:
        return Prototype(
            family=ApproximationFamily.CHEBYSHEV_TYPE_I,
            order=order,
            g_values=g_values,
            epsilon=eps,
            passband_ripple_db=passband_ripple_db,
            load_ratio=g_values[-1],
            notes=(
                "classical even-order Chebyshev; ωc=1 at ripple edge; "
                "R_L/R_S=g(n+1); output transformer (ADR-017)"
            ),
        )
    return Prototype(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        order=order,
        g_values=g_values,
        epsilon=eps,
        passband_ripple_db=passband_ripple_db,
    )
