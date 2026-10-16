"""Marker-driven retune (bind a marker to a spec landmark and drag)."""

from __future__ import annotations

import pytest

from filterdesk.domain.overlays import (
    Marker,
    markers_from_mapping,
    markers_to_mapping,
)

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

from filterdesk.gui.main_window import MainWindow  # noqa: E402
from filterdesk.gui.panels.markers_panel import MarkersPanel  # noqa: E402
from filterdesk.services.session import DesignSession  # noqa: E402


def test_marker_landmark_validation() -> None:
    assert Marker(id="M1", frequency_hz=1e6, landmark="cutoff").landmark == "cutoff"
    with pytest.raises(ValueError):
        Marker(id="M1", frequency_hz=1e6, landmark="nope")  # type: ignore[arg-type]


def test_marker_landmark_serialization_roundtrip() -> None:
    markers = [
        Marker(id="M1", frequency_hz=100e6, label="cut", landmark="cutoff"),
        Marker(id="M2", frequency_hz=50e6, label="plain"),
    ]
    restored = markers_from_mapping(markers_to_mapping(markers))
    assert restored[0].landmark == "cutoff"
    assert restored[1].landmark is None
    assert [m.frequency_hz for m in restored] == [100e6, 50e6]


def test_plot_marker_drag_preserves_landmark() -> None:
    from filterdesk.gui.panels.plot_panel import PlotPanel

    app = QApplication.instance() or QApplication([])
    panel = PlotPanel()
    panel.set_markers([Marker(id="M1", frequency_hz=100e6, landmark="cutoff")])
    panel._apply_marker_frequency(0, 150e6)
    assert panel._markers[0].landmark == "cutoff"
    assert panel._markers[0].frequency_hz == pytest.approx(150e6)
    assert app is not None


def test_markers_panel_sets_landmark() -> None:
    app = QApplication.instance() or QApplication([])
    panel = MarkersPanel()
    recorded: list[object] = []
    panel.markers_changed.connect(recorded.append)
    panel.set_markers([Marker(id="M1", frequency_hz=100e6)])
    combo = panel._table.cellWidget(0, 3)
    assert isinstance(combo, QComboBox)
    combo.setCurrentIndex(combo.findData("cutoff"))
    assert panel.markers()[0].landmark == "cutoff"
    assert recorded
    assert app is not None


def test_main_window_marker_drag_retunes_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    before = session.spec.cutoff_hz
    session.markers = [
        Marker(id="M1", frequency_hz=before, label="cut", landmark="cutoff")
    ]
    window = MainWindow(session, auto_run=False)
    monkeypatch.setattr(window, "_after_circuit_change", lambda: None)
    monkeypatch.setattr(window, "_after_overlays_change", lambda: None)

    moved = [Marker(id="M1", frequency_hz=200e6, label="cut", landmark="cutoff")]
    window._on_markers_dragged(moved)

    assert session.spec.cutoff_hz == pytest.approx(200e6)
    assert session.markers[0].frequency_hz == pytest.approx(200e6)

    window._undo.undo()
    assert session.spec.cutoff_hz == pytest.approx(before)
    assert session.markers[0].frequency_hz == pytest.approx(before)
    window.close()
    assert app is not None


def test_main_window_plain_drag_keeps_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    before = session.spec.cutoff_hz
    session.markers = [Marker(id="M1", frequency_hz=before)]
    window = MainWindow(session, auto_run=False)
    monkeypatch.setattr(window, "_after_overlays_change", lambda: None)

    moved = [Marker(id="M1", frequency_hz=180e6)]
    window._on_markers_dragged(moved)

    assert session.spec.cutoff_hz == pytest.approx(before)
    assert session.markers[0].frequency_hz == pytest.approx(180e6)
    window.close()
    assert app is not None
