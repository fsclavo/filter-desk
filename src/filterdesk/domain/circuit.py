"""Canonical lumped circuit model (GUI-independent)."""

from __future__ import annotations

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


Element = (
    IdealResistor
    | IdealCapacitor
    | IdealInductor
    | IdealSeriesLC
    | IdealParallelLC
    | IdealBruneLC
    | IdealDualBruneLC
)


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
