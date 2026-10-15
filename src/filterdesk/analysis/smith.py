"""Smith-chart geometry in the reflection-coefficient plane."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def gamma_to_z(
    gamma: complex | NDArray[np.complexfloating],
) -> NDArray[np.complexfloating]:
    """Normalized impedance z = (1+Γ)/(1-Γ)."""
    g = np.asarray(gamma, dtype=np.complex128)
    return (1.0 + g) / (1.0 - g)


def z_to_gamma(
    z: complex | NDArray[np.complexfloating],
) -> NDArray[np.complexfloating]:
    """Reflection coefficient Γ = (z-1)/(z+1)."""
    zz = np.asarray(z, dtype=np.complex128)
    return (zz - 1.0) / (zz + 1.0)


def resistance_circle(
    r: float, *, n: int = 256
) -> tuple[NDArray[np.floating], NDArray[np.floating]]:
    """Constant-resistance circle in the Γ plane (normalized z)."""
    if r < 0.0:
        raise ValueError("r must be >= 0")
    center = r / (1.0 + r)
    radius = 1.0 / (1.0 + r)
    theta = np.linspace(0.0, 2.0 * np.pi, n, endpoint=True)
    return center + radius * np.cos(theta), radius * np.sin(theta)


def reactance_arc(
    x: float, *, n: int = 256
) -> tuple[NDArray[np.floating], NDArray[np.floating]]:
    """Constant-reactance locus for r≥0 (inside/on the unit circle)."""
    # Sweep resistance from ~0 (short) to large (open) at fixed x.
    r = np.geomspace(1e-6, 1e6, n)
    z = r + 1j * float(x)
    g = z_to_gamma(z)
    return g.real, g.imag


def unit_circle(*, n: int = 361) -> tuple[NDArray[np.floating], NDArray[np.floating]]:
    theta = np.linspace(0.0, 2.0 * np.pi, n, endpoint=True)
    return np.cos(theta), np.sin(theta)


def gamma_circle(
    radius: float, *, n: int = 361
) -> tuple[NDArray[np.floating], NDArray[np.floating]]:
    """Constant-|Γ| circle (centered at the origin) in the Γ plane."""
    if radius < 0.0:
        raise ValueError("radius must be >= 0")
    re, im = unit_circle(n=n)
    return radius * re, radius * im


DEFAULT_R_CIRCLES = (0.0, 0.2, 0.5, 1.0, 2.0, 5.0)
DEFAULT_X_ARCS = (0.2, 0.5, 1.0, 2.0, 5.0)


def nearest_gamma_index(
    gamma: complex,
    s11: NDArray[np.complexfloating],
    s22: NDArray[np.complexfloating] | None = None,
) -> int:
    """Index of the S11/S22 sample closest to ``gamma`` in the Γ plane."""
    g = complex(gamma)
    s11_a = np.asarray(s11, dtype=np.complex128)
    if s11_a.size == 0:
        raise ValueError("s11 is empty")
    d11 = (s11_a.real - g.real) ** 2 + (s11_a.imag - g.imag) ** 2
    if s22 is None:
        return int(np.argmin(d11))
    s22_a = np.asarray(s22, dtype=np.complex128)
    if s22_a.size != s11_a.size:
        return int(np.argmin(d11))
    d22 = (s22_a.real - g.real) ** 2 + (s22_a.imag - g.imag) ** 2
    return int(np.argmin(np.minimum(d11, d22)))


def smith_grid_polylines(
    *,
    r_values: tuple[float, ...] = DEFAULT_R_CIRCLES,
    x_values: tuple[float, ...] = DEFAULT_X_ARCS,
    n: int = 256,
) -> list[tuple[NDArray[np.floating], NDArray[np.floating]]]:
    """Return (re, im) polylines for a standard Smith grid."""
    lines: list[tuple[NDArray[np.floating], NDArray[np.floating]]] = []
    lines.append(unit_circle(n=n + 1))
    for r in r_values:
        if r == 0.0:
            continue  # same as unit circle
        lines.append(resistance_circle(r, n=n))
    # Real axis (x = 0)
    lines.append(reactance_arc(0.0, n=n))
    for x in x_values:
        lines.append(reactance_arc(x, n=n))
        lines.append(reactance_arc(-x, n=n))
    return lines
