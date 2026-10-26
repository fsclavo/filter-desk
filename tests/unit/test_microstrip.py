"""Microstrip line, stub and quarter-wave transformer calculator."""

from __future__ import annotations

import json
import math

import pytest

from filterdesk.__main__ import main
from filterdesk.components_std import (
    MicrostripError,
    StubKind,
    Substrate,
    design_microstrip,
    design_quarter_wave_transformer,
    design_stub,
    find_substrate,
    list_substrates,
    microstrip_width_for_z0,
)


def test_fr4_50_ohm_line() -> None:
    substrate = find_substrate("FR4")
    line = design_microstrip(50.0, substrate, 1e9, length_m=0.05)
    assert line.width_mm == pytest.approx(3.079, rel=2e-3)
    assert line.z0_ohm == pytest.approx(50.0, abs=1e-3)
    assert line.eeff == pytest.approx(3.332, rel=2e-3)
    assert line.quarter_wave_m == pytest.approx(line.wavelength_m / 4.0)
    assert line.loss_db_per_m > 0.0
    assert line.dielectric_loss_db_per_m > line.conductor_loss_db_per_m
    assert line.loss_db() == pytest.approx(line.loss_db_per_m * 0.05)
    assert line.electrical_length_deg() == pytest.approx(
        360.0 * 0.05 / line.wavelength_m
    )


def test_width_monotonic_and_round_trip() -> None:
    substrate = find_substrate("RO4350B")
    widths = [microstrip_width_for_z0(z, substrate) for z in (25.0, 50.0, 100.0)]
    assert widths[0] > widths[1] > widths[2]
    for z0 in (25.0, 50.0, 75.0, 100.0):
        width = microstrip_width_for_z0(z0, substrate)
        back = design_microstrip(
            z0, substrate, 1e9, length_m=0.0
        )
        assert back.width_mm == pytest.approx(width, rel=1e-9)
        assert back.z0_ohm == pytest.approx(z0, rel=1e-9)


def test_quarter_wave_transformer() -> None:
    substrate = find_substrate("FR4")
    qwt = design_quarter_wave_transformer(50.0, 100.0, substrate, 1e9)
    assert qwt.z0_ohm == pytest.approx(math.sqrt(5000.0))
    assert qwt.line.length_m == pytest.approx(qwt.line.wavelength_m / 4.0)
    assert qwt.line.width_mm > 0.0


def test_open_and_short_stub_reactance() -> None:
    substrate = find_substrate("FR4")
    open_stub = design_stub(50.0, 45.0, substrate, 1e9, kind=StubKind.OPEN)
    short_stub = design_stub(50.0, 45.0, substrate, 1e9, kind="short")
    assert open_stub.input_impedance_ohm().real == pytest.approx(0.0, abs=1e-9)
    assert open_stub.input_impedance_ohm().imag == pytest.approx(-50.0, rel=1e-6)
    assert short_stub.input_impedance_ohm().real == pytest.approx(0.0, abs=1e-9)
    assert short_stub.input_impedance_ohm().imag == pytest.approx(50.0, rel=1e-6)
    assert open_stub.line.length_m == pytest.approx(
        open_stub.line.wavelength_m / 8.0
    )


def test_loss_increases_with_frequency_and_tan_delta() -> None:
    substrate = find_substrate("FR4")
    low = design_microstrip(50.0, substrate, 1e8)
    high = design_microstrip(50.0, substrate, 1e9)
    lossy = Substrate("Lossy", 4.4, 1.6, 0.05)
    lossy_line = design_microstrip(50.0, lossy, 1e9)
    assert high.loss_db_per_m > low.loss_db_per_m
    assert lossy_line.loss_db_per_m > high.loss_db_per_m


def test_air_substrate_is_lossless_in_this_model() -> None:
    line = design_microstrip(50.0, find_substrate("Air"), 1e9)
    assert line.dielectric_loss_db_per_m == 0.0
    assert line.conductor_loss_db_per_m == 0.0
    assert line.eeff == pytest.approx(1.0, rel=1e-6)


def test_substrate_catalog_and_validation() -> None:
    names = [s.name for s in list_substrates()]
    assert "FR4" in names and "RO4350B" in names
    with pytest.raises(MicrostripError, match="unknown substrate"):
        find_substrate("unobtainium")
    with pytest.raises(MicrostripError, match="Z0"):
        design_microstrip(0.0, find_substrate("FR4"), 1e9)
    with pytest.raises(MicrostripError, match="frequency"):
        design_microstrip(50.0, find_substrate("FR4"), 0.0)
    with pytest.raises(MicrostripError, match="angle"):
        design_stub(50.0, 0.0, find_substrate("FR4"), 1e9)
    with pytest.raises(MicrostripError, match="impedances"):
        design_quarter_wave_transformer(0.0, 100.0, find_substrate("FR4"), 1e9)


def test_cli_microstrip_qwt_stub_json(capsys) -> None:
    assert (
        main(
            [
                "microstrip",
                "--z0",
                "50",
                "--substrate",
                "FR4",
                "--frequency",
                "1G",
                "--length",
                "50m",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["width_mm"] == pytest.approx(3.079, rel=2e-3)
    assert payload["length_deg"] == pytest.approx(109.6, abs=0.2)

    assert (
        main(
            [
                "qwt",
                "--z-low",
                "50",
                "--z-high",
                "100",
                "--frequency",
                "1G",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["z0_ohm"] == pytest.approx(math.sqrt(5000.0))

    assert (
        main(
            [
                "stub",
                "--z0",
                "50",
                "--angle",
                "45",
                "--kind",
                "open",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["zin_imag_ohm"] == pytest.approx(-50.0, rel=1e-6)


def test_cli_microstrip_text_and_error(capsys) -> None:
    assert main(["microstrip", "--z0", "50", "--frequency", "1G"]) == 0
    out = capsys.readouterr().out
    assert "W =" in out and "lambda_g" in out
    assert main(["microstrip", "--z0", "0", "--frequency", "1G"]) == 2
    assert "error:" in capsys.readouterr().err


def test_microstrip_dialog_live_values(qtbot) -> None:
    from filterdesk.gui.widgets import MicrostripDialog

    dialog = MicrostripDialog()
    qtbot.addWidget(dialog)
    line = dialog.current_line()
    assert line is not None
    assert line.width_mm == pytest.approx(3.079, rel=2e-3)
    dialog._z0.setText("100")
    dialog._recompute()
    line = dialog.current_line()
    assert line is not None
    assert line.width_mm < 3.079
    dialog._z0.setText("bad")
    dialog._recompute()
    assert dialog.current_line() is None
