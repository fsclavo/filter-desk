"""Apply assigned real parts to system circuits."""

from __future__ import annotations

from dataclasses import replace

import pytest

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std import (
    STARTER_PARTS,
    LibraryPart,
    ManufacturerModel,
    ModelPoint,
)
from filterdesk.domain.circuit import NonIdealInductor
from filterdesk.domain.enums import ApproximationFamily, ElementRole
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


def _part(kind: str, value_si: float, **kwargs) -> LibraryPart:  # type: ignore[no-untyped-def]
    return LibraryPart(
        id=f"test-{kind}",
        manufacturer="Test",
        mpn=f"TEST-{kind}",
        kind=kind,
        value_si=value_si,
        unit="H" if kind == "inductor" else "F",
        package="0603",
        **kwargs,
    )


def test_replace_composite_value_branches() -> None:
    from filterdesk.domain.circuit import (
        IdealBruneLC,
        IdealDualBruneLC,
        IdealParallelLC,
        IdealSeriesLC,
    )
    from filterdesk.services.part_application import _replace_composite_value

    series = IdealSeriesLC(
        "X1", 1e-6, 1e-12, "a", "b", ElementRole.SERIES
    )
    parallel = IdealParallelLC(
        "X2", 1e-6, 1e-12, "a", "b", ElementRole.SHUNT
    )
    inductor = _part("inductor", 2e-6, dcr_ohm=0.5, srf_hz=1e9)
    capacitor = _part("capacitor", 2e-12, esr_ohm=0.2, esl_h=1e-10)
    for element in (series, parallel):
        updated_l = _replace_composite_value(element, ".L", inductor)
        assert updated_l.value_h == pytest.approx(2e-6)
        assert updated_l.l_series_resistance_ohm == pytest.approx(0.5)
        assert updated_l.l_srf_hz == pytest.approx(1e9)
        updated_c = _replace_composite_value(element, ".C", capacitor)
        assert updated_c.value_f == pytest.approx(2e-12, abs=0.0)
        assert updated_c.c_esr_ohm == pytest.approx(0.2)
        assert updated_c.c_esl_h == pytest.approx(1e-10)

    q_part = _part("inductor", 2e-6, q_min=100.0)
    updated = _replace_composite_value(series, ".L", q_part)
    expected_r = 2.0 * 3.141592653589793 * 250e6 * 2e-6 / 100.0
    assert updated.l_series_resistance_ohm == pytest.approx(
        expected_r, abs=1e-9
    )

    brune = IdealBruneLC(
        "X3", 1e-6, 1e-12, 2e-6, 2e-12, "a", "b", ElementRole.SERIES
    )
    dual = IdealDualBruneLC(
        "X4", 1e-6, 1e-12, 2e-6, 2e-12, "a", "b", ElementRole.SHUNT
    )
    brune_inductor = _part("inductor", 3e-6)
    brune_capacitor = _part("capacitor", 3e-12)
    for element in (brune, dual):
        assert _replace_composite_value(
            element, ".Ls", brune_inductor
        ).series_l_h == pytest.approx(3e-6, abs=0.0)
        assert _replace_composite_value(
            element, ".Cs", brune_capacitor
        ).series_c_f == pytest.approx(3e-12, abs=0.0)
        assert _replace_composite_value(
            element, ".Lp", brune_inductor
        ).parallel_l_h == pytest.approx(3e-6, abs=0.0)
        assert _replace_composite_value(
            element, ".Cp", brune_capacitor
        ).parallel_c_f == pytest.approx(3e-12, abs=0.0)

    with pytest.raises(ValueError, match="unsupported composite part"):
        _replace_composite_value(series, ".X", inductor)
    with pytest.raises(ValueError, match="unsupported composite part"):
        _replace_composite_value(series, ".L", capacitor)
    for suffix in (".Ls", ".Lp"):
        with pytest.raises(ValueError, match="unsupported composite part"):
            _replace_composite_value(brune, suffix, capacitor)
    for suffix in (".Cs", ".Cp"):
        with pytest.raises(ValueError, match="unsupported composite part"):
            _replace_composite_value(brune, suffix, inductor)


