"""Coaxial cable stub notch calculator (TEM, ideal transmission line)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

_C0 = 299_792_458.0


class CoaxStubError(ValueError):
    """Raised for an invalid coaxial-stub design request."""


class CoaxStubKind(StrEnum):
    """Notch stub type: open λ/4 or shorted λ/2."""

    OPEN_QUARTER = "open_quarter"
    SHORT_HALF = "short_half"


@dataclass(frozen=True, slots=True)
class CoaxStubDesign:
    """Physical length and electrical data for a shunt coaxial notch stub."""

    frequency_hz: float
    z0_ohm: float
    velocity_factor: float
    kind: CoaxStubKind
    length_m: float
    wavelength_m: float
    electrical_length_deg: float
    loss_db_per_m: float

    @property
    def loss_db(self) -> float:
        return self.loss_db_per_m * self.length_m

    @property
    def notch_frequency_hz(self) -> float:
        """Frequency at which the shunt stub presents a short circuit."""
        return self.frequency_hz


def design_coax_stub(
    z0_ohm: float,
    frequency_hz: float,
    velocity_factor: float,
    *,
    kind: CoaxStubKind | str = CoaxStubKind.OPEN_QUARTER,
    loss_db_per_m: float = 0.0,
) -> CoaxStubDesign:
    """Design a shunt coaxial stub whose input is a short at the notch.

    An open stub is λ/4 long; a shorted stub is λ/2 long. Both formulas use the
    cable velocity factor and are intended for a narrowband notch, not a
    complete filter synthesis.
    """
    if not math.isfinite(z0_ohm) or z0_ohm <= 0.0:
        raise CoaxStubError("Z0 must be finite and > 0")
    if not math.isfinite(frequency_hz) or frequency_hz <= 0.0:
        raise CoaxStubError("frequency must be finite and > 0")
    if not math.isfinite(velocity_factor) or not 0.0 < velocity_factor <= 1.0:
        raise CoaxStubError("velocity factor must be in (0, 1]")
    if not math.isfinite(loss_db_per_m) or loss_db_per_m < 0.0:
        raise CoaxStubError("loss must be finite and >= 0")
    kind_value = CoaxStubKind(str(kind))
    angle = 90.0 if kind_value is CoaxStubKind.OPEN_QUARTER else 180.0
    wavelength = velocity_factor * _C0 / frequency_hz
    return CoaxStubDesign(
        frequency_hz=float(frequency_hz),
        z0_ohm=float(z0_ohm),
        velocity_factor=float(velocity_factor),
        kind=kind_value,
        length_m=wavelength * angle / 360.0,
        wavelength_m=wavelength,
        electrical_length_deg=angle,
        loss_db_per_m=float(loss_db_per_m),
    )


__all__ = [
    "CoaxStubDesign",
    "CoaxStubError",
    "CoaxStubKind",
    "design_coax_stub",
]
