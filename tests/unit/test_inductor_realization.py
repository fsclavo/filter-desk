"""Realize circuit inductors with toroid / air-core windings."""

from __future__ import annotations

from dataclasses import replace

import pytest

from filterdesk.components_std import find_core
from filterdesk.components_std.toroid import design_toroid
from filterdesk.domain.circuit import (
    Circuit,
    IdealInductor,
    NonIdealInductor,
    Port,
)
from filterdesk.domain.enums import ElementRole
from filterdesk.io.build_sheet import build_sheet_rows
from filterdesk.services.inductor_realization import (
    InductorRealizationError,
    apply_realization,
    realize_air_coil,
    realize_from_toroid_design,
    realize_toroid,
)


def _ports() -> tuple[Port, Port]:
    return (
        Port(name="port1", node="in", impedance_ohm=50.0),
        Port(name="port2", node="out", impedance_ohm=50.0),
    )


def _ideal(value_h: float = 1e-6) -> IdealInductor:
    return IdealInductor("L1", value_h, "in", "out", ElementRole.SERIES)


def _circuit(element: IdealInductor | NonIdealInductor) -> Circuit:
    port_in, port_out = _ports()
    return Circuit(elements=[element], port_in=port_in, port_out=port_out)


def test_realize_toroid_populates_winding_and_dcr() -> None:
    core = find_core("FT50-43")
    realization = realize_toroid(_ideal(), core, current_a=1.0)
    element = realization.element
    assert element.value_h > 0.0
    assert element.winding is not None
    assert element.winding.kind == "toroid"
    assert element.winding.core == core.name
    assert element.winding.turns and element.winding.turns >= 1
    assert element.winding.wire_awg is not None
    assert realization.dcr_ohm > 0.0
    assert element.series_resistance_ohm == pytest.approx(realization.dcr_ohm)
    assert realization.saturation_current_a is not None
    assert realization.saturation_current_a > 0.0
    assert element.saturation_current_a == pytest.approx(
        realization.saturation_current_a
    )


def test_realize_from_toroid_design_preserves_model_fields() -> None:
    core = find_core("T50-2")
    design = design_toroid(core, inductance_h=1e-6, current_a=0.0)
    existing = NonIdealInductor(
        id="L1",
        value_h=1e-6,
        node_a="in",
        node_b="out",
        role=ElementRole.SERIES,
        srf_hz=200e6,
        loss_model="dc_skin",
    )
    realization = realize_from_toroid_design(existing, design)
    assert realization.element.srf_hz == pytest.approx(200e6)
    assert realization.element.loss_model == "dc_skin"
    assert realization.element.winding is not None


def test_realize_air_coil() -> None:
    realization = realize_air_coil(
        _ideal(), diameter_mm=10.0, awg=20
    )
    element = realization.element
    assert element.winding is not None
    assert element.winding.kind == "air"
    assert element.winding.turns and element.winding.turns >= 1
    assert realization.dcr_ohm > 0.0
    assert realization.saturation_current_a is None
    assert element.saturation_current_a is None


def test_apply_realization_replaces_element() -> None:
    circuit = _circuit(_ideal())
    realization = realize_air_coil(_ideal(), diameter_mm=10.0, awg=20)
    updated = apply_realization(circuit, realization)
    assert len(updated.elements) == 1
    element = updated.elements[0]
    assert isinstance(element, NonIdealInductor)
    assert element.id == "L1"
    assert element.winding == realization.element.winding
    # Original circuit is untouched (frozen copy).
    assert isinstance(circuit.elements[0], IdealInductor)


def test_apply_realization_unknown_element() -> None:
    circuit = _circuit(_ideal())
    realization = realize_air_coil(_ideal(), diameter_mm=10.0, awg=20)
    unknown = replace(
        realization, element=replace(realization.element, id="L9")
    )
    with pytest.raises(InductorRealizationError):
        apply_realization(circuit, unknown)


def test_build_sheet_uses_realized_winding() -> None:
    core = find_core("FT50-43")
    realization = realize_toroid(_ideal(), core, current_a=1.0)
    updated = apply_realization(_circuit(_ideal()), realization)
    row = build_sheet_rows(updated)[0]
    assert row.core == core.name
    assert row.turns == realization.element.winding.turns  # type: ignore[union-attr]
    assert row.wire_awg is not None
    assert row.dcr_ohm is not None and row.dcr_ohm > 0.0
    assert row.srf_hz is None
