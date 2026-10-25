"""Single-layer air-core solenoid calculator tests (Phase 12)."""

from __future__ import annotations

import json
import math

import pytest

from filterdesk.__main__ import main
from filterdesk.components_std.air_coil import (
    COPPER_RESISTIVITY_OHM_M,
    AirCoilError,
    air_coil_inductance_h,
    awg_for_diameter_mm,
    design_air_coil,
)
from filterdesk.components_std.toroid import awg_diameter_mm


def test_fixed_turns_wheeler() -> None:
    design = design_air_coil(diameter_mm=10.0, awg=24, turns=10)
    assert design.turns == 10
    assert design.turns_exact == pytest.approx(10.0)
    assert design.wire_diameter_mm == pytest.approx(0.510559, rel=1e-5)
    assert design.length_mm == pytest.approx(10 * design.wire_diameter_mm)
    assert design.length_to_diameter == pytest.approx(
        design.length_mm / 10.0
    )
    assert design.inductance_h == pytest.approx(
        air_coil_inductance_h(
            10, 10.0, wire_diameter_mm=design.wire_diameter_mm
        )
    )
    assert design.target_inductance_h is None


def test_design_from_target_rounds_up() -> None:
    design = design_air_coil(diameter_mm=10.0, awg=24, inductance_h=1e-6)
    assert design.turns_exact < 10.0
    assert design.turns == 10
    assert design.target_inductance_h == pytest.approx(1e-6)
    assert design.inductance_h >= 1e-6
    assert design.inductance_h == pytest.approx(1.02467e-6, rel=1e-4)
    assert not design.short_coil


def test_wire_and_resistance() -> None:
    design = design_air_coil(diameter_mm=10.0, awg=24, turns=10)
    expected_length = 10 * math.pi * 0.010
    assert design.wire_length_m == pytest.approx(expected_length)
    area = math.pi * (design.wire_diameter_mm / 1000.0 / 2.0) ** 2
    expected_r = COPPER_RESISTIVITY_OHM_M * expected_length / area
    assert design.resistance_ohm == pytest.approx(expected_r)
    assert design.resistance_ohm > 0.0


def test_custom_mm_wire_matches_awg() -> None:
    diameter = awg_diameter_mm(24)
    by_awg = design_air_coil(diameter_mm=10.0, awg=24, turns=10)
    by_mm = design_air_coil(
        diameter_mm=10.0, wire_diameter_mm=diameter, turns=10
    )
    assert by_mm.wire_diameter_mm == pytest.approx(diameter)
    assert by_mm.awg == awg_for_diameter_mm(diameter)
    assert by_mm.inductance_h == pytest.approx(by_awg.inductance_h)
    assert by_mm.resistance_ohm == pytest.approx(by_awg.resistance_ohm)


def test_awg_for_diameter() -> None:
    assert awg_for_diameter_mm(awg_diameter_mm(20)) == 20
    assert 8 <= awg_for_diameter_mm(0.6) <= 40
    with pytest.raises(AirCoilError, match="wire diameter"):
        awg_for_diameter_mm(0.0)


def test_short_coil_flag() -> None:
    design = design_air_coil(diameter_mm=50.0, awg=24, turns=1)
    assert design.short_coil
    assert design.length_to_diameter < 0.2


def test_validation() -> None:
    with pytest.raises(AirCoilError, match="diameter"):
        design_air_coil(diameter_mm=0.0, awg=24, turns=5)
    with pytest.raises(AirCoilError, match="AWG"):
        design_air_coil(diameter_mm=10.0, awg=7, turns=5)
    with pytest.raises(AirCoilError, match="awg or wire_diameter_mm"):
        design_air_coil(diameter_mm=10.0, turns=5)
    with pytest.raises(AirCoilError, match="awg or wire_diameter_mm"):
        design_air_coil(
            diameter_mm=10.0, awg=24, wire_diameter_mm=0.5, turns=5
        )
    with pytest.raises(AirCoilError, match="exactly one"):
        design_air_coil(diameter_mm=10.0, awg=24)
    with pytest.raises(AirCoilError, match="exactly one"):
        design_air_coil(diameter_mm=10.0, awg=24, turns=5, inductance_h=1e-6)
    with pytest.raises(AirCoilError, match="inductance"):
        design_air_coil(diameter_mm=10.0, awg=24, inductance_h=0.0)
    with pytest.raises(AirCoilError, match="turns"):
        design_air_coil(diameter_mm=10.0, awg=24, turns=0)


def test_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    args = [
        "air-coil",
        "--diameter",
        "10",
        "--awg",
        "24",
        "--inductance",
        "1u",
        "--json",
    ]
    assert main(args) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["turns"] == 10
    assert data["target_inductance_h"] == pytest.approx(1e-6)
    assert data["resistance_ohm"] > 0.0
    assert data["short_coil"] is False

    assert (
        main(
            [
                "air-coil",
                "--diameter",
                "10",
                "--wire-mm",
                "0.5",
                "--turns",
                "10",
                "--json",
            ]
        )
        == 0
    )
    custom = json.loads(capsys.readouterr().out)
    assert custom["wire_diameter_mm"] == pytest.approx(0.5)
    assert custom["awg"] == awg_for_diameter_mm(0.5)


def test_cli_text_and_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["air-coil", "--diameter", "10", "--awg", "24", "--turns", "10"]) == 0
    out = capsys.readouterr().out
    assert "Air-core solenoid" in out
    assert "Turns:" in out and "R_DC" in out
    assert main(["air-coil", "--diameter", "10", "--awg", "24"]) == 2
    assert "error:" in capsys.readouterr().err
