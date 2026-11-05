"""N-port primitives: validation, port operations and Touchstone conversion."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.multiport import (
    MultiportError,
    SParameters,
    _s_to_y,
    _y_to_s,
)
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


def test_cascade_matched_attenuators() -> None:
    first = _matched_attenuator(0.5)
    second = _matched_attenuator(0.5)
    cascaded = first.cascade(second)
    assert cascaded.n_ports == 2
    assert cascaded.s[:, 1, 0] == pytest.approx(0.25)
    assert cascaded.s[:, 0, 1] == pytest.approx(0.25)
    assert cascaded.s[:, 0, 0] == pytest.approx(0.0)


def test_connect_ideal_thru_and_port_order() -> None:
    frequency = _frequencies()
    thru_s = np.zeros((3, 2, 2), dtype=complex)
    thru_s[:, 1, 0] = 1.0
    thru_s[:, 0, 1] = 1.0
    thru = SParameters(frequency, thru_s)
    three_s = np.zeros((3, 3, 3), dtype=complex)
    three_s[:, 1, 0] = 0.8
    three_s[:, 2, 0] = 0.6
    three_s[:, 0, 1] = 0.8
    three_s[:, 0, 2] = 0.6
    three = SParameters(frequency, three_s)
    result = SParameters.connect((three, thru), ((0, 2, 1, 1),))
    assert result.n_ports == 3
    # External order: three port 1, three port 3, thru port 2.
    assert result.s[:, 1, 0] == pytest.approx(0.6)
    assert result.s[:, 2, 0] == pytest.approx(0.8)
    assert result.s[:, 1, 1] == pytest.approx(0.0)


def test_connect_rejects_invalid_connections() -> None:
    branch = _matched_attenuator()
    with pytest.raises(MultiportError):
        SParameters.connect((branch,), ())
    with pytest.raises(MultiportError):
        SParameters.connect((branch, branch), ((0, 1, 1, 1), (0, 1, 1, 2)))
    with pytest.raises(MultiportError):
        SParameters.connect(
            (branch, branch), ((0, 1, 1, 1), (0, 2, 1, 2))
        )
    other = SParameters(_frequencies() * 2.0, branch.s)
    with pytest.raises(MultiportError):
        SParameters.connect((branch, other), ((0, 2, 1, 1),))


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

    cascaded_path = tmp_path / "cascaded.s2p"
    assert (
        main(
            [
                "network",
                "cascade",
                str(first),
                str(second),
                "--output",
                str(cascaded_path),
            ]
        )
        == 0
    )
    assert read_sparameters(cascaded_path).s[:, 1, 0] == pytest.approx(0.25)

    connected_path = tmp_path / "connected.s2p"
    assert (
        main(
            [
                "network",
                "connect",
                str(first),
                str(second),
                "--left-port",
                "2",
                "--right-port",
                "1",
                "--output",
                str(connected_path),
            ]
        )
        == 0
    )
    assert read_sparameters(connected_path).s[:, 1, 0] == pytest.approx(0.25)
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


def test_sparameters_exact_validation_messages() -> None:
    s = np.zeros((2, 2, 2), dtype=complex)
    cases = [
        (
            lambda: SParameters(np.array([]), np.zeros((0, 2, 2))),
            "frequency_hz must be a non-empty 1-D array",
        ),
        (
            lambda: SParameters(np.array([1e6, 2e6]), np.zeros((2, 3, 2))),
            "s must have shape (points, ports, ports)",
        ),
        (
            lambda: SParameters(np.array([1e6, 2e6]), np.zeros((1, 2, 2))),
            "s has 1 points but frequency has 2",
        ),
        (
            lambda: SParameters(np.array([1e6]), np.zeros((1, 0, 0))),
            "a network needs at least one port",
        ),
        (
            lambda: SParameters(np.array([0.0]), s[:1]),
            "frequencies must be finite and > 0",
        ),
        (
            lambda: SParameters(np.array([2e6, 1e6]), s),
            "frequencies must be strictly increasing",
        ),
        (
            lambda: SParameters(np.array([1e6, 2e6]), np.full((2, 2, 2), np.nan)),
            "S-parameters must be finite",
        ),
        (
            lambda: SParameters(np.array([1e6]), s[:1], z0_ohm=0.0),
            "z0_ohm must be finite and > 0",
        ),
    ]
    for call, message in cases:
        with pytest.raises(MultiportError) as info:
            call()
        assert str(info.value) == message


def test_sparameters_converts_numeric_dtypes() -> None:
    network = SParameters(
        np.array([1, 2], dtype=int),
        np.zeros((2, 2, 2), dtype=int),
    )
    assert network.frequency_hz.dtype == np.float64
    assert network.s.dtype == np.complex128


def test_sparameter_accessors_and_summary() -> None:
    network = _matched_attenuator(0.5)
    assert network.s_param(2, 1) == pytest.approx(network.s[:, 1, 0])
    with pytest.raises(MultiportError, match=r"port must be in 1\.\.2: 0"):
        network.s_param(0, 1)
    with pytest.raises(MultiportError, match=r"port must be in 1\.\.2: 3"):
        network.s_param(1, 3)
    assert network.summary() == (
        "2-port, 3 points, 1e+06–1e+08 Hz, Z0=50 ohm"
    )


def test_from_analysis_rejects_unequal_impedances() -> None:
    frequency = _frequencies()
    zeros = np.zeros_like(frequency)
    result = AnalysisResult(
        frequency_hz=frequency,
        s11=zeros,
        s21=zeros,
        s12=zeros,
        s22=zeros,
        zin_ohm=zeros,
        zout_ohm=zeros,
        z0_source_ohm=50.0,
        z0_load_ohm=75.0,
        backend="test",
    )
    with pytest.raises(MultiportError, match="unequal port impedances"):
        SParameters.from_analysis(result)


def test_terminate_and_connect_exact_errors() -> None:
    one_port = SParameters(np.array([1e6]), np.zeros((1, 1, 1), dtype=complex))
    with pytest.raises(MultiportError, match="cannot terminate the only port"):
        one_port.terminate(1, z_load_ohm=50.0)
    branch = _matched_attenuator()
    with pytest.raises(MultiportError, match="load reflection coefficient"):
        branch.terminate(2, z_load_ohm=complex(np.inf, 1.0))
    singular_s = np.ones((3, 2, 2), dtype=complex)
    singular = SParameters(_frequencies(), singular_s)
    with pytest.raises(MultiportError, match="terminated network is singular"):
        singular.terminate(2, z_load_ohm=complex(np.inf))
    with pytest.raises(MultiportError, match="connect needs at least one network"):
        SParameters.connect((), ())
    with pytest.raises(MultiportError, match="connect needs at least one port pair"):
        SParameters.connect((branch,), ())
    with pytest.raises(MultiportError, match="same reference impedance"):
        SParameters.connect(
            (branch, SParameters(_frequencies(), branch.s, z0_ohm=75.0)),
            ((0, 2, 1, 1),),
        )
    with pytest.raises(MultiportError, match="connection network index"):
        SParameters.connect((branch, branch), ((0, 2, 2, 1),))
    with pytest.raises(MultiportError, match="connection port is out of range"):
        SParameters.connect((branch, branch), ((0, 3, 1, 1),))
    with pytest.raises(MultiportError, match="cannot connect a port to itself"):
        SParameters.connect((branch,), ((0, 1, 0, 1),))
    with pytest.raises(MultiportError, match="only one connection"):
        SParameters.connect(
            (branch, branch), ((0, 1, 1, 1), (0, 1, 1, 2))
        )
    with pytest.raises(MultiportError, match="no external ports"):
        SParameters.connect(
            (branch, branch), ((0, 1, 1, 1), (0, 2, 1, 2))
        )
    with pytest.raises(MultiportError, match="cascade requires two 2-port"):
        branch.cascade(SParameters(_frequencies(), np.zeros((3, 3, 3))))


def test_parallel_branches_exact_errors() -> None:
    branch = _matched_attenuator()
    with pytest.raises(MultiportError, match="at least two branches"):
        SParameters.parallel_branches((branch,))
    with pytest.raises(MultiportError, match="must be 2-ports"):
        SParameters.parallel_branches(
            (branch, SParameters(_frequencies(), np.zeros((3, 3, 3))))
        )
    with pytest.raises(MultiportError, match="same reference impedance"):
        SParameters.parallel_branches(
            (branch, SParameters(_frequencies(), branch.s, z0_ohm=75.0))
        )
    with pytest.raises(MultiportError, match="S-to-Y conversion is singular"):
        short = SParameters(
            _frequencies(), np.broadcast_to(-np.eye(2), (3, 2, 2))
        )
        SParameters.parallel_branches((short, short))


def _multiport_message(call) -> str:  # type: ignore[no-untyped-def]
    with pytest.raises(MultiportError) as info:
        call()
    return str(info.value)


def test_sparameters_accepts_small_z0_and_rejects_duplicate_frequencies() -> None:
    network = SParameters(
        np.array([1e6, 2e6]), np.zeros((2, 2, 2)), z0_ohm=0.5
    )
    assert network.z0_ohm == pytest.approx(0.5)
    assert _multiport_message(
        lambda: SParameters(np.array([1e6, 1e6]), np.zeros((2, 2, 2)))
    ) == "frequencies must be strictly increasing"


def test_from_analysis_preserves_complex_values_and_impedance() -> None:
    frequency = _frequencies()
    zeros = np.zeros_like(frequency)
    result = AnalysisResult(
        frequency_hz=frequency,
        s11=zeros + 0.1 + 0.2j,
        s21=zeros + 0.3 - 0.1j,
        s12=zeros + 0.4 + 0.05j,
        s22=zeros - 0.2 + 0.3j,
        zin_ohm=zeros + 75.0,
        zout_ohm=zeros + 75.0,
        z0_source_ohm=75.0,
        z0_load_ohm=75.0,
        backend="solver",
    )
    network = SParameters.from_analysis(result)
    assert network.z0_ohm == pytest.approx(75.0)
    assert network.source == "solver"
    assert network.s[:, 0, 0] == pytest.approx(0.1 + 0.2j)
    assert network.s[:, 1, 0] == pytest.approx(0.3 - 0.1j)
    assert network.s[:, 0, 1] == pytest.approx(0.4 + 0.05j)
    assert network.s[:, 1, 1] == pytest.approx(-0.2 + 0.3j)


def test_from_analysis_rejects_close_unequal_impedances_exactly() -> None:
    frequency = _frequencies()
    zeros = np.zeros_like(frequency)
    result = AnalysisResult(
        frequency_hz=frequency,
        s11=zeros,
        s21=zeros,
        s12=zeros,
        s22=zeros,
        zin_ohm=zeros,
        zout_ohm=zeros,
        z0_source_ohm=50.0,
        z0_load_ohm=50.0001,
        backend="test",
    )
    assert _multiport_message(lambda: SParameters.from_analysis(result)) == (
        "a 2-port AnalysisResult with unequal port impedances cannot be "
        "represented by one scalar z0"
    )


def test_port_renumber_exact_message() -> None:
    network = SParameters(np.array([1e6]), np.zeros((1, 3, 3)))
    assert _multiport_message(lambda: network.port_renumber((1, 2))) == (
        "order must be a permutation of 1..3: (1, 2)"
    )


def test_terminate_exact_messages_and_finite_load() -> None:
    one_port = SParameters(np.array([1e6]), np.zeros((1, 1, 1)))
    assert _multiport_message(
        lambda: one_port.terminate(1, z_load_ohm=50.0)
    ) == "cannot terminate the only port of a 1-port"

    branch = _matched_attenuator()
    assert _multiport_message(
        lambda: branch.terminate(2, z_load_ohm=complex(np.inf, 1.0))
    ) == "load reflection coefficient is not finite"

    singular = SParameters(_frequencies(), np.ones((3, 2, 2), dtype=complex))
    assert _multiport_message(
        lambda: singular.terminate(2, z_load_ohm=complex(np.inf))
    ) == "terminated network is singular"

    s = np.zeros((1, 2, 2), dtype=complex)
    s[0, 0, 0] = 0.1 + 0.05j
    s[0, 1, 1] = 0.2 - 0.1j
    s[0, 1, 0] = 0.6 + 0.2j
    s[0, 0, 1] = 0.5 - 0.3j
    network = SParameters(np.array([1e6]), s)
    reduced = network.terminate(2, z_load_ohm=75.0)
    gamma = (75.0 - 50.0) / (75.0 + 50.0)
    expected = s[0, 0, 0] + s[0, 0, 1] * s[0, 1, 0] * gamma / (
        1.0 - s[0, 1, 1] * gamma
    )
    assert reduced.s[0, 0, 0] == pytest.approx(expected)


def test_connect_exact_errors_metadata_and_schur_complement() -> None:
    branch = _matched_attenuator()
    other_frequency = SParameters(_frequencies() * 2.0, branch.s)
    other_z0 = SParameters(_frequencies(), branch.s, z0_ohm=75.0)

    assert _multiport_message(
        lambda: SParameters.connect((), ())
    ) == "connect needs at least one network"
    assert _multiport_message(
        lambda: SParameters.connect((branch,), ())
    ) == "connect needs at least one port pair"
    assert _multiport_message(
        lambda: SParameters.connect((branch, other_frequency), ((0, 2, 1, 1),))
    ) == "connected networks must share one frequency grid"
    assert _multiport_message(
        lambda: SParameters.connect((branch, other_z0), ((0, 2, 1, 1),))
    ) == "connected networks must use the same reference impedance"
    close_z0 = SParameters(_frequencies(), branch.s, z0_ohm=50.00005)
    assert _multiport_message(
        lambda: SParameters.connect((branch, close_z0), ((0, 2, 1, 1),))
    ) == "connected networks must use the same reference impedance"
    assert _multiport_message(
        lambda: SParameters.connect((branch, branch), ((2, 1, 0, 1),))
    ) == "connection network index is out of range"
    assert _multiport_message(
        lambda: SParameters.connect((branch, branch), ((0, 3, 1, 1),))
    ) == "connection port is out of range"
    assert _multiport_message(
        lambda: SParameters.connect((branch, branch), ((0, 1, 1, 3),))
    ) == "connection port is out of range"
    assert _multiport_message(
        lambda: SParameters.connect((branch,), ((0, 1, 0, 1),))
    ) == "cannot connect a port to itself"
    assert _multiport_message(
        lambda: SParameters.connect(
            (branch, branch), ((0, 1, 1, 1), (0, 1, 1, 2))
        )
    ) == "each port can participate in only one connection"
    assert _multiport_message(
        lambda: SParameters.connect(
            (branch, branch), ((0, 1, 1, 1), (0, 2, 1, 2))
        )
    ) == "connection leaves no external ports"

    open_s = np.zeros((3, 2, 2), dtype=complex)
    open_s[:, 0, 0] = 1.0
    open_network = SParameters(_frequencies(), open_s)
    assert _multiport_message(
        lambda: SParameters.connect(
            (open_network, open_network), ((0, 1, 1, 1),)
        )
    ) == "connected network is singular"

    s_a = np.zeros((3, 2, 2), dtype=complex)
    s_a[:, 0, 0] = 0.1 + 0.05j
    s_a[:, 1, 0] = 0.7 + 0.2j
    s_a[:, 0, 1] = 0.6 - 0.1j
    s_a[:, 1, 1] = -0.2 + 0.3j
    s_b = np.zeros((3, 2, 2), dtype=complex)
    s_b[:, 0, 0] = -0.05 + 0.1j
    s_b[:, 1, 0] = 0.4 - 0.2j
    s_b[:, 0, 1] = 0.3 + 0.15j
    s_b[:, 1, 1] = 0.25 - 0.05j
    first = SParameters(_frequencies(), s_a, z0_ohm=75.0, source="a")
    second = SParameters(_frequencies(), s_b, z0_ohm=75.0, source="b")
    result = SParameters.connect((first, second), ((0, 2, 1, 1),))
    assert result.source == "connected"
    assert result.z0_ohm == pytest.approx(75.0)

    all_s = np.zeros((3, 4, 4), dtype=complex)
    all_s[:, :2, :2] = s_a
    all_s[:, 2:, 2:] = s_b
    external = [0, 3]
    internal = [1, 2]
    s_ee = all_s[:, external, :][:, :, external]
    s_ei = all_s[:, external, :][:, :, internal]
    s_ie = all_s[:, internal, :][:, :, external]
    s_ii = all_s[:, internal, :][:, :, internal]
    connection = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
    expected = s_ee + s_ei @ np.linalg.solve(
        np.eye(2, dtype=complex) - connection @ s_ii,
        connection @ s_ie,
    )
    assert result.s == pytest.approx(expected)


def test_cascade_exact_error_and_port_mapping() -> None:
    branch = _matched_attenuator()
    three_port = SParameters(_frequencies(), np.zeros((3, 3, 3)))
    assert _multiport_message(
        lambda: branch.cascade(three_port)
    ) == "cascade requires two 2-port networks"

    s_a = np.zeros((3, 2, 2), dtype=complex)
    s_a[:, 0, 0] = 0.1
    s_a[:, 1, 0] = 0.6
    s_a[:, 0, 1] = 0.5
    s_a[:, 1, 1] = -0.2
    s_b = np.zeros((3, 2, 2), dtype=complex)
    s_b[:, 0, 0] = -0.3
    s_b[:, 1, 0] = 0.4
    s_b[:, 0, 1] = 0.2
    s_b[:, 1, 1] = 0.15
    first = SParameters(_frequencies(), s_a)
    second = SParameters(_frequencies(), s_b)
    assert first.cascade(second).s == pytest.approx(
        SParameters.connect((first, second), ((0, 2, 1, 1),)).s
    )


def test_parallel_branches_exact_errors_and_metadata() -> None:
    branch = _matched_attenuator()
    three_port = SParameters(_frequencies(), np.zeros((3, 3, 3)))
    other_frequency = SParameters(_frequencies() * 2.0, branch.s)
    other_z0 = SParameters(_frequencies(), branch.s, z0_ohm=75.0)

    assert _multiport_message(
        lambda: SParameters.parallel_branches((branch,))
    ) == "parallel combination needs at least two branches"
    assert _multiport_message(
        lambda: SParameters.parallel_branches((branch, three_port))
    ) == "parallel branches must be 2-ports"
    assert _multiport_message(
        lambda: SParameters.parallel_branches((branch, other_frequency))
    ) == "parallel branches must share one frequency grid"
    assert _multiport_message(
        lambda: SParameters.parallel_branches((branch, other_z0))
    ) == "parallel branches must use the same reference impedance"
    close_z0 = SParameters(_frequencies(), branch.s, z0_ohm=50.00005)
    assert _multiport_message(
        lambda: SParameters.parallel_branches((branch, close_z0))
    ) == "parallel branches must use the same reference impedance"
    assert _multiport_message(
        lambda: _s_to_y(np.broadcast_to(-np.eye(2), (3, 2, 2)), 50.0)
    ) == "S-to-Y conversion is singular"
    singular_y = np.array(
        [[[1.0, 0.0], [0.0, -1.0 / 50.0]]], dtype=complex
    )
    assert _multiport_message(
        lambda: _y_to_s(singular_y, 50.0)
    ) == "Y-to-S conversion is singular"

    s_a = np.zeros((3, 2, 2), dtype=complex)
    s_a[:, 1, 0] = 0.5
    s_a[:, 0, 1] = 0.5
    s_b = np.zeros((3, 2, 2), dtype=complex)
    s_b[:, 1, 0] = 0.4
    s_b[:, 0, 1] = 0.4
    first = SParameters(_frequencies(), s_a, z0_ohm=75.0, source="first")
    second = SParameters(_frequencies(), s_b, z0_ohm=75.0, source="second")
    combined = SParameters.parallel_branches((first, second))
    assert combined.source == "first"
    assert combined.z0_ohm == pytest.approx(75.0)
    assert combined.frequency_hz == pytest.approx(first.frequency_hz)
