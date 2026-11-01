"""Deterministic system sensitivity."""

from __future__ import annotations

import json
from pathlib import Path

from filterdesk.__main__ import main
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.services.diplexer import DiplexerConfig, design_diplexer
from filterdesk.services.duplexer import DuplexerConfig, design_duplexer
from filterdesk.services.multiplexer import (
    MultiplexerBand,
    MultiplexerConfig,
    design_multiplexer,
)
from filterdesk.services.system_sensitivity import analyze_system_sensitivity


def test_diplexer_sensitivity_ranks_components() -> None:
    config = DiplexerConfig(
        low_cutoff_hz=30e6,
        high_cutoff_hz=40e6,
        order=5,
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        ripple_db=0.1,
    )
    design = design_diplexer(
        config, SweepConfig(1e6, 200e6, 401, SweepSpacing.LOGARITHMIC)
    )
    report = analyze_system_sensitivity(design, 5.0)
    assert report.rows
    assert report.rows[0].score_db >= report.rows[-1].score_db
    assert {row.branch for row in report.rows} == {"Low", "High"}
    assert all(row.isolation_delta_db is None for row in report.rows)
    assert all(row.insertion_delta_db is not None for row in report.rows)
    assert "components" in report.summary()


def test_duplexer_sensitivity_reports_isolation() -> None:
    config = DuplexerConfig(
        tx_center_hz=145e6,
        tx_bandwidth_hz=1e6,
        rx_center_hz=147e6,
        rx_bandwidth_hz=1e6,
        order=6,
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        ripple_db=0.1,
        min_isolation_db=60.0,
    )
    design = design_duplexer(
        config, SweepConfig(140e6, 152e6, 401, SweepSpacing.LOGARITHMIC)
    )
    report = analyze_system_sensitivity(design, 2.0)
    assert report.rows
    assert all(row.isolation_delta_db is not None for row in report.rows)
    assert {row.branch for row in report.rows} == {"TX", "RX"}
    assert report.rows[0].score_db > 0.0


def test_triplexer_sensitivity_handles_composite_parts() -> None:
    config = MultiplexerConfig(
        bands=(
            MultiplexerBand("low", 14e6, 0.3e6),
            MultiplexerBand("mid", 21e6, 0.5e6),
            MultiplexerBand("high", 28e6, 0.5e6),
        ),
        order=5,
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        ripple_db=0.1,
    )
    design = design_multiplexer(
        config, SweepConfig(5e6, 40e6, 401, SweepSpacing.LOGARITHMIC)
    )
    report = analyze_system_sensitivity(design, 5.0)
    refs = {row.ref for row in report.rows}
    assert any(".L" in ref or ".C" in ref for ref in refs)
    assert {row.branch for row in report.rows} == {"Low", "Mid", "High"}
    assert report.rows[0].out_of_band_delta_db is not None


def test_cli_multiplexer_sensitivity_json(
    tmp_path: Path, capsys
) -> None:
    code = main(
        [
            "multiplexer",
            "--band",
            "low:14M:300k",
            "--band",
            "mid:21M:500k",
            "--band",
            "high:28M:500k",
            "--f-start",
            "5M",
            "--f-stop",
            "40M",
            "--points",
            "201",
            "--output",
            str(tmp_path / "mux.s4p"),
            "--sensitivity",
            "5",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["sensitivity"]["delta_pct"] == 5.0
    assert payload["sensitivity"]["rows"]
