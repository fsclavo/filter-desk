"""Toroid calculator tests (Phase 12)."""

from __future__ import annotations

import json

import pytest

from filterdesk.__main__ import main
from filterdesk.components_std.toroid import (
    CORES,
    ToroidError,
    awg_diameter_mm,
    design_toroid,
    find_core,
    flux_density_t,
    inductance_for_turns,
    make_custom_core,
    turns_for_inductance,
    wire_fit,
)


def test_core_table_and_lookup() -> None:
    assert len(CORES) >= 10
    core = find_core("t50-2")
    assert core.name == "T50-2"
    assert find_core("FT-50-43").name == "FT50-43"
    with pytest.raises(ToroidError, match="unknown core"):
        find_core("nope")


def test_known_amidon_al_values() -> None:
    expected = {
        "T37-2": 4.0,
        "T50-2": 4.9,
        "T68-2": 5.7,
        "T80-2": 5.5,
        "T106-2": 13.5,
        "T37-6": 3.0,
        "T50-6": 4.0,
        "T68-6": 4.7,
        "T80-6": 4.5,
        "T37-10": 2.5,
        "T50-10": 3.1,
        "T68-10": 3.2,
        "T80-10": 3.2,
        "FT37-43": 350.0,
        "FT50-43": 440.0,
        "FT82-43": 470.0,
        "FT114-31": 956.0,
        "FT140-31": 1659.0,
        "FT114-43": 510.0,
        "FT140-43": 885.0,
        "FT240-43": 1075.0,
        "FT290-43": 1300.0,
        "FT114-61": 80.0,
        "FT350-61": 178.0,
        "FT114-52": 160.0,
        "FT140-61": 140.0,
        "FT240-61": 170.0,
        "FT140-52": 283.0,
        "FT240-52": 325.0,
        "FT240-31": 2053.0,
    }
    for name, al_nh in expected.items():
        assert find_core(name).al_nh == pytest.approx(al_nh)


def test_large_hf_power_cores() -> None:
    assert find_core("ft-240-43").name == "FT240-43"
    ft140 = find_core("FT140-43")
    ft240 = find_core("FT240-43")
    assert ft140.ae_mm2 > find_core("FT82-43").ae_mm2
    assert ft240.ae_mm2 > ft140.ae_mm2
    assert ft240.id_mm > ft140.id_mm
    assert find_core("FT240-31").material == "31"
    assert find_core("FT240-52").bsat_t == pytest.approx(0.42)
    assert find_core("FT240-61").bsat_t == pytest.approx(0.25)


def test_turns_and_inductance_roundtrip() -> None:
    al = 4.9
    turns = turns_for_inductance(1e-6, al)
    assert turns == pytest.approx(14.2857, rel=1e-4)
    assert inductance_for_turns(turns, al) == pytest.approx(1e-6, rel=1e-12)
    with pytest.raises(ToroidError):
        turns_for_inductance(0.0, al)
    with pytest.raises(ToroidError):
        inductance_for_turns(0.0, al)


def test_design_from_target_rounds_up() -> None:
    core = find_core("T50-2")
    design = design_toroid(core, inductance_h=1e-6)
    assert design.turns == 15
    assert design.target_inductance_h == pytest.approx(1e-6)
    assert design.inductance_h >= 1e-6
    assert design.inductance_h == pytest.approx(4.9 * 15**2 * 1e-9)
    assert design.wire.fits
    assert design.wire.awg == 16
    assert design.wire.diameter_mm == pytest.approx(awg_diameter_mm(16))
    assert 0.0 < design.wire.fill_ratio < 1.0
    assert design.wire_length_m > 0.0
    assert design.saturation_ratio is None  # iron powder


@pytest.mark.parametrize("target", [0.5e-6, 1e-6, 2.2e-6, 10e-6])
def test_turns_are_minimal(target: float) -> None:
    core = find_core("T50-2")
    design = design_toroid(core, inductance_h=target)
    assert design.inductance_h >= target
    if design.turns > 1:
        previous = inductance_for_turns(design.turns - 1, core.al_nh)
        assert previous < target


def test_design_from_turns_and_saturation() -> None:
    core = find_core("FT50-43")
    design = design_toroid(core, turns=5, current_a=0.5)
    assert design.turns == 5
    assert design.inductance_h == pytest.approx(440.0 * 25 * 1e-9)
    b = flux_density_t(
        design.inductance_h, 0.5, 5, core.ae_mm2 * 1e-6
    )
    assert design.flux_density_t == pytest.approx(b)
    assert design.saturation_ratio == pytest.approx(b / 0.295)
    assert not design.saturated
    assert design.saturation_margin == pytest.approx(0.295 / b)


def test_saturated_flag() -> None:
    core = find_core("FT50-43")
    design = design_toroid(core, turns=5, current_a=5.0)
    assert design.saturated
    assert design.saturation_ratio is not None and design.saturation_ratio > 1.0


def test_wire_fit_thickest_gauge() -> None:
    core = find_core("T50-2")
    fit = wire_fit(core, 15)
    assert fit.fits and fit.awg == 16
    # A very thin inner diameter cannot fit many turns of even AWG 40.
    tiny = make_custom_core("tiny", 10.0, od_mm=3.0, id_mm=0.5, height_mm=1.0)
    assert not wire_fit(tiny, 200).fits


def test_custom_core_without_dimensions() -> None:
    core = make_custom_core("custom", 10.0)
    design = design_toroid(core, inductance_h=1e-6, current_a=1.0)
    assert design.turns == 10
    assert design.wire.awg is None
    assert design.wire_length_m == 0.0
    assert design.flux_density_t is None


def test_design_validation() -> None:
    core = find_core("T50-2")
    with pytest.raises(ToroidError, match="exactly one"):
        design_toroid(core)
    with pytest.raises(ToroidError, match="exactly one"):
        design_toroid(core, inductance_h=1e-6, turns=10)
    with pytest.raises(ToroidError, match="turns"):
        design_toroid(core, turns=0)
    with pytest.raises(ToroidError, match="AL"):
        turns_for_inductance(1e-6, 0.0)
    with pytest.raises(ToroidError, match="dimensions"):
        make_custom_core("bad", 5.0, od_mm=5.0, id_mm=6.0, height_mm=1.0)


def test_cli_list(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["toroid", "--list"]) == 0
    out = capsys.readouterr().out
    assert "T50-2" in out and "FT50-43" in out and "nH/N^2" in out


def test_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["toroid", "--core", "T50-2", "--turns", "15", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["turns"] == 15
    assert data["core"]["name"] == "T50-2"
    assert data["inductance_h"] == pytest.approx(1.1025e-6)
    assert data["wire"]["awg"] == 16


def test_cli_text_and_custom(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "toroid",
                "--core",
                "FT50-43",
                "--inductance",
                "10u",
                "--current",
                "0.5",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "FT50-43" in out and "Turns:" in out and "B/Bsat" in out
    assert main(["toroid", "--al", "4.9", "--inductance", "1u"]) == 0
    assert "custom" in capsys.readouterr().out
    assert main(["toroid"]) == 2
