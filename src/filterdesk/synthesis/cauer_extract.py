"""Cauer ladder extraction from analog zpk (Cheby II / elliptic)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy import optimize, signal

from filterdesk.domain.prototype import NormalizedArm


def _trim(poly: np.ndarray, rel: float = 1e-10) -> np.ndarray:
    p = np.real_if_close(np.asarray(poly, dtype=complex), tol=1000)
    p = np.asarray(p, dtype=float)
    if p.size == 0:
        return p
    scale = max(1.0, float(np.max(np.abs(p))))
    i = 0
    while i < len(p) - 1 and abs(p[i]) < rel * scale:
        i += 1
    return p[i:]


def _pdiv(u: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    uu = [float(x) for x in u]
    vv = [float(x) for x in v]
    q: list[float] = []
    while len(uu) >= len(vv):
        factor = uu[0] / vv[0]
        q.append(factor)
        for i in range(len(vv)):
            uu[i] -= factor * vv[i]
        uu = uu[1:]
    return np.asarray(q, dtype=float), np.asarray(uu, dtype=float)


def _complementary_F(b: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Spectral factor F(s) with F(s)F(-s) ≈ |A|² − |B|² on jω."""
    n = len(a) - 1
    omegas = np.linspace(0.02, 3.0, n + 16)
    y = np.empty(omegas.shape[0], dtype=float)
    for i, omega in enumerate(omegas):
        s = 1j * omega
        ya = np.polyval(a, s)
        yb = np.polyval(b, s)
        y[i] = float(np.real(ya * np.conj(ya) - yb * np.conj(yb)))
    alpha = np.polyfit(omegas**2, y, n)
    full: list[float] = []
    for i in range(n + 1):
        k = n - i
        full.append(float(alpha[i] * ((-1) ** k)))
        if i < n:
            full.append(0.0)
    full_arr = np.asarray(full, dtype=float)
    scale = float(np.max(np.abs(full_arr))) or 1.0
    full_arr[np.abs(full_arr) < 1e-9 * scale] = 0.0
    roots = np.roots(full_arr)

    jw_raw = sorted(
        abs(float(np.imag(r)))
        for r in roots
        if abs(float(np.real(r))) < 1e-3 and abs(float(np.imag(r))) > 1e-3
    )
    jw: list[float] = []
    for w in jw_raw:
        if not jw or abs(jw[-1] - w) > 1e-3:
            jw.append(w)
        else:
            jw[-1] = 0.5 * (jw[-1] + w)
    near0 = sum(1 for r in roots if abs(r) < 1e-3)

    if not jw and near0 >= 2 * n - 2:
        return np.array([1.0] + [0.0] * n, dtype=float)

    expected_finite = (n - 1) // 2 if n % 2 == 1 else n // 2
    passband = [w for w in jw if w < 1.0 - 1e-6]
    if len(passband) >= expected_finite:
        jw_use = sorted(passband, reverse=True)[:expected_finite]
    else:
        jw_use = sorted(jw)[:expected_finite]

    roots_f: list[complex] = []
    if n % 2 == 1:
        roots_f.append(0.0)
    for w in jw_use:
        roots_f.extend([1j * w, -1j * w])
    if not roots_f:
        return np.array([1.0] + [0.0] * n, dtype=float)
    F: np.ndarray = np.asarray(
        np.real_if_close(np.poly(roots_f), tol=1000), dtype=float
    )
    if len(F) - 1 < n:
        F = np.concatenate([np.zeros(n + 1 - len(F)), F])
    elif len(F) - 1 > n:
        return np.array([1.0] + [0.0] * n, dtype=float)
    if abs(F[0]) < 1e-30:
        return np.array([1.0] + [0.0] * n, dtype=float)
    return F / float(F[0])


def _transmission_zeros(z: np.ndarray) -> list[float]:
    return sorted(
        {
            abs(float(np.imag(zz)))
            for zz in z
            if abs(float(np.real(zz))) < 1e-8 and abs(float(np.imag(zz))) > 1e-8
        }
    )


def _arms_all_positive(arms: Sequence[NormalizedArm]) -> bool:
    return all(
        (a.value is None or a.value > 1e-12)
        and (a.L is None or a.L > 1e-12)
        and (a.C is None or a.C > 1e-12)
        for a in arms
    )


