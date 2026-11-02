"""Apply assigned real parts to system circuits."""

from __future__ import annotations

from dataclasses import replace

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std import (
    STARTER_PARTS,
    ManufacturerModel,
    ModelPoint,
)
from filterdesk.domain.circuit import NonIdealInductor
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.services.diplexer import DiplexerConfig, design_diplexer
from filterdesk.services.part_application import apply_assigned_parts
from filterdesk.services.part_assignment import assign_nearest_parts


def _design():
    return design_diplexer(
        DiplexerConfig(
            low_cutoff_hz=30e6,
            high_cutoff_hz=40e6,
            order=5,
            family=ApproximationFamily.CHEBYSHEV_TYPE_I,
            ripple_db=0.1,
        ),
        SweepConfig(1e6, 200e6, 201, SweepSpacing.LOGARITHMIC),
    )


def test_apply_assigned_parts_changes_values_and_reanalyzes() -> None:
    design = _design()
    assigned = assign_nearest_parts(
        [("Low", design.low_circuit), ("High", design.high_circuit)],
        STARTER_PARTS,
        max_delta_pct=100.0,
    )
    result = apply_assigned_parts(design, assigned.assignments)
    assert result.applied
    assert result.design.network.n_ports == 3
    assert result.design.metrics is not design.metrics
    assert result.design.low_circuit.elements
    assert not result.warnings


def test_composite_parts_apply_subpart_models() -> None:
    from filterdesk.services.multiplexer import (
        MultiplexerBand,
        MultiplexerConfig,
        design_multiplexer,
    )

    design = design_multiplexer(
        MultiplexerConfig(
            bands=(
                MultiplexerBand("low", 14e6, 0.3e6),
                MultiplexerBand("mid", 21e6, 0.5e6),
                MultiplexerBand("high", 28e6, 0.5e6),
            ),
            order=5,
            family=ApproximationFamily.CHEBYSHEV_TYPE_I,
            ripple_db=0.1,
        ),
        SweepConfig(5e6, 40e6, 201, SweepSpacing.LOGARITHMIC),
    )
    branches = [
        (band.label.capitalize(), circuit)
        for band, circuit in zip(design.bands, design.circuits, strict=True)
    ]
    assigned = assign_nearest_parts(branches, STARTER_PARTS, max_delta_pct=100.0)
    result = apply_assigned_parts(design, assigned.assignments)
    assert result.applied
    assert not any("composite" in warning for warning in result.warnings)
    assert any(
        el.l_series_resistance_ohm > 0.0
        or el.l_srf_hz is not None
        for el in result.design.circuits[0].elements
        if hasattr(el, "l_series_resistance_ohm")
    )


def test_manufacturer_q_curve_is_applied_to_simple_inductor() -> None:
    design = _design()
    assigned = assign_nearest_parts(
        [("Low", design.low_circuit), ("High", design.high_circuit)],
        STARTER_PARTS,
        max_delta_pct=100.0,
    )
    key, part = next(
        (key, part)
        for key, part in assigned.assignments.items()
        if part.kind == "inductor" and ":L" in key
    )
    modelled = replace(
        part,
        model=ManufacturerModel(
            model_id="test-q",
            confidence="datasheet",
            q_points=(
                ModelPoint(1e6, 80.0),
                ModelPoint(50e6, 40.0),
            ),
        ),
    )
    result = apply_assigned_parts(design, {key: modelled})
    branch, ref = key.split(":", 1)
    circuit = (
        result.design.low_circuit
        if branch == "Low"
        else result.design.high_circuit
    )
    element = next(
        el
        for el in circuit.elements
        if el.id == ref and isinstance(el, NonIdealInductor)
    )
    assert element.q_curve == ((1e6, 80.0), (50e6, 40.0))
