"""Kirschning-Jansen microstrip dispersion for line/stub analysis."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def dispersion_eeff_z0(
    frequency_hz: NDArray[np.floating],
    *,
    z0_ohm: float,
    eeff_static: float,
    er: float,
    height_mm: float,
    width_mm: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return frequency-dependent ``(eeff, Z0)``.

    Uses the Kirschning-Jansen effective-permittivity and impedance dispersion
    formulas.  Falls back to the static values when geometry data is missing.
    """
    freq = np.asarray(frequency_hz, dtype=float)
    if (
        er <= 1.0
        or height_mm <= 0.0
        or width_mm <= 0.0
        or eeff_static <= 0.0
        or z0_ohm <= 0.0
    ):
        return (
            np.full(freq.size, eeff_static, dtype=np.float64),
            np.full(freq.size, z0_ohm, dtype=np.float64),
        )
    u = width_mm / height_mm
    # f[Hz] * h[m] * 1e-6 == f[GHz] * h[mm].
    fn = freq * height_mm * 1e-9
    p1 = (
        0.27488
        + (0.6315 + 0.525 / (1.0 + 0.0157 * fn) ** 20) * u
        - 0.065683 * np.exp(-8.7513 * u)
    )
    p2 = 0.33622 * (1.0 - np.exp(-0.03442 * er))
    p3 = 0.0363 * np.exp(-4.6 * u) * (1.0 - np.exp(-((fn / 38.7) ** 4.97)))
    p4 = 1.0 + 2.751 * (1.0 - np.exp(-((er / 15.916) ** 8)))
    pf = p1 * p2 * np.maximum((0.1844 + p3 * p4) * fn, 0.0) ** 1.5763
    eeff = er - (er - eeff_static) / (1.0 + pf)

    r1 = np.minimum(0.03891 * er**1.4, 20.0)
    r2 = np.minimum(0.2671 * u**7, 20.0)
    r3 = 4.766 * np.exp(-3.228 * u**0.641)
    r4 = 0.016 + (0.0514 * er) ** 4.524
    r5 = (fn / 28.843) ** 12
    r6 = np.minimum(22.20 * u**1.92, 20.0)
    r7 = 1.206 - 0.3144 * np.exp(-r1) * (1.0 - np.exp(-r2))
    r8 = 1.0 + 1.275 * (
        1.0 - np.exp(-0.004625 * r3 * er**1.674 * np.maximum(fn / 18.365, 0.0) ** 2.745)
    )
    r9 = (
        5.086
        * r4
        * r5
        / (0.3838 + 0.386 * r4)
        * np.exp(-r6)
        / (1.0 + 1.2992 * r5)
        * (er - 1.0) ** 6
        / (1.0 + 10.0 * (er - 1.0) ** 6)
    )
    r10 = 0.00044 * er**2.136 + 0.0184
    r11 = np.maximum(fn / 19.47, 0.0) ** 6 / (
        1.0 + 0.0962 * np.maximum(fn / 19.47, 0.0) ** 6
    )
    r12 = 1.0 / (1.0 + 0.00245 * u**2)
    r13 = 0.9408 * eeff**r8 - 0.9603
    r14 = (0.9408 - r9) * eeff_static**r8 - 0.9603
    r15 = 0.707 * r10 * np.maximum(fn / 12.3, 0.0) ** 1.097
    r16 = 1.0 + 0.0503 * er**2 * r11 * (1.0 - np.exp(-((u / 15.0) ** 6)))
    r17 = r7 * (
        1.0 - 1.1241 * r12 / r16 * np.exp(-0.026 * np.maximum(fn, 0.0) ** 1.15656 - r15)
    )
    z0 = z0_ohm * np.maximum(r13 / r14, 1e-15) ** r17
    return np.asarray(eeff, dtype=np.float64), np.asarray(z0, dtype=np.float64)


__all__ = ["dispersion_eeff_z0"]
