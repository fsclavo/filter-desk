"""N-port primitives: validation, port operations and Touchstone conversion."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.multiport import MultiportError, SParameters
from filterdesk.analysis.types import AnalysisResult
from filterdesk.io.touchstone import read_sparameters, write_sparameters


def _frequencies() -> np.ndarray:
    return np.array([1e6, 10e6, 100e6], dtype=float)


def _matched_attenuator(s21: float = 0.5) -> SParameters:
    s = np.zeros((3, 2, 2), dtype=np.complex128)
    s[:, 0, 1] = s21
    s[:, 1, 0] = s21
    return SParameters(_frequencies(), s, z0_ohm=50.0)


def test_sparameters_validation() -> None:
    s = np.zeros((2, 2, 2), dtype=complex)
    with pytest.raises(MultiportError):
        SParameters(np.array([0.0, 1.0]), s)
    with pytest.raises(MultiportError):
        SParameters(np.array([2.0, 1.0]), s)
    with pytest.raises(MultiportError):
        SParameters(np.array([1.0]), s)
    with pytest.raises(MultiportError):
        SParameters(np.array([1.0, 2.0]), s, z0_ohm=0.0)
    with pytest.raises(MultiportError):
        SParameters(np.array([1.0, 2.0]), np.full((2, 2, 2), np.nan))


def test_from_analysis_result_keeps_port_order() -> None:
    frequency = _frequencies()
    zeros = np.zeros_like(frequency)
    result = AnalysisResult(
        frequency_hz=frequency,
        s11=zeros + 0.1,
        s21=zeros + 0.2,
        s12=zeros + 0.3,
        s22=zeros + 0.4,
        zin_ohm=zeros + 50.0,
        zout_ohm=zeros + 50.0,
        z0_source_ohm=50.0,
        z0_load_ohm=50.0,
        backend="test",
    )
    network = SParameters.from_analysis(result)
    assert network.s[:, 0, 0] == pytest.approx(0.1)
    assert network.s[:, 1, 0] == pytest.approx(0.2)
    assert network.s[:, 0, 1] == pytest.approx(0.3)
    assert network.s[:, 1, 1] == pytest.approx(0.4)
    assert network.source == "test"


def test_port_renumber_maps_new_ports_to_old_ports() -> None:
    s = np.zeros((1, 3, 3), dtype=complex)
    for out_port in range(3):
        for in_port in range(3):
            s[0, out_port, in_port] = 10 * (out_port + 1) + (in_port + 1)
    network = SParameters(np.array([1e6]), s)
    reordered = network.port_renumber((3, 1, 2))
    assert reordered.s[0, 0, 0] == 33
    assert reordered.s[0, 0, 1] == 31
    assert reordered.s[0, 1, 0] == 13
    assert reordered.s[0, 2, 1] == 21
    with pytest.raises(MultiportError):
        network.port_renumber((1, 2))


def test_terminate_matched_load_keeps_input_reflection() -> None:
    network = _matched_attenuator()
    reduced = network.terminate(2, z_load_ohm=50.0)
    assert reduced.n_ports == 1
    assert reduced.s[:, 0, 0] == pytest.approx(network.s[:, 0, 0])


def test_terminate_open_load_uses_schur_complement() -> None:
    s = np.zeros((1, 2, 2), dtype=complex)
    s[0, 0, 0] = 0.1 + 0.05j
    s[0, 1, 1] = 0.2 - 0.1j
    s[0, 1, 0] = 0.6 + 0.2j
    s[0, 0, 1] = 0.5 - 0.3j
    network = SParameters(np.array([1e6]), s)
    reduced = network.terminate(2, z_load_ohm=complex(np.inf))
    expected = s[0, 0, 0] + s[0, 0, 1] * s[0, 1, 0] / (1.0 - s[0, 1, 1])
    assert reduced.s[0, 0, 0] == pytest.approx(expected)


def test_parallel_branches_match_three_resistor_junction() -> None:
    branch = _matched_attenuator(0.5)
    combined = SParameters.parallel_branches((branch, branch))
    assert combined.n_ports == 3
    # Common node sees three 50 ohm terminations in parallel => -1/3.
    assert combined.s[:, 0, 0] == pytest.approx(-1.0 / 3.0)
    # The 3-way junction transmits 2/3 into each branch; the 6 dB attenuator
    # then multiplies by 0.5 => 1/3 at each output.
    assert combined.s[:, 1, 0] == pytest.approx(1.0 / 3.0)
    assert combined.s[:, 2, 0] == pytest.approx(1.0 / 3.0)
    # Backward path: 0.5 into the common node, 2/3 into the other branch,
    # then 0.5 through its attenuator => 1/6.
    assert combined.s[:, 2, 1] == pytest.approx(1.0 / 6.0)
    assert combined.s[:, 1, 1] == pytest.approx(-1.0 / 12.0)


def test_parallel_branches_reject_incompatible_inputs() -> None:
    branch = _matched_attenuator()
    other = SParameters(_frequencies() * 2.0, branch.s)
    with pytest.raises(MultiportError):
        SParameters.parallel_branches((branch, other))
    with pytest.raises(MultiportError):
        SParameters.parallel_branches((branch,))
    three_port = SParameters(
        _frequencies(), np.zeros((3, 3, 3), dtype=complex)
    )
    with pytest.raises(MultiportError):
        SParameters.parallel_branches((branch, three_port))


def test_touchstone_nport_round_trip(tmp_path: Path) -> None:
    branch = _matched_attenuator()
    combined = SParameters.parallel_branches((branch, branch))
    path = tmp_path / "combined.s3p"
    write_sparameters(combined, path, comment="test")
    loaded = read_sparameters(path)
    assert loaded.n_ports == 3
    assert loaded.frequency_hz == pytest.approx(combined.frequency_hz)
    assert loaded.s == pytest.approx(combined.s)
    assert loaded.z0_ohm == pytest.approx(50.0)


def test_cli_network_info_renumber_terminate_and_combine(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    branch = _matched_attenuator(0.5)
    first = tmp_path / "branch.s2p"
    write_sparameters(branch, first)

    assert main(["network", "info", str(first), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["n_ports"] == 2
    assert payload["n_points"] == 3

    reordered = tmp_path / "reordered.s2p"
    assert (
        main(
            [
                "network",
                "renumber",
                str(first),
                "--order",
                "2,1",
                "--output",
                str(reordered),
            ]
        )
        == 0
    )
    assert read_sparameters(reordered).s == pytest.approx(branch.s)

    terminated = tmp_path / "terminated.s1p"
    assert (
        main(
            [
                "network",
                "terminate",
                str(first),
                "--port",
                "2",
                "--load",
                "open",
                "--output",
                str(terminated),
            ]
        )
        == 0
    )
    assert read_sparameters(terminated).n_ports == 1

    second = tmp_path / "branch2.s2p"
    write_sparameters(branch, second)
    combined_path = tmp_path / "combined.s3p"
    assert (
        main(
            [
                "network",
                "combine",
                str(first),
                str(second),
                "--output",
                str(combined_path),
            ]
        )
        == 0
    )
    combined = read_sparameters(combined_path)
    assert combined.n_ports == 3
    assert combined.s[:, 0, 0] == pytest.approx(-1.0 / 3.0)
    assert "Wrote" in capsys.readouterr().err


def test_cli_network_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    branch = _matched_attenuator()
    path = tmp_path / "branch.s2p"
    write_sparameters(branch, path)
    assert (
        main(
            [
                "network",
                "renumber",
                str(path),
                "--order",
                "1",
                "--output",
                str(tmp_path / "bad.s2p"),
            ]
        )
        == 2
    )
    assert "error:" in capsys.readouterr().err
    assert (
        main(
            [
                "network",
                "terminate",
                str(path),
                "--port",
                "9",
                "--output",
                str(tmp_path / "bad.s1p"),
            ]
        )
        == 2
    )
