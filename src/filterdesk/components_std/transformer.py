"""Transformer / unun / balun calculator on top of the toroid core table.

The model is an ideal transformer of impedance ratio ``R_high/R_low``:
turns ratio ``n = sqrt(R_high/R_low)``. The low-impedance winding is sized so
the magnetizing reactance at the lowest frequency is at least ``k * R_low``.
Flux density and wire gauges are first-order checks; verify against the core
datasheet and the winding layout.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from filterdesk.components_std.toroid import (
    ToroidCore,
    WireFit,
    awg_diameter_mm,
    wire_fit,
)


class TransformerError(ValueError):
    """Raised for an invalid transformer design request."""


class TransformerKind(StrEnum):
    TRANSFORMER = "transformer"
    UNUN = "unun"
    BALUN = "balun"


@dataclass(frozen=True, slots=True)
class TransformerDesign:
    core: ToroidCore
    kind: TransformerKind
    z_low_ohm: float
    z_high_ohm: float
    impedance_ratio: float
    turns_ratio: float
    n_low: int
    n_high: int
    actual_impedance_ratio: float
    magnetizing_inductance_h: float
    v_low_rms: float
    v_high_rms: float
    i_low_rms_a: float
    i_high_rms_a: float
    b_peak_t: float | None
    bsat_margin: float | None
    awg_low: int | None
    awg_high: int | None
    fit: WireFit
    notes: tuple[str, ...]

    @property
    def saturated(self) -> bool:
        return self.bsat_margin is not None and self.bsat_margin < 1.0


def _awg_for_area(area_mm2: float) -> int | None:
    """Thinnest AWG whose copper area meets ``area_mm2``."""
    for awg in range(40, 7, -1):
        d = awg_diameter_mm(awg)
        if math.pi * (d / 2.0) ** 2 >= area_mm2:
            return awg
    return None


def design_transformer(
    core: ToroidCore,
    *,
    z_low_ohm: float,
    z_high_ohm: float,
    frequency_hz: float,
    power_w: float,
    kind: TransformerKind | str = TransformerKind.UNUN,
    reactance_factor: float = 4.0,
    current_density_a_mm2: float = 4.0,
) -> TransformerDesign:
    """Design a transformer-type unun/balun (ideal impedance transformation)."""
    if z_low_ohm <= 0.0 or z_high_ohm <= 0.0:
        raise TransformerError("impedances must be > 0")
    if z_high_ohm < z_low_ohm:
        raise TransformerError("z_high must be >= z_low")
    if frequency_hz <= 0.0:
        raise TransformerError("frequency must be > 0")
    if power_w <= 0.0:
        raise TransformerError("power must be > 0")
    if reactance_factor <= 0.0 or current_density_a_mm2 <= 0.0:
        raise TransformerError("reactance factor / current density must be > 0")
    if core.ae_mm2 <= 0.0:
        raise TransformerError("core dimensions are required for a transformer")

    kind_value = TransformerKind(str(kind))
    ratio = z_high_ohm / z_low_ohm
    turns = math.sqrt(ratio)
    al_h = core.al_nh * 1e-9
    n_low_min = math.sqrt(
        reactance_factor * z_low_ohm / (2.0 * math.pi * frequency_hz * al_h)
    )
    n_low = max(1, math.ceil(n_low_min - 1e-9))
    n_high = max(1, round(turns * n_low))
    actual_ratio = (n_high / n_low) ** 2

    lm = al_h * n_low * n_low
    v_low = math.sqrt(power_w * z_low_ohm)
    v_high = math.sqrt(power_w * z_high_ohm)
    i_low = math.sqrt(power_w / z_low_ohm)
    i_high = math.sqrt(power_w / z_high_ohm)

    ae_m2 = core.ae_mm2 * 1e-6
    b_peak = math.sqrt(2.0) * v_low / (2.0 * math.pi * frequency_hz * n_low * ae_m2)
    bsat_margin = core.bsat_t / b_peak if core.bsat_t is not None else None

    awg_low = _awg_for_area(i_low / current_density_a_mm2)
    awg_high = _awg_for_area(i_high / current_density_a_mm2)
    fit = wire_fit(core, n_low + n_high)

    notes: list[str] = []
    if n_high / n_low != turns:
        notes.append(
            f"rounded turns give impedance ratio {actual_ratio:.3f} "
            f"(target {ratio:.3f})"
        )
    if core.bsat_t is None:
        notes.append("Bsat not specified for this core; flux check is informational")
    elif bsat_margin is not None and bsat_margin < 1.0:
        notes.append("core is saturated at this power/frequency")
    if not fit.fits:
        notes.append("windings do not fit in a single layer; use a larger core")
    if awg_low is None or awg_high is None:
        notes.append("required current needs thicker wire than AWG 8")
    if kind_value == TransformerKind.BALUN:
        notes.append("transformer-type balun; verify common-mode/choke requirements")

    return TransformerDesign(
        core=core,
        kind=kind_value,
        z_low_ohm=z_low_ohm,
        z_high_ohm=z_high_ohm,
        impedance_ratio=ratio,
        turns_ratio=turns,
        n_low=n_low,
        n_high=n_high,
        actual_impedance_ratio=actual_ratio,
        magnetizing_inductance_h=lm,
        v_low_rms=v_low,
        v_high_rms=v_high,
        i_low_rms_a=i_low,
        i_high_rms_a=i_high,
        b_peak_t=b_peak,
        bsat_margin=bsat_margin,
        awg_low=awg_low,
        awg_high=awg_high,
        fit=fit,
        notes=tuple(notes),
    )


__all__ = [
    "TransformerDesign",
    "TransformerError",
    "TransformerKind",
    "design_transformer",
]
