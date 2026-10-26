"""Toroid turn / wire / saturation calculator (Phase 12).

Inductance follows ``L = AL * N^2`` with ``AL`` in nH/N². The built-in core
table holds typical Amidon values (iron powder mixes 2/6/10 and ferrite 43);
AL has a batch spread of roughly ±20–25 %, so treat results as a starting point
and check the core datasheet. Geometric ``Ae`` and mean turn length are derived
from the catalog dimensions (coating ignored).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "CORES",
    "WINDING_FILL",
    "ToroidCore",
    "ToroidDesign",
    "ToroidError",
    "WireFit",
    "awg_diameter_mm",
    "design_toroid",
    "find_core",
    "flux_density_t",
    "inductance_for_turns",
    "list_cores",
    "make_custom_core",
    "turns_for_inductance",
    "wire_fit",
]

#: Fraction of the inner circumference available for a single-layer winding.
WINDING_FILL = 0.85


class ToroidError(ValueError):
    """Raised for invalid core, inductance, turns or current values."""


@dataclass(frozen=True, slots=True)
class ToroidCore:
    """A catalog toroid: AL in nH/N², dimensions in mm, optional Bsat in tesla."""

    name: str
    material: str
    kind: str
    color: str
    al_nh: float
    od_mm: float
    id_mm: float
    height_mm: float
    bsat_t: float | None = None

    @property
    def ae_mm2(self) -> float:
        """Effective cross-section estimate from the rectangular core profile."""
        return self.height_mm * (self.od_mm - self.id_mm) / 2.0

    @property
    def mean_turn_mm(self) -> float:
        """Approximate wire length per turn (rectangular cross-section perimeter)."""
        return 2.0 * self.height_mm + (self.od_mm - self.id_mm)

    @property
    def volume_cm3(self) -> float:
        """Approximate magnetic volume from mean path and geometric Ae."""
        if self.od_mm <= 0.0 or self.id_mm <= 0.0:
            return 0.0
        mean_path_mm = math.pi * (self.od_mm + self.id_mm) / 2.0
        return mean_path_mm * self.ae_mm2 / 1000.0


def _core(
    name: str,
    material: str,
    kind: str,
    color: str,
    al_nh: float,
    od_mm: float,
    id_mm: float,
    height_mm: float,
    bsat_t: float | None = None,
) -> ToroidCore:
    return ToroidCore(
        name=name,
        material=material,
        kind=kind,
        color=color,
        al_nh=al_nh,
        od_mm=od_mm,
        id_mm=id_mm,
        height_mm=height_mm,
        bsat_t=bsat_t,
    )


#: Common Amidon/Fair-Rite cores. AL from the vendor tables (nH/N²); powder
#: mixes 2/6/10 and ferrite mixes 31/43/52/61. AL is specified with roughly
#: ±20–25 % tolerance. Ferrite Bsat is a room-temperature typical value; derate
#: with temperature and DC bias. Large 43/61 cores cover HF power transformers;
#: 31 is aimed at low-HF common-mode chokes and 52 at wideband/high-power use.
CORES: tuple[ToroidCore, ...] = (
    _core("T37-2", "2", "iron_powder", "red", 4.0, 9.53, 5.21, 3.25),
    _core("T50-2", "2", "iron_powder", "red", 4.9, 12.70, 7.70, 4.83),
    _core("T68-2", "2", "iron_powder", "red", 5.7, 17.53, 9.40, 4.83),
    _core("T80-2", "2", "iron_powder", "red", 5.5, 20.19, 12.57, 6.35),
    _core("T106-2", "2", "iron_powder", "red", 13.5, 26.92, 14.48, 11.10),
    _core("T37-6", "6", "iron_powder", "yellow", 3.0, 9.53, 5.21, 3.25),
    _core("T50-6", "6", "iron_powder", "yellow", 4.0, 12.70, 7.62, 4.83),
    _core("T68-6", "6", "iron_powder", "yellow", 4.7, 17.53, 9.40, 4.83),
    _core("T80-6", "6", "iron_powder", "yellow", 4.5, 20.19, 12.57, 6.35),
    _core("T37-10", "10", "iron_powder", "black", 2.5, 9.53, 5.21, 3.25),
    _core("T50-10", "10", "iron_powder", "black", 3.1, 12.70, 7.62, 4.83),
    _core("T68-10", "10", "iron_powder", "black", 3.2, 17.53, 9.40, 4.83),
    _core("T80-10", "10", "iron_powder", "black", 3.2, 20.19, 12.57, 6.35),
    _core("FT37-43", "43", "ferrite", "black", 350.0, 9.53, 4.75, 3.18, 0.295),
    _core("FT50-43", "43", "ferrite", "black", 440.0, 12.70, 7.14, 4.78, 0.295),
    _core("FT82-43", "43", "ferrite", "black", 470.0, 20.96, 13.21, 6.35, 0.295),
    # 31/52 AL values for the smaller/extra sizes are scaled from the
    # same-size 43 core using the vendor μi ratio; verify the exact batch
    # before production (the 240-31 value is from the Amidon table).
    _core("FT114-31", "31", "ferrite", "gray/blue", 956.0, 29.01, 19.00, 7.49, 0.360),
    _core("FT140-31", "31", "ferrite", "gray/blue", 1659.0, 35.56, 22.86, 12.70, 0.360),
    _core("FT114-43", "43", "ferrite", "black", 510.0, 29.01, 19.00, 7.49, 0.295),
    _core("FT140-43", "43", "ferrite", "black", 885.0, 35.56, 22.86, 12.70, 0.295),
    _core("FT240-43", "43", "ferrite", "black", 1075.0, 60.96, 35.56, 12.70, 0.295),
    _core("FT290-43", "43", "ferrite", "black", 1300.0, 73.66, 38.86, 12.70, 0.295),
    _core("FT114-61", "61", "ferrite", "gray", 80.0, 29.01, 19.00, 7.49, 0.250),
    _core("FT140-61", "61", "ferrite", "gray", 140.0, 35.56, 22.86, 12.70, 0.250),
    _core("FT240-61", "61", "ferrite", "gray", 170.0, 60.96, 35.56, 12.70, 0.250),
    _core("FT350-61", "61", "ferrite", "gray", 178.0, 88.90, 50.80, 12.70, 0.250),
    _core("FT114-52", "52", "ferrite", "gray", 160.0, 29.01, 19.00, 7.49, 0.420),
    _core("FT140-52", "52", "ferrite", "gray", 283.0, 35.25, 22.60, 12.70, 0.420),
    _core("FT240-52", "52", "ferrite", "gray", 325.0, 61.00, 35.55, 12.70, 0.420),
    _core("FT240-31", "31", "ferrite", "gray/blue", 2053.0, 61.00, 35.55, 12.70, 0.360),
)


def _norm(name: str) -> str:
    return "".join(ch for ch in name.upper() if ch.isalnum())


_CORE_BY_NAME: dict[str, ToroidCore] = {_norm(core.name): core for core in CORES}


def list_cores() -> tuple[ToroidCore, ...]:
    """Return the built-in core table."""
    return CORES


def find_core(name: str) -> ToroidCore:
    """Look up a built-in core by name (case and dashes are ignored)."""
    try:
        return _CORE_BY_NAME[_norm(name)]
    except KeyError:
        raise ToroidError(
            f"unknown core {name!r}; use --list to see the table"
        ) from None


def make_custom_core(
    name: str,
    al_nh: float,
    *,
    od_mm: float = 0.0,
    id_mm: float = 0.0,
    height_mm: float = 0.0,
    bsat_t: float | None = None,
) -> ToroidCore:
    """Build a custom core; leave dimensions at 0 when they are unknown."""
    if al_nh <= 0.0:
        raise ToroidError("AL must be > 0")
    if od_mm < 0.0 or id_mm < 0.0 or height_mm < 0.0:
        raise ToroidError("core dimensions must be >= 0")
    if (od_mm or id_mm or height_mm) and not (
        od_mm > id_mm > 0.0 and height_mm > 0.0
    ):
        raise ToroidError("need OD > ID > 0 and H > 0 when dimensions are supplied")
    return ToroidCore(
        name=name or "custom",
        material="?",
        kind="custom",
        color="?",
        al_nh=al_nh,
        od_mm=od_mm,
        id_mm=id_mm,
        height_mm=height_mm,
        bsat_t=bsat_t,
    )


def turns_for_inductance(inductance_h: float, al_nh: float) -> float:
    """Exact (non-integer) turn count for a target inductance."""
    if inductance_h <= 0.0:
        raise ToroidError("inductance must be > 0")
    if al_nh <= 0.0:
        raise ToroidError("AL must be > 0")
    return math.sqrt(inductance_h * 1e9 / al_nh)


def inductance_for_turns(turns: float, al_nh: float) -> float:
    """Inductance in henries for a (possibly fractional) turn count."""
    if turns <= 0.0:
        raise ToroidError("turns must be > 0")
    if al_nh <= 0.0:
        raise ToroidError("AL must be > 0")
    return al_nh * turns * turns * 1e-9


def awg_diameter_mm(awg: int) -> float:
    """Bare copper diameter for an AWG size (8–40) in millimetres."""
    if not 0 <= awg <= 40:
        raise ToroidError("AWG must be between 0 and 40")
    return float(25.4 * 0.005 * 92.0 ** ((36.0 - awg) / 39.0))


@dataclass(frozen=True, slots=True)
class WireFit:
    """Recommended single-layer wire for a given core and turn count."""

    max_diameter_mm: float
    awg: int | None
    diameter_mm: float | None
    fill_ratio: float | None

    @property
    def fits(self) -> bool:
        return self.awg is not None


def wire_fit(core: ToroidCore, turns: int) -> WireFit:
    """Pick the thickest AWG that fits one layer through the inner diameter."""
    if turns < 1:
        raise ToroidError("turns must be >= 1")
    if core.id_mm <= 0.0:
        return WireFit(0.0, None, None, None)
    max_d = WINDING_FILL * math.pi * core.id_mm / turns
    for awg in range(8, 41):
        diameter = awg_diameter_mm(awg)
        if diameter <= max_d:
            fill = turns * diameter / (math.pi * core.id_mm)
            return WireFit(max_d, awg, diameter, fill)
    return WireFit(max_d, None, None, None)


def flux_density_t(
    inductance_h: float,
    current_a: float,
    turns: int,
    ae_m2: float,
) -> float:
    """Peak flux density ``B = L*I / (N*Ae)`` in tesla."""
    if inductance_h <= 0.0 or current_a <= 0.0 or turns < 1 or ae_m2 <= 0.0:
        raise ToroidError("invalid inductance/current/turns/area")
    return inductance_h * current_a / (turns * ae_m2)


@dataclass(frozen=True, slots=True)
class ToroidDesign:
    """Result of a toroid design (integer turns, wire fit, optional saturation)."""

    core: ToroidCore
    turns_exact: float
    turns: int
    inductance_h: float
    target_inductance_h: float | None
    wire: WireFit
    wire_length_m: float
    flux_density_t: float | None
    saturation_ratio: float | None

    @property
    def saturation_margin(self) -> float | None:
        if self.saturation_ratio is None or self.saturation_ratio <= 0.0:
            return None
        return 1.0 / self.saturation_ratio

    @property
    def saturated(self) -> bool:
        return self.saturation_ratio is not None and self.saturation_ratio > 1.0


def design_toroid(
    core: ToroidCore,
    *,
    inductance_h: float | None = None,
    turns: int | None = None,
    current_a: float = 0.0,
) -> ToroidDesign:
    """Design a winding from a target inductance or a fixed turn count.

    With a target, the recommended turn count is rounded **up** so the achieved
    inductance is at least the requested value.
    """
    if (inductance_h is None) == (turns is None):
        raise ToroidError("supply exactly one of inductance_h or turns")
    if current_a < 0.0:
        raise ToroidError("current must be >= 0")

    if turns is None:
        assert inductance_h is not None
        exact = turns_for_inductance(inductance_h, core.al_nh)
        count = max(1, math.ceil(exact - 1e-9))
        target: float | None = inductance_h
    else:
        if turns < 1:
            raise ToroidError("turns must be >= 1")
        count = int(turns)
        exact = float(count)
        target = None

    achieved = inductance_for_turns(count, core.al_nh)
    wire = wire_fit(core, count)
    wire_length_m = count * core.mean_turn_mm / 1000.0

    flux: float | None = None
    ratio: float | None = None
    if current_a > 0.0 and core.ae_mm2 > 0.0:
        flux = flux_density_t(achieved, current_a, count, core.ae_mm2 * 1e-6)
        if core.bsat_t is not None and core.bsat_t > 0.0:
            ratio = flux / core.bsat_t

    return ToroidDesign(
        core=core,
        turns_exact=exact,
        turns=count,
        inductance_h=achieved,
        target_inductance_h=target,
        wire=wire,
        wire_length_m=wire_length_m,
        flux_density_t=flux,
        saturation_ratio=ratio,
    )
