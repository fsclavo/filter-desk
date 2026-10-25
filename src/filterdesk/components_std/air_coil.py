"""Single-layer air-core solenoid calculator (Phase 12).

Close-wound solenoid using Wheeler's formula (a = radius, b = length, both in
inches)::

    L[uH] = a^2 * N^2 / (9a + 10b)

with ``b = N * p`` (pitch per turn). By default the wire is assumed to be
**grade-1 enamelled copper**: the bare diameter defines the copper cross-section
(and DC resistance), while the enamel build sets the winding pitch and length.
The build is interpolated from IEC 60317-0-1 typical (mid-range) overall
diameters; pass ``enamel_build_mm=0`` for bare wire or an explicit value.

The model assumes a single close-wound layer; it does **not** model
self-capacitance / SRF, AC resistance or Q, so treat the result as a starting
point for HF work.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from filterdesk.components_std.toroid import awg_diameter_mm

__all__ = [
    "COPPER_RESISTIVITY_OHM_M",
    "ENAMEL_OVERALL_MM",
    "AirCoilDesign",
    "AirCoilError",
    "air_coil_inductance_h",
    "awg_for_diameter_mm",
    "design_air_coil",
    "enamel_overall_diameter_mm",
]

#: Copper resistivity at 20 °C (ohm·m).
COPPER_RESISTIVITY_OHM_M = 1.724e-8

_MM_PER_INCH = 25.4

#: Typical overall diameter (mm) of grade-1 enamelled wire vs bare diameter:
#: midpoint of the IEC 60317-0-1 minimum-insulation and maximum-overall values.
ENAMEL_OVERALL_MM: tuple[tuple[float, float], ...] = (
    (0.080, 0.0905),
    (0.090, 0.1015),
    (0.100, 0.1125),
    (0.112, 0.1255),
    (0.125, 0.1395),
    (0.140, 0.1555),
    (0.160, 0.1770),
    (0.180, 0.1985),
    (0.200, 0.2200),
    (0.224, 0.2455),
    (0.250, 0.2740),
    (0.280, 0.3050),
    (0.315, 0.3415),
    (0.355, 0.3835),
    (0.400, 0.4300),
    (0.450, 0.4815),
    (0.500, 0.5340),
    (0.560, 0.5955),
    (0.630, 0.6680),
    (0.710, 0.7500),
    (0.800, 0.8425),
    (0.900, 0.9455),
    (1.000, 1.0480),
    (1.120, 1.1690),
    (1.250, 1.3005),
    (1.400, 1.4520),
    (1.600, 1.6540),
    (1.800, 1.8555),
    (2.000, 2.0570),
    (2.240, 2.2985),
    (2.500, 2.5600),
    (2.800, 2.8615),
    (3.150, 3.2140),
    (3.550, 3.6155),
    (4.000, 4.0675),
)


class AirCoilError(ValueError):
    """Raised for invalid air-core coil inputs."""


def enamel_overall_diameter_mm(bare_mm: float) -> float:
    """Typical grade-1 enamelled overall diameter for a bare wire (mm)."""
    if bare_mm <= 0.0:
        raise AirCoilError("wire diameter must be > 0")
    table = ENAMEL_OVERALL_MM
    if bare_mm <= table[0][0]:
        return table[0][1]
    if bare_mm >= table[-1][0]:
        ratio = table[-1][1] / table[-1][0]
        return bare_mm * ratio
    for (d0, o0), (d1, o1) in zip(table, table[1:], strict=False):
        if d0 <= bare_mm <= d1:
            fraction = (bare_mm - d0) / (d1 - d0)
            return o0 + fraction * (o1 - o0)
    return bare_mm  # pragma: no cover - unreachable


def awg_for_diameter_mm(diameter_mm: float) -> int:
    """Nearest standard AWG (8–40) for a bare wire diameter in millimetres."""
    if diameter_mm <= 0.0:
        raise AirCoilError("wire diameter must be > 0")
    return min(
        range(8, 41), key=lambda awg: abs(awg_diameter_mm(awg) - diameter_mm)
    )


def air_coil_inductance_h(
    turns: int,
    diameter_mm: float,
    *,
    wire_diameter_mm: float,
    enamel_build_mm: float = 0.0,
) -> float:
    """Wheeler inductance (henries) for a close-wound single-layer solenoid."""
    if turns < 1:
        raise AirCoilError("turns must be >= 1")
    if diameter_mm <= 0.0:
        raise AirCoilError("diameter must be > 0")
    if wire_diameter_mm <= 0.0:
        raise AirCoilError("wire diameter must be > 0")
    if enamel_build_mm < 0.0:
        raise AirCoilError("enamel build must be >= 0")
    diameter_in = diameter_mm / _MM_PER_INCH
    pitch_in = (wire_diameter_mm + enamel_build_mm) / _MM_PER_INCH
    radius = diameter_in / 2.0
    length = turns * pitch_in
    return 1e-6 * (radius * radius * turns * turns) / (
        9.0 * radius + 10.0 * length
    )


@dataclass(frozen=True, slots=True)
class AirCoilDesign:
    """Result of a single-layer air-core design.

    ``wire_diameter_mm`` is the **bare copper** diameter; ``overall_diameter_mm``
    includes the enamel and is what sets the winding pitch. ``awg`` is the
    nearest standard gauge for reference.
    """

    diameter_mm: float
    awg: int
    wire_diameter_mm: float
    enamel_build_mm: float
    overall_diameter_mm: float
    turns_exact: float
    turns: int
    turns_below: int
    inductance_h: float
    inductance_below_h: float
    target_inductance_h: float | None
    length_mm: float
    length_to_diameter: float
    wire_length_m: float
    resistance_ohm: float

    @property
    def short_coil(self) -> bool:
        """True when the winding is short enough for Wheeler's formula to drift."""
        return self.length_to_diameter < 0.2