def _extract_with_order(
    z_num: np.ndarray,
    z_den: np.ndarray,
    tz_order: Sequence[float],
    *,
    allow_negative: bool = False,
) -> list[NormalizedArm] | None:
    num, den = _trim(z_num), _trim(z_den)
    arms: list[NormalizedArm] = []
    for wz in tz_order:
        if len(num) < 2 or len(den) < 1:
            return None
        Z = np.polyval(num, 1j * wz) / np.polyval(den, 1j * wz)
        if not np.isfinite(Z):
            return None
        L = float(np.real(Z / (1j * wz)))
        if not allow_negative and L <= 1e-12:
            return None
        if allow_negative and abs(L) <= 1e-15:
            return None
        num = _trim(np.polysub(num, np.polymul([L, 0.0], den)))
        arms.append(NormalizedArm(kind="series_L", value=L))

        y_num, y_den = den, num
        q, rem = _pdiv(y_den, np.array([1.0, 0.0, wz * wz]))
        if q.size == 0:
            return None
        res = np.polyval(y_num, 1j * wz) / ((2j * wz) * np.polyval(q, 1j * wz))
        if not np.isfinite(res) or abs(res) < 1e-30:
            return None
        L_arm = float(np.real(1.0 / (2.0 * res)))
        if not allow_negative and L_arm <= 1e-12:
            return None
        if allow_negative and abs(L_arm) <= 1e-15:
            return None
        C_arm = 1.0 / (L_arm * wz * wz)
        if not allow_negative and C_arm <= 1e-12:
            return None
        arms.append(NormalizedArm(kind="shunt_series_LC", L=L_arm, C=C_arm))

        y_num2 = _trim(np.polysub(y_num, np.polymul([1.0 / L_arm, 0.0], q)))
        q2, rem2 = _pdiv(y_num2, np.array([1.0, 0.0, wz * wz]))
        if rem2.size == 0 or float(np.max(np.abs(rem2))) < 1e-4:
            y_num2 = _trim(q2)
        num, den = _trim(q), y_num2

    num, den = _trim(num), _trim(den)
    if len(num) == len(den) + 1:
        L = float(num[0] / den[0])
        if not allow_negative and L <= 1e-12:
            return None
        if allow_negative and abs(L) <= 1e-15:
            return None
        arms.append(NormalizedArm(kind="series_L", value=L))
    elif len(num) == 1 and len(den) == 1:
        if abs(float(num[0] / den[0]) - 1.0) > 0.05:
            return None
    else:
        return None

    if not allow_negative and not _arms_all_positive(arms):
        return None
    return arms


def _ladder_s21_db_vec(arms: Sequence[NormalizedArm], ws: np.ndarray) -> np.ndarray:
    """Vectorized |S21| dB for series-L / shunt-series-LC ladder, RS=RL=1."""
    s = 1j * np.asarray(ws, dtype=float)
    a = np.ones(s.shape, dtype=complex)
    b = np.zeros(s.shape, dtype=complex)
    c = np.zeros(s.shape, dtype=complex)
    d = np.ones(s.shape, dtype=complex)
    for arm in arms:
        if arm.kind == "series_L":
            assert arm.value is not None
            z = s * arm.value
            # cascade [[1,z],[0,1]]
            a, b, c, d = a, a * z + b, c, c * z + d
        elif arm.kind == "shunt_series_LC":
            assert arm.L is not None and arm.C is not None
            zsh = s * arm.L + 1.0 / (s * arm.C)
            y = 1.0 / zsh
            # cascade [[1,0],[y,1]]
            a, b, c, d = a + b * y, b, c + d * y, d
        else:
            raise ValueError(f"unexpected arm in fit: {arm.kind}")
    s21 = 2.0 / (a + b + c + d)
    return 20.0 * np.log10(np.abs(s21) + 1e-30)


def _ladder_s21_db(arms: Sequence[NormalizedArm], w: float) -> float:
    return float(_ladder_s21_db_vec(arms, np.array([w]))[0])


def _pack_series_first(x: np.ndarray, tz: Sequence[float]) -> list[NormalizedArm]:
    """x = [L0, Lt0, L1, Lt1, ..., L_final] with tanks tied to tz order."""
    arms: list[NormalizedArm] = []
    idx = 0
    for wz in tz:
        arms.append(NormalizedArm(kind="series_L", value=float(x[idx])))
        idx += 1
        lt = float(x[idx])
        idx += 1
        arms.append(
            NormalizedArm(kind="shunt_series_LC", L=lt, C=1.0 / (lt * wz * wz))
        )
    arms.append(NormalizedArm(kind="series_L", value=float(x[idx])))
    return arms


def _unpack_series_first(arms: Sequence[NormalizedArm]) -> np.ndarray:
    vals: list[float] = []
    for arm in arms:
        if arm.kind == "series_L":
            assert arm.value is not None
            vals.append(abs(float(arm.value)))
        elif arm.kind == "shunt_series_LC":
            assert arm.L is not None
            vals.append(abs(float(arm.L)))
    return np.asarray(vals, dtype=float)


