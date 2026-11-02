"""Ideal circulator/isolator models and CLI export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.io.touchstone import read_sparameters
from filterdesk.services.circulator import (
    CirculatorConfig,
    CirculatorError,
    design_circulator,
    design_isolator,
)


def _sweep() -> SweepConfig:
    return SweepConfig(
        f_start_hz=100e6,
        f_stop_hz=200e6,
        n_points=11,
        spacing=SweepSpacing.LINEAR,
    )


def test_ideal_circulator_paths() -> None:
    config = CirculatorConfig(
        insertion_loss_db=0.0,
        isolation_db=120.0,
        return_loss_db=120.0,
    )
    design = design_circulator(config, _sweep())
    assert design.network.n_ports == 3
    assert design.network.s[:, 1, 0] == pytest.approx(1.0)
    assert design.network.s[:, 2, 1] == pytest.approx(1.0)
    assert design.network.s[:, 0, 2] == pytest.approx(1.0)
    assert abs(design.network.s[0, 0, 1]) < 1e-5
    assert abs(design.network.s[0, 0, 0]) < 1e-5
    assert "Circulator" in design.summary()


def test_isolator_terminates_port_three() -> None:
    config = CirculatorConfig(
        insertion_loss_db=0.0,
        isolation_db=120.0,
        return_loss_db=120.0,
    )
    design = design_isolator(config, _sweep())
    assert design.network.n_ports == 2
    assert design.network.s[:, 1, 0] == pytest.approx(1.0)
    assert abs(design.network.s[0, 0, 1]) < 1e-5
    assert "Isolator" in design.summary()


def test_circulator_config_validation() -> None:
    with pytest.raises(CirculatorError):
        CirculatorConfig(insertion_loss_db=-1.0)
    with pytest.raises(CirculatorError):
        CirculatorConfig(isolation_db=-1.0)
    with pytest.raises(CirculatorError):
        CirculatorConfig(z0_ohm=0.0)


def test_cli_circulator_and_isolator(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    circ = tmp_path / "circ.s3p"
    assert (
        main(
            [
                "circulator",
                "--f-start",
                "100M",
                "--f-stop",
                "200M",
                "--points",
                "11",
                "--output",
                str(circ),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "circulator"
    assert payload["n_ports"] == 3
    assert read_sparameters(circ).n_ports == 3

    iso = tmp_path / "iso.s2p"
    assert (
        main(
            [
                "isolator",
                "--f-start",
                "100M",
                "--f-stop",
                "200M",
                "--points",
                "11",
                "--output",
                str(iso),
            ]
        )
        == 0
    )
    assert read_sparameters(iso).n_ports == 2
    assert "Isolator" in capsys.readouterr().out


def test_circulator_dialog_design_and_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import circulator_dialog as module

    app = QApplication.instance() or QApplication([])
    dialog = module.CirculatorDialog()
    assert dialog.design is not None
    assert dialog._export_button.isEnabled()
    dialog._mode.setCurrentIndex(1)
    assert dialog.design is None
    dialog._run_design()
    assert dialog.design is not None
    assert dialog.design.network.n_ports == 2
    output = tmp_path / "iso.s2p"
    monkeypatch.setattr(
        module.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(output), ""),
    )
    dialog._export()
    assert output.is_file()
    dialog.close()
    assert app is not None
