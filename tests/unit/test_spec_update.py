"""Manual target updates derived from the current circuit response."""

from __future__ import annotations

from dataclasses import replace

import pytest

from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.circuit import IdealCapacitor, IdealInductor
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.gui.commands import SetSpecCommand
from filterdesk.services.session import DesignSession
from filterdesk.services.spec_update import (
    SpecUpdateError,
    update_spec_from_response,
)
from filterdesk.synthesis import synthesize


def _hpf(cutoff_hz: float = 10e6) -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.HIGH_PASS,
        order=7,
        cutoff_hz=cutoff_hz,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_HP_SERIES_C_INPUT,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.1,
    )


def _analysis(spec: FilterSpec, scale: float = 1.0):
    circuit = synthesize(spec).circuit
    elements = []
    for el in circuit.elements:
        if isinstance(el, IdealCapacitor):
            elements.append(replace(el, value_f=el.value_f * scale))
        elif isinstance(el, IdealInductor):
            elements.append(replace(el, value_h=el.value_h * scale))
        else:
            elements.append(el)
    circuit = replace(circuit, elements=elements)
    sweep = SweepConfig(1e5, 1e8, 20000, SweepSpacing.LOGARITHMIC)
    return circuit, analyze_circuit(circuit, sweep)


def test_hpf_target_update_preserves_structure() -> None:
    spec = _hpf(10e6)
    circuit, analysis = _analysis(spec)
    update = update_spec_from_response(spec, circuit, analysis)
    assert update.new_spec.family is spec.family
    assert update.new_spec.order == spec.order
    assert update.new_spec.topology_id is spec.topology_id
    assert update.new_spec.cutoff_definition is CutoffDefinition.RIPPLE_EDGE
    assert update.new_spec.cutoff_hz == pytest.approx(10e6, rel=1e-6)
    assert update.criterion == "passband ripple edge"
    assert update.threshold_db == pytest.approx(-0.1)


def test_scaled_circuit_derives_shifted_cutoff() -> None:
    spec = _hpf(10e6)
    circuit, analysis = _analysis(spec, scale=10.0)
    update = update_spec_from_response(spec, circuit, analysis)
    assert update.new_spec.cutoff_hz == pytest.approx(1e6, rel=1e-6)
    assert update.old_spec.cutoff_hz == 10e6


def test_update_errors_when_no_crossing() -> None:
    spec = _hpf(10e6)
    circuit, _ = _analysis(spec)
    analysis = analyze_circuit(
        circuit, SweepConfig(100e6, 200e6, 101, SweepSpacing.LOGARITHMIC)
    )
    with pytest.raises(SpecUpdateError, match="no .* crossing"):
        update_spec_from_response(spec, circuit, analysis)


def test_set_spec_command_undo_keeps_circuit() -> None:
    session = DesignSession()
    session.synthesize()
    old_spec = session.spec
    old_circuit = session.circuit
    new_spec = replace(old_spec, cutoff_hz=50e6)

    class DummyUndo:
        def push(self, command):
            command.redo()

    undo = DummyUndo()
    command = SetSpecCommand(session, new_spec)
    undo.push(command)
    assert session.spec.cutoff_hz == 50e6
    assert session.circuit is old_circuit
    command.undo()
    assert session.spec == old_spec
    assert session.circuit is old_circuit


def test_design_menu_has_update_spec() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    design = next(
        a.menu() for a in window.menuBar().actions() if "&Design" in a.text()
    )
    labels = [a.text().replace("&", "") for a in design.actions()]
    assert any("Update spec from circuit" in label for label in labels)
    window.close()
    assert app is not None
