"""Topology editing operations for ladder circuits (pure, GUI-independent).

Edits always rebuild node names and reference designators so the resulting
:class:`Circuit` stays a valid LC ladder: series arms chain along
``in -> n1 -> ... -> out`` and shunt arms tap the current series node back to
ground.
"""

from __future__ import annotations

import math
from dataclasses import replace

from filterdesk.domain.circuit import (
    Circuit,
    Element,
    IdealCapacitor,
    IdealInductor,
    IdealResistor,
    series_node_path,
)
from filterdesk.domain.enums import ElementRole


class CircuitEditError(ValueError):
    """Raised when an edit would produce an invalid ladder."""


def reference_frequency_hz(circuit: Circuit) -> float | None:
    """Frequency used to convert between L and C (center, else cutoff)."""
    for key in ("f_center_hz", "cutoff_hz"):
        value = circuit.meta.get(key)
        if isinstance(value, (int, float)) and float(value) > 0.0:
            return float(value)
    return None


def _prefix(el: Element) -> str:
    if isinstance(el, IdealCapacitor):
        return "C"
    if isinstance(el, IdealInductor):
        return "L"
    if isinstance(el, IdealResistor):
        return "R"
    return "X"


def _index_of(elements: list[Element], element_id: str) -> int:
    for index, el in enumerate(elements):
        if el.id == element_id:
            return index
    raise CircuitEditError(f"unknown element: {element_id}")


def rebuild_ladder(circuit: Circuit, elements: list[Element]) -> Circuit:
    """Reassign node names and ids for an ordered list of ladder arms."""
    if not elements:
        raise CircuitEditError("a ladder must contain at least one element")
    num_series = sum(1 for el in elements if el.role == ElementRole.SERIES)
    nodes = series_node_path(num_series)
    cursor = 0
    current = circuit.port_in.node
    rebuilt: list[Element] = []
    for index, el in enumerate(elements, start=1):
        if el.role == ElementRole.SERIES:
            node_a = nodes[cursor]
            node_b = nodes[cursor + 1]
            cursor += 1
            current = node_b
        else:
            node_a = current
            node_b = circuit.ground
        rebuilt.append(
            replace(el, id=f"{_prefix(el)}{index}", node_a=node_a, node_b=node_b)
        )
    out_node = nodes[-1] if num_series > 0 else current
    return Circuit(
        elements=rebuilt,
        port_in=circuit.port_in,
        port_out=replace(circuit.port_out, node=out_node),
        ground=circuit.ground,
        topology_id=circuit.topology_id,
        meta=dict(circuit.meta),
    )


def insert_simple_arm(
    circuit: Circuit,
    *,
    role: ElementRole,
    kind: str,
    value_si: float,
    before_id: str | None = None,
) -> Circuit:
    """Insert a new ideal L/C/R arm before ``before_id`` (append if ``None``)."""
    if value_si <= 0.0:
        raise CircuitEditError("component value must be > 0")
    new_el: Element
    if kind == "L":
        new_el = IdealInductor(
            id="X", value_h=value_si, node_a="", node_b="", role=role
        )
    elif kind == "C":
        new_el = IdealCapacitor(
            id="X", value_f=value_si, node_a="", node_b="", role=role
        )
    elif kind == "R":
        new_el = IdealResistor(
            id="X", value_ohm=value_si, node_a="", node_b="", role=role
        )
    else:
        raise CircuitEditError(f"unsupported element kind: {kind!r}")
    elements = list(circuit.elements)
    if before_id is None:
        elements.append(new_el)
    else:
        elements.insert(_index_of(elements, before_id), new_el)
    return rebuild_ladder(circuit, elements)


def delete_arm(circuit: Circuit, element_id: str) -> Circuit:
    """Remove one arm; raises if it is the last remaining element."""
    elements = list(circuit.elements)
    del elements[_index_of(elements, element_id)]
    return rebuild_ladder(circuit, elements)


def convert_simple_arm(
    circuit: Circuit,
    element_id: str,
    target_kind: str,
    reference_hz: float,
) -> Circuit:
    """Convert an ideal L <-> C arm, preserving ``|X|`` at ``reference_hz``."""
    if target_kind not in ("L", "C"):
        raise CircuitEditError(f"unsupported target kind: {target_kind!r}")
    if reference_hz <= 0.0:
        raise CircuitEditError("reference frequency must be > 0")
    omega = 2.0 * math.pi * reference_hz
    w2 = omega * omega
    elements: list[Element] = []
    found = False
    for el in circuit.elements:
        if el.id != element_id:
            elements.append(el)
            continue
        found = True
        new_el: Element
        if isinstance(el, IdealCapacitor):
            if target_kind == "C":
                new_el = el
            else:
                new_el = IdealInductor(
                    id=el.id,
                    value_h=1.0 / (w2 * el.value_f),
                    node_a=el.node_a,
                    node_b=el.node_b,
                    role=el.role,
                    g=el.g,
                )
        elif isinstance(el, IdealInductor):
            if target_kind == "L":
                new_el = el
            else:
                new_el = IdealCapacitor(
                    id=el.id,
                    value_f=1.0 / (w2 * el.value_h),
                    node_a=el.node_a,
                    node_b=el.node_b,
                    role=el.role,
                    g=el.g,
                )
        else:
            raise CircuitEditError("only ideal L/C arms can change type")
        elements.append(new_el)
    if not found:
        raise CircuitEditError(f"unknown element: {element_id}")
    return rebuild_ladder(circuit, elements)
