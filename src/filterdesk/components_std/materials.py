"""Ferrite material data and first-order core-loss/thermal helpers.

Loss is derived from Fair-Rite complex-permeability data (mu' and mu'') rather
than fitted Steinmetz coefficients. The complex permeability is measured at low
flux; extrapolation to high flux is approximate, so the result is a conservative
engineering estimate, not a substitute for the vendor's core-loss curves.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass

_MU0 = 4e-7 * math.pi
_RHO_CU = 1.724e-8  # ohm m


@dataclass(frozen=True, slots=True)
class FerriteMaterial:
    name: str
    mu_i: float
    bsat_t: float
    curie_c: float
    #: (frequency Hz, mu_real, mu_imag) from the vendor complex-permeability
    #: table; interpolated logarithmically in frequency.
    loss_points: tuple[tuple[float, float, float], ...]

    def mu_at(self, frequency_hz: float) -> tuple[float, float]:
        if not self.loss_points:
            return self.mu_i, 0.0
        freqs = [point[0] for point in self.loss_points]
        f = max(frequency_hz, 1.0)
        if f <= freqs[0]:
            return self.loss_points[0][1], self.loss_points[0][2]
        if f >= freqs[-1]:
            return self.loss_points[-1][1], self.loss_points[-1][2]
        i = bisect.bisect_left(freqs, f)
        f0, r0, i0 = self.loss_points[i - 1]
        f1, r1, i1 = self.loss_points[i]
        t = (math.log(f) - math.log(f0)) / (math.log(f1) - math.log(f0))
        return r0 + (r1 - r0) * t, i0 + (i1 - i0) * t


# Fair-Rite complex-permeability data, selected points (0.1–100 MHz). The
# values are typical; batch spread is ±20–25 %.
MATERIALS: dict[str, FerriteMaterial] = {
    "31": FerriteMaterial(
        "31",
        1500.0,
        0.360,
        130.0,
        (
            (1e5, 1401.9, 41.6),
            (1e6, 1400.7, 463.2),
            (2e6, 980.8, 734.8),
            (3.5e6, 599.4, 662.3),
            (5e6, 438.8, 552.7),
            (7e6, 336.3, 452.3),
            (10e6, 264.1, 365.9),
            (14e6, 212.0, 305.5),
            (21e6, 156.9, 249.3),
            (28e6, 121.8, 216.2),
            (30e6, 113.9, 208.5),
            (50e6, 64.7, 155.1),
            (100e6, 25.3, 103.2),
        ),
    ),
    "43": FerriteMaterial(
        "43",
        800.0,
        0.295,
        130.0,
        (
            (1e5, 788.2, 5.6),
            (1e6, 747.1, 62.8),
            (2e6, 589.2, 166.5),
            (3.5e6, 474.2, 221.0),
            (5e6, 396.5, 231.1),
            (7e6, 327.5, 228.2),
            (10e6, 260.3, 218.4),
            (14e6, 201.5, 203.8),
            (21e6, 136.7, 178.5),
            (28e6, 98.8, 156.0),
            (30e6, 91.0, 150.4),
            (50e6, 46.0, 109.3),
            (100e6, 14.9, 63.0),
        ),
    ),
    "52": FerriteMaterial(
        "52",
        250.0,
        0.420,
        250.0,
        (
            (1e5, 268.1, 3.1),
            (1e6, 265.4, 3.1),
            (2e6, 267.3, 4.7),
            (3.5e6, 276.0, 9.6),
            (5e6, 293.5, 18.9),
            (7e6, 299.1, 65.9),
            (10e6, 258.9, 133.8),
            (14e6, 189.7, 148.4),
            (21e6, 132.2, 127.5),
            (28e6, 108.4, 108.9),
            (30e6, 104.2, 105.1),
            (50e6, 78.7, 85.4),
            (100e6, 47.9, 69.0),
        ),
    ),
    "61": FerriteMaterial(
        "61",
        125.0,
        0.250,
        300.0,
        (
            (1e5, 117.6, 0.5),
            (1e6, 118.6, 0.6),
            (2e6, 118.5, 0.8),
            (3.5e6, 118.9, 0.8),
            (5e6, 119.7, 0.9),
            (7e6, 121.4, 1.2),
            (10e6, 125.5, 2.0),
            (14e6, 135.2, 5.6),
            (21e6, 152.2, 39.9),
            (28e6, 125.1, 74.9),
            (30e6, 116.0, 78.3),
            (50e6, 64.3, 73.2),
            (100e6, 32.9, 51.4),
        ),
    ),
}


def material_for(name: str) -> FerriteMaterial | None:
    return MATERIALS.get(name)


def core_loss_density_w_cm3(
    material: FerriteMaterial, frequency_hz: float, b_peak_t: float
) -> float:
    """Core loss density from complex permeability (W/cm³)."""
    if frequency_hz <= 0.0 or b_peak_t <= 0.0:
        return 0.0
    mu_real, mu_imag = material.mu_at(frequency_hz)
    if mu_real <= 0.0:
        return 0.0
    pv_w_m3 = (
        math.pi
        * frequency_hz
        * b_peak_t
        * b_peak_t
        * mu_imag
        / (_MU0 * mu_real * mu_real)
    )
    return pv_w_m3 / 1e6


def bsat_at_temperature(material: FerriteMaterial, temperature_c: float) -> float:
    """Conservative linear Bsat derating between 25 °C and the Curie point."""
    span = max(material.curie_c - 25.0, 1.0)
    fraction = 1.0 - 0.25 * (temperature_c - 25.0) / span
    return material.bsat_t * max(0.5, min(1.0, fraction))


def copper_resistance_ohm(
    length_m: float, wire_diameter_mm: float | None
) -> float | None:
    """DC copper resistance for a wire length/diameter (20 °C)."""
    if length_m <= 0.0 or not wire_diameter_mm or wire_diameter_mm <= 0.0:
        return None
    area_m2 = math.pi * (wire_diameter_mm * 1e-3 / 2.0) ** 2
    return _RHO_CU * length_m / area_m2


def copper_loss_w(
    current_a: float, length_m: float, wire_diameter_mm: float | None
) -> float:
    if current_a <= 0.0:
        return 0.0
    resistance = copper_resistance_ohm(length_m, wire_diameter_mm)
    return 0.0 if resistance is None else current_a * current_a * resistance


def thermal_resistance_c_w(
    core_od_mm: float,
    core_id_mm: float,
    core_height_mm: float,
    *,
    h_w_m2k: float = 12.0,
) -> float:
    """Approximate natural-convection thermal resistance of a toroid."""
    if min(core_od_mm, core_id_mm, core_height_mm) <= 0.0:
        return 0.0
    ro = core_od_mm / 2.0
    ri = core_id_mm / 2.0
    area_mm2 = (
        2.0 * math.pi * ro * core_height_mm
        + 2.0 * math.pi * ri * core_height_mm
        + 2.0 * math.pi * (ro * ro - ri * ri)
    )
    area_m2 = area_mm2 * 1e-6
    return 1.0 / (h_w_m2k * area_m2) if area_m2 > 0.0 else 0.0


__all__ = [
    "MATERIALS",
    "FerriteMaterial",
    "bsat_at_temperature",
    "core_loss_density_w_cm3",
    "copper_loss_w",
    "material_for",
    "thermal_resistance_c_w",
]
