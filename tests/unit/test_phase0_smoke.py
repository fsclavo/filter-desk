"""Smoke / CLI tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from filterdesk import __version__
from filterdesk.__main__ import main

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests/golden/cheby1_hp_n7_0p01db_140mhz_50ohm"


def test_version() -> None:
    assert __version__ == "0.6.1"


def test_cli_no_args_prints_help() -> None:
    assert main([]) == 0


def test_cli_synthesize_help() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["synthesize", "--help"])
    assert exc.value.code == 0


def test_cli_synthesize_from_golden_spec() -> None:
    assert main(["synthesize", "--spec", str(GOLDEN / "spec.json")]) == 0


def test_cli_synthesize_json_milestone() -> None:
    # Capture via running synthesize API path through CLI --json
    code = main(
        [
            "synthesize",
            "--family",
            "chebyshev_type_i",
            "--response",
            "high_pass",
            "--order",
            "7",
            "--ripple",
            "0.01",
            "--cutoff",
            "140M",
            "--json",
        ]
    )
    assert code == 0


def test_cli_analyze_milestone() -> None:
    assert (
        main(
            [
                "analyze",
                "--spec",
                str(GOLDEN / "spec.json"),
                "--points",
                "128",
                "--backend",
                "abcd",
            ]
        )
        == 0
    )


def test_cli_touchstone_info(tmp_path: Path) -> None:
    from filterdesk.io.touchstone import write_touchstone_s2p
    from filterdesk.services.session import DesignSession

    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.analysis is not None
    path = tmp_path / "sim.s2p"
    write_touchstone_s2p(session.analysis, path)
    assert main(["touchstone-info", str(path)]) == 0
    assert main(["touchstone-info", "--json", str(path)]) == 0


def test_cli_estimate_order_bandpass() -> None:
    assert (
        main(
            [
                "estimate-order",
                "--family",
                "chebyshev_type_i",
                "--response",
                "band_pass",
                "--pass-band",
                "0.9M",
                "1.1M",
                "--stop-band",
                "0.7M",
                "1.4M",
                "--ap",
                "0.5",
                "--as",
                "40",
                "--json",
            ]
        )
        == 0
    )


def test_cli_estimate_order_band_requires_edges() -> None:
    assert (
        main(
            [
                "estimate-order",
                "--family",
                "butterworth",
                "--response",
                "band_pass",
                "--ap",
                "3",
                "--as",
                "40",
            ]
        )
        == 1
    )


def test_cli_compare(tmp_path: Path) -> None:
    from filterdesk.io.touchstone import write_touchstone_s2p
    from filterdesk.services.session import DesignSession

    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.analysis is not None
    sim = tmp_path / "sim.s2p"
    mea = tmp_path / "mea.s2p"
    write_touchstone_s2p(session.analysis, sim)
    write_touchstone_s2p(session.analysis, mea)
    assert main(["compare", str(sim), str(mea)]) == 0
    assert main(["compare", "--json", str(sim), str(mea)]) == 0
