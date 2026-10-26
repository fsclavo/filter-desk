"""First-order microstrip line, stub and quarter-wave transformer design.

Uses the Hammerstad-Jensen closed-form quasi-static model for Z0 and effective
permittivity. Conductor loss uses surface resistance with a skin-depth/thickness
term; dielectric loss uses the standard quasi-static formula. Finite strip
thickness is not included in Z0, and discontinuity/radiation losses are ignored.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

ETA0 = 376.730313668
C0 = 299_792_458.0
MU0 = 4.0e-7 * math.pi
SIGMA_CU = 5.8e7


class MicrostripError(ValueError):
    """Raised for an invalid microstrip design request."""


@dataclass(frozen=True, slots=True)
class Substrate:
    name: str
    er: float
    h_mm: float
    tan_delta: float = 0.0
    t_mm: float = 0.035
    roughness_um: float = 1.0


_SUBSTRATES: tuple[Substrate, ...] = (
    Substrate("FR4", 4.4, 1.6, 0.020, 0.035, 1.5),
    Substrate("RO4350B", 3.66, 0.762, 0.0037, 0.035, 1.0),
    Substrate("RO4003C", 3.55, 0.813, 0.0027, 0.035, 1.0),
    Substrate("PTFE", 2.20, 0.508, 0.0009, 0.035, 0.5),
    Substrate("Alumina", 9.8, 0.635, 0.0001, 0.010, 0.2),
    Substrate("Air", 1.0, 1.0, 0.0, 0.0, 0.0),
)


def list_substrates() -> tuple[Substrate, ...]:
    return _SUBSTRATES


def find_substrate(name: str) -> Substrate:
    needle = name.strip().lower()
    for substrate in _SUBSTRATES:
        if substrate.name.lower() == needle:
            return substrate
    names = [s.name for s in _SUBSTRATES]
    raise MicrostripError(f"unknown substrate {name!r}; choose from {names}")


def _validate_substrate(substrate: Substrate) -> None:
    if substrate.er < 1.0:
        raise MicrostripError("substrate er must be >= 1")
    if substrate.h_mm <= 0.0:
        raise MicrostripError("substrate height must be > 0")
    if substrate.tan_delta < 0.0:
        raise MicrostripError("tan_delta must be >= 0")
    if substrate.t_mm < 0.0 or substrate.roughness_um < 0.0:
        raise MicrostripError("thickness / roughness must be >= 0")


def _z0_eeff(wh: float, er: float) -> tuple[float, float]:
    if wh <= 0.0:
        raise MicrostripError("W/h must be > 0")
    if wh <= 1.0:
        eeff = (er + 1.0) / 2.0 + (er - 1.0) / 2.0 * (
            1.0 / math.sqrt(1.0 + 12.0 / wh) + 0.04 * (1.0 - wh) ** 2
        )
        z0 = ETA0 / (2.0 * math.pi * math.sqrt(eeff)) * math.log(
            8.0 / wh + wh / 4.0
        )
    else:
        eeff = (er + 1.0) / 2.0 + (er - 1.0) / 2.0 / math.sqrt(1.0 + 12.0 / wh)
        z0 = ETA0 / math.sqrt(eeff) / (
            wh + 1.393 + 0.667 * math.log(wh + 1.444)
        )
    return z0, eeff


def microstrip_width_for_z0(
    z0_ohm: float, substrate: Substrate, *, tolerance: float = 1e-9
) -> float:
    """Synthesize the strip width (mm) for a target quasi-static Z0."""
    _validate_substrate(substrate)
    if z0_ohm <= 0.0:
        raise MicrostripError("Z0 must be > 0")
    lo, hi = 1e-6, 1e4
    if _z0_eeff(lo, substrate.er)[0] < z0_ohm:
        raise MicrostripError("Z0 too high for this substrate")
    if _z0_eeff(hi, substrate.er)[0] > z0_ohm:
        raise MicrostripError("Z0 too low for this substrate")
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        z0_mid, _ = _z0_eeff(mid, substrate.er)
        if z0_mid > z0_ohm:
            lo = mid
        else:
            hi = mid
        if hi - lo <= tolerance * max(lo, 1e-12):
            break
    return math.sqrt(lo * hi) * substrate.h_mm


@dataclass(frozen=True, slots=True)
class MicrostripLine:
    substrate: Substrate
    z0_ohm: float
    width_mm: float
    eeff: float
    wavelength_m: float
    frequency_hz: float
    length_m: float
    conductor_loss_db_per_m: float
    dielectric_loss_db_per_m: float

    @property
    def loss_db_per_m(self) -> float:
        return self.conductor_loss_db_per_m + self.dielectric_loss_db_per_m

    @property
    def quarter_wave_m(self) -> float:
        return self.wavelength_m / 4.0

    def loss_db(self, length_m: float | None = None) -> float:
        length = self.length_m if length_m is None else length_m
        return self.loss_db_per_m * length

    def electrical_length_deg(self, length_m: float | None = None) -> float:
        length = self.length_m if length_m is None else length_m
        return 360.0 * length / self.wavelength_m


def _losses(
    z0: float,
    width_m: float,
    eeff: float,
    substrate: Substrate,
    frequency_hz: float,
) -> tuple[float, float]:
    t_m = substrate.t_mm * 1e-3
    delta = math.sqrt(1.0 / (math.pi * frequency_hz * MU0 * SIGMA_CU))
    if t_m <= 0.0:
        conductor_np_m = 0.0
    else:
        t_eff = max(min(t_m, delta), 1e-9)
        roughness = 1.0 + (2.0 / math.pi) * math.atan(
            1.4 * ((substrate.roughness_um * 1e-6) / delta) ** 2
        )
        conductor_np_m = (1.0 / (SIGMA_CU * t_eff * width_m * 1e-3)) / (2.0 * z0)
        conductor_np_m *= roughness
    lambda0 = C0 / frequency_hz
    if substrate.er > 1.0:
        dielectric_np_m = (math.pi / lambda0) * (substrate.er / math.sqrt(eeff)) * (
            (eeff - 1.0) / (substrate.er - 1.0)
        ) * substrate.tan_delta
    else:
        dielectric_np_m = 0.0
    return conductor_np_m * 8.686, dielectric_np_m * 8.686


def design_microstrip(
    z0_ohm: float,
    substrate: Substrate,
    frequency_hz: float,
    *,
    length_m: float = 0.0,
) -> MicrostripLine:
    _validate_substrate(substrate)
    if frequency_hz <= 0.0:
        raise MicrostripError("frequency must be > 0")
    if length_m < 0.0:
        raise MicrostripError("length must be >= 0")
    width_mm = microstrip_width_for_z0(z0_ohm, substrate)
    wh = width_mm / substrate.h_mm
    z0, eeff = _z0_eeff(wh, substrate.er)
    wavelength = C0 / (frequency_hz * math.sqrt(eeff))
    conductor, dielectric = _losses(
        z0, width_mm, eeff, substrate, frequency_hz
    )
    return MicrostripLine(
        substrate=substrate,
        z0_ohm=z0,
        width_mm=width_mm,
        eeff=eeff,
        wavelength_m=wavelength,
        frequency_hz=frequency_hz,
        length_m=length_m,
        conductor_loss_db_per_m=conductor,
        dielectric_loss_db_per_m=dielectric,
    )


@dataclass(frozen=True, slots=True)
class QuarterWaveTransformer:
    z_low_ohm: float
    z_high_ohm: float
    line: MicrostripLine

    @property
    def z0_ohm(self) -> float:
        return self.line.z0_ohm


def design_quarter_wave_transformer(
    z_low_ohm: float,
    z_high_ohm: float,
    substrate: Substrate,
    frequency_hz: float,
) -> QuarterWaveTransformer:
    if z_low_ohm <= 0.0 or z_high_ohm <= 0.0:
        raise MicrostripError("impedances must be > 0")
    z0 = math.sqrt(z_low_ohm * z_high_ohm)
    base = design_microstrip(z0, substrate, frequency_hz)
    line = MicrostripLine(
        substrate=base.substrate,
        z0_ohm=base.z0_ohm,
        width_mm=base.width_mm,
        eeff=base.eeff,
        wavelength_m=base.wavelength_m,
        frequency_hz=base.frequency_hz,
        length_m=base.quarter_wave_m,
        conductor_loss_db_per_m=base.conductor_loss_db_per_m,
        dielectric_loss_db_per_m=base.dielectric_loss_db_per_m,
    )
    return QuarterWaveTransformer(z_low_ohm, z_high_ohm, line)


class StubKind(StrEnum):
    OPEN = "open"
    SHORT = "short"


@dataclass(frozen=True, slots=True)
class Stub:
    kind: StubKind
    line: MicrostripLine
    angle_deg: float

    def input_impedance_ohm(self) -> complex:
        theta = math.radians(self.angle_deg)
        if self.kind is StubKind.OPEN:
            tan = math.tan(theta)
            if abs(tan) < 1e-12:
                return complex(1e12, 0.0)
            return complex(0.0, -self.line.z0_ohm / tan)
        tan = math.tan(theta)
        if abs(tan) < 1e-12:
            return complex(0.0, 0.0)
        return complex(0.0, self.line.z0_ohm * tan)


def design_stub(
    z0_ohm: float,
    angle_deg: float,
    substrate: Substrate,
    frequency_hz: float,
    *,
    kind: StubKind | str = StubKind.OPEN,
) -> Stub:
    if not 0.0 < angle_deg <= 180.0:
        raise MicrostripError("stub angle must be in (0, 180] degrees")
    kind_value = StubKind(str(kind))
    base = design_microstrip(z0_ohm, substrate, frequency_hz)
    length = base.wavelength_m * angle_deg / 360.0
    line = MicrostripLine(
        substrate=base.substrate,
        z0_ohm=base.z0_ohm,
        width_mm=base.width_mm,
        eeff=base.eeff,
        wavelength_m=base.wavelength_m,
        frequency_hz=base.frequency_hz,
        length_m=length,
        conductor_loss_db_per_m=base.conductor_loss_db_per_m,
        dielectric_loss_db_per_m=base.dielectric_loss_db_per_m,
    )
    return Stub(kind=kind_value, line=line, angle_deg=angle_deg)


__all__ = [
    "MicrostripError",
    "MicrostripLine",
    "QuarterWaveTransformer",
    "Stub",
    "StubKind",
    "Substrate",
    "design_microstrip",
    "design_quarter_wave_transformer",
    "design_stub",
    "find_substrate",
    "list_substrates",
    "microstrip_width_for_z0",
]
