"""Measured overlays must not advertise a legend entry before data exists."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def _legend_labels(plot: object) -> list[str]:
    legend = plot.plotItem.legend  # type: ignore[attr-defined]
    assert legend is not None
    return [label.text for _, label in legend.items]


def test_plot_panel_hides_measurement_legends_before_load() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.panels.plot_panel import PlotPanel

    _ = QApplication.instance() or QApplication([])
    panel = PlotPanel()

    assert _legend_labels(panel._mag) == ["S21", "S11"]
    assert _legend_labels(panel._rev_plot) == ["S22", "S12"]
    assert _legend_labels(panel._phase_plot) == ["∠S21", "∠S11"]
    assert _legend_labels(panel._z_plot) == ["|Zin|", "Re(Zin)", "Im(Zin)", "|Zout|"]
    assert _legend_labels(panel._smith._plot) == ["S11", "S22"]
    panel.close()
