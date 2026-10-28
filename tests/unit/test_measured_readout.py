"""Measured-vs-simulated cursor readout."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def _result(
    freq: np.ndarray,
    *,
    s11: np.ndarray,
    s21: np.ndarray,
) -> object:
    from filterdesk.analysis.types import AnalysisResult

    return AnalysisResult(
        frequency_hz=freq,
        s11=s11,
        s21=s21,
        s12=s21.copy(),
        s22=s11.copy(),
        zin_ohm=np.full(freq.size, 50.0 + 0j),
        zout_ohm=np.full(freq.size, 50.0 + 0j),
        z0_source_ohm=50.0,
        z0_load_ohm=50.0,
        backend="test",
    )


def test_measured_cursor_readout_visibility_and_deltas() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.i18n import tr
    from filterdesk.gui.panels.plot_panel import PlotPanel

    _ = QApplication.instance() or QApplication([])
    sim_f = np.array([80e6, 100e6, 120e6])
    sim_s11 = np.full(3, 0.1 + 0j, dtype=np.complex128)
    sim_s21 = np.full(3, 0.9 + 0j, dtype=np.complex128)
    sim = _result(sim_f, s11=sim_s11, s21=sim_s21)

    mea_f = np.array([90e6, 100e6, 110e6])
    mea_s11 = np.full(3, 0.2 + 0j, dtype=np.complex128)
    mea_s21 = np.full(3, 0.5 + 0j, dtype=np.complex128)
    measured = _result(mea_f, s11=mea_s11, s21=mea_s21)

    panel = PlotPanel()
    panel.set_result(sim)  # type: ignore[arg-type]
    panel.set_measured(measured)  # type: ignore[arg-type]
    bits = panel._measured_readout_bits(
        100e6, s21=-0.915, s11=-20.0, vswr_value=1.2, phase21=10.0
    )
    assert "meas:" in bits
    assert "Δ" in bits
    assert "S21=" in bits and "S11=" in bits and "VSWR=" in bits
    assert "Δ+5.11" in bits
    assert "Δ-6.02" in bits
    assert "Δ-0.300" in bits

    panel.set_measured_visible(False)
    assert (
        panel._measured_readout_bits(
            100e6, s21=-0.915, s11=-20.0, vswr_value=1.2, phase21=10.0
        )
        == ""
    )
    panel.set_measured_visible(True)
    out = panel._measured_readout_bits(
        80e6, s21=0.0, s11=0.0, vswr_value=1.0, phase21=0.0
    )
    assert out == tr("   | meas: —")
    panel.close()
