"""Ideal circulator/isolator models and CLI export."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
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


def test_circulator_config_messages_and_boundaries() -> None:
    valid = CirculatorConfig(
        insertion_loss_db=0.5,
        isolation_db=0.5,
        return_loss_db=0.5,
        z0_ohm=0.5,
    )
    assert valid.z0_ohm == pytest.approx(0.5)

    def message(call) -> str:  # type: ignore[no-untyped-def]
        with pytest.raises(CirculatorError) as info:
            call()
        return str(info.value)

    assert message(lambda: CirculatorConfig(insertion_loss_db=-1.0)) == (
        "insertion_loss_db must be finite and >= 0"
    )
    assert message(lambda: CirculatorConfig(isolation_db=-1.0)) == (
        "isolation_db must be finite and >= 0"
    )
    assert message(lambda: CirculatorConfig(return_loss_db=-1.0)) == (
        "return_loss_db must be finite and >= 0"
    )
    assert message(lambda: CirculatorConfig(z0_ohm=0.0)) == (
        "z0_ohm must be > 0"
    )


def test_circulator_and_isolator_summary_exact() -> None:
    config = CirculatorConfig(
        insertion_loss_db=0.5,
        isolation_db=30.0,
        return_loss_db=20.0,
        z0_ohm=50.0,
    )
    assert design_circulator(config, _sweep()).summary() == (
        "Circulator: IL 0.50 dB, isolation 30.00 dB, RL 20.00 dB, "
        "Z0 50 ohm"
    )
    assert design_isolator(config, _sweep()).summary() == (
        "Isolator: IL 0.50 dB, isolation 30.00 dB, RL 20.00 dB, "
        "Z0 50 ohm"
    )


def test_finite_circulator_matrix_all_paths_and_dtype() -> None:
    config = CirculatorConfig(
        insertion_loss_db=1.0,
        isolation_db=20.0,
        return_loss_db=10.0,
    )
    design = design_circulator(config, _sweep())
    s = design.network.s
    through = 10.0 ** (-1.0 / 20.0)
    isolated = 10.0 ** (-20.0 / 20.0)
    reflection = 10.0 ** (-10.0 / 20.0)
    assert s.dtype == np.complex128
    assert s[:, 1, 0] == pytest.approx(through)
    assert s[:, 2, 1] == pytest.approx(through)
    assert s[:, 0, 2] == pytest.approx(through)
    assert s[:, 0, 1] == pytest.approx(isolated)
    assert s[:, 1, 2] == pytest.approx(isolated)
    assert s[:, 2, 0] == pytest.approx(isolated)
    assert s[:, 0, 0] == pytest.approx(reflection)
    assert s[:, 1, 1] == pytest.approx(reflection)
    assert s[:, 2, 2] == pytest.approx(reflection)


def test_circulator_metadata_and_isolator_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from filterdesk.analysis.multiport import MultiportError, SParameters

    config = CirculatorConfig(z0_ohm=75.0)
    sweep = _sweep()
    design = design_circulator(config, sweep)
    assert design.sweep is sweep
    assert design.network.z0_ohm == pytest.approx(75.0)
    assert design.network.source == "circulator-model"

    isolator = design_isolator(config, sweep)
    assert isolator.sweep is sweep

    def fail_terminate(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise MultiportError("boom")

    monkeypatch.setattr(SParameters, "terminate", fail_terminate)
    with pytest.raises(CirculatorError) as info:
        design_isolator(config, sweep)
    assert str(info.value) == "boom"
