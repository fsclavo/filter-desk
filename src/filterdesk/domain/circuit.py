"""Canonical lumped circuit model (GUI-independent)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from filterdesk.domain.enums import ElementRole, ElementType, TopologyId


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
class NonIdealInductor:
    """Inductor with series resistance (DCR / finite Q) and parasitic parallel C.

    Two-terminal model: ``(R + jw L) || 1/(jw Cp)``. Used as a series or shunt arm.
    """

    id: str
    value_h: float
    node_a: str
    node_b: str
    role: ElementRole
    series_resistance_ohm: float = 0.0
    parallel_capacitance_f: float = 0.0
    g: float | None = None

    @property
    def element_type(self) -> ElementType:
        return ElementType.NONIDEAL_INDUCTOR

    @property
    def self_resonant_frequency_hz(self) -> float | None:
        if self.parallel_capacitance_f <= 0.0:
            return None
        return 1.0 / (
            2.0 * math.pi * math.sqrt(self.value_h * self.parallel_capacitance_f)
        )


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
                    series_resistance_ohm=el.series_resistance_ohm,
                    parallel_capacitance_f=el.parallel_capacitance_f,
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
            else:
                row["value_Ohm"] = el.value_ohm
            rows.append(row)
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
