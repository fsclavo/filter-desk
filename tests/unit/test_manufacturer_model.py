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
from filterdesk.components_std.manufacturer_model import (
    ManufacturerModelError,
    _interp_log,
)
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


def test_model_mapping_full_round_trip() -> None:
    model = ManufacturerModel(
        model_id="vendor-q",
        source="datasheet figure 5",
        confidence="measured",
        notes="fixture",
        q_points=(ModelPoint(1e6, 100.0), ModelPoint(10e6, 50.0)),
        esr_points=(ModelPoint(2e6, 0.2),),
    )
    mapping = model.to_mapping()
    assert mapping == {
        "model_id": "vendor-q",
        "source": "datasheet figure 5",
        "confidence": "measured",
        "notes": "fixture",
        "q_points": [[1e6, 100.0], [10e6, 50.0]],
        "esr_points": [[2e6, 0.2]],
    }
    assert ManufacturerModel.from_mapping(mapping) == model
    assert model.has_curve


def test_model_mapping_defaults_and_empty_curves() -> None:
    model = ManufacturerModel.from_mapping({})
    assert model.model_id == ""
    assert model.source == ""
    assert model.confidence == "datasheet"
    assert model.notes == ""
    assert model.q_points == ()
    assert model.esr_points == ()
    assert not model.has_curve
    assert model.to_mapping()["q_points"] == []
    assert model.q_at(1e6) is None
    assert model.esr_at(1e6) is None


def test_model_interpolation_clamps_and_linear_zero_endpoint() -> None:
    model = ManufacturerModel(
        q_points=(ModelPoint(1e6, 100.0), ModelPoint(10e6, 50.0)),
        esr_points=(ModelPoint(1e6, 0.0), ModelPoint(10e6, 1.0)),
    )
    assert model.q_at(0.1e6) == pytest.approx(100.0)
    assert model.q_at(100e6) == pytest.approx(50.0)
    assert model.esr_at(0.1e6) == pytest.approx(0.0)
    assert model.esr_at(100e6) == pytest.approx(1.0)
    assert model.esr_at(3.1622776601683795e6) == pytest.approx(0.5)
    single = ManufacturerModel(q_points=(ModelPoint(5e6, 77.0),))
    assert single.q_at(1e6) == pytest.approx(77.0)
    assert single.q_at(100e6) == pytest.approx(77.0)


def test_model_validation_rejects_bad_points_and_confidence() -> None:
    with pytest.raises(ValueError):
        ManufacturerModel(confidence="unknown")
    with pytest.raises(ValueError):
        ManufacturerModel(
            q_points=(ModelPoint(10e6, 50.0), ModelPoint(1e6, 100.0))
        )
    with pytest.raises(ValueError):
        ManufacturerModel(
            q_points=(ModelPoint(1e6, 50.0), ModelPoint(1e6, 100.0))
        )
    with pytest.raises(ValueError):
        ManufacturerModel(
            esr_points=(ModelPoint(10e6, 1.0), ModelPoint(1e6, 0.1))
        )
    with pytest.raises(ValueError):
        ManufacturerModel(
            esr_points=(ModelPoint(1e6, 0.1), ModelPoint(1e6, 1.0))
        )


def test_model_point_validation() -> None:
    with pytest.raises(ValueError):
        ModelPoint(0.0, 1.0)
    with pytest.raises(ValueError):
        ModelPoint(-1.0, 1.0)
    with pytest.raises(ValueError):
        ModelPoint(float("nan"), 1.0)
    with pytest.raises(ValueError):
        ModelPoint(float("inf"), 1.0)
    with pytest.raises(ValueError):
        ModelPoint(1e6, -1.0)
    with pytest.raises(ValueError):
        ModelPoint(1e6, float("nan"))
    with pytest.raises(ValueError):
        ModelPoint(1e6, float("inf"))


def test_model_from_mapping_rejects_invalid_documents() -> None:
    with pytest.raises(ValueError):
        ManufacturerModel.from_mapping([])
    with pytest.raises(ValueError):
        ManufacturerModel.from_mapping({"q_points": [["bad", 1]]})
    with pytest.raises(ValueError):
        ManufacturerModel.from_mapping({"q_points": [[1e6]]})
    with pytest.raises(ValueError):
        ManufacturerModel.from_mapping({"q_points": "not-a-list"})
    with pytest.raises(ValueError):
        ManufacturerModel.from_mapping(
            {"q_points": [[10e6, 50.0], [1e6, 100.0]]}
        )
    with pytest.raises(ValueError):
        ManufacturerModel.from_mapping({"confidence": "made-up"})