def test_apply_part_errors_and_composite_warnings() -> None:
    from filterdesk.domain.circuit import (
        Circuit,
        IdealBruneLC,
        Port,
    )
    from filterdesk.services.part_application import _apply_part

    ports = (Port("P1", "in", 50.0), Port("P2", "out", 50.0))
    brune = IdealBruneLC(
        "X1", 1e-6, 1e-12, 2e-6, 2e-12, "in", "out", ElementRole.SERIES
    )
    circuit = Circuit([brune], ports[0], ports[1])
    updated, warnings = _apply_part(
        circuit, "X1.Ls", _part("inductor", 3e-6)
    )
    assert updated.elements[0].series_l_h == pytest.approx(3e-6)
    assert any("value only" in warning for warning in warnings)

    with pytest.raises(KeyError, match="unknown component"):
        _apply_part(circuit, "NOPE", _part("inductor", 3e-6))
    with pytest.raises(ValueError, match="does not match"):
        _apply_part(circuit, "X1.Ls", _part("capacitor", 3e-12))


def test_apply_assigned_parts_validation_and_warnings() -> None:
    from filterdesk.services.part_application import (
        PartApplicationError,
        apply_assigned_parts,
    )

    design = _design()
    with pytest.raises(PartApplicationError, match="no assigned parts"):
        apply_assigned_parts(design, {})
    with pytest.raises(PartApplicationError, match="no assigned parts could"):
        apply_assigned_parts(design, {"bad-key": _part("inductor", 1e-6)})
    with pytest.raises(PartApplicationError, match="no assigned parts could"):
        apply_assigned_parts(design, {"Nope:L1": _part("inductor", 1e-6)})


def test_apply_part_simple_values_and_parasitics() -> None:
    from filterdesk.domain.circuit import (
        Circuit,
        IdealCapacitor,
        IdealInductor,
        IdealResistor,
        Port,
    )
    from filterdesk.services.part_application import _apply_part

    ports = (Port("P1", "in", 50.0), Port("P2", "out", 50.0))
    circuit = Circuit(
        [
            IdealResistor("R1", 50.0, "in", "n1", ElementRole.SERIES),
            IdealInductor("L2", 1e-6, "n1", "n2", ElementRole.SERIES),
            IdealCapacitor("C3", 1e-12, "n2", "out", ElementRole.SERIES),
        ],
        ports[0],
        ports[1],
    )
    updated, _ = _apply_part(
        circuit, "L2", _part("inductor", 2e-6, dcr_ohm=0.5, srf_hz=1e9)
    )
    inductor = next(el for el in updated.elements if el.id == "L2")
    assert isinstance(inductor, NonIdealInductor)
    assert inductor.value_h == pytest.approx(2e-6)
    assert inductor.series_resistance_ohm == pytest.approx(0.5)
    assert inductor.srf_hz == pytest.approx(1e9)

    q_updated, _ = _apply_part(circuit, "L2", _part("inductor", 2e-6, q_min=100.0))
    q_inductor = next(el for el in q_updated.elements if el.id == "L2")
    assert isinstance(q_inductor, NonIdealInductor)
    assert q_inductor.q_ref == pytest.approx(100.0)
    assert q_inductor.q_frequency_hz == 250e6

    cap_updated, _ = _apply_part(
        circuit, "C3", _part("capacitor", 2e-12, esr_ohm=0.2, esl_h=1e-10)
    )
    capacitor = next(el for el in cap_updated.elements if el.id == "C3")
    assert capacitor.value_f == pytest.approx(2e-12, abs=0.0)
    assert capacitor.esr_ohm == pytest.approx(0.2)
    assert capacitor.esl_h == pytest.approx(1e-10)


def test_composite_manufacturer_curve_warning() -> None:
    from filterdesk.domain.circuit import (
        Circuit,
        IdealSeriesLC,
        Port,
    )
    from filterdesk.services.part_application import _apply_part

    ports = (Port("P1", "in", 50.0), Port("P2", "out", 50.0))
    circuit = Circuit(
        [IdealSeriesLC("X1", 1e-6, 1e-12, "in", "out", ElementRole.SERIES)],
        ports[0],
        ports[1],
    )
    modelled = _part(
        "inductor",
        2e-6,
        model=ManufacturerModel(
            q_points=(ModelPoint(1e6, 100.0),),
        ),
    )
    _, warnings = _apply_part(circuit, "X1.L", modelled)
    assert warnings == [
        "X1.L: manufacturer Q/ESR curve not applied to a composite "
        "resonator; constant DCR/ESR used"
    ]


def test_partial_assignment_reports_warnings() -> None:
    design = _design()
    assigned = assign_nearest_parts(
        [("Low", design.low_circuit), ("High", design.high_circuit)],
        STARTER_PARTS,
        max_delta_pct=100.0,
    )
    key, part = next(iter(assigned.assignments.items()))
    result = apply_assigned_parts(
        design,
        {key: part, "bad-key": part},
    )
    assert result.applied == (key,)
    assert any("invalid assignment key" in warning for warning in result.warnings)


