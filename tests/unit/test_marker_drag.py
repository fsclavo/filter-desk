"""Marker drag-edit on response plots."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def test_marker_drag_snaps_emits_and_syncs_plots() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.overlays import Marker
    from filterdesk.gui.panels.plot_panel import PlotPanel
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.analysis is not None

    panel = PlotPanel()
    panel.set_result(session.analysis)
    start_f = float(session.analysis.frequency_hz[10])
    target_f = float(session.analysis.frequency_hz[40])
    panel.set_markers([Marker(id="M1", frequency_hz=start_f, label="fc")])

    received: list[list[Marker]] = []
    panel.markers_changed.connect(lambda m: received.append(list(m)))

    line = panel._marker_items[0][0]
    panel._drag_marker_index = 0
    panel._drag_start_freq = start_f
    panel._apply_marker_frequency(0, target_f)
    panel._on_marker_line_finished(line)

    assert len(received) == 1
    assert received[0][0].frequency_hz == target_f
    # Sibling plots stay aligned in log-x space
    expected_x = float(np.log10(target_f))
    for ln in panel._marker_items[0]:
        assert abs(float(ln.value()) - expected_x) < 1e-9
    assert app is not None


def test_marker_drag_no_emit_when_unchanged() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.overlays import Marker
    from filterdesk.gui.panels.plot_panel import PlotPanel
    from filterdesk.services.session import DesignSession

    _ = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.analysis is not None
    f0 = float(session.analysis.frequency_hz[20])

    panel = PlotPanel()
    panel.set_result(session.analysis)
    panel.set_markers([Marker(id="M1", frequency_hz=f0)])
    received: list[object] = []
    panel.markers_changed.connect(lambda m: received.append(m))

    line = panel._marker_items[0][0]
    panel._drag_marker_index = 0
    panel._drag_start_freq = f0
    panel._on_marker_line_finished(line)
    assert received == []


def test_smith_limit_circles() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.overlays import LimitMetric, LimitRegion
    from filterdesk.gui.panels.smith_chart import SmithChartWidget

    _ = QApplication.instance() or QApplication([])
    widget = SmithChartWidget()
    assert widget._limit_items == []
    widget.set_limits(
        [
            # S11 max → one boundary circle
            LimitRegion(
                id="L1",
                metric=LimitMetric.S11_MAG,
                f_low_hz=1e6,
                f_high_hz=1e9,
                y_max=0.1,
            ),
            # Cartesian metric → ignored on Smith
            LimitRegion(
                id="L2",
                metric=LimitMetric.S21_DB,
                f_low_hz=1e6,
                f_high_hz=1e9,
                y_max=-40.0,
            ),
            # annulus → two boundary circles
            LimitRegion(
                id="L3",
                metric=LimitMetric.S11_MAG,
                f_low_hz=1e6,
                f_high_hz=1e9,
                y_min=0.05,
                y_max=0.2,
            ),
        ]
    )
    assert len(widget._limit_items) == 3
    # Disabling clears the overlays
    widget.set_limits([])
    assert widget._limit_items == []


def test_smith_marker_drag_snaps_emits_and_syncs_cartesian() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.overlays import Marker
    from filterdesk.gui.panels.plot_panel import PlotPanel
    from filterdesk.services.session import DesignSession

    _ = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.analysis is not None

    panel = PlotPanel()
    panel.set_result(session.analysis)
    start_f = float(session.analysis.frequency_hz[10])
    target_f = float(session.analysis.frequency_hz[40])
    panel.set_markers([Marker(id="M1", frequency_hz=start_f, label="fc")])

    received: list[list[Marker]] = []
    panel.markers_changed.connect(lambda m: received.append(list(m)))

    smith = panel._smith
    item = smith._marker_items[0]
    # Drag toward the S11 sample at target_f
    g = session.analysis.s11[40]
    smith._drag_marker_index = 0
    smith._drag_start_freq = start_f
    item.setPos(float(g.real), float(g.imag))
    smith._on_marker_finished(item)

    assert len(received) == 1
    assert received[0][0].frequency_hz == target_f
    expected_x = float(np.log10(target_f))
    for ln in panel._marker_items[0]:
        assert abs(float(ln.value()) - expected_x) < 1e-9
