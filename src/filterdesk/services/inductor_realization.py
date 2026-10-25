"""Realize a circuit inductor with a toroid or air-core winding.

Uses the component calculators to turn an ideal (or partly non-ideal) inductor
into a physical part: achieved inductance, DC resistance from the wire, winding
provenance (for the BOM) and, for toroids, a saturation current.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from filterdesk.components_std.air_coil import (
    COPPER_RESISTIVITY_OHM_M,
    AirCoilDesign,
    design_air_coil,
)
from filterdesk.components_std.toroid import (
    ToroidCore,
    ToroidDesign,
    design_toroid,
)
from filterdesk.domain.circuit import (
    Circuit,
    Element,
    IdealInductor,
    NonIdealInductor,
    WindingSpec,
)


class InductorRealizationError(ValueError):
    """Raised when a winding design cannot be applied to an inductor."""


@dataclass(frozen=True, slots=True)
class InductorRealization:
    element: NonIdealInductor
    dcr_ohm: float
    saturation_current_a: float | None
    notes: tuple[str, ...]


def _wire_resistance_ohm(wire_length_m: float, bare_mm: float | None) -> float:
    if bare_mm is None or bare_mm <= 0.0 or wire_length_m <= 0.0:
        return 0.0
    area_m2 = math.pi * (bare_mm / 1000.0 / 2.0) ** 2
    return COPPER_RESISTIVITY_OHM_M * wire_length_m / area_m2


def _existing(element: IdealInductor | NonIdealInductor) -> NonIdealInductor | None:
    return element if isinstance(element, NonIdealInductor) else None


def _notes_for_toroid(
    design: ToroidDesign, target_h: float, current_a: float
) -> list[str]:
    notes: list[str] = []
    if target_h > 0.0 and abs(design.inductance_h - target_h) > 1e-12:
        notes.append(
            f"achieved L = {design.inductance_h * 1e9:.3f} nH "
            f"(target {target_h * 1e9:.3f} nH)"
        )
    if not design.wire.fits:
        notes.append(
            "wire does not fit in one layer; use a finer gauge or a larger core"
        )
    if design.saturated:
        notes.append(
            f"core saturates at {current_a:g} A "
            f"(B/Bsat = {design.saturation_ratio:.2f})"
        )
    elif design.saturation_ratio is not None:
        notes.append(
            f"B/Bsat = {design.saturation_ratio:.2f} at {current_a:g} A"
        )
    return notes


def realize_from_toroid_design(
    element: IdealInductor | NonIdealInductor,
    design: ToroidDesign,
    *,
    current_a: float = 0.0,
) -> InductorRealization:
    """Apply a toroid design (turns/L/wire) to ``element``."""
    previous = _existing(element)
    dcr = _wire_resistance_ohm(design.wire_length_m, design.wire.diameter_mm)
    core = design.core
    saturation_current: float | None = None
    if (
        core.bsat_t is not None
        and core.bsat_t > 0.0
        and core.ae_mm2 > 0.0
        and design.turns > 0
        and design.inductance_h > 0.0
    ):
        saturation_current = (
            core.bsat_t * design.turns * core.ae_mm2 * 1e-6 / design.inductance_h
        )
    winding = WindingSpec(
        kind="toroid",
        core=core.name,
        material=core.material,
        turns=design.turns,
        wire_awg=design.wire.awg,
        wire_bare_mm=design.wire.diameter_mm,
        wire_overall_mm=design.wire.diameter_mm,
    )
    realized = NonIdealInductor(
        id=element.id,
        value_h=design.inductance_h,
        node_a=element.node_a,
        node_b=element.node_b,
        role=element.role,
        series_resistance_ohm=dcr,
        parallel_capacitance_f=(
            previous.parallel_capacitance_f if previous is not None else 0.0
        ),
        g=element.g,
        q_ref=previous.q_ref if previous is not None else None,
        q_frequency_hz=previous.q_frequency_hz if previous is not None else None,
        srf_hz=previous.srf_hz if previous is not None else None,
        loss_model=previous.loss_model if previous is not None else "constant",
        dc_current_a=current_a,
        saturation_current_a=saturation_current,
        winding=winding,
    )
    target = design.target_inductance_h or 0.0
    return InductorRealization(
        element=realized,
        dcr_ohm=dcr,
        saturation_current_a=saturation_current,
        notes=tuple(_notes_for_toroid(design, target, current_a)),
    )


def realize_toroid(
    element: IdealInductor | NonIdealInductor,
    core: ToroidCore,
    *,
    current_a: float = 0.0,
) -> InductorRealization:
    """Design a toroid for the element's inductance and apply it."""
    design = design_toroid(
        core, inductance_h=element.value_h, current_a=current_a
    )
    return realize_from_toroid_design(element, design, current_a=current_a)


def realize_from_air_design(
    element: IdealInductor | NonIdealInductor,
    design: AirCoilDesign,
) -> InductorRealization:
    """Apply an air-core design to ``element`` (no saturation model)."""
    previous = _existing(element)
    winding = WindingSpec(
        kind="air",
        turns=design.turns,
        wire_awg=design.awg,
        wire_bare_mm=design.wire_diameter_mm,
        wire_overall_mm=design.overall_diameter_mm,
    )
    realized = NonIdealInductor(
        id=element.id,
        value_h=design.inductance_h,
        node_a=element.node_a,
        node_b=element.node_b,
        role=element.role,
        series_resistance_ohm=design.resistance_ohm,
        parallel_capacitance_f=(
            previous.parallel_capacitance_f if previous is not None else 0.0
        ),
        g=element.g,
        q_ref=previous.q_ref if previous is not None else None,
        q_frequency_hz=previous.q_frequency_hz if previous is not None else None,
        srf_hz=previous.srf_hz if previous is not None else None,
        loss_model=previous.loss_model if previous is not None else "constant",
        dc_current_a=0.0,
        saturation_current_a=None,
        winding=winding,
    )
    notes: list[str] = []
    if design.short_coil:
        notes.append("short coil: Wheeler's formula loses accuracy")
    return InductorRealization(
        element=realized,
        dcr_ohm=design.resistance_ohm,
        saturation_current_a=None,
        notes=tuple(notes),
    )


def realize_air_coil(
    element: IdealInductor | NonIdealInductor,
    *,
    diameter_mm: float,
    awg: int | None = None,
    wire_diameter_mm: float | None = None,
    enamel_build_mm: float | None = None,
) -> InductorRealization:
    """Design an air-core coil for the element's inductance and apply it."""
    design = design_air_coil(
        diameter_mm=diameter_mm,
        awg=awg,
        wire_diameter_mm=wire_diameter_mm,
        enamel_build_mm=enamel_build_mm,
        inductance_h=element.value_h,
    )
    return realize_from_air_design(element, design)


def apply_realization(
    circuit: Circuit, realization: InductorRealization
) -> Circuit:
    """Return a copy of ``circuit`` with the realized inductor installed."""
    target = realization.element.id
    replaced = False
    elements: list[Element] = []
    for element in circuit.elements:
        if element.id == target:
            elements.append(realization.element)
            replaced = True
        else:
            elements.append(element)
    if not replaced:
        raise InductorRealizationError(f"unknown element: {target}")
    return replace(circuit, elements=elements)


__all__ = [
    "InductorRealization",
    "InductorRealizationError",
    "apply_realization",
    "realize_air_coil",
    "realize_from_air_design",
    "realize_from_toroid_design",
    "realize_toroid",
]