def _low_assignment(design, kind: str, value_si: float):  # type: ignore[no-untyped-def]
    from filterdesk.domain.circuit import physical_components

    component = next(
        item
        for item in physical_components(design.low_circuit)
        if item.kind == kind
    )
    return f"Low:{component.ref}", _part(kind, value_si)


def test_branches_labels_for_multiplexer_and_duplexer() -> None:
    from filterdesk.domain.circuit import Circuit, Port
    from filterdesk.services.duplexer import DuplexerDesign
    from filterdesk.services.multiplexer import MultiplexerBand, MultiplexerDesign
    from filterdesk.services.part_application import _branches

    ports = (Port("P1", "in", 50.0), Port("P2", "out", 50.0))
    circuits = tuple(Circuit([], ports[0], ports[1]) for _ in range(3))
    bands = (
        MultiplexerBand("low", 14e6, 0.3e6),
        MultiplexerBand("mid", 21e6, 0.5e6),
        MultiplexerBand("high", 28e6, 0.5e6),
    )
    multiplexer = MultiplexerDesign(
        config=None,  # type: ignore[arg-type]
        bands=bands,
        specs=(),
        circuits=circuits,
        analyses=(),
        network=None,  # type: ignore[arg-type]
        metrics=None,  # type: ignore[arg-type]
        sweep=None,  # type: ignore[arg-type]
    )
    assert _branches(multiplexer) == [
        ("Low", circuits[0]),
        ("Mid", circuits[1]),
        ("High", circuits[2]),
    ]

    tx = Circuit([], ports[0], ports[1])
    rx = Circuit([], ports[0], ports[1])
    duplexer = DuplexerDesign(
        config=None,  # type: ignore[arg-type]
        tx_spec=None,  # type: ignore[arg-type]
        rx_spec=None,  # type: ignore[arg-type]
        tx_circuit=tx,
        rx_circuit=rx,
        tx_analysis=None,  # type: ignore[arg-type]
        rx_analysis=None,  # type: ignore[arg-type]
        network=None,  # type: ignore[arg-type]
        metrics=None,  # type: ignore[arg-type]
        attempted_orders=(),
        sweep=None,  # type: ignore[arg-type]
    )
    assert _branches(duplexer) == [("TX", tx), ("RX", rx)]


def test_apply_assigned_parts_exact_errors_and_control_flow() -> None:
    from filterdesk.services.part_application import PartApplicationError

    design = _design()
    with pytest.raises(PartApplicationError) as info:
        apply_assigned_parts(design, {})
    assert str(info.value) == "no assigned parts to apply"
    with pytest.raises(PartApplicationError) as info:
        apply_assigned_parts(design, {"bad-key": _part("inductor", 1e-6)})
    assert str(info.value) == "no assigned parts could be applied"

    key, part = _low_assignment(design, "inductor", 2e-6)
    result = apply_assigned_parts(design, {"bad-key": part, key: part})
    assert result.applied == (key,)
    assert result.warnings == ("bad-key: invalid assignment key",)

    result = apply_assigned_parts(design, {"Nope:L1": part, key: part})
    assert result.applied == (key,)
    assert result.warnings == ("Nope:L1: unknown branch",)

    result = apply_assigned_parts(design, {"Low:NOPE": part, key: part})
    assert result.applied == (key,)
    assert result.warnings == ("Low:NOPE: 'unknown component NOPE'",)

    result = apply_assigned_parts(design, {key: part, "Low:L1:extra": part})
    assert result.applied == (key,)
    assert result.warnings == (
        "Low:L1:extra: 'unknown component L1:extra'",
    )


def test_apply_assigned_parts_keeps_earlier_branch_update() -> None:
    design = _design()
    l_key, l_part = _low_assignment(design, "inductor", 2e-6)
    c_key, c_part = _low_assignment(design, "capacitor", 2e-12)
    result = apply_assigned_parts(design, {l_key: l_part, c_key: c_part})
    assert result.applied == (l_key, c_key)
    elements = {el.id: el for el in result.design.low_circuit.elements}
    assert elements["L1"].value_h == pytest.approx(2e-6, abs=0.0)
    assert elements["C2"].value_f == pytest.approx(2e-12, abs=0.0)


