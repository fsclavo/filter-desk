"""CLI JSON / error-path smoke tests for commands not covered elsewhere."""

from __future__ import annotations

import json

from filterdesk.__main__ import main

SPEC_BASE = [
    "--family",
    "butterworth",
    "--response",
    "low_pass",
    "--order",
    "3",
    "--cutoff",
    "100M",
]
ANALYZE_BASE = [*SPEC_BASE, "--points", "24"]


def test_cli_snap_json(capsys) -> None:
    args = [
        "snap",
        *SPEC_BASE,
        "--series",
        "E24",
        "--strategy",
        "preserve_lc_resonances",
        "--json",
    ]
    assert main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["snap"]["series"] == "E24"
    assert payload["snap"]["strategy"] == "preserve_lc_resonances"


def test_cli_montecarlo_json(capsys) -> None:
    args = [
        "montecarlo",
        *ANALYZE_BASE,
        "--trials",
        "3",
        "--tol",
        "2",
        "--distribution",
        "normal",
        "--seed",
        "1",
        "--element-tol",
        "L1=3",
        "--json",
    ]
    assert main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["trials"] == 3
    assert payload["distribution"] == "normal"
    assert "element_tolerances" in payload


def test_cli_optimize_json(capsys) -> None:
    args = [
        "optimize",
        *ANALYZE_BASE,
        "--objective",
        "passband:1M:100M",
        "--method",
        "nelder_mead",
        "--max-iter",
        "3",
        "--json",
    ]
    assert main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["method"] == "nelder_mead"
    assert payload["components"]


def test_cli_sensitivity_json(capsys) -> None:
    args = [
        "sensitivity",
        *SPEC_BASE,
        "--points",
        "128",
        "--relative-step",
        "2",
        "--band-range",
        "50M",
        "200M",
        "--json",
    ]
    assert main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["relative_step_pct"] == 2
    assert payload["band_hz"] == [50e6, 200e6]
    assert payload["components"]


def test_cli_estimate_order_json(capsys) -> None:
    assert (
        main(
            [
                "estimate-order",
                "--family",
                "butterworth",
                "--response",
                "low_pass",
                "--f-pass",
                "1M",
                "--f-stop",
                "2M",
                "--ap",
                "0.5",
                "--as",
                "40",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["order"] >= 1
    assert "f_pass_hz" in payload

    assert (
        main(
            [
                "estimate-order",
                "--family",
                "butterworth",
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
    band = json.loads(capsys.readouterr().out)
    assert "f_pass_low_hz" in band
    assert "natural_freq_high_hz" in band


def test_cli_estimate_order_error(capsys) -> None:
    assert (
        main(
            [
                "estimate-order",
                "--family",
                "butterworth",
                "--response",
                "band_pass",
                "--ap",
                "0.5",
                "--as",
                "40",
            ]
        )
        == 1
    )
    assert "estimate-order failed" in capsys.readouterr().err


def test_cli_analyze_json_power_harmonics_nonideal(capsys) -> None:
    args = [
        "analyze",
        *ANALYZE_BASE,
        "--power",
        "10",
        "--harmonics",
        "--harmonics-f0",
        "100M",
        "--inductor-dcr",
        "0.1",
        "--inductor-cpar",
        "1p",
        "--capacitor-esr",
        "0.05",
        "--capacitor-esl",
        "1n",
        "--json",
    ]
    assert main(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["n_points"] == 24
    assert "stress" in payload
    assert "harmonics" in payload
    assert "nonideal" in payload


def test_cli_analyze_invalid_spec(capsys) -> None:
    args = [
        "analyze",
        "--family",
        "elliptic",
        "--response",
        "low_pass",
        "--order",
        "4",
        "--cutoff",
        "100M",
        "--ripple",
        "0.5",
        "--stopband-att",
        "40",
        "--points",
        "8",
    ]
    # Even-order elliptic is rejected by validate_spec.
    assert main(args) == 2
    assert "error:" in capsys.readouterr().err
