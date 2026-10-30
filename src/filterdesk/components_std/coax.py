"""Coaxial cable stub notch calculator with optional cable presets.

Loss tables are rounded typical datasheet values. Cable clones, connectors,
temperature and installation details can change the real result; use the
calculator as a starting point and verify with a VNA.
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass
from enum import StrEnum

_C0 = 299_792_458.0
#: Frequency grid for the typical cable-loss tables (Hz).
_LOSS_FREQ_HZ = (
    10e6,
    50e6,
    100e6,
    150e6,
    450e6,
    1000e6,
    2500e6,
)


class CoaxStubError(ValueError):
    """Raised for an invalid coaxial-stub design request."""


class CoaxStubKind(StrEnum):
    """Notch stub type: open λ/4 or shorted λ/2."""

    OPEN_QUARTER = "open_quarter"
    SHORT_HALF = "short_half"


@dataclass(frozen=True, slots=True)
class CoaxCable:
    """Typical coaxial cable data (rounded datasheet values)."""

    name: str
    z0_ohm: float
    velocity_factor: float
    loss_db_per_100m: tuple[float, ...]

    def loss_db_per_m(self, frequency_hz: float) -> float:
        """Interpolate loss (dB/m) on a log-log frequency grid."""
        if frequency_hz <= 0.0:
            raise CoaxStubError("frequency must be > 0")
        if len(self.loss_db_per_100m) != len(_LOSS_FREQ_HZ):
            raise CoaxStubError("invalid loss table")
        x = math.log10(frequency_hz)
        xs = [math.log10(f) for f in _LOSS_FREQ_HZ]
        ys = [math.log10(max(value, 1e-12)) for value in self.loss_db_per_100m]
        if x <= xs[0]:
            loss = self.loss_db_per_100m[0]
        elif x >= xs[-1]:
            loss = self.loss_db_per_100m[-1]
        else:
            index = next(i for i in range(1, len(xs)) if x <= xs[i])
            t = (x - xs[index - 1]) / (xs[index] - xs[index - 1])
            loss = 10.0 ** (ys[index - 1] + t * (ys[index] - ys[index - 1]))
        return loss / 100.0


COAX_CABLES: tuple[CoaxCable, ...] = (
    CoaxCable(
        "RG-58",
        50.0,
        0.66,
        (4.9, 12.1, 17.7, 22.0, 44.0, 74.8, 130.0),
    ),
    CoaxCable(
        "RG-8X",
        50.0,
        0.66,
        (3.3, 8.9, 12.4, 15.0, 29.0, 49.0, 85.0),
    ),
    CoaxCable(
        "RG-213",
        50.0,
        0.66,
        (2.0, 4.9, 6.9, 8.4, 15.2, 26.9, 50.0),
    ),
    CoaxCable(
        "RG-174",
        50.0,
        0.66,
        (7.2, 20.0, 30.0, 36.0, 60.0, 103.0, 180.0),
    ),
    CoaxCable(
        "RG-316",
        50.0,
        0.69,
        (6.9, 19.0, 28.0, 33.0, 56.0, 98.0, 160.0),
    ),
    CoaxCable(
        "LMR-400",
        50.0,
        0.85,
        (1.2, 2.8, 4.1, 5.0, 9.2, 13.5, 22.3),
    ),
    CoaxCable(
        "LMR-600",
        50.0,
        0.87,
        (0.7, 1.7, 2.5, 3.0, 5.7, 10.2, 17.0),
    ),
)


def find_coax_cable(name: str) -> CoaxCable:
    key = name.strip().upper()
    for cable in COAX_CABLES:
        if cable.name.upper() == key:
            return cable
    raise CoaxStubError(f"unknown coax cable {name!r}")


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
    cable: CoaxCable | None = None

    @property
    def loss_db(self) -> float:
        return self.loss_db_per_m * self.length_m

    @property
    def notch_frequency_hz(self) -> float:
        return self.frequency_hz

    def loss_at(self, frequency_hz: float) -> float:
        if self.cable is not None:
            return self.cable.loss_db_per_m(frequency_hz)
        return self.loss_db_per_m


@dataclass(frozen=True, slots=True)
class CoaxStubResponse:
    """Estimated frequency response of a shunt coax notch stub."""

    frequency_hz: tuple[float, ...]
    s21_db: tuple[float, ...]
    s11_db: tuple[float, ...]
    notch_depth_db: float
    bandwidth_3db_hz: float | None
    loaded_q: float | None
    line_z0_ohm: float


def _stub_zin(design: CoaxStubDesign, frequency_hz: float) -> complex:
    loss_np_m = design.loss_at(frequency_hz) / 8.686
    beta = 2.0 * math.pi * frequency_hz / (
        design.velocity_factor * _C0
    )
    gl = complex(loss_np_m * design.length_m, beta * design.length_m)
    if design.kind is CoaxStubKind.OPEN_QUARTER:
        value = cmath.cosh(gl) / cmath.sinh(gl)
    else:
        value = cmath.sinh(gl) / cmath.cosh(gl)
    return design.z0_ohm * value


def _db(value: complex) -> float:
    magnitude = max(abs(value), 1e-15)
    return 20.0 * math.log10(magnitude)


def coax_stub_response(
    design: CoaxStubDesign,
    *,
    line_z0_ohm: float = 50.0,
    points: int = 1001,
) -> CoaxStubResponse:
    """Estimate S21/S11 for a shunt stub across a line of ``line_z0_ohm``.

    The model is ideal TEM plus the cable loss table; connectors, open-end
    capacitance and radiation are not included.
    """
    if line_z0_ohm <= 0.0:
        raise CoaxStubError("line Z0 must be > 0")
    if points < 9:
        raise CoaxStubError("points must be >= 9")
    f0 = design.frequency_hz
    freqs = tuple(
        f0 * (0.5 + index / (points - 1))
        for index in range(points)
    )
    s21: list[float] = []
    s11: list[float] = []
    for frequency in freqs:
        zin = _stub_zin(design, frequency)
        denom = 2.0 * zin + line_z0_ohm
        if abs(denom) < 1e-18:
            s21.append(-300.0)
            s11.append(0.0)
        else:
            s21.append(_db(2.0 * zin / denom))
            s11.append(_db(-line_z0_ohm / denom))
    center = points // 2
    notch_depth = max(0.0, -min(s21))
    threshold = -3.0
    if s21[center] > threshold:
        bandwidth = None
    else:
        left = center
        while left > 0 and s21[left - 1] <= threshold:
            left -= 1
        right = center
        while right < points - 1 and s21[right + 1] <= threshold:
            right += 1
        bandwidth = (
            freqs[right] - freqs[left]
            if left > 0 and right < points - 1
            else None
        )
    loaded_q = f0 / bandwidth if bandwidth and bandwidth > 0.0 else None
    return CoaxStubResponse(
        frequency_hz=freqs,
        s21_db=tuple(s21),
        s11_db=tuple(s11),
        notch_depth_db=notch_depth,
        bandwidth_3db_hz=bandwidth,
        loaded_q=loaded_q,
        line_z0_ohm=line_z0_ohm,
    )


def design_coax_stub(
    z0_ohm: float,
    frequency_hz: float,
    velocity_factor: float,
    *,
    kind: CoaxStubKind | str = CoaxStubKind.OPEN_QUARTER,
    loss_db_per_m: float = 0.0,
    cable: CoaxCable | str | None = None,
) -> CoaxStubDesign:
    """Design a shunt coaxial stub whose input is a short at the notch.

    An open stub is λ/4 long; a shorted stub is λ/2 long. When ``cable`` is
    supplied it overrides Z0/vf and supplies a frequency-dependent loss table;
    explicit ``loss_db_per_m`` remains available for the custom case.
    """
    cable_value = find_coax_cable(cable) if isinstance(cable, str) else cable
    if cable_value is not None:
        z0_ohm = cable_value.z0_ohm
        velocity_factor = cable_value.velocity_factor
        loss_db_per_m = cable_value.loss_db_per_m(frequency_hz)
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
        cable=cable_value,
    )


__all__ = [
    "COAX_CABLES",
    "CoaxCable",
    "CoaxStubDesign",
    "CoaxStubError",
    "CoaxStubKind",
    "CoaxStubResponse",
    "coax_stub_response",
    "design_coax_stub",
    "find_coax_cable",
]
