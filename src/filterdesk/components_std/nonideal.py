"""Build non-ideal (lossy / parasitic) elements from ideal ones (FR-P2)."""

from __future__ import annotations

import math

from filterdesk.domain.circuit import (
    Circuit,
    Element,
    IdealCapacitor,
    IdealInductor,
    NonIdealCapacitor,
    NonIdealInductor,
)


def inductor_resistance_ohm_from_q(
    value_h: float, q: float, frequency_hz: float
) -> float:
    """Series resistance for a finite unloaded ``q`` at ``frequency_hz``."""
    if q <= 0.0:
        raise ValueError("q must be > 0")
    if frequency_hz <= 0.0:
        raise ValueError("frequency_hz must be > 0")
    return 2.0 * math.pi * frequency_hz * value_h / q


def make_nonideal_inductor(
    el: IdealInductor,
    *,
    series_resistance_ohm: float = 0.0,
    parallel_capacitance_f: float = 0.0,
) -> NonIdealInductor:
    return NonIdealInductor(
        id=el.id,
        value_h=el.value_h,
        node_a=el.node_a,
        node_b=el.node_b,
        role=el.role,
        series_resistance_ohm=series_resistance_ohm,
        parallel_capacitance_f=parallel_capacitance_f,
        g=el.g,
    )


def make_nonideal_capacitor(
    el: IdealCapacitor,
    *,
    esr_ohm: float = 0.0,
    esl_h: float = 0.0,
) -> NonIdealCapacitor:
    return NonIdealCapacitor(
        id=el.id,
        value_f=el.value_f,
        node_a=el.node_a,
        node_b=el.node_b,
        role=el.role,
        esr_ohm=esr_ohm,
        esl_h=esl_h,
        g=el.g,
    )


def nonidealize_circuit(
    circuit: Circuit,
    *,
    inductor_q: float | None = None,
    q_frequency_hz: float | None = None,
    inductor_dcr_ohm: float = 0.0,
    inductor_parallel_capacitance_f: float = 0.0,
    capacitor_esr_ohm: float = 0.0,
    capacitor_esl_h: float = 0.0,
) -> Circuit:
    """Return a copy where inductors/capacitors gain loss / parasitics.

    Inductors become ``NonIdealInductor`` when they get a non-zero series
    resistance (``inductor_dcr_ohm`` plus, if ``inductor_q`` is given,
    ``ω_ref·L/Q`` at ``q_frequency_hz``) or a parallel capacitance; capacitors
    become ``NonIdealCapacitor`` when they get a non-zero ESR or ESL. Elements
    with no applied loss are left untouched.
    """
    if inductor_q is not None and q_frequency_hz is None:
        raise ValueError("q_frequency_hz is required when inductor_q is given")
    new_elements: list[Element] = []
    for el in circuit.elements:
        if isinstance(el, IdealInductor):
            r = inductor_dcr_ohm
            if inductor_q is not None:
                assert q_frequency_hz is not None
                r += inductor_resistance_ohm_from_q(
                    el.value_h, inductor_q, q_frequency_hz
                )
            if r > 0.0 or inductor_parallel_capacitance_f > 0.0:
                new_elements.append(
                    make_nonideal_inductor(
                        el,
                        series_resistance_ohm=r,
                        parallel_capacitance_f=inductor_parallel_capacitance_f,
                    )
                )
            else:
                new_elements.append(el)
        elif isinstance(el, IdealCapacitor):
            if capacitor_esr_ohm > 0.0 or capacitor_esl_h > 0.0:
                new_elements.append(
                    make_nonideal_capacitor(
                        el, esr_ohm=capacitor_esr_ohm, esl_h=capacitor_esl_h
                    )
                )
            else:
                new_elements.append(el)
        else:
            new_elements.append(el)
    return Circuit(
        elements=new_elements,
        port_in=circuit.port_in,
        port_out=circuit.port_out,
        ground=circuit.ground,
        topology_id=circuit.topology_id,
        meta=dict(circuit.meta),
    )


def set_element_parasitics(
    circuit: Circuit,
    element_id: str,
    *,
    series_resistance_ohm: float | None = None,
    parallel_capacitance_f: float | None = None,
    esr_ohm: float | None = None,
    esl_h: float | None = None,
) -> Circuit:
    """Return a copy with one L/C arm's parasitics changed (per-part editing).

    For an inductor, ``series_resistance_ohm`` / ``parallel_capacitance_f`` are
    applied; for a capacitor, ``esr_ohm`` / ``esl_h``. ``None`` keeps the current
    value. An element with all-zero parasitics is converted back to its ideal
    type, a non-zero one to the non-ideal type. Raises ``KeyError`` if the id is
    unknown and ``ValueError`` if it is not a two-terminal L/C arm.
    """
    target = next((el for el in circuit.elements if el.id == element_id), None)
    if target is None:
        raise KeyError(element_id)
    new_elements: list[Element] = []
    replaced = False
    for el in circuit.elements:
        if el.id != element_id:
            new_elements.append(el)
            continue
        if isinstance(el, (IdealInductor, NonIdealInductor)):
            cur_r = (
                el.series_resistance_ohm if isinstance(el, NonIdealInductor) else 0.0
            )
            cur_cp = (
                el.parallel_capacitance_f if isinstance(el, NonIdealInductor) else 0.0
            )
            r = cur_r if series_resistance_ohm is None else series_resistance_ohm
            cp = (
                cur_cp
                if parallel_capacitance_f is None
                else parallel_capacitance_f
            )
            replaced = True
            if r == 0.0 and cp == 0.0:
                new_elements.append(
                    IdealInductor(
                        id=el.id,
                        value_h=el.value_h,
                        node_a=el.node_a,
                        node_b=el.node_b,
                        role=el.role,
                        g=el.g,
                    )
                )
            else:
                new_elements.append(
                    NonIdealInductor(
                        id=el.id,
                        value_h=el.value_h,
                        node_a=el.node_a,
                        node_b=el.node_b,
                        role=el.role,
                        series_resistance_ohm=r,
                        parallel_capacitance_f=cp,
                        g=el.g,
                    )
                )
        elif isinstance(el, (IdealCapacitor, NonIdealCapacitor)):
            cur_esr = el.esr_ohm if isinstance(el, NonIdealCapacitor) else 0.0
            cur_esl = el.esl_h if isinstance(el, NonIdealCapacitor) else 0.0
            esr = cur_esr if esr_ohm is None else esr_ohm
            esl = cur_esl if esl_h is None else esl_h
            replaced = True
            if esr == 0.0 and esl == 0.0:
                new_elements.append(
                    IdealCapacitor(
                        id=el.id,
                        value_f=el.value_f,
                        node_a=el.node_a,
                        node_b=el.node_b,
                        role=el.role,
                        g=el.g,
                    )
                )
            else:
                new_elements.append(
                    NonIdealCapacitor(
                        id=el.id,
                        value_f=el.value_f,
                        node_a=el.node_a,
                        node_b=el.node_b,
                        role=el.role,
                        esr_ohm=esr,
                        esl_h=esl,
                        g=el.g,
                    )
                )
        else:
            raise ValueError(f"element {element_id} is not an L/C arm")
    if not replaced:
        raise KeyError(element_id)
    return Circuit(
        elements=new_elements,
        port_in=circuit.port_in,
        port_out=circuit.port_out,
        ground=circuit.ground,
        topology_id=circuit.topology_id,
        meta=dict(circuit.meta),
    )