def design_air_coil(
    *,
    diameter_mm: float,
    awg: int | None = None,
    wire_diameter_mm: float | None = None,
    enamel_build_mm: float | None = None,
    inductance_h: float | None = None,
    turns: int | None = None,
) -> AirCoilDesign:
    """Design a close-wound air-core solenoid from a target L or a fixed turn count.

    Specify the wire either by ``awg`` or by ``wire_diameter_mm`` (exactly one).
    ``enamel_build_mm`` defaults to the typical grade-1 enamelled build; pass
    ``0.0`` for bare wire. With a target, the turn count is rounded **up** so the
    achieved inductance is at least the requested value.
    """
    if diameter_mm <= 0.0:
        raise AirCoilError("diameter must be > 0")
    if (awg is None) == (wire_diameter_mm is None):
        raise AirCoilError("supply exactly one of awg or wire_diameter_mm")
    if (inductance_h is None) == (turns is None):
        raise AirCoilError("supply exactly one of inductance_h or turns")

    if wire_diameter_mm is None:
        assert awg is not None
        if not 8 <= awg <= 40:
            raise AirCoilError("AWG must be between 8 and 40")
        wire_mm = awg_diameter_mm(awg)
        awg_ref = int(awg)
    else:
        if wire_diameter_mm <= 0.0:
            raise AirCoilError("wire diameter must be > 0")
        wire_mm = float(wire_diameter_mm)
        awg_ref = awg_for_diameter_mm(wire_mm)

    if enamel_build_mm is None:
        build_mm = enamel_overall_diameter_mm(wire_mm) - wire_mm
    else:
        if enamel_build_mm < 0.0:
            raise AirCoilError("enamel build must be >= 0")
        build_mm = float(enamel_build_mm)
    overall_mm = wire_mm + build_mm

    radius_in = diameter_mm / _MM_PER_INCH / 2.0
    pitch_in = overall_mm / _MM_PER_INCH

    if turns is None:
        assert inductance_h is not None
        if inductance_h <= 0.0:
            raise AirCoilError("inductance must be > 0")
        target_u_h = inductance_h * 1e6
        # a^2 N^2 - 10 L p N - 9 a L = 0 (L in uH, a/p in inches)
        b = 10.0 * target_u_h * pitch_in
        c = 9.0 * radius_in * target_u_h
        disc = b * b + 4.0 * radius_in * radius_in * c
        exact = (b + math.sqrt(disc)) / (2.0 * radius_in * radius_in)
        count = max(1, math.ceil(exact - 1e-9))
        target: float | None = inductance_h
    else:
        if turns < 1:
            raise AirCoilError("turns must be >= 1")
        count = int(turns)
        exact = float(count)
        target = None

    achieved = air_coil_inductance_h(
        count,
        diameter_mm,
        wire_diameter_mm=wire_mm,
        enamel_build_mm=build_mm,
    )
    below = max(1, math.floor(exact))
    if below >= count:
        below = count
    below_h = air_coil_inductance_h(
        below,
        diameter_mm,
        wire_diameter_mm=wire_mm,
        enamel_build_mm=build_mm,
    )
    length_mm = count * overall_mm
    length_to_diameter = length_mm / diameter_mm
    wire_length_m = count * math.pi * diameter_mm / 1000.0
    area_m2 = math.pi * (wire_mm / 1000.0 / 2.0) ** 2
    resistance = COPPER_RESISTIVITY_OHM_M * wire_length_m / area_m2

    return AirCoilDesign(
        diameter_mm=diameter_mm,
        awg=awg_ref,
        wire_diameter_mm=wire_mm,
        enamel_build_mm=build_mm,
        overall_diameter_mm=overall_mm,
        turns_exact=exact,
        turns=count,
        turns_below=below,
        inductance_h=achieved,
        inductance_below_h=below_h,
        target_inductance_h=target,
        length_mm=length_mm,
        length_to_diameter=length_to_diameter,
        wire_length_m=wire_length_m,
        resistance_ohm=resistance,
    )
