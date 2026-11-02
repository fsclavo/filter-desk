"""Ideal coupled-line bandpass synthesis and CLI."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.io.touchstone import read_sparameters
from filterdesk.services.coupled_line import (
    CoupledLineBpfConfig,
    CoupledLineError,
    design_coupled_line_bpf,
)


def _sweep() -> SweepConfig:
    return SweepConfig(
        f_start_hz=80e6,
        f_stop_hz=120e6,
        n_points=801,
        spacing=SweepSpacing.LINEAR,
    )


def test_coupled_line_bpf_response_and_sections() -> None:
    config = CoupledLineBpfConfig(
        center_hz=100e6,
        bandwidth_hz=10e6,
        order=3,
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        ripple_db=0.1,
    )
    design = design_coupled_line_bpf(config, _sweep())
    assert design.network.n_ports == 2
    assert len(design.sections) == 4
    assert all(section.z0e_ohm > section.z0o_ohm for section in design.sections)
    assert all(0.0 < section.coupling < 1.0 for section in design.sections)
    index = int(np.argmin(np.abs(design.network.frequency_hz - 100e6)))
    assert 20.0 * np.log10(abs(design.network.s[index, 1, 0])) == pytest.approx(
        0.0, abs=1e-6
    )
    assert 20.0 * np.log10(abs(design.network.s[index, 0, 0])) < -60.0
    assert design.network.s[:, 1, 0] == pytest.approx(
        design.network.s[:, 0, 1]
    )
    assert "Coupled-line BPF" in design.summary()


def test_butterworth_even_order_is_allowed() -> None:
    config = CoupledLineBpfConfig(
        center_hz=100e6,
        bandwidth_hz=10e6,
        order=4,
        family=ApproximationFamily.BUTTERWORTH,
        ripple_db=None,
    )
    design = design_coupled_line_bpf(config, _sweep())
    assert len(design.sections) == 5


def test_coupled_line_validation() -> None:
    with pytest.raises(CoupledLineError):
        CoupledLineBpfConfig(center_hz=0.0, bandwidth_hz=1e6)
    with pytest.raises(CoupledLineError):
        CoupledLineBpfConfig(center_hz=100e6, bandwidth_hz=0.0)
    with pytest.raises(CoupledLineError):
        CoupledLineBpfConfig(center_hz=100e6, bandwidth_hz=200e6)
    with pytest.raises(CoupledLineError):
        CoupledLineBpfConfig(
            center_hz=100e6,
            bandwidth_hz=10e6,
            order=4,
            family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        )
    with pytest.raises(CoupledLineError):
        CoupledLineBpfConfig(
            center_hz=100e6,
            bandwidth_hz=10e6,
            family=ApproximationFamily.ELLIPTIC,
        )


def test_cli_coupled_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "coupled.s2p"
    assert (
        main(
            [
                "coupled-line",
                "--center",
                "100M",
                "--bandwidth",
                "10M",
                "--order",
                "3",
                "--points",
                "401",
                "--output",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "coupled-line"
    assert payload["n_ports"] == 2
    assert len(payload["sections"]) == 4
    assert read_sparameters(output).n_ports == 2

    text_output = tmp_path / "coupled_text.s2p"
    assert (
        main(
            [
                "coupled-line",
                "--center",
                "100M",
                "--bandwidth",
                "10M",
                "--output",
                str(text_output),
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "Coupled-line BPF" in captured.out
    assert "section 1" in captured.out
    assert "warning:" in captured.err


def test_coupled_line_dialog_design_and_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import coupled_line_dialog as module

    app = QApplication.instance() or QApplication([])
    dialog = module.CoupledLineDialog()
    assert dialog.design is not None
    assert dialog._table.rowCount() == 4
    assert dialog._export_button.isEnabled()
    dialog._family.setCurrentIndex(1)
    dialog._order.setValue(4)
    dialog._run_design()
    assert dialog.design is not None
    assert dialog._table.rowCount() == 5
    output = tmp_path / "coupled_gui.s2p"
    monkeypatch.setattr(
        module.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(output), ""),
    )
    dialog._export()
    assert output.is_file()
    dialog.close()
    assert app is not None
