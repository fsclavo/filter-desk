"""Single-layer air-core solenoid calculator (Phase 12).

Close-wound solenoid using Wheeler's formula (a = radius, b = length, both in
inches)::

    L[uH] = a^2 * N^2 / (9a + 10b)

with ``b = N * d`` (bare wire diameter). The model assumes a single close-wound
layer and uniform winding; it does **not** model self-capacitance / SRF, AC
resistance or Q, so treat the result as a starting point for HF work.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from filterdesk.components_std.toroid import awg_diameter_mm

__all__ = [
    "COPPER_RESISTIVITY_OHM_M",
    "AirCoilDesign",
    "AirCoilError",
    "air_coil_inductance_h",
    "awg_for_diameter_mm",
    "design_air_coil",
]

#: Copper resistivity at 20 °C (ohm·m).
COPPER_RESISTIVITY_OHM_M = 1.724e-8

_MM_PER_INCH = 25.4


class AirCoilError(ValueError):
    """Raised for invalid air-core coil inputs."""


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
) -> float:
    """Wheeler inductance (henries) for a close-wound single-layer solenoid."""
    if turns < 1:
        raise AirCoilError("turns must be >= 1")
    if diameter_mm <= 0.0:
        raise AirCoilError("diameter must be > 0")
    if wire_diameter_mm <= 0.0:
        raise AirCoilError("wire diameter must be > 0")
    diameter_in = diameter_mm / _MM_PER_INCH
    wire_in = wire_diameter_mm / _MM_PER_INCH
    radius = diameter_in / 2.0
    length = turns * wire_in
    return 1e-6 * (radius * radius * turns * turns) / (
        9.0 * radius + 10.0 * length
    )


@dataclass(frozen=True, slots=True)
class AirCoilDesign:
    """Result of a single-layer air-core design.

    ``awg`` is the nearest standard gauge for reference; the exact wire size is
    always ``wire_diameter_mm`` (so a custom millimetre diameter is honoured).
    """

    diameter_mm: float
    awg: int
    wire_diameter_mm: float
    turns_exact: float
    turns: int
    inductance_h: float
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
    inductance_h: float | None = None,
    turns: int | None = None,
) -> AirCoilDesign:
    """Design a close-wound air-core solenoid from a target L or a fixed turn count.

    Specify the wire either by ``awg`` or by ``wire_diameter_mm`` (exactly one).
    With a target, the turn count is rounded **up** so the achieved inductance is
    at least the requested value.
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
    radius_in = diameter_mm / _MM_PER_INCH / 2.0
    wire_in = wire_mm / _MM_PER_INCH

    if turns is None:
        assert inductance_h is not None
        if inductance_h <= 0.0:
            raise AirCoilError("inductance must be > 0")
        target_u_h = inductance_h * 1e6
        # a^2 N^2 - 10 L d N - 9 a L = 0 (L in uH, a/d in inches)
        b = 10.0 * target_u_h * wire_in
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
        count, diameter_mm, wire_diameter_mm=wire_mm
    )
    length_mm = count * wire_mm
    length_to_diameter = length_mm / diameter_mm
    wire_length_m = count * math.pi * diameter_mm / 1000.0
    area_m2 = math.pi * (wire_mm / 1000.0 / 2.0) ** 2
    resistance = COPPER_RESISTIVITY_OHM_M * wire_length_m / area_m2

    return AirCoilDesign(
        diameter_mm=diameter_mm,
        awg=awg_ref,
        wire_diameter_mm=wire_mm,
        turns_exact=exact,
        turns=count,
        inductance_h=achieved,
        target_inductance_h=target,
        length_mm=length_mm,
        length_to_diameter=length_to_diameter,
        wire_length_m=wire_length_m,
        resistance_ohm=resistance,
    )
