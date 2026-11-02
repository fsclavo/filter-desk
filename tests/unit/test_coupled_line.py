"""Ideal coupled-line bandpass synthesis and CLI."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std.coupled_microstrip import (
    CoupledMicrostripError,
    coupled_microstrip_impedances,
    design_coupled_microstrip,
)
from filterdesk.components_std.microstrip import Substrate
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
    design = design_coupled_line_bpf(config, _sweep(), substrate="FR4")
    assert design.network.n_ports == 2
    assert len(design.sections) == 4
    assert design.substrate is not None
    assert all(section.z0e_ohm > section.z0o_ohm for section in design.sections)
    assert all(0.0 < section.coupling < 1.0 for section in design.sections)
    assert all(
        section.width_mm is not None and section.width_mm > 0
        for section in design.sections
    )
    assert all(
        section.gap_mm is not None and section.gap_mm > 0
        for section in design.sections
    )
    index = int(np.argmin(np.abs(design.network.frequency_hz - 100e6)))
    assert 20.0 * np.log10(abs(design.network.s[index, 1, 0])) == pytest.approx(
        0.0, abs=1e-6
    )
    assert 20.0 * np.log10(abs(design.network.s[index, 0, 0])) < -60.0
    assert design.network.s[:, 1, 0] == pytest.approx(
        design.network.s[:, 0, 1]
    )
    assert "Coupled-line BPF" in design.summary()


def test_coupled_microstrip_forward_and_inverse() -> None:
    substrate = Substrate("Alumina", 10.0, 0.5, 0.0001, 0.01, 0.2)
    z0e, z0o, eeff_e, eeff_o = coupled_microstrip_impedances(
        0.5, 0.25, substrate
    )
    assert z0e == pytest.approx(59.0, abs=0.2)
    assert z0o == pytest.approx(37.0, abs=0.2)
    assert eeff_e == pytest.approx(7.27, abs=0.02)
    assert eeff_o == pytest.approx(5.82, abs=0.02)
    geometry = design_coupled_microstrip(59.0, 37.0, substrate)
    assert geometry.width_mm == pytest.approx(0.5, abs=0.01)
    assert geometry.gap_mm == pytest.approx(0.25, abs=0.01)
    assert geometry.residual < 1e-6
    with pytest.raises(CoupledMicrostripError):
        design_coupled_microstrip(37.0, 59.0, substrate)


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
    assert all(section.width_mm is None for section in design.sections)


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
    assert payload["sections"][0]["width_mm"] > 0
    assert payload["sections"][0]["gap_mm"] > 0
    assert read_sparameters(output).n_ports == 2

    layout_path = tmp_path / "coupled_layout.svg"
    assert (
        main(
            [
                "coupled-line",
                "--center",
                "100M",
                "--bandwidth",
                "10M",
                "--layout",
                "hairpin",
                "--layout-output",
                str(layout_path),
                "--output",
                str(tmp_path / "coupled_layout.s2p"),
            ]
        )
        == 0
    )
    assert layout_path.is_file()
    assert "<svg" in layout_path.read_text(encoding="utf-8")

    dxf_path = tmp_path / "coupled_layout.dxf"
    assert (
        main(
            [
                "coupled-line",
                "--center",
                "100M",
                "--bandwidth",
                "10M",
                "--layout",
                "interdigital",
                "--layout-output",
                str(dxf_path),
                "--output",
                str(tmp_path / "coupled_layout_dxf.s2p"),
            ]
        )
        == 0
    )
    assert "TOP_COPPER" in dxf_path.read_text(encoding="utf-8")

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
    assert dialog._table.columnCount() == 7
    assert dialog._export_button.isEnabled()
    assert dialog._layout_mode.count() == 3
    dialog._layout_mode.setCurrentIndex(1)
    assert "Conceptual" in dialog._layout_status.text()
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
    layout_output = tmp_path / "coupled_gui.svg"
    monkeypatch.setattr(
        module.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(layout_output), ""),
    )
    dialog._export_layout()
    assert layout_output.is_file()
    assert "<svg" in layout_output.read_text(encoding="utf-8")
    dxf_output = tmp_path / "coupled_gui.dxf"
    monkeypatch.setattr(
        module.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(dxf_output), ""),
    )
    dialog._export_layout()
    assert "TOP_COPPER" in dxf_output.read_text(encoding="utf-8")
    dialog.close()
    assert app is not None
