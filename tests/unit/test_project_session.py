"""Native project I/O and DesignSession tests."""

from __future__ import annotations

from pathlib import Path

from filterdesk.io.native import load_project, save_project
from filterdesk.services.session import DesignSession


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
