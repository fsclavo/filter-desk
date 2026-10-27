"""Canonical lumped circuit model (GUI-independent)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from filterdesk.domain.enums import (
    ElementRole,
    ElementType,
    MicrostripStubKind,
    TopologyId,
)


@dataclass(frozen=True, slots=True)
class Port:
    name: str
    node: str
    impedance_ohm: float


@dataclass(frozen=True, slots=True)
class IdealResistor:
    id: str
    value_ohm: float
    node_a: str
    node_b: str
    role: ElementRole = ElementRole.SERIES
    g: float | None = None

    @property
    def element_type(self) -> ElementType:
        return ElementType.RESISTOR


@dataclass(frozen=True, slots=True)
class IdealCapacitor:
    id: str
    value_f: float
    node_a: str
    node_b: str
    role: ElementRole
    g: float | None = None

    @property
    def element_type(self) -> ElementType:
        return ElementType.CAPACITOR


@dataclass(frozen=True, slots=True)
class IdealInductor:
    id: str
    value_h: float
    node_a: str
    node_b: str
    role: ElementRole
    g: float | None = None

    @property
    def element_type(self) -> ElementType:
        return ElementType.INDUCTOR


@dataclass(frozen=True, slots=True)
class IdealSeriesLC:
    """Series connection of L and C (series arm or shunt branch)."""

    id: str
    value_h: float
    value_f: float
    node_a: str
    node_b: str
    role: ElementRole
    g: float | None = None

    @property
    def element_type(self) -> ElementType:
        return ElementType.SERIES_LC


@dataclass(frozen=True, slots=True)
class IdealParallelLC:
    """Parallel connection of L and C (series arm or shunt branch)."""

    id: str
    value_h: float
    value_f: float
    node_a: str
    node_b: str
    role: ElementRole
    g: float | None = None

    @property
    def element_type(self) -> ElementType:
        return ElementType.PARALLEL_LC


@dataclass(frozen=True, slots=True)
class IdealBruneLC:
    """Series of series-LC and parallel-LC (finite-zero BP/BS transform)."""

    id: str
    series_l_h: float
    series_c_f: float
    parallel_l_h: float
    parallel_c_f: float
    node_a: str
    node_b: str
    role: ElementRole
    g: float | None = None

    @property
    def element_type(self) -> ElementType:
        return ElementType.BRUNE_LC


@dataclass(frozen=True, slots=True)
class IdealDualBruneLC:
    """Parallel of series-LC and parallel-LC (finite-zero BP/BS transform)."""

    id: str
    series_l_h: float
    series_c_f: float
    parallel_l_h: float
    parallel_c_f: float
    node_a: str
    node_b: str
    role: ElementRole
    g: float | None = None

    @property
    def element_type(self) -> ElementType:
        return ElementType.DUAL_BRUNE_LC


@dataclass(frozen=True, slots=True)
class WindingSpec:
    """Physical winding provenance for an inductor/transformer (BOM/reports)."""

    kind: str  # "toroid", "air" or "balun"
    core: str = ""
    material: str = ""
    turns: int | None = None
    turns_secondary: int | None = None
    topology: str = ""
    impedance_ratio: float | None = None
    wire_awg: int | None = None
    wire_bare_mm: float | None = None
    wire_overall_mm: float | None = None


@dataclass(frozen=True, slots=True)
class BalunSpec:
    """Boundary balun/unun model (first-order behavioral 2-port).

    ``turns_ratio`` is primary:secondary (``Np/Ns``), so a 50 -> 200 ohm
    transformer has ``turns_ratio = 0.5``. ``kind`` selects the model:
    ``ideal``, ``unun``, ``guanella``, ``ruthroff`` or ``choke``. For TLT
    kinds the line section uses ``z0_line_ohm``, ``length_m`` and
    ``velocity_factor``; leakage, winding capacitance and core loss are
    optional first-order parasitics.
    """

    kind: str = "ideal"
    topology: str = "autotransformer"
    turns_ratio: float = 1.0
    total_turns: int = 0
    z_unbalanced_ohm: float = 0.0
    z_balanced_ohm: float = 0.0
    z0_line_ohm: float = 50.0
    length_m: float = 0.0
    velocity_factor: float = 1.0
    loss_db_per_m: float = 0.0
    leakage_h: float = 0.0
    shunt_c_f: float = 0.0
    core_loss_ohm: float | None = None
    common_mode_impedance_ohm: float = 0.0
    magnetizing_inductance_h: float = 0.0
    winding_option: str = ""
    dcr_primary_ohm: float | None = None
    dcr_secondary_ohm: float | None = None
    core: str = ""
    turns: int | None = None
    wire_awg: int | None = None

    @property
    def secondary_turns(self) -> int | None:
        if self.turns is None or self.total_turns <= 0:
            return None
        if self.topology == "isolated":
            return max(1, self.total_turns - self.turns)
        return self.total_turns

    @staticmethod
    def _ratio_text(primary: int, secondary: int) -> str:
        if primary <= 0 or secondary <= 0:
            return "?"
        if secondary >= primary:
            return f"1:{secondary / primary:.3g}"
        return f"{primary / secondary:.3g}:1"

    @property
    def turns_text(self) -> str:
        secondary = self.secondary_turns
        if self.turns is None or secondary is None:
            return f"{self.turns_ratio:.4g}:1"
        return self._ratio_text(self.turns, secondary)

    @property
    def impedance_text(self) -> str:
        secondary = self.secondary_turns
        if self.turns is None or secondary is None:
            return "?"
        return self._ratio_text(self.turns * self.turns, secondary * secondary)

    @property
    def ratio_text(self) -> str:
        return f"{self.turns_text} turns / {self.impedance_text} Z"

    @property
    def guanella_line_count(self) -> int | None:
        """Integer number of parallel/series lines for a Guanella TLT, if any."""
        if self.kind != "guanella":
            return None
        ratio = self.turns_ratio
        lines = round(1.0 / ratio) if ratio < 1.0 else round(ratio)
        if lines < 1:
            return None
        expected = 1.0 / lines if ratio < 1.0 else float(lines)
        if abs(ratio - expected) > 1e-6 * max(1.0, abs(ratio)):
            return None
        return int(lines)

    def __post_init__(self) -> None:
        if self.kind not in {"ideal", "unun", "guanella", "ruthroff", "choke"}:
            raise ValueError(f"unknown balun kind {self.kind!r}")
        if self.topology not in {"autotransformer", "isolated"}:
            raise ValueError(f"unknown balun topology {self.topology!r}")
        if self.turns_ratio <= 0.0:
            raise ValueError("balun turns_ratio must be > 0")
        if self.z0_line_ohm <= 0.0:
            raise ValueError("balun z0_line_ohm must be > 0")
        if self.length_m < 0.0:
            raise ValueError("balun length_m must be >= 0")
        if self.velocity_factor <= 0.0:
            raise ValueError("balun velocity_factor must be > 0")
        if self.loss_db_per_m < 0.0:
            raise ValueError("balun loss_db_per_m must be >= 0")
        if self.leakage_h < 0.0 or self.shunt_c_f < 0.0:
            raise ValueError("balun leakage/capacitance must be >= 0")
        if self.core_loss_ohm is not None and self.core_loss_ohm <= 0.0:
            raise ValueError("balun core_loss_ohm must be > 0")
        if self.magnetizing_inductance_h < 0.0:
            raise ValueError("balun magnetizing_inductance_h must be >= 0")
        for name, value in (
            ("dcr_primary_ohm", self.dcr_primary_ohm),
            ("dcr_secondary_ohm", self.dcr_secondary_ohm),
        ):
            if value is not None and value < 0.0:
                raise ValueError(f"balun {name} must be >= 0")


@dataclass(frozen=True, slots=True)
class NonIdealInductor:
    """Inductor with losses, self-resonance and optional DC-bias derating.

    Two-terminal model: ``(R(f) + jw L_eff) || 1/(jw Cp)``. ``R(f)`` comes from
    the reference resistance (``series_resistance_ohm`` or ``q_ref`` at
    ``q_frequency_hz``); ``loss_model="dc_skin"`` makes it rise as ``sqrt(f)``.
    ``srf_hz`` (if set) overrides ``parallel_capacitance_f``. ``dc_current_a``
    against ``saturation_current_a`` derates the inductance.
    """

    id: str
    value_h: float
    node_a: str
    node_b: str
    role: ElementRole
    series_resistance_ohm: float = 0.0
    parallel_capacitance_f: float = 0.0
    g: float | None = None
    q_ref: float | None = None
    q_frequency_hz: float | None = None
    srf_hz: float | None = None
    loss_model: str = "constant"
    dc_current_a: float = 0.0
    saturation_current_a: float | None = None
    winding: WindingSpec | None = None

    def __post_init__(self) -> None:
        if self.loss_model not in ("constant", "dc_skin"):
            raise ValueError("loss_model must be 'constant' or 'dc_skin'")
        if self.q_ref is not None and self.q_ref <= 0.0:
            raise ValueError("q_ref must be > 0")
        if self.srf_hz is not None and self.srf_hz <= 0.0:
            raise ValueError("srf_hz must be > 0")
        if self.saturation_current_a is not None and self.saturation_current_a <= 0.0:
            raise ValueError("saturation_current_a must be > 0")
        if self.dc_current_a < 0.0:
            raise ValueError("dc_current_a must be >= 0")

    @property
    def element_type(self) -> ElementType:
        return ElementType.NONIDEAL_INDUCTOR

    @property
    def reference_resistance_ohm(self) -> float:
        """Series resistance at the reference frequency (DCR or from Q)."""
        if self.series_resistance_ohm > 0.0:
            return self.series_resistance_ohm
        if (
            self.q_ref is not None
            and self.q_ref > 0.0
            and self.q_frequency_hz is not None
            and self.q_frequency_hz > 0.0
        ):
            return 2.0 * math.pi * self.q_frequency_hz * self.value_h / self.q_ref
        return 0.0

    @property
    def effective_parallel_capacitance_f(self) -> float:
        if self.srf_hz is not None and self.srf_hz > 0.0 and self.value_h > 0.0:
            return 1.0 / ((2.0 * math.pi * self.srf_hz) ** 2 * self.value_h)
        return self.parallel_capacitance_f

    @property
    def dc_bias_factor(self) -> float:
        """Inductance retention from the first-order DC-bias roll-off."""
        if (
            self.saturation_current_a is None
            or self.saturation_current_a <= 0.0
            or self.dc_current_a <= 0.0
        ):
            return 1.0
        ratio = self.dc_current_a / self.saturation_current_a
        return 1.0 / (1.0 + ratio * ratio)

    @property
    def effective_inductance_h(self) -> float:
        return self.value_h * self.dc_bias_factor

    @property
    def self_resonant_frequency_hz(self) -> float | None:
        if self.srf_hz is not None and self.srf_hz > 0.0:
            return self.srf_hz
        capacitance = self.parallel_capacitance_f
        if capacitance <= 0.0:
            return None
        return 1.0 / (2.0 * math.pi * math.sqrt(self.value_h * capacitance))


@dataclass(frozen=True, slots=True)
class NonIdealCapacitor:
    """Capacitor with series resistance (ESR) and series inductance (ESL).

    Two-terminal model: ``R + jw L + 1/(jw C)``. Used as a series or shunt arm.
    """

    id: str
    value_f: float
    node_a: str
    node_b: str
    role: ElementRole
    esr_ohm: float = 0.0
    esl_h: float = 0.0
    g: float | None = None

    @property
    def element_type(self) -> ElementType:
        return ElementType.NONIDEAL_CAPACITOR

    @property
    def self_resonant_frequency_hz(self) -> float | None:
        if self.esl_h <= 0.0:
            return None
        return 1.0 / (2.0 * math.pi * math.sqrt(self.esl_h * self.value_f))


@dataclass(frozen=True, slots=True)
class MicrostripLineElement:
    """Ideal TEM microstrip line as a series ladder arm.

    Electrical fields are authoritative for analysis; ``substrate``,
    ``width_mm`` and ``angle_deg`` are descriptive/provenance fields used by the
    BOM and schematic. Dispersion, discontinuities and radiation are not modeled.
    """

    id: str
    z0_ohm: float
    length_m: float
    eeff: float
    node_a: str
    node_b: str
    role: ElementRole = ElementRole.SERIES
    loss_db_per_m: float = 0.0
    substrate: str = ""
    width_mm: float = 0.0
    angle_deg: float = 0.0
    g: float | None = None

    @property
    def element_type(self) -> ElementType:
        return ElementType.MICROSTRIP_LINE

    @property
    def velocity_factor(self) -> float:
        return 1.0 / math.sqrt(self.eeff)

    def __post_init__(self) -> None:
        if self.z0_ohm <= 0.0:
            raise ValueError("microstrip line Z0 must be > 0")
        if self.length_m < 0.0:
            raise ValueError("microstrip line length must be >= 0")
        if self.eeff <= 0.0:
            raise ValueError("microstrip line eeff must be > 0")
        if self.loss_db_per_m < 0.0:
            raise ValueError("microstrip line loss must be >= 0")
        if self.role != ElementRole.SERIES:
            raise ValueError("microstrip line elements are series arms")
        if self.width_mm < 0.0:
            raise ValueError("microstrip width must be >= 0")


@dataclass(frozen=True, slots=True)
class MicrostripStubElement:
    """Ideal TEM open/short shunt stub (microstrip or equivalent line)."""

    id: str
    z0_ohm: float
    length_m: float
    eeff: float
    stub_kind: MicrostripStubKind
    node_a: str
    node_b: str
    role: ElementRole = ElementRole.SHUNT
    loss_db_per_m: float = 0.0
    substrate: str = ""
    width_mm: float = 0.0
    angle_deg: float = 0.0
    g: float | None = None

    @property
    def element_type(self) -> ElementType:
        return ElementType.MICROSTRIP_STUB

    @property
    def velocity_factor(self) -> float:
        return 1.0 / math.sqrt(self.eeff)

    def __post_init__(self) -> None:
        if self.z0_ohm <= 0.0:
            raise ValueError("microstrip stub Z0 must be > 0")
        if self.length_m < 0.0:
            raise ValueError("microstrip stub length must be >= 0")
        if self.eeff <= 0.0:
            raise ValueError("microstrip stub eeff must be > 0")
        if self.loss_db_per_m < 0.0:
            raise ValueError("microstrip stub loss must be >= 0")
        if self.role != ElementRole.SHUNT:
            raise ValueError("microstrip stub elements are shunt arms")
        if self.width_mm < 0.0:
            raise ValueError("microstrip width must be >= 0")


Element = (
    IdealResistor
    | IdealCapacitor
    | IdealInductor
    | IdealSeriesLC
    | IdealParallelLC
    | IdealBruneLC
    | IdealDualBruneLC
    | NonIdealInductor
    | NonIdealCapacitor
    | MicrostripLineElement
    | MicrostripStubElement
)


@dataclass(frozen=True, slots=True)
class PhysicalComponent:
    """One physical L/C/R part of a (possibly compound) circuit element.

    ``ref`` is the part designator (``L1``, ``C2``, ``X1.L`` …), ``element_id``
    the originating circuit element. ``unit`` is ``"H"``, ``"F"`` or ``"Ohm"``.
    """

    ref: str
    element_id: str
    role: str
    kind: str
    value: float
    unit: str
    series_resistance_ohm: float = 0.0
    parallel_capacitance_f: float = 0.0
    esr_ohm: float = 0.0
    esl_h: float = 0.0
    srf_hz: float | None = None
    winding: WindingSpec | None = None
    substrate: str = ""
    width_mm: float = 0.0
    length_mm: float = 0.0
    angle_deg: float = 0.0
    stub_kind: str = ""
    winding_option: str = ""
    dcr_primary_ohm: float | None = None
    dcr_secondary_ohm: float | None = None
    leakage_h: float | None = None


def physical_components(circuit: Circuit) -> list[PhysicalComponent]:
    """Expand circuit elements into one row per physical part (BOM view)."""
    rows: list[PhysicalComponent] = []
    for el in circuit.elements:
        role = el.role.value
        if isinstance(el, (IdealSeriesLC, IdealParallelLC)):
            rows.append(
                PhysicalComponent(
                    f"{el.id}.L", el.id, role, "inductor", el.value_h, "H"
                )
            )
            rows.append(
                PhysicalComponent(
                    f"{el.id}.C", el.id, role, "capacitor", el.value_f, "F"
                )
            )
        elif isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
            for ref, value, unit, kind in (
                (f"{el.id}.Ls", el.series_l_h, "H", "inductor"),
                (f"{el.id}.Cs", el.series_c_f, "F", "capacitor"),
                (f"{el.id}.Lp", el.parallel_l_h, "H", "inductor"),
                (f"{el.id}.Cp", el.parallel_c_f, "F", "capacitor"),
            ):
                rows.append(PhysicalComponent(ref, el.id, role, kind, value, unit))
        elif isinstance(el, NonIdealInductor):
            rows.append(
                PhysicalComponent(
                    el.id,
                    el.id,
                    role,
                    "inductor",
                    el.value_h,
                    "H",
                    series_resistance_ohm=el.reference_resistance_ohm,
                    parallel_capacitance_f=el.effective_parallel_capacitance_f,
                    srf_hz=el.self_resonant_frequency_hz,
                    winding=el.winding,
                )
            )
        elif isinstance(el, NonIdealCapacitor):
            rows.append(
                PhysicalComponent(
                    el.id,
                    el.id,
                    role,
                    "capacitor",
                    el.value_f,
                    "F",
                    esr_ohm=el.esr_ohm,
                    esl_h=el.esl_h,
                )
            )
        elif isinstance(el, MicrostripLineElement):
            rows.append(
                PhysicalComponent(
                    el.id,
                    el.id,
                    role,
                    "microstrip_line",
                    el.z0_ohm,
                    "Ohm",
                    substrate=el.substrate,
                    width_mm=el.width_mm,
                    length_mm=el.length_m * 1e3,
                    angle_deg=el.angle_deg,
                )
            )
        elif isinstance(el, MicrostripStubElement):
            rows.append(
                PhysicalComponent(
                    el.id,
                    el.id,
                    role,
                    "microstrip_stub",
                    el.z0_ohm,
                    "Ohm",
                    substrate=el.substrate,
                    width_mm=el.width_mm,
                    length_mm=el.length_m * 1e3,
                    angle_deg=el.angle_deg,
                    stub_kind=el.stub_kind.value,
                )
            )
        elif isinstance(el, IdealCapacitor):
            rows.append(
                PhysicalComponent(el.id, el.id, role, "capacitor", el.value_f, "F")
            )
        elif isinstance(el, IdealInductor):
            rows.append(
                PhysicalComponent(el.id, el.id, role, "inductor", el.value_h, "H")
            )
        else:
            rows.append(
                PhysicalComponent(el.id, el.id, role, "resistor", el.value_ohm, "Ohm")
            )
    if circuit.output_transformer_ratio != 1.0:
        rows.append(
            PhysicalComponent(
                "T1",
                "T1",
                "series",
                "transformer",
                circuit.output_transformer_ratio,
                "",
            )
        )
    if circuit.output_balun is not None:
        balun = circuit.output_balun
        rows.append(
            PhysicalComponent(
                "BAL1",
                "BAL1",
                "series",
                "balun",
                balun.turns_ratio,
                "",
                winding=WindingSpec(
                    kind="balun",
                    core=balun.core,
                    material=balun.kind,
                    turns=balun.turns,
                    turns_secondary=balun.secondary_turns,
                    topology=balun.topology,
                    impedance_ratio=(
                        None
                        if balun.secondary_turns is None or not balun.turns
                        else (balun.secondary_turns / balun.turns) ** 2
                    ),
                    wire_awg=balun.wire_awg,
                ),
                winding_option=balun.winding_option,
                dcr_primary_ohm=balun.dcr_primary_ohm,
                dcr_secondary_ohm=balun.dcr_secondary_ohm,
                leakage_h=balun.leakage_h,
            )
        )
    return rows


def series_node_path(num_series: int) -> list[str]:
    """Node sequence spanning series arms: ``in, n1, …, out``."""
    if num_series <= 0:
        return ["in"]
    if num_series == 1:
        return ["in", "out"]
    return ["in", *[f"n{i}" for i in range(1, num_series)], "out"]


@dataclass(slots=True)
class Circuit:
    """Canonical circuit: ports + ideal R/L/C elements on named nodes."""

    elements: list[Element]
    port_in: Port
    port_out: Port
    ground: str = "gnd"
    topology_id: TopologyId | None = None
    meta: dict[str, object] = field(default_factory=dict)
    #: Ideal output transformer turns ratio Np/Ns (ladder side : load side).
    #: ``Zin_primary = ratio**2 * Z_load``; 1.0 means no transformer.
    output_transformer_ratio: float = 1.0
    #: Optional modeled output balun/unun (mutually exclusive with T1).
    output_balun: BalunSpec | None = None

    def __post_init__(self) -> None:
        if self.output_transformer_ratio <= 0.0:
            raise ValueError("output_transformer_ratio must be > 0")
        if self.output_balun is not None and self.output_transformer_ratio != 1.0:
            raise ValueError(
                "output_balun and output_transformer_ratio cannot both be set"
            )

    def ladder_elements(self) -> list[Element]:
        """Elements in ladder order (excludes terminations if ever present)."""
        return list(self.elements)

    def component_table(
        self,
    ) -> list[dict[str, float | str | None]]:
        rows: list[dict[str, float | str | None]] = []
        for el in self.elements:
            row: dict[str, float | str | None] = {
                "ref": el.id,
                "role": el.role.value,
                "type": el.element_type.value,
                "g": el.g,
            }
            if isinstance(el, IdealCapacitor):
                row["value_F"] = el.value_f
            elif isinstance(el, IdealInductor):
                row["value_H"] = el.value_h
            elif isinstance(el, (IdealSeriesLC, IdealParallelLC)):
                row["value_H"] = el.value_h
                row["value_F"] = el.value_f
            elif isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
                row["series_L_H"] = el.series_l_h
                row["series_C_F"] = el.series_c_f
                row["parallel_L_H"] = el.parallel_l_h
                row["parallel_C_F"] = el.parallel_c_f
            elif isinstance(el, NonIdealInductor):
                row["value_H"] = el.value_h
                row["series_R_Ohm"] = el.series_resistance_ohm
                row["parallel_C_F"] = el.parallel_capacitance_f
            elif isinstance(el, NonIdealCapacitor):
                row["value_F"] = el.value_f
                row["esr_Ohm"] = el.esr_ohm
                row["esl_H"] = el.esl_h
            elif isinstance(el, MicrostripLineElement):
                row["z0_Ohm"] = el.z0_ohm
                row["length_m"] = el.length_m
                row["eeff"] = el.eeff
                row["loss_db_per_m"] = el.loss_db_per_m
                row["substrate"] = el.substrate
                row["width_mm"] = el.width_mm
                row["angle_deg"] = el.angle_deg
            elif isinstance(el, MicrostripStubElement):
                row["z0_Ohm"] = el.z0_ohm
                row["length_m"] = el.length_m
                row["eeff"] = el.eeff
                row["loss_db_per_m"] = el.loss_db_per_m
                row["stub_kind"] = el.stub_kind.value
                row["substrate"] = el.substrate
                row["width_mm"] = el.width_mm
                row["angle_deg"] = el.angle_deg
            else:
                row["value_Ohm"] = el.value_ohm
            rows.append(row)
        if self.output_transformer_ratio != 1.0:
            rows.append(
                {
                    "ref": "T1",
                    "role": "series",
                    "type": "transformer",
                    "g": None,
                    "turns_ratio": self.output_transformer_ratio,
                }
            )
        if self.output_balun is not None:
            rows.append(
                {
                    "ref": "BAL1",
                    "role": "series",
                    "type": "balun",
                    "g": None,
                    "turns_ratio": self.output_balun.turns_ratio,
                    "kind": self.output_balun.kind,
                }
            )
        return rows


ArmKind = Literal[
    "series_L",
    "series_C",
    "shunt_L",
    "shunt_C",
    "series_series_LC",
    "shunt_parallel_LC",
    "series_parallel_LC",
    "shunt_series_LC",
    "series_brune_LC",
    "shunt_brune_LC",
    "series_dual_brune_LC",
    "shunt_dual_brune_LC",
]
