"""Smith-chart legend visibility for measured overlays."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def _legend_labels(widget: object) -> list[str]:
    legend = widget._plot.plotItem.legend
    assert legend is not None
    return [label.text for _, label in legend.items]


def test_smith_measured_legend_hidden_without_data() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.panels.smith_chart import SmithChartWidget

    _ = QApplication.instance() or QApplication([])
    widget = SmithChartWidget()

    assert _legend_labels(widget) == ["S11", "S22"]
    widget.set_measured_s_params(np.array([]), np.array([]), None)
    assert _legend_labels(widget) == ["S11", "S22"]


def test_smith_measured_legend_tracks_overlay_data() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.panels.smith_chart import SmithChartWidget

    _ = QApplication.instance() or QApplication([])
    widget = SmithChartWidget()
    f = np.array([1e6, 2e6, 3e6])
    s11 = np.array([0.1 + 0.0j, 0.2 + 0.1j, 0.3 + 0.2j])

    widget.set_measured_s_params(f, s11, None)
    assert _legend_labels(widget) == ["S11", "S22", "S11 meas"]

    widget.set_measured_s_params(f, s11, s11 * 0.5)
    assert _legend_labels(widget) == ["S11", "S22", "S11 meas", "S22 meas"]

    widget.set_measured_s_params(np.array([]), np.array([]), None)
    assert _legend_labels(widget) == ["S11", "S22"]
