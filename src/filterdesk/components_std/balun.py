"""Balun/unun design and first-order behavioral model parameters.

The calculator designs turns, core flux and wire on a toroid, then exposes a
:class:`BalunSpec` that the circuit can cascade at its output boundary. The
electrical model includes an ideal transformer, leakage inductance, winding
capacitance, a shunt core-loss resistance and (for Guanella/Ruthhoff) a TEM
line section. It is not a full multi-line transmission-line transformer or an
EM solver: verify the winding layout and common-mode behavior on hardware.
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
from filterdesk.domain.circuit import BalunSpec

_C0 = 299_792_458.0


class BalunError(ValueError):
    """Raised for an invalid balun design request."""


class BalunKind(StrEnum):
    IDEAL = "ideal"
    UNUN = "unun"
    GUANELLA = "guanella"
    RUTHROFF = "ruthroff"
    CHOKE = "choke"


@dataclass(frozen=True, slots=True)
class BalunDesign:
    core: ToroidCore
    kind: BalunKind
    z_unbalanced_ohm: float
    z_balanced_ohm: float
    turns_ratio: float
    n_primary: int
    n_secondary: int
    actual_turns_ratio: float
    magnetizing_inductance_h: float
    leakage_inductance_h: float
    winding_capacitance_f: float
    core_loss_ohm: float | None
    common_mode_impedance_ohm: float
    z0_line_ohm: float
    length_m: float
    velocity_factor: float
    loss_db_per_m: float
    v_unbalanced_rms: float
    v_balanced_rms: float
    i_unbalanced_rms_a: float
    i_balanced_rms_a: float
    b_peak_t: float | None
    bsat_margin: float | None
    awg_primary: int | None
    awg_secondary: int | None
    fit: WireFit
    notes: tuple[str, ...]

    @property
    def saturated(self) -> bool:
        return self.bsat_margin is not None and self.bsat_margin < 1.0

    def to_spec(self) -> BalunSpec:
        return BalunSpec(
            kind=self.kind.value,
            turns_ratio=self.actual_turns_ratio,
            z_unbalanced_ohm=self.z_unbalanced_ohm,
            z_balanced_ohm=self.z_balanced_ohm,
            z0_line_ohm=self.z0_line_ohm,
            length_m=self.length_m,
            velocity_factor=self.velocity_factor,
            loss_db_per_m=self.loss_db_per_m,
            leakage_h=self.leakage_inductance_h,
            shunt_c_f=self.winding_capacitance_f,
            core_loss_ohm=self.core_loss_ohm,
            common_mode_impedance_ohm=self.common_mode_impedance_ohm,
            core=self.core.name,
            turns=self.n_primary,
            wire_awg=self.awg_primary,
        )


def _awg_for_area(area_mm2: float) -> int | None:
    for awg in range(40, 7, -1):
        diameter = awg_diameter_mm(awg)
        if math.pi * (diameter / 2.0) ** 2 >= area_mm2:
            return awg
    return None


def design_balun(
    core: ToroidCore,
    *,
    kind: BalunKind | str,
    z_unbalanced_ohm: float,
    z_balanced_ohm: float,
    f_min_hz: float,
    f_max_hz: float,
    power_w: float,
    coupling: float = 0.98,
    tan_delta: float = 0.02,
    winding_capacitance_f: float = 0.0,
    line_z0_ohm: float | None = None,
    line_length_m: float | None = None,
    velocity_factor: float = 0.7,
    line_loss_db_per_m: float = 0.0,
    reactance_factor: float = 4.0,
    current_density_a_mm2: float = 4.0,
) -> BalunDesign:
    """Design a transformer-type or TLT balun/unun on a toroid core."""
    kind_value = BalunKind(str(kind))
    for name, value in (
        ("z_unbalanced_ohm", z_unbalanced_ohm),
        ("z_balanced_ohm", z_balanced_ohm),
        ("f_min_hz", f_min_hz),
        ("f_max_hz", f_max_hz),
        ("power_w", power_w),
    ):
        if value <= 0.0:
            raise BalunError(f"{name} must be > 0")
    if f_max_hz <= f_min_hz:
        raise BalunError("f_max_hz must be > f_min_hz")
    if not 0.0 < coupling < 1.0:
        raise BalunError("coupling must be in (0, 1)")
    if not 0.0 <= tan_delta < 1.0:
        raise BalunError("tan_delta must be in [0, 1)")
    if winding_capacitance_f < 0.0:
        raise BalunError("winding capacitance must be >= 0")
    if line_loss_db_per_m < 0.0:
        raise BalunError("line loss must be >= 0")
    if velocity_factor <= 0.0:
        raise BalunError("velocity factor must be > 0")
    if reactance_factor <= 0.0 or current_density_a_mm2 <= 0.0:
        raise BalunError("reactance factor / current density must be > 0")
    if kind_value is BalunKind.CHOKE and z_unbalanced_ohm != z_balanced_ohm:
        raise BalunError("a choke balun requires equal impedances")
    if core.ae_mm2 <= 0.0:
        raise BalunError("core dimensions are required")

    turns = math.sqrt(z_unbalanced_ohm / z_balanced_ohm)
    al_h = core.al_nh * 1e-9
    n_primary_min = math.sqrt(
        reactance_factor * z_unbalanced_ohm / (2.0 * math.pi * f_min_hz * al_h)
    )
    n_primary = max(1, math.ceil(n_primary_min - 1e-9))
    n_secondary = max(1, round(n_primary / turns))
    actual_turns = n_primary / n_secondary
    lm = al_h * n_primary * n_primary
    leakage = lm * (1.0 - coupling)
    core_loss = (
        2.0 * math.pi * f_min_hz * lm / tan_delta if tan_delta > 0.0 else None
    )
    common_mode = (
        2.0 * math.pi * f_min_hz * lm if kind_value is BalunKind.CHOKE else 0.0
    )

    z0_line = (
        float(line_z0_ohm)
        if line_z0_ohm is not None
        else math.sqrt(z_unbalanced_ohm * z_balanced_ohm)
    )
    if z0_line <= 0.0:
        raise BalunError("line_z0_ohm must be > 0")
    f_center = math.sqrt(f_min_hz * f_max_hz)
    if line_length_m is not None:
        length = float(line_length_m)
    elif kind_value in (BalunKind.GUANELLA, BalunKind.RUTHROFF):
        length = velocity_factor * _C0 / (4.0 * f_center)
    else:
        length = 0.0
    if length < 0.0:
        raise BalunError("line length must be >= 0")

    v_unbalanced = math.sqrt(power_w * z_unbalanced_ohm)
    v_balanced = math.sqrt(power_w * z_balanced_ohm)
    i_unbalanced = math.sqrt(power_w / z_unbalanced_ohm)
    i_balanced = math.sqrt(power_w / z_balanced_ohm)
    ae_m2 = core.ae_mm2 * 1e-6
    b_peak = math.sqrt(2.0) * v_unbalanced / (
        2.0 * math.pi * f_min_hz * n_primary * ae_m2
    )
    bsat_margin = core.bsat_t / b_peak if core.bsat_t is not None else None
    awg_primary = _awg_for_area(i_unbalanced / current_density_a_mm2)
    awg_secondary = _awg_for_area(i_balanced / current_density_a_mm2)
    fit = wire_fit(core, n_primary + n_secondary)

    notes: list[str] = []
    if abs(actual_turns - turns) > 1e-12:
        notes.append(
            f"rounded turns give ratio {actual_turns:.3f} (target {turns:.3f})"
        )
    if core.bsat_t is None:
        notes.append("Bsat not specified; flux check is informational")
    elif bsat_margin is not None and bsat_margin < 1.0:
        notes.append("core saturates at this power/frequency")
    if not fit.fits:
        notes.append("windings do not fit in one layer; use a larger core")
    if kind_value in (BalunKind.GUANELLA, BalunKind.RUTHROFF):
        notes.append(
            "TLT model is behavioral (one TEM section); verify the real "
            "multi-line Guanella/Ruthroff layout"
        )
    if kind_value is BalunKind.CHOKE:
        notes.append(
            "common-mode impedance is reported separately; the differential "
            "2-port does not model the choke's common-mode stopband"
        )
    if core_loss is not None:
        notes.append("core loss uses a shunt Rp = 2*pi*f_min*Lm/tan_delta")

    return BalunDesign(
        core=core,
        kind=kind_value,
        z_unbalanced_ohm=z_unbalanced_ohm,
        z_balanced_ohm=z_balanced_ohm,
        turns_ratio=turns,
        n_primary=n_primary,
        n_secondary=n_secondary,
        actual_turns_ratio=actual_turns,
        magnetizing_inductance_h=lm,
        leakage_inductance_h=leakage,
        winding_capacitance_f=winding_capacitance_f,
        core_loss_ohm=core_loss,
        common_mode_impedance_ohm=common_mode,
        z0_line_ohm=z0_line,
        length_m=length,
        velocity_factor=velocity_factor,
        loss_db_per_m=line_loss_db_per_m,
        v_unbalanced_rms=v_unbalanced,
        v_balanced_rms=v_balanced,
        i_unbalanced_rms_a=i_unbalanced,
        i_balanced_rms_a=i_balanced,
        b_peak_t=b_peak,
        bsat_margin=bsat_margin,
        awg_primary=awg_primary,
        awg_secondary=awg_secondary,
        fit=fit,
        notes=tuple(notes),
    )


__all__ = ["BalunDesign", "BalunError", "BalunKind", "design_balun"]