def _refine_positive_arms(
    z: np.ndarray,
    p: np.ndarray,
    k: float,
    seed: Sequence[NormalizedArm],
    tz_order: Sequence[float],
    *,
    max_err_db: float = 0.75,
) -> list[NormalizedArm] | None:
    """Least-squares fit of a positive series-L / shunt-series-LC ladder to |H|."""
    if len(tz_order) == 0:
        return None
    # Expected pattern: (series_L, shunt_series_LC)*n_tz + series_L
    if len(seed) != 2 * len(tz_order) + 1:
        return None
    x_seed = _unpack_series_first(seed)
    if x_seed.size != 2 * len(tz_order) + 1:
        return None

    ws = np.concatenate(
        [np.logspace(-2.0, 0.0, 64), np.linspace(1.0, 4.0, 48)]
    )
    _, href = signal.freqs_zpk(z, p, k, worN=ws)
    target = np.asarray(20.0 * np.log10(np.abs(href) + 1e-30), dtype=float)

    def residuals(x: np.ndarray) -> np.ndarray:
        arms = _pack_series_first(np.maximum(x, 1e-9), tz_order)
        return np.asarray(_ladder_s21_db_vec(arms, ws) - target, dtype=float)

    starts: list[np.ndarray] = [
        np.maximum(x_seed, 1e-4),
        np.full(x_seed.shape, 0.3),
        np.full(x_seed.shape, 0.8),
        np.full(x_seed.shape, 1.5),
        np.full(x_seed.shape, 3.0),
    ]
    # Mild permutations of the analytic seed
    if np.all(np.isfinite(x_seed)):
        starts.append(np.maximum(x_seed * 0.5, 1e-4))
        starts.append(np.maximum(x_seed * 2.0, 1e-4))

    best_arms: list[NormalizedArm] | None = None
    best_err = float("inf")
    lo = np.full_like(x_seed, 1e-5)
    hi = np.full_like(x_seed, 100.0)
    for x0 in starts:
        x0 = np.clip(np.asarray(x0, dtype=float), lo, hi)
        result = optimize.least_squares(
            residuals, x0, bounds=(lo, hi), ftol=1e-12, xtol=1e-12, max_nfev=2500
        )
        err = float(np.max(np.abs(residuals(result.x))))
        if err < best_err:
            arms = _pack_series_first(result.x, tz_order)
            if _arms_all_positive(arms):
                best_err = err
                best_arms = arms
                if err <= max_err_db * 0.5:
                    break
    if best_arms is None or best_err > max_err_db:
        return None
    return best_arms


def dual_arms(arms: Sequence[NormalizedArm]) -> tuple[NormalizedArm, ...]:
    """Series-L-first ↔ shunt-C-first dual (normalized)."""
    out: list[NormalizedArm] = []
    for a in arms:
        if a.kind == "series_L":
            assert a.value is not None
            out.append(NormalizedArm(kind="shunt_C", value=a.value))
        elif a.kind == "shunt_C":
            assert a.value is not None
            out.append(NormalizedArm(kind="series_L", value=a.value))
        elif a.kind == "shunt_series_LC":
            assert a.L is not None and a.C is not None
            out.append(NormalizedArm(kind="series_parallel_LC", L=a.C, C=a.L))
        elif a.kind == "series_parallel_LC":
            assert a.L is not None and a.C is not None
            out.append(NormalizedArm(kind="shunt_series_LC", L=a.C, C=a.L))
        elif a.kind == "series_C":
            assert a.value is not None
            out.append(NormalizedArm(kind="shunt_L", value=a.value))
        elif a.kind == "shunt_L":
            assert a.value is not None
            out.append(NormalizedArm(kind="series_C", value=a.value))
        else:
            raise ValueError(f"cannot dualize arm kind {a.kind}")
    return tuple(out)


