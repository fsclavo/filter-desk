"""Manufacturer Q/ESR curves, persistence and analysis."""

from __future__ import annotations

import math

import numpy as np
import pytest

from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig
from filterdesk.components_std import (
    ManufacturerModel,
    ModelPoint,
    library_from_mapping,
    library_to_mapping,
)
from filterdesk.components_std.library import LibraryPart
from filterdesk.domain.circuit import (
    Circuit,
    ElementRole,
    NonIdealCapacitor,
    NonIdealInductor,
    Port,
)
from filterdesk.domain.project import Project, project_from_mapping, project_to_mapping


def _model() -> ManufacturerModel:
    return ManufacturerModel(
        model_id="test-model",
        source="datasheet",
        confidence="datasheet",
        q_points=(ModelPoint(1e6, 100.0), ModelPoint(10e6, 50.0)),
        esr_points=(ModelPoint(1e6, 0.1), ModelPoint(10e6, 1.0)),
    )


def test_model_interpolation_and_validation() -> None:
    model = _model()
    assert model.q_at(1e6) == pytest.approx(100.0)
    assert model.q_at(10e6) == pytest.approx(50.0)
    assert model.q_at(3.1622776601683795e6) == pytest.approx(
        math.sqrt(100.0 * 50.0), rel=1e-6
    )
    assert model.esr_at(3.1622776601683795e6) == pytest.approx(
        math.sqrt(0.1 * 1.0), rel=1e-6
    )
    with pytest.raises(ValueError):
        ManufacturerModel(q_points=(ModelPoint(10e6, 50), ModelPoint(1e6, 100)))
    with pytest.raises(ValueError):
        ModelPoint(0.0, 10.0)


def test_library_model_round_trip() -> None:
    part = LibraryPart(
        "test",
        "Maker",
        "MPN-1",
        "inductor",
        10e-9,
        "H",
        "0603",
        model=_model(),
    )
    data = library_to_mapping((part,))
    loaded = library_from_mapping(data)[0]
    assert loaded.model is not None
    assert loaded.model.model_id == "test-model"
    assert loaded.model.q_at(1e6) == pytest.approx(100.0)


def test_project_persists_curves() -> None:
    circuit = Circuit(
        [
            NonIdealInductor(
                "L1",
                1e-6,
                "in",
                "out",
                ElementRole.SERIES,
                q_curve=((1e6, 100.0), (10e6, 50.0)),
            ),
            NonIdealCapacitor(
                "C1",
                1e-12,
                "out",
                "gnd",
                ElementRole.SHUNT,
                esr_curve=((1e6, 0.1), (10e6, 1.0)),
            ),
        ],
        Port("P1", "in", 50.0),
        Port("P2", "out", 50.0),
    )
    project = Project(circuit=circuit)
    loaded = project_from_mapping(project_to_mapping(project))
    assert loaded.circuit is not None
    inductor = loaded.circuit.elements[0]
    capacitor = loaded.circuit.elements[1]
    assert isinstance(inductor, NonIdealInductor)
    assert isinstance(capacitor, NonIdealCapacitor)
    assert inductor.q_curve == ((1e6, 100.0), (10e6, 50.0))
    assert capacitor.esr_curve == ((1e6, 0.1), (10e6, 1.0))


def test_q_curve_changes_inductor_loss() -> None:
    inductor = NonIdealInductor(
        "L1",
        1e-6,
        "in",
        "out",
        ElementRole.SERIES,
        q_curve=((1e6, 100.0), (10e6, 50.0)),
    )
    circuit = Circuit(
        [inductor], Port("P1", "in", 50.0), Port("P2", "out", 50.0)
    )
    sweep = SweepConfig(f_start_hz=1e6, f_stop_hz=10e6, n_points=2)
    result = analyze_circuit(circuit, sweep)
    z1 = (
        2.0 * math.pi * 1e6 * 1e-6 / 100.0
        + 1j * 2.0 * math.pi * 1e6 * 1e-6
    )
    z2 = (
        2.0 * math.pi * 10e6 * 1e-6 / 50.0
        + 1j * 2.0 * math.pi * 10e6 * 1e-6
    )
    assert result.s21[0] == pytest.approx(100.0 / (100.0 + z1), rel=1e-6)
    assert result.s21[1] == pytest.approx(100.0 / (100.0 + z2), rel=1e-6)
    assert np.abs(result.s21[1]) < np.abs(result.s21[0])
