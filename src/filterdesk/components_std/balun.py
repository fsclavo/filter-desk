"""Balun/unun design and boundary-model parameters.

The calculator designs turns, core flux and wire on a toroid, then exposes a
:class:`BalunSpec` that the circuit can cascade at its output boundary. Integer
1:N² Guanella ratios use an explicit N-line parallel-input/series-output
network; Ruthroff and other ratios keep the first-order transformer + TEM-line
model. Leakage, winding capacitance, shunt core loss and common-mode estimates
are included where applicable. This is not an EM solver: verify the layout and
common-mode behavior on hardware.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from filterdesk.components_std.materials import (
    bsat_at_temperature,
    copper_loss_w,
    core_loss_density_w_cm3,
    material_for,
    thermal_resistance_c_w,
)
from filterdesk.components_std.toroid import (
    ToroidCore,
    WireFit,
    awg_diameter_mm,
    wire_fit,
)
from filterdesk.components_std.transformer import TransformerTopology
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
    topology: TransformerTopology = TransformerTopology.AUTOTRANSFORMER
    total_turns: int = 0
    reactance_ratio: float = 0.0
    hf_caution: bool = False
    power_w: float = 0.0
    core_loss_w: float | None = None
    copper_loss_w: float = 0.0
    total_loss_w: float | None = None
    thermal_resistance_c_w: float = 0.0
    temperature_rise_c: float | None = None
    hot_temperature_c: float | None = None
    bsat_margin_hot: float | None = None
    thermal_caution: bool = False

    @property
    def power_density_w_cm3(self) -> float:
        volume = self.core.volume_cm3
        return self.power_w / volume if volume > 0.0 else 0.0

    @property
    def thermal_text(self) -> str:
        if self.hot_temperature_c is None:
            return "not modeled"
        material = material_for(self.core.material)
        if material is not None and self.hot_temperature_c >= material.curie_c:
            return f">{material.curie_c:.0f} C (over Tc)"
        return f"{self.hot_temperature_c:.0f} C"

    @property
    def warnings(self) -> tuple[str, ...]:
        flags: list[str] = []
        if self.reactance_ratio < 4.0:
            flags.append(f"LF X/Z {self.reactance_ratio:.1f}")
        margin = self.bsat_margin_hot or self.bsat_margin
        if margin is None:
            flags.append("SAT unknown")
        elif margin < 1.0:
            flags.append("SAT saturated")
        elif margin < 3.0:
            flags.append(f"SAT {margin:.1f}")
        if self.fit.awg is None:
            flags.append("FIT no")
        if self.hf_caution:
            flags.append(f"HF {self.total_turns}T")
        if self.thermal_caution:
            flags.append(f"THERMAL {self.thermal_text}")
        return tuple(flags)

    @property
    def status_text(self) -> str:
        return "; ".join(self.warnings) if self.warnings else "OK"

    @property
    def saturated(self) -> bool:
        return self.bsat_margin is not None and self.bsat_margin < 1.0

    @property
    def impedance_ratio(self) -> float:
        """Balanced / unbalanced impedance ratio (e.g. 4.0 for a 1:4 unun)."""
        return (self.n_secondary / self.n_primary) ** 2

    @property
    def ratio_text(self) -> str:
        return self.to_spec().ratio_text

    @property
    def common_mode_attenuation_db(self) -> float | None:
        """First-order series-choke common-mode attenuation at ``f_min``."""
        if self.kind is not BalunKind.CHOKE or self.common_mode_impedance_ohm <= 0.0:
            return None
        z0 = self.z_unbalanced_ohm
        s21 = 2.0 * z0 / (2.0 * z0 + self.common_mode_impedance_ohm)
        return -20.0 * math.log10(abs(s21))

    def to_spec(self) -> BalunSpec:
        return BalunSpec(
            kind=self.kind.value,
            topology=self.topology.value,
            turns_ratio=self.actual_turns_ratio,
            total_turns=self.total_turns,
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
            magnetizing_inductance_h=self.magnetizing_inductance_h,
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
    topology: TransformerTopology | str = TransformerTopology.AUTOTRANSFORMER,
    turns_primary: int | None = None,
) -> BalunDesign:
    """Design a transformer-type or TLT balun/unun on a toroid core."""
    kind_value = BalunKind(str(kind))
    topology_value = TransformerTopology(str(topology))
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
    if turns_primary is not None and turns_primary < 1:
        raise BalunError("turns_primary must be >= 1")

    turns = math.sqrt(z_unbalanced_ohm / z_balanced_ohm)
    al_h = core.al_nh * 1e-9
    n_primary_min = math.sqrt(
        reactance_factor * z_unbalanced_ohm / (2.0 * math.pi * f_min_hz * al_h)
    )
    n_primary = (
        turns_primary
        if turns_primary is not None
        else max(1, math.ceil(n_primary_min - 1e-9))
    )
    n_secondary = max(1, round(n_primary / turns))
    actual_turns = n_primary / n_secondary
    lm = al_h * n_primary * n_primary
    leakage = lm * (1.0 - coupling)
    core_loss_resistance = (
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
    b_peak = (
        math.sqrt(2.0) * v_unbalanced / (2.0 * math.pi * f_min_hz * n_primary * ae_m2)
    )
    bsat_margin = core.bsat_t / b_peak if core.bsat_t is not None else None
    awg_primary = _awg_for_area(i_unbalanced / current_density_a_mm2)
    awg_secondary = _awg_for_area(i_balanced / current_density_a_mm2)
    total_turns = (
        n_secondary
        if topology_value is TransformerTopology.AUTOTRANSFORMER
        else n_primary + n_secondary
    )
    fit = wire_fit(core, total_turns)
    reactance_ratio = 2.0 * math.pi * f_min_hz * lm / z_unbalanced_ohm
    hf_caution = f_max_hz >= 20e6 and total_turns > 24

    material = material_for(core.material)
    core_loss: float | None = None
    if material is not None:
        loss_candidates = []
        for freq in (f_min_hz, math.sqrt(f_min_hz * f_max_hz), f_max_hz):
            b_at_f = b_peak * f_min_hz / freq
            density = core_loss_density_w_cm3(material, freq, b_at_f)
            loss_candidates.append(density * core.volume_cm3)
        core_loss = max(loss_candidates)
    d_pri = awg_diameter_mm(awg_primary) if awg_primary is not None else None
    d_sec = awg_diameter_mm(awg_secondary) if awg_secondary is not None else None
    l_pri = core.mean_turn_mm * n_primary / 1000.0
    l_sec = core.mean_turn_mm * n_secondary / 1000.0
    copper_loss = copper_loss_w(i_unbalanced, l_pri, d_pri) + copper_loss_w(
        i_balanced, l_sec, d_sec
    )
    rth = thermal_resistance_c_w(core.od_mm, core.id_mm, core.height_mm)
    total_loss = None if core_loss is None else core_loss + copper_loss
    rise = None if total_loss is None else total_loss * rth
    hot = None if rise is None else 25.0 + rise
    bsat_hot = (
        None if material is None or hot is None else bsat_at_temperature(material, hot)
    )
    margin_hot = None if bsat_hot is None else bsat_hot / b_peak
    thermal_caution = hot is not None and hot > 100.0

    notes: list[str] = []
    if topology_value is TransformerTopology.AUTOTRANSFORMER:
        notes.append(
            "autotransformer: one tapped winding (input across primary, output "
            "across total); no galvanic isolation"
        )
    else:
        notes.append("isolated two-winding transformer")
    if reactance_ratio < reactance_factor:
        notes.append(
            f"X_Lm/Z = {reactance_ratio:.2f} below target {reactance_factor:.2f}; "
            "low-frequency response may suffer"
        )
    if hf_caution:
        notes.append(
            "many turns at HF: leakage/capacitance may degrade the high bands "
            "(prefer fewer turns)"
        )
    if core_loss is not None and hot is not None:
        notes.append(
            f"estimated core+copper loss {total_loss:.2f} W, "
            f"hot {hot:.0f} C (complex-permeability model; "
            "verify with measurement)"
        )
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
    if kind_value is BalunKind.GUANELLA:
        lines = round(1.0 / actual_turns) if actual_turns < 1.0 else round(actual_turns)
        expected = 1.0 / lines if actual_turns < 1.0 else float(lines)
        if lines >= 1 and abs(actual_turns - expected) <= 1e-6 * max(1.0, actual_turns):
            notes.append(
                f"Guanella {lines}-line parallel/series network; verify the "
                "winding layout and common-mode behavior"
            )
        else:
            notes.append(
                "non-integer Guanella ratio uses the first-order transformer + "
                "TEM-line model; verify the winding layout"
            )
    elif kind_value is BalunKind.RUTHROFF:
        if abs(actual_turns - 0.5) <= 1e-6 or abs(actual_turns - 2.0) <= 1e-6:
            notes.append(
                "Ruthroff 1:4 uses an equal-delay bootstrap ABCD; verify the "
                "real winding layout and common-mode behavior"
            )
        else:
            notes.append(
                "Ruthroff ratio is outside 1:4; using the first-order "
                "transformer + TEM-line model"
            )
    if kind_value is BalunKind.CHOKE:
        notes.append(
            "common-mode impedance/attenuation is reported separately; the "
            "differential 2-port does not model the choke's common-mode stopband"
        )
    if core_loss_resistance is not None:
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
        core_loss_ohm=core_loss_resistance,
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
        topology=topology_value,
        total_turns=total_turns,
        reactance_ratio=reactance_ratio,
        hf_caution=hf_caution,
        power_w=power_w,
        core_loss_w=core_loss,
        copper_loss_w=copper_loss,
        total_loss_w=total_loss,
        thermal_resistance_c_w=rth,
        temperature_rise_c=rise,
        hot_temperature_c=hot,
        bsat_margin_hot=margin_hot,
        thermal_caution=thermal_caution,
    )


def design_balun_options(
    core: ToroidCore,
    *,
    kind: BalunKind | str,
    z_unbalanced_ohm: float,
    z_balanced_ohm: float,
    f_min_hz: float,
    f_max_hz: float,
    power_w: float,
    topology: TransformerTopology | str = TransformerTopology.AUTOTRANSFORMER,
    coupling: float = 0.98,
    tan_delta: float = 0.02,
    winding_capacitance_f: float = 0.0,
    line_z0_ohm: float | None = None,
    line_length_m: float | None = None,
    velocity_factor: float = 0.7,
    line_loss_db_per_m: float = 0.0,
    reactance_factor: float = 4.0,
    current_density_a_mm2: float = 4.0,
) -> list[BalunDesign]:
    """Return compact / recommended / robust turns options for one ratio."""
    base = design_balun(
        core,
        kind=kind,
        z_unbalanced_ohm=z_unbalanced_ohm,
        z_balanced_ohm=z_balanced_ohm,
        f_min_hz=f_min_hz,
        f_max_hz=f_max_hz,
        power_w=power_w,
        topology=topology,
        coupling=coupling,
        tan_delta=tan_delta,
        winding_capacitance_f=winding_capacitance_f,
        line_z0_ohm=line_z0_ohm,
        line_length_m=line_length_m,
        velocity_factor=velocity_factor,
        line_loss_db_per_m=line_loss_db_per_m,
        reactance_factor=reactance_factor,
        current_density_a_mm2=current_density_a_mm2,
    )
    candidates = sorted(
        {max(1, base.n_primary - 1), base.n_primary, base.n_primary + 1}
    )
    return [
        design_balun(
            core,
            kind=kind,
            z_unbalanced_ohm=z_unbalanced_ohm,
            z_balanced_ohm=z_balanced_ohm,
            f_min_hz=f_min_hz,
            f_max_hz=f_max_hz,
            power_w=power_w,
            topology=topology,
            coupling=coupling,
            tan_delta=tan_delta,
            winding_capacitance_f=winding_capacitance_f,
            line_z0_ohm=line_z0_ohm,
            line_length_m=line_length_m,
            velocity_factor=velocity_factor,
            line_loss_db_per_m=line_loss_db_per_m,
            reactance_factor=reactance_factor,
            current_density_a_mm2=current_density_a_mm2,
            turns_primary=n_primary,
        )
        for n_primary in candidates
    ]


__all__ = [
    "BalunDesign",
    "BalunError",
    "BalunKind",
    "design_balun",
    "design_balun_options",
]
