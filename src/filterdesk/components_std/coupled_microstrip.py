"""Quasi-static synthesis of symmetric coupled microstrip lines.

Forward model: Hammerstad-Jensen coupled-line equations (even/odd mode).
Inverse: bounded numerical fit of width/gap to target even/odd impedances.

The model is zero-thickness, quasi-static and symmetric. It does not include
finite thickness, dispersion, discontinuities or radiation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

from filterdesk.components_std.microstrip import Substrate

ETA0 = 376.730313668
_U_MIN = 0.05
_U_MAX = 20.0
_G_MIN = 0.01
_G_MAX = 20.0


class CoupledMicrostripError(ValueError):
    """Raised when coupled-microstrip geometry cannot be synthesized."""


@dataclass(frozen=True, slots=True)
class CoupledMicrostripGeometry:
    substrate: Substrate
    z0e_target_ohm: float
    z0o_target_ohm: float
    z0e_ohm: float
    z0o_ohm: float
    width_mm: float
    gap_mm: float
    eeff_even: float
    eeff_odd: float
    u: float
    g: float
    residual: float
    warnings: tuple[str, ...] = ()


def _ab(u: float, er: float) -> tuple[float, float]:
    a = (
        1.0
        + (1.0 / 49.0)
        * math.log((u**4 + (u / 52.0) ** 2) / (u**4 + 0.432))
        + (1.0 / 18.7) * math.log(1.0 + (u / 18.1) ** 3)
    )
    b = 0.564 * ((er - 0.9) / (er + 3.0)) ** 0.053
    return a, b


def _single_free_space(u: float) -> float:
    return float(ETA0 / (u + 1.98 * u**0.172))


def coupled_microstrip_impedances(
    width_mm: float, gap_mm: float, substrate: Substrate
) -> tuple[float, float, float, float]:
    """Return ``(Z0e, Z0o, eeff_even, eeff_odd)`` for a geometry."""
    if width_mm <= 0.0 or gap_mm <= 0.0:
        raise CoupledMicrostripError("width and gap must be > 0")
    if substrate.h_mm <= 0.0 or substrate.er < 1.0:
        raise CoupledMicrostripError("invalid substrate")
    u = width_mm / substrate.h_mm
    g = gap_mm / substrate.h_mm
    if not _U_MIN <= u <= _U_MAX:
        raise CoupledMicrostripError(
            f"normalized width u={u:.4g} is outside {_U_MIN}..{_U_MAX}"
        )
    if not _G_MIN <= g <= _G_MAX:
        raise CoupledMicrostripError(
            f"normalized gap g={g:.4g} is outside {_G_MIN}..{_G_MAX}"
        )
    er = substrate.er
    a_u, b_er = _ab(u, er)
    z0_free = _single_free_space(u)
    mu = g * math.exp(-g) + u * (20.0 + g * g) / (10.0 + g * g)
    a_mu, _ = _ab(mu, er)
    f_even = (1.0 + 10.0 / mu) ** (-a_mu * b_er)
    eeff_even = (er + 1.0) / 2.0 + (er - 1.0) / 2.0 * f_even

    phi = 0.8645 * u**0.172
    psi = 1.0 + g / 1.45 + g**2.09 / 3.95
    alpha = 0.5 * math.exp(-g)
    m = (
        0.2175
        + (4.113 + (20.36 / g) ** 6) ** (-0.251)
        + (1.0 / 323.0) * math.log(g**10 / (1.0 + (g / 13.8) ** 10))
    )
    phi_even = phi / (
        psi * (alpha * u**m + (1.0 - alpha) * u ** (-m))
    )
    theta = 1.729 + 1.175 * math.log(
        1.0 + 0.627 / (g + 0.327 * g**2.17)
    )
    beta = (
        0.2306
        + (1.0 / 301.8) * math.log(g**10 / (1.0 + (g / 3.73) ** 10))
        + (1.0 / 5.3) * math.log(1.0 + 0.646 * g**1.175)
    )
    n = (
        1.0 / 17.7
        + math.exp(-6.424 - 0.76 * math.log(g) - (g / 0.23) ** 5)
    ) * math.log((10.0 + 68.3 * g * g) / (1.0 + 32.5 * g**3.093))
    phi_odd = phi_even - theta / psi * math.exp(
        beta * u**n * math.log(u)
    )
    z01_even = z0_free / (1.0 - z0_free * phi_even / ETA0)
    z01_odd = z0_free / (1.0 - z0_free * phi_odd / ETA0)

    p = math.exp(-0.745 * g**0.295) / math.cosh(g**0.68)
    q = math.exp(-1.366 - g)
    r = 1.0 + 0.15 * (
        1.0
        - math.exp(1.0 - (er - 1.0) ** 2 / 8.2) / (1.0 + g**-6)
    )
    f_o1 = 1.0 - math.exp(
        -0.179 * g**0.15
        - 0.328 * g**r / math.log(math.e + (g / 7.0) ** 2.8)
    )
    f_o = f_o1 * math.exp(
        p * math.log(u) + q * math.sin(math.pi * math.log10(u))
    )
    f_odd = f_o * (1.0 + 10.0 / u) ** (-a_u * b_er)
    eeff_odd = (er + 1.0) / 2.0 + (er - 1.0) / 2.0 * f_odd
    z0e = z01_even / math.sqrt(eeff_even)
    z0o = z01_odd / math.sqrt(eeff_odd)
    return z0e, z0o, eeff_even, eeff_odd


def _residual(
    x: np.ndarray, z0e: float, z0o: float, substrate: Substrate
) -> np.ndarray:
    u = math.exp(float(x[0]))
    g = math.exp(float(x[1]))
    try:
        actual_e, actual_o, _, _ = coupled_microstrip_impedances(
            u * substrate.h_mm, g * substrate.h_mm, substrate
        )
    except (CoupledMicrostripError, ValueError, OverflowError):
        return np.asarray([1e6, 1e6], dtype=float)
    return np.asarray(
        [(actual_e - z0e) / z0e, (actual_o - z0o) / z0o], dtype=float
    )


def design_coupled_microstrip(
    z0e_ohm: float, z0o_ohm: float, substrate: Substrate
) -> CoupledMicrostripGeometry:
    """Fit width/gap to target even/odd impedances."""
    if not np.isfinite(z0e_ohm) or not np.isfinite(z0o_ohm):
        raise CoupledMicrostripError("target impedances must be finite")
    if z0e_ohm <= z0o_ohm:
        raise CoupledMicrostripError("Z0e must be above Z0o")
    if z0o_ohm <= 0.0:
        raise CoupledMicrostripError("Z0o must be > 0")
    if substrate.h_mm <= 0.0 or substrate.er < 1.0:
        raise CoupledMicrostripError("invalid substrate")
    bounds = (
        [math.log(_U_MIN), math.log(_G_MIN)],
        [math.log(_U_MAX), math.log(_G_MAX)],
    )
    best: least_squares | None = None
    best_norm = math.inf
    for u0 in (0.2, 0.5, 1.0, 2.0, 5.0):
        for g0 in (0.02, 0.05, 0.1, 0.25, 0.6, 1.5, 4.0):
            solution = least_squares(
                _residual,
                [math.log(u0), math.log(g0)],
                args=(z0e_ohm, z0o_ohm, substrate),
                bounds=bounds,
                max_nfev=250,
                ftol=1e-11,
                xtol=1e-11,
                gtol=1e-11,
            )
            norm = float(np.linalg.norm(solution.fun))
            if norm < best_norm:
                best = solution
                best_norm = norm
    if best is None or best_norm > 2e-3:
        raise CoupledMicrostripError(
            "cannot fit Z0e/Z0o inside the quasi-static geometry range; "
            "check the substrate and coupling target"
        )
    u = math.exp(float(best.x[0]))
    g = math.exp(float(best.x[1]))
    width_mm = u * substrate.h_mm
    gap_mm = g * substrate.h_mm
    actual_e, actual_o, eeff_e, eeff_o = coupled_microstrip_impedances(
        width_mm, gap_mm, substrate
    )
    warnings: list[str] = []
    if not 0.1 <= u <= 10.0:
        warnings.append(
            f"normalized width u={u:.3g} is outside the validated 0.1..10 range"
        )
    if g > 10.0:
        warnings.append(
            f"normalized gap g={g:.3g} is outside the validated 0.01..10 range"
        )
    return CoupledMicrostripGeometry(
        substrate=substrate,
        z0e_target_ohm=z0e_ohm,
        z0o_target_ohm=z0o_ohm,
        z0e_ohm=actual_e,
        z0o_ohm=actual_o,
        width_mm=width_mm,
        gap_mm=gap_mm,
        eeff_even=eeff_e,
        eeff_odd=eeff_o,
        u=u,
        g=g,
        residual=best_norm,
        warnings=tuple(warnings),
    )


__all__ = [
    "CoupledMicrostripError",
    "CoupledMicrostripGeometry",
    "coupled_microstrip_impedances",
    "design_coupled_microstrip",
]
