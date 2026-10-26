"""Transformer / unun / balun calculator."""

from __future__ import annotations

import json
import math

import pytest

from filterdesk.__main__ import main
from filterdesk.components_std import (
    TransformerError,
    TransformerKind,
    design_transformer,
    find_core,
)


def test_unun_1_to_4_turns_flux_and_wire() -> None:
    core = find_core("FT50-43")
    d = design_transformer(
        core,
        z_low_ohm=50.0,
        z_high_ohm=200.0,
        frequency_hz=3.5e6,
        power_w=10.0,
    )
    assert d.kind is TransformerKind.UNUN
    assert d.impedance_ratio == pytest.approx(4.0)
    assert d.turns_ratio == pytest.approx(2.0)
    assert d.n_low == 5
    assert d.n_high == 10
    assert d.actual_impedance_ratio == pytest.approx(4.0)
    assert d.magnetizing_inductance_h == pytest.approx(440e-9 * 25)
    assert d.i_low_rms_a == pytest.approx(math.sqrt(10.0 / 50.0))
    assert d.i_high_rms_a == pytest.approx(math.sqrt(10.0 / 200.0))
    assert d.b_peak_t is not None and d.b_peak_t < core.bsat_t
    assert d.bsat_margin is not None and d.bsat_margin > 1.0
    assert d.awg_low is not None and d.awg_high is not None
    assert not d.saturated


def test_unun_1_to_9_and_balun_note() -> None:
    core = find_core("FT82-43")
    d = design_transformer(
        core,
        z_low_ohm=50.0,
        z_high_ohm=450.0,
        frequency_hz=7e6,
        power_w=5.0,
        kind=TransformerKind.BALUN,
    )
    assert d.impedance_ratio == pytest.approx(9.0)
    assert d.n_high == pytest.approx(3 * d.n_low, abs=1)
    assert any("common-mode" in note for note in d.notes)


def test_iron_powder_core_without_bsat_reports_note() -> None:
    d = design_transformer(
        find_core("T50-2"),
        z_low_ohm=50.0,
        z_high_ohm=50.0,
        frequency_hz=1e6,
        power_w=1.0,
    )
    assert d.bsat_margin is None
    assert d.b_peak_t is not None
    assert any("Bsat" in note for note in d.notes)


def test_rounding_actual_ratio_is_reported() -> None:
    d = design_transformer(
        find_core("FT50-43"),
        z_low_ohm=50.0,
        z_high_ohm=100.0,
        frequency_hz=1e6,
        power_w=1.0,
    )
    assert d.n_high / d.n_low != pytest.approx(math.sqrt(2.0))
    assert any("rounded turns" in note for note in d.notes)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"z_low_ohm": 0.0}, "impedances"),
        ({"z_high_ohm": 10.0}, "z_high"),
        ({"frequency_hz": 0.0}, "frequency"),
        ({"power_w": 0.0}, "power"),
        ({"reactance_factor": 0.0}, "reactance"),
    ],
)
def test_invalid_requests(kwargs, message: str) -> None:
    base = {
        "z_low_ohm": 50.0,
        "z_high_ohm": 200.0,
        "frequency_hz": 3.5e6,
        "power_w": 10.0,
    }
    base.update(kwargs)
    with pytest.raises(TransformerError, match=message):
        design_transformer(find_core("FT50-43"), **base)


def test_cli_transformer_json(capsys) -> None:
    assert (
        main(
            [
                "transformer",
                "--kind",
                "unun",
                "--z-low",
                "50",
                "--z-high",
                "200",
                "--core",
                "FT50-43",
                "--frequency",
                "3.5M",
                "--power",
                "10",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["impedance_ratio"] == pytest.approx(4.0)
    assert payload["n_low"] == 5 and payload["n_high"] == 10
    assert payload["kind"] == "unun"
    assert payload["core"] == "FT50-43"
    assert payload["notes"] == []


def test_cli_transformer_text_and_error(capsys) -> None:
    assert (
        main(
            [
                "transformer",
                "--z-low",
                "50",
                "--z-high",
                "50",
                "--core",
                "FT50-43",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Turns:" in out and "Wire:" in out
    assert (
        main(
            ["transformer", "--z-low", "0", "--z-high", "50", "--core", "FT50-43"]
        )
        == 2
    )
    assert "error:" in capsys.readouterr().err


def test_transformer_dialog_live_values(qtbot) -> None:
    from filterdesk.gui.widgets import TransformerDialog

    dialog = TransformerDialog()
    qtbot.addWidget(dialog)
    design = dialog.current_design()
    assert design is not None
    assert design.impedance_ratio == pytest.approx(4.0)
    dialog._z_high.setText("450")
    dialog._recompute()
    design = dialog.current_design()
    assert design is not None
    assert design.impedance_ratio == pytest.approx(9.0)
    dialog._z_high.setText("bad")
    dialog._recompute()
    assert dialog.current_design() is None
