"""Symmetric resistive attenuator design (T and Pi pads) — Phase 12."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AttenuatorKind(StrEnum):
    TEE = "t"
    PI = "pi"


class AttenuatorError(ValueError):
    """Raised for an invalid attenuator request."""


@dataclass(frozen=True, slots=True)
class AttenuatorDesign:
    kind: AttenuatorKind
    attenuation_db: float
    z0_ohm: float
    r_series_ohm: float
    """T: the two series resistors; Pi: the middle series resistor."""
    r_shunt_ohm: float
    """T: the middle shunt resistor; Pi: the two shunt resistors."""


def design_attenuator(
    attenuation_db: float,
    z0_ohm: float = 50.0,
    kind: AttenuatorKind = AttenuatorKind.TEE,
) -> AttenuatorDesign:
    """Symmetric T/Pi pad resistor values for ``attenuation_db`` at ``z0_ohm``."""
    if attenuation_db <= 0.0:
        raise AttenuatorError("attenuation_db must be > 0")
    if z0_ohm <= 0.0:
        raise AttenuatorError("z0_ohm must be > 0")
    k = 10.0 ** (attenuation_db / 20.0)  # voltage ratio
    if kind == AttenuatorKind.TEE:
        r_series = z0_ohm * (k - 1.0) / (k + 1.0)
        r_shunt = z0_ohm * (2.0 * k) / (k * k - 1.0)
    else:
        r_series = z0_ohm * (k * k - 1.0) / (2.0 * k)
        r_shunt = z0_ohm * (k + 1.0) / (k - 1.0)
    return AttenuatorDesign(
        kind=kind,
        attenuation_db=attenuation_db,
        z0_ohm=z0_ohm,
        r_series_ohm=r_series,
        r_shunt_ohm=r_shunt,
    )


__all__ = ["AttenuatorDesign", "AttenuatorError", "AttenuatorKind", "design_attenuator"]