def lp_arms_to_hp(arms: Sequence[NormalizedArm]) -> tuple[NormalizedArm, ...]:
    """Low-pass → high-pass reactance inversion (still ω'=1, Z'=1)."""
    out: list[NormalizedArm] = []
    for a in arms:
        if a.kind == "series_L":
            assert a.value is not None
            out.append(NormalizedArm(kind="series_C", value=1.0 / a.value))
        elif a.kind == "shunt_C":
            assert a.value is not None
            out.append(NormalizedArm(kind="shunt_L", value=1.0 / a.value))
        elif a.kind == "shunt_L":
            assert a.value is not None
            out.append(NormalizedArm(kind="shunt_C", value=1.0 / a.value))
        elif a.kind == "series_C":
            assert a.value is not None
            out.append(NormalizedArm(kind="series_L", value=1.0 / a.value))
        elif a.kind == "shunt_series_LC":
            assert a.L is not None and a.C is not None
            out.append(
                NormalizedArm(kind="shunt_series_LC", L=1.0 / a.C, C=1.0 / a.L)
            )
        elif a.kind == "series_parallel_LC":
            assert a.L is not None and a.C is not None
            out.append(
                NormalizedArm(kind="series_parallel_LC", L=1.0 / a.C, C=1.0 / a.L)
            )
        else:
            raise ValueError(f"HP transform not defined for {a.kind}")
    return tuple(out)


def extract_cauer_arms_from_zpk(
    z: np.ndarray,
    p: np.ndarray,
    k: float,
    *,
    reflection_zeros_at_origin: bool = False,
) -> tuple[NormalizedArm, ...]:
    """Series-L-first equal-R Cauer ladder from analog prototype zpk.

    Odd and even orders are supported. Even-order elliptic equal-R ladders are
    obtained by positive-element |S21| fitting (exact Darlington often needs a
    transformer); Chebyshev Type II even-order fits tightly.

    For some (n, As/Ap) pairs the exact Cauer expansion needs a negative element.
    In that case we refine an all-positive ladder by fitting |S21| to the prototype
    (same topology; zeros stay at the analytic transmission-zero frequencies).

    Set ``reflection_zeros_at_origin=True`` for Inverse Chebyshev (F(s)=s^n).
    """
    b, a = signal.zpk2tf(z, p, k)
    n = len(p)
    if n < 1:
        raise ValueError("order must be >= 1")
    if reflection_zeros_at_origin:
        F = np.array([1.0] + [0.0] * n, dtype=float)
    else:
        F = _complementary_F(b, a)
    Dd = np.asarray(a, dtype=float)
    Nn = np.asarray(F, dtype=float)
    if len(Nn) < len(Dd):
        Nn = np.concatenate([np.zeros(len(Dd) - len(Nn)), Nn])
    if abs(Nn[0]) < 1e-30:
        Nn = np.array([1.0] + [0.0] * n, dtype=float)
    Nn = Nn * (Dd[0] / Nn[0])
    if Nn[0] / Dd[0] < 0:
        Nn = -Nn
    z_num = np.polyadd(Dd, Nn)
    z_den = np.polysub(Dd, Nn)
    tz = _transmission_zeros(np.asarray(z, dtype=complex))
    # Even-order elliptic equal-R is approximate; allow a bit more fit error.
    max_err = 0.75 if (n % 2 == 0 and not reflection_zeros_at_origin) else 0.55

    orders: list[tuple[float, ...]] = []
    if tz:
        orders.append(tuple(sorted(tz, reverse=True)))
        orders.append(tuple(sorted(tz)))
        if len(tz) >= 3:
            mid = list(sorted(tz, reverse=True))
            mid[0], mid[1] = mid[1], mid[0]
            orders.append(tuple(mid))
    else:
        orders.append(tuple())

    # 1) Exact positive extraction
    for order in orders:
        arms = _extract_with_order(z_num, z_den, order, allow_negative=False)
        if arms is not None and _arms_all_positive(arms):
            return tuple(arms)

    # 2) Signed seed + positive |S21| fit
    for order in orders[:2]:
        seed = _extract_with_order(z_num, z_den, order, allow_negative=True)
        if seed is None:
            continue
        fitted = _refine_positive_arms(
            z, p, float(k), seed, order, max_err_db=max_err
        )
        if fitted is not None:
            return tuple(fitted)

    # 3) Last resort: generic positive seeds on high-first zeros
    if tz:
        order = tuple(sorted(tz, reverse=True))
        for seed_val, tank_val in ((1.0, 0.5), (0.3, 0.2), (2.0, 0.8)):
            generic: list[NormalizedArm] = []
            for wz in order:
                generic.append(NormalizedArm(kind="series_L", value=seed_val))
                generic.append(
                    NormalizedArm(
                        kind="shunt_series_LC",
                        L=tank_val,
                        C=1.0 / (tank_val * wz * wz),
                    )
                )
            generic.append(NormalizedArm(kind="series_L", value=seed_val))
            fitted = _refine_positive_arms(
                z, p, float(k), generic, order, max_err_db=max_err
            )
            if fitted is not None:
                return tuple(fitted)

    raise ValueError("Cauer extraction failed to produce a valid ladder")
