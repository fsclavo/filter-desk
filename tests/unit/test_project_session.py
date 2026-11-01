"""Native project I/O and DesignSession tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from filterdesk.domain.circuit import Circuit, IdealSeriesLC, Port
from filterdesk.domain.enums import ElementRole
from filterdesk.domain.project import (
    ProjectMetadata,
    circuit_from_mapping,
    circuit_to_mapping,
)
from filterdesk.io.native import load_project, save_project
from filterdesk.montecarlo import ToleranceDistribution
from filterdesk.services.session import DesignSession


def test_default_title_is_neutral() -> None:
    assert DesignSession().title == "Untitled"


def test_legacy_milestone_title_is_normalised() -> None:
    session = DesignSession()
    session.synthesize()
    project = session.to_project()
    project.metadata = ProjectMetadata(title="Milestone Chebyshev HP")
    restored = DesignSession()
    restored.load_project(project)
    assert restored.title == "Untitled"


def test_session_synthesize_analyze() -> None:
    session = DesignSession()
    result = session.synthesize_and_analyze()
    assert session.circuit is not None
    assert len(session.circuit.elements) == 7
    assert result.frequency_hz.shape[0] == session.sweep.n_points  # type: ignore[union-attr]


def test_project_roundtrip(tmp_path: Path) -> None:
    session = DesignSession()
    session.synthesize()
    session.title = "Roundtrip"
    path = tmp_path / "demo.filterdesk.json"
    save_project(session.to_project(), path)
    loaded = load_project(path)
    assert loaded.specification is not None
    assert loaded.circuit is not None
    assert loaded.metadata.title == "Roundtrip"
    assert len(loaded.circuit.elements) == 7

    session2 = DesignSession()
    session2.load_project(loaded, path=str(path))
    assert session2.circuit is not None
    assert session2.circuit.elements[0].id == session.circuit.elements[0].id


def test_project_roundtrip_preserves_analysis_attributes(tmp_path: Path) -> None:
    session = DesignSession()
    session.synthesize()
    l_id = next(el.id for el in session.circuit.elements if el.id.startswith("L"))
    session.set_element_step(l_id, 0.05)
    session.set_element_tolerance(l_id, 4.0, ToleranceDistribution.NORMAL)
    session.power_w = 100.0
    session.harmonics_f0_hz = 7.1e6

    path = tmp_path / "attrs.filterdesk.json"
    save_project(session.to_project(), path)

    restored = DesignSession()
    restored.load_project(load_project(path), path=str(path))
    assert restored.step_fraction(l_id) == pytest.approx(0.05)
    tol = restored.element_tolerance(l_id)
    assert tol is not None
    assert tol.tolerance_pct == pytest.approx(4.0)
    assert tol.distribution == ToleranceDistribution.NORMAL
    assert restored.power_w == pytest.approx(100.0)
    assert restored.harmonics_f0_hz == pytest.approx(7.1e6)


def test_load_project_without_extensions_uses_defaults(tmp_path: Path) -> None:
    session = DesignSession()
    session.synthesize()
    project = session.to_project()
    project.extensions = {}
    restored = DesignSession()
    restored.power_w = 50.0  # stale value must be reset by load
    restored.load_project(project)
    assert restored.element_steps == {}
    assert restored.element_tolerances == {}
    assert restored.power_w == 0.0
    assert restored.harmonics_f0_hz is None


def test_update_element_value() -> None:
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    el = session.circuit.elements[0]
    from filterdesk.domain.circuit import IdealCapacitor

    assert isinstance(el, IdealCapacitor)
    session.update_element_value(el.id, el.value_f * 1.1)
    assert isinstance(session.circuit.elements[0], IdealCapacitor)
    assert abs(session.circuit.elements[0].value_f - el.value_f * 1.1) < 1e-30


def test_composite_parasitics_survive_project_roundtrip() -> None:
    circuit = Circuit(
        [
            IdealSeriesLC(
                "X1",
                10e-9,
                1e-12,
                "in",
                "out",
                ElementRole.SERIES,
                l_series_resistance_ohm=0.25,
                l_srf_hz=2e9,
                c_esr_ohm=0.1,
                c_esl_h=1e-9,
            )
        ],
        Port("P1", "in", 50.0),
        Port("P2", "out", 50.0),
    )
    restored = circuit_from_mapping(circuit_to_mapping(circuit))
    element = restored.elements[0]
    assert isinstance(element, IdealSeriesLC)
    assert element.l_series_resistance_ohm == pytest.approx(0.25)
    assert element.l_srf_hz == pytest.approx(2e9)
    assert element.c_esr_ohm == pytest.approx(0.1)
    assert element.c_esl_h == pytest.approx(1e-9)