def test_interp_log_private_branches() -> None:
    with pytest.raises(ValueError):
        _interp_log(1e6, ())
    points = (ModelPoint(10e6, 50.0), ModelPoint(1e6, 100.0))
    assert _interp_log(1e6, points) == pytest.approx(100.0)
    assert _interp_log(5e6, points) == pytest.approx(61.6011844344503)
    assert _interp_log(1e6, (ModelPoint(1e6, 10.0),)) == pytest.approx(10.0)
    zero = (ModelPoint(1e6, 0.0), ModelPoint(10e6, 1.0))
    assert _interp_log(3.1622776601683795e6, zero) == pytest.approx(0.5)


def test_model_point_accepts_zero_value_and_sub_one_hz() -> None:
    assert ModelPoint(1e6, 0.0).value == 0.0
    assert ModelPoint(0.5, 1.0).frequency_hz == pytest.approx(0.5)


def test_error_messages_and_vendor_confidence() -> None:
    assert ManufacturerModel(confidence="vendor").confidence == "vendor"
    with pytest.raises(ManufacturerModelError, match="no model points"):
        _interp_log(1e6, ())
    with pytest.raises(ManufacturerModelError, match="model must be an object"):
        ManufacturerModel.from_mapping([])
    with pytest.raises(
        ManufacturerModelError, match="model point frequency must be > 0"
    ):
        ModelPoint(0.0, 1.0)
    with pytest.raises(
        ManufacturerModelError, match="model point value must be >= 0"
    ):
        ModelPoint(1e6, -1.0)
    with pytest.raises(
        ManufacturerModelError, match="must be sorted by frequency"
    ):
        ManufacturerModel(
            q_points=(ModelPoint(10e6, 50.0), ModelPoint(1e6, 100.0))
        )
    with pytest.raises(
        ManufacturerModelError, match="has duplicate frequencies"
    ):
        ManufacturerModel(
            q_points=(ModelPoint(1e6, 50.0), ModelPoint(1e6, 100.0))
        )
    with pytest.raises(
        ManufacturerModelError, match="unsupported model confidence"
    ):
        ManufacturerModel(confidence="unknown")
    with pytest.raises(ManufacturerModelError, match="invalid model point"):
        ManufacturerModel.from_mapping({"q_points": [["bad", 1]]})


def test_exact_error_messages_and_all_confidences() -> None:
    for confidence in ("datasheet", "measured", "vendor", "estimated"):
        assert ManufacturerModel(confidence=confidence).confidence == confidence

    def message(call) -> str:  # type: ignore[no-untyped-def]
        with pytest.raises(ManufacturerModelError) as info:
            call()
        return str(info.value)

    assert message(lambda: _interp_log(1e6, ())) == "no model points"
    assert (
        message(lambda: ManufacturerModel.from_mapping([]))
        == "model must be an object"
    )
    assert (
        message(lambda: ModelPoint(0.0, 1.0))
        == "model point frequency must be > 0"
    )
    assert (
        message(lambda: ModelPoint(1e6, -1.0))
        == "model point value must be >= 0"
    )
    assert (
        message(
            lambda: ManufacturerModel(
                q_points=(ModelPoint(10e6, 1.0), ModelPoint(1e6, 2.0))
            )
        )
        == "q_points must be sorted by frequency"
    )
    assert (
        message(
            lambda: ManufacturerModel(
                esr_points=(ModelPoint(10e6, 1.0), ModelPoint(1e6, 2.0))
            )
        )
        == "esr_points must be sorted by frequency"
    )
    assert (
        message(
            lambda: ManufacturerModel(
                q_points=(ModelPoint(1e6, 1.0), ModelPoint(1e6, 2.0))
            )
        )
        == "q_points has duplicate frequencies"
    )
    assert (
        message(
            lambda: ManufacturerModel(
                esr_points=(ModelPoint(1e6, 1.0), ModelPoint(1e6, 2.0))
            )
        )
        == "esr_points has duplicate frequencies"
    )
    assert message(
        lambda: ManufacturerModel(confidence="unknown")
    ).startswith("unsupported model confidence:")


def test_linear_zero_endpoint_with_nonunit_span() -> None:
    points = (ModelPoint(1e6, 0.0), ModelPoint(10e6, 2.0))
    assert _interp_log(3.1622776601683795e6, points) == pytest.approx(1.0)


def test_interp_log_non_decade_span_zero_right_and_nan_fallback() -> None:
    points = (ModelPoint(1e6, 100.0), ModelPoint(100e6, 10.0))
    expected = 10.0 ** (
        math.log10(100.0)
        + 0.5 * (math.log10(10.0) - math.log10(100.0))
    )
    assert _interp_log(10e6, points) == pytest.approx(expected)

    zero_right = (ModelPoint(1e6, 1.0), ModelPoint(10e6, 0.0))
    assert _interp_log(3.1622776601683795e6, zero_right) == pytest.approx(
        0.5
    )
