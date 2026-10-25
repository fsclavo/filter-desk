"""Chebyshev Type I low-pass prototype g-values.

Odd orders use the classical closed-form g-values (equal terminations).
Even orders use the *modified* Chebyshev (relocated reflection zero) so an
all-pole LC ladder can be built with equal terminations; the element values
come from Darlington synthesis (continued fractions) of the impedance function.

See ``docs/math/chebyshev_type_i.md`` and ADR-006 (ωc'=1 at the ripple edge).
"""

from __future__ import annotations

import cmath
import math

import numpy as np
from scipy import optimize, signal

from filterdesk.domain.circuit import ArmKind
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.prototype import NormalizedArm, Prototype

_EVEN_FIT_WEIGHT_GRID = (
    np.concatenate([np.linspace(0.0, 1.0, 100), np.logspace(0.0, 1.2, 60)])
    .astype(float)
)


def chebyshev_epsilon(passband_ripple_db: float) -> float:
    if passband_ripple_db <= 0.0:
        raise ValueError("passband_ripple_db must be > 0")
    return math.sqrt(10.0 ** (0.1 * passband_ripple_db) - 1.0)


def chebyshev_type_i_g_values(
    order: int, passband_ripple_db: float
) -> tuple[float, ...]:
    """Return g0..g(n+1) for the classical Chebyshev Type I LP prototype.

    Normalization: ωc = 1 at the **ripple edge** (ADR-006).
    Uses γ = sinh(β/n) with β = asinh(1/ε) — see docs/math/chebyshev_type_i.md.

    For even orders the terminating g(n+1) = coth²(β/2) is the *unequal*
    termination ratio of the classical prototype. FilterDesk realizes even
    orders with the modified equal-termination network instead (``arms``); the
    g-values are still reported for reference.
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


def _modified_chebyshev_poles(order: int, ripple_db: float) -> np.ndarray:
    """Even-order modified Chebyshev poles (lowest reflection zero at ω=0)."""
    _, poles, _ = signal.cheby1(order, ripple_db, 1.0, analog=True, output="zpk")
    theta = math.pi * (order - 1) / (2 * order)
    cos2 = math.cos(theta) ** 2
    mapped: list[complex] = []
    for pole in poles:
        root = cmath.sqrt((complex(pole) ** 2 + cos2) / (1.0 - cos2))
        if root.real > 0.0:
            root = -root
        mapped.append(root)
    return np.asarray(mapped, dtype=complex)


def _reflection_numerator(poles: np.ndarray) -> np.ndarray:
    """Even reflection numerator F(s) with F(s)F(-s) = A(s)A(-s) − k²."""
    order = poles.size
    a = np.real_if_close(np.poly(poles), tol=1000).astype(float)
    a = a / a[0]
    gain = float(a[-1])
    a_mirror = np.asarray(
        [c * ((-1.0) ** (order - i)) for i, c in enumerate(a)], dtype=float
    )
    gram = np.polymul(a, a_mirror).astype(float)
    gram_u = gram[::2].copy()  # G(s) is even: express as a polynomial in u = s²
    gram_u[-1] -= gain * gain
    roots_u = np.sort(np.roots(gram_u).real)
    paired = np.asarray(
        [(roots_u[i] + roots_u[i + 1]) * 0.5 for i in range(0, roots_u.size - 1, 2)]
    )
    poly_u = np.real_if_close(np.poly(paired), tol=1000).astype(float)
    poly_u[np.abs(poly_u) < 1e-9 * np.max(np.abs(poly_u))] = 0.0
    if poly_u[0] != 0.0:
        poly_u = poly_u / poly_u[0]
    f = np.zeros(2 * poly_u.size - 1)
    f[::2] = poly_u
    return f


def _arms_from_values(values: list[float]) -> tuple[NormalizedArm, ...]:
    arms: list[NormalizedArm] = []
    for index, value in enumerate(values):
        kind: ArmKind = "series_L" if index % 2 == 0 else "shunt_C"
        arms.append(NormalizedArm(kind=kind, value=float(value)))
    return tuple(arms)


def _cauer_even_arms(order: int, ripple_db: float) -> tuple[NormalizedArm, ...] | None:
    """Exact continued-fraction (Darlington) synthesis; None if ill-conditioned."""
    poles = _modified_chebyshev_poles(order, ripple_db)
    a = np.real_if_close(np.poly(poles), tol=1000).astype(float)
    a = a / a[0]
    f = _reflection_numerator(poles)
    num = np.trim_zeros(a + f, "f")
    den = np.trim_zeros(a - f, "f")
    values: list[float] = []
    rtol = 1e-4
    for _ in range(order):
        if den.size == 0 or den[0] == 0.0:
            return None
        scale = max(float(np.max(np.abs(num))), float(np.max(np.abs(den))), 1.0)
        value = float(num[0] / den[0])
        if not math.isfinite(value) or value <= 0.0 or value > 1e4:
            return None
        values.append(value)
        remainder = np.polysub(num, np.polymul([value, 0.0], den))
        remainder = remainder[1:] if remainder.size else remainder
        remainder[np.abs(remainder) < rtol * scale] = 0.0
        nonzero = np.nonzero(remainder)[0]
        num = remainder[nonzero[0]:] if nonzero.size else np.asarray([0.0])
        num, den = den, num
    return _check_symmetric(_arms_from_values(values), order)


def _check_symmetric(
    arms: tuple[NormalizedArm, ...], order: int
) -> tuple[NormalizedArm, ...] | None:
    values = [float(arm.value) for arm in arms if arm.value is not None]
    if len(values) != order or any(v <= 0.0 for v in values):
        return None
    for i in range(order // 2):
        j = order - 1 - i
        if abs(values[i] - values[j]) > 1e-3 * max(1.0, abs(values[i])):
            return None
    return arms


def _ladder_s21_db(arms: tuple[NormalizedArm, ...], ws: np.ndarray) -> np.ndarray:
    s = 1j * np.asarray(ws, dtype=float)
    a = np.ones(s.shape, dtype=complex)
    b = np.zeros(s.shape, dtype=complex)
    c = np.zeros(s.shape, dtype=complex)
    d = np.ones(s.shape, dtype=complex)
    for arm in arms:
        assert arm.value is not None
        if arm.kind == "series_L":
            z = s * arm.value
            a, b, c, d = a, a * z + b, c, c * z + d
        else:
            y = s * arm.value
            a, b, c, d = a + b * y, b, c + d * y, d
    return np.asarray(
        20.0 * np.log10(np.abs(2.0 / (a + b + c + d)) + 1e-30), dtype=float
    )


def _fit_even_arms(order: int, ripple_db: float) -> tuple[NormalizedArm, ...] | None:
    """Symmetric positive-element |S21| fit (robust fallback for high orders)."""
    poles = _modified_chebyshev_poles(order, ripple_db)
    gain = float(np.real(np.prod(-poles)))
    ws = _EVEN_FIT_WEIGHT_GRID
    _, reference = signal.freqs_zpk([], poles, gain, worN=ws)
    target = np.asarray(
        20.0 * np.log10(np.abs(reference) + 1e-30), dtype=float
    )
    half = order // 2

    def expand(x: np.ndarray) -> tuple[NormalizedArm, ...]:
        values = list(x) + list(x[::-1])
        return _arms_from_values([float(v) for v in values])

    def residuals(x: np.ndarray) -> np.ndarray:
        return np.asarray(
            _ladder_s21_db(expand(np.maximum(x, 1e-7)), ws) - target, dtype=float
        )

    lo = np.full(half, 1e-3)
    hi = np.full(half, 60.0)
    seeds = [
        np.full(half, 1.0),
        np.linspace(1.0, 2.0, half),
        np.full(half, 0.4),
        np.linspace(0.5, 1.5, half),
    ]
    best: np.ndarray | None = None
    best_err = math.inf
    for seed in seeds:
        result = optimize.least_squares(
            residuals,
            np.clip(seed, lo, hi),
            bounds=(lo, hi),
            xtol=1e-12,
            ftol=1e-12,
            max_nfev=2000,
        )
        err = float(np.max(np.abs(residuals(result.x))))
        if err < best_err:
            best_err = err
            best = result.x
    if best is None or best_err > 0.05:
        return None
    return expand(best)


def _synthesize_even_arms(order: int, ripple_db: float) -> tuple[NormalizedArm, ...]:
    arms = _cauer_even_arms(order, ripple_db)
    if arms is not None:
        return arms
    arms = _fit_even_arms(order, ripple_db)
    if arms is None:
        raise ValueError(
            f"even-order Chebyshev Type I synthesis failed for order {order}"
        )
    return arms


def synthesize_chebyshev_i_prototype(
    order: int, passband_ripple_db: float
) -> Prototype:
    eps = chebyshev_epsilon(passband_ripple_db)
    if order % 2 == 0:
        return Prototype(
            family=ApproximationFamily.CHEBYSHEV_TYPE_I,
            order=order,
            arms=_synthesize_even_arms(order, passband_ripple_db),
            epsilon=eps,
            passband_ripple_db=passband_ripple_db,
            notes=(
                "even-order modified Chebyshev (relocated reflection zero); "
                "ωc=1 at ripple edge; equal terminations; Z0'=1 ohm"
            ),
        )
    return Prototype(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        order=order,
        g_values=chebyshev_type_i_g_values(order, passband_ripple_db),
        epsilon=eps,
        passband_ripple_db=passband_ripple_db,
    )
