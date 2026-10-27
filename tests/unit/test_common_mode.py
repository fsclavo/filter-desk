"""Common-mode choke sweep and project persistence."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.common_mode import (
    CommonModeError,
    common_mode_sweep,
)
from filterdesk.domain.circuit import BalunSpec
from filterdesk.domain.project import circuit_from_mapping, circuit_to_mapping


def _choke() -> BalunSpec:
    return BalunSpec(
        kind="choke",
        turns_ratio=1.0,
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=50.0,
        magnetizing_inductance_h=1e-5,
        common_mode_impedance_ohm=2 * math.pi * 1e6 * 1e-5,
    )


def test_common_mode_sweep_formula_and_monotonicity() -> None:
    report = common_mode_sweep(_choke(), np.array([1e6, 3e6, 10e6]))
    assert report.z0_ohm == pytest.approx(50.0)
    assert len(report.points) == 3
    attenuations = [point.attenuation_db for point in report.points]
    assert attenuations == sorted(attenuations)
    zcm = 2 * math.pi * 1e6 * 1e-5
    expected = -20 * math.log10(abs(2 * 50 / (2 * 50 + 1j * zcm)))
    assert attenuations[0] == pytest.approx(expected)


def test_common_mode_errors() -> None:
    with pytest.raises(CommonModeError, match="choke"):
        common_mode_sweep(BalunSpec(kind="unun", turns_ratio=0.5), [1e6])
    with pytest.raises(CommonModeError, match="no common-mode"):
        common_mode_sweep(
            BalunSpec(
                kind="choke",
                turns_ratio=1.0,
                z_unbalanced_ohm=50.0,
                z_balanced_ohm=50.0,
            ),
            [1e6],
        )
    with pytest.raises(CommonModeError, match="frequencies"):
        common_mode_sweep(_choke(), [])


def test_choke_inductance_project_round_trip() -> None:
    spec = _choke()
    from filterdesk.domain.circuit import Circuit, IdealResistor, Port

    circuit = Circuit(
        [IdealResistor("R1", 50.0, "in", "out")],
        Port("P1", "in", 50.0),
        Port("P2", "out", 50.0),
        output_balun=spec,
    )
    restored = circuit_from_mapping(circuit_to_mapping(circuit))
    assert restored.output_balun is not None
    assert restored.output_balun.magnetizing_inductance_h == pytest.approx(1e-5)


def test_cli_transformer_common_mode_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "transformer",
            "--kind",
            "choke",
            "--z-low",
            "50",
            "--z-high",
            "50",
            "--core",
            "FT240-43",
            "--frequency",
            "1M",
            "--f-max",
            "30M",
            "--power",
            "100",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    sweep = payload["common_mode_sweep"]
    assert len(sweep) == 5
    assert sweep[0]["attenuation_db"] < sweep[-1]["attenuation_db"]
