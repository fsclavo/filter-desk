"""Transformer / unun / balun calculator."""

from __future__ import annotations

import json
import math

import pytest

from filterdesk.__main__ import main
from filterdesk.components_std import (
    TransformerError,
    TransformerKind,
    TransformerTopology,
    design_transformer,
    design_transformer_options,
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


def test_autotransformer_is_default_and_options() -> None:
    core = find_core("FT240-43")
    design = design_transformer(
        core,
        z_low_ohm=50.0,
        z_high_ohm=2500.0,
        frequency_hz=7e6,
        power_w=100.0,
    )
    assert design.topology is TransformerTopology.AUTOTRANSFORMER
    assert design.total_turns == 21
    options = design_transformer_options(
        core,
        z_low_ohm=50.0,
        z_high_ohm=2500.0,
        frequency_hz=7e6,
        power_w=100.0,
        frequency_max_hz=28e6,
    )
    assert [(d.n_low, d.n_high, d.total_turns) for d in options] == [
        (2, 14, 14),
        (3, 21, 21),
        (4, 28, 28),
    ]
    assert options[0].reactance_ratio < 4.0
    assert options[1].reactance_ratio >= 4.0
    assert not options[0].hf_caution
    assert not options[1].hf_caution
    assert options[2].hf_caution
    assert any("low-frequency" in note for note in options[0].notes)
    assert any("HF" in note for note in options[2].notes)

    isolated = design_transformer_options(
        core,
        z_low_ohm=50.0,
        z_high_ohm=2500.0,
        frequency_hz=7e6,
        power_w=100.0,
        topology="isolated",
        frequency_max_hz=28e6,
    )
    assert [d.total_turns for d in isolated] == [16, 24, 32]
    assert not isolated[1].hf_caution
    assert isolated[2].hf_caution


def test_hf_power_cores_support_100w_designs() -> None:
    for core_name, z_high, freq in (
        ("FT140-43", 200.0, 3.5e6),
        ("FT240-43", 450.0, 7e6),
        ("FT240-61", 200.0, 28e6),
        ("FT240-52", 200.0, 14e6),
    ):
        design = design_transformer(
            find_core(core_name),
            z_low_ohm=50.0,
            z_high_ohm=z_high,
            frequency_hz=freq,
            power_w=100.0,
        )
        assert design.n_low >= 1 and design.n_high >= 1
        assert design.fit.fits
        assert design.bsat_margin is not None
        assert design.bsat_margin > 1.0


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


def test_cli_transformer_options_and_topology(capsys) -> None:
    assert (
        main(
            [
                "transformer",
                "--z-low",
                "50",
                "--z-high",
                "2500",
                "--core",
                "FT240-43",
                "--frequency",
                "7M",
                "--power",
                "100",
                "--topology",
                "isolated",
                "--f-max",
                "28M",
                "--show-options",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["topology"] == "isolated"
    assert payload["total_turns"] == 24
    option_turns = [
        (o["n_low"], o["n_high"], o["total_turns"])
        for o in payload["options"]
    ]
    assert option_turns == [(2, 14, 16), (3, 21, 24), (4, 28, 32)]
    assert payload["options"][2]["hf_caution"] is True


def test_transformer_dialog_options_and_topology(qtbot) -> None:
    from filterdesk.gui.widgets import TransformerDialog

    dialog = TransformerDialog()
    qtbot.addWidget(dialog)
    for index, core in enumerate(dialog._cores):
        if core.name == "FT240-43":
            dialog._core.setCurrentIndex(index)
            break
    dialog._z_high.setText("2500")
    dialog._frequency.setText("7M")
    dialog._frequency_max.setText("28M")
    dialog._power.setText("100")
    dialog._recompute()
    assert dialog._topology.currentText() == "autotransformer"
    assert len(dialog._options) == 3
    assert dialog.current_design() is not None
    assert dialog.current_design().n_low == 3
    assert dialog._options_table.rowCount() == 3
    dialog._options_table.selectRow(2)
    design = dialog.current_design()
    assert design is not None
    assert design.total_turns == 28
    assert design.hf_caution
    dialog._topology.setCurrentText("isolated")
    dialog._recompute()
    assert dialog.current_design() is not None
    assert dialog.current_design().total_turns in {16, 24, 32}


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
    assert payload["topology"] == "autotransformer"
    assert any("autotransformer" in note for note in payload["notes"])


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