def test_apply_part_inductor_parasitic_condition_branches() -> None:
    from filterdesk.domain.circuit import Circuit, IdealInductor, Port
    from filterdesk.services.part_application import _apply_part

    ports = (Port("P1", "in", 50.0), Port("P2", "out", 50.0))
    circuit = Circuit(
        [IdealInductor("L1", 1e-6, "in", "out", ElementRole.SERIES)],
        ports[0],
        ports[1],
    )
    dcr_only = _part("inductor", 2e-6, dcr_ohm=0.5, q_min=100.0)
    updated, _ = _apply_part(circuit, "L1", dcr_only)
    inductor = updated.elements[0]
    assert isinstance(inductor, NonIdealInductor)
    assert inductor.series_resistance_ohm == pytest.approx(0.5)
    assert inductor.q_ref is None
    assert inductor.q_frequency_hz is None
    assert inductor.srf_hz is None

    srf_only = _part("inductor", 2e-6, srf_hz=1e9)
    updated, _ = _apply_part(circuit, "L1", srf_only)
    inductor = updated.elements[0]
    assert isinstance(inductor, NonIdealInductor)
    assert inductor.srf_hz == pytest.approx(1e9)


def test_apply_part_capacitor_curve_and_single_parasitic_branches() -> None:
    from filterdesk.domain.circuit import Circuit, IdealCapacitor, Port
    from filterdesk.services.part_application import _apply_part

    ports = (Port("P1", "in", 50.0), Port("P2", "out", 50.0))
    circuit = Circuit(
        [IdealCapacitor("C1", 1e-12, "in", "out", ElementRole.SERIES)],
        ports[0],
        ports[1],
    )
    model = ManufacturerModel(
        esr_points=(ModelPoint(1e6, 0.1), ModelPoint(10e6, 1.0)),
    )
    updated, _ = _apply_part(
        circuit, "C1", _part("capacitor", 2e-12, model=model)
    )
    capacitor = updated.elements[0]
    assert capacitor.value_f == pytest.approx(2e-12, abs=0.0)
    assert capacitor.esr_curve == ((1e6, 0.1), (10e6, 1.0))

    updated, _ = _apply_part(
        circuit, "C1", _part("capacitor", 3e-12, esl_h=1e-10)
    )
    capacitor = updated.elements[0]
    assert capacitor.value_f == pytest.approx(3e-12, abs=0.0)
    assert capacitor.esl_h == pytest.approx(1e-10)

    updated, _ = _apply_part(
        circuit, "C1", _part("capacitor", 4e-12, esr_ohm=0.2)
    )
    capacitor = updated.elements[0]
    assert capacitor.value_f == pytest.approx(4e-12, abs=0.0)
    assert capacitor.esr_ohm == pytest.approx(0.2)


def test_apply_part_non_lc_and_missing_element_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from filterdesk.domain.circuit import (
        Circuit,
        IdealResistor,
        PhysicalComponent,
        Port,
    )
    from filterdesk.services import part_application as module

    ports = (Port("P1", "in", 50.0), Port("P2", "out", 50.0))
    circuit = Circuit(
        [IdealResistor("R1", 50.0, "in", "out", ElementRole.SERIES)],
        ports[0],
        ports[1],
    )
    fake = PhysicalComponent("R1", "R1", "series", "inductor", 50.0, "Ohm")
    monkeypatch.setattr(module, "physical_components", lambda _: [fake])
    with pytest.raises(ValueError) as info:
        module._apply_part(circuit, "R1", _part("inductor", 2e-6))
    assert str(info.value) == "R1 is not an L/C component"

    missing = PhysicalComponent("X1", "missing", "series", "inductor", 2e-6, "H")
    monkeypatch.setattr(module, "physical_components", lambda _: [missing])
    with pytest.raises(KeyError) as info:
        module._apply_part(circuit, "X1", _part("inductor", 2e-6))
    assert str(info.value) == "'unknown element missing'"



def test_replace_composite_capacitor_defaults_zero() -> None:
    from filterdesk.domain.circuit import IdealSeriesLC
    from filterdesk.services.part_application import _replace_composite_value

    series = IdealSeriesLC(
        "X1", 1e-6, 1e-12, "a", "b", ElementRole.SERIES
    )
    updated = _replace_composite_value(
        series, ".C", _part("capacitor", 2e-12)
    )
    assert updated.value_f == pytest.approx(2e-12, abs=0.0)
    assert updated.c_esr_ohm == 0.0
    assert updated.c_esl_h == 0.0
