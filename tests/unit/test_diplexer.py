"""LPF+HPF diplexer service and CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import ApproximationFamily, FilterResponse
from filterdesk.io.touchstone import read_sparameters
from filterdesk.services.diplexer import (
    DiplexerConfig,
    DiplexerError,
    design_diplexer,
)


def _config(**overrides: object) -> DiplexerConfig:
    values: dict[str, object] = {
        "low_cutoff_hz": 30e6,
        "high_cutoff_hz": 40e6,
        "order": 5,
        "family": ApproximationFamily.CHEBYSHEV_TYPE_I,
        "ripple_db": 0.1,
    }
    values.update(overrides)
    return DiplexerConfig(**values)  # type: ignore[arg-type]


def _sweep() -> SweepConfig:
    return SweepConfig(1e6, 200e6, 2001, SweepSpacing.LOGARITHMIC)


def test_diplexer_routes_low_and_high_bands() -> None:
    design = design_diplexer(_config(), _sweep())
    metrics = design.metrics
    assert design.network.n_ports == 3
    assert design.low_spec.response is FilterResponse.LOW_PASS
    assert design.high_spec.response is FilterResponse.HIGH_PASS
    assert metrics.low_insertion_loss_db is not None
    assert metrics.high_insertion_loss_db is not None
    assert metrics.low_insertion_loss_db > -0.5
    assert metrics.high_insertion_loss_db > -0.5
    assert metrics.low_out_of_band_db is not None
    assert metrics.high_out_of_band_db is not None
    assert metrics.low_out_of_band_db < -15.0
    assert metrics.high_out_of_band_db < -15.0
    assert metrics.crossover_hz is not None
    assert 30e6 < metrics.crossover_hz < 40e6
    assert "Low path" in metrics.summary()


def test_diplexer_validation_and_family_rules() -> None:
    with pytest.raises(DiplexerError, match="above"):
        _config(high_cutoff_hz=20e6)
    with pytest.raises(DiplexerError, match="cutoff"):
        _config(low_cutoff_hz=0.0)
    with pytest.raises(DiplexerError, match="stopband"):
        design_diplexer(
            _config(family=ApproximationFamily.CHEBYSHEV_TYPE_II), _sweep()
        )


def test_diplexer_supports_chebyshev_ii() -> None:
    design = design_diplexer(
        _config(
            family=ApproximationFamily.CHEBYSHEV_TYPE_II,
            stopband_attenuation_db=40.0,
        ),
        _sweep(),
    )
    assert design.network.n_ports == 3
    assert design.metrics.low_insertion_loss_db is not None
    assert design.metrics.high_insertion_loss_db is not None


def test_cli_diplexer_writes_three_port(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "diplexer.s3p"
    low = tmp_path / "low.s2p"
    high = tmp_path / "high.s2p"
    code = main(
        [
            "diplexer",
            "--low-cutoff",
            "30M",
            "--high-cutoff",
            "40M",
            "--order",
            "5",
            "--ripple",
            "0.1",
            "--f-start",
            "1M",
            "--f-stop",
            "200M",
            "--points",
            "1001",
            "--output",
            str(output),
            "--low-output",
            str(low),
            "--high-output",
            str(high),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["network"]["n_ports"] == 3
    assert payload["metrics"]["crossover_hz"] is not None
    network = read_sparameters(output)
    assert network.n_ports == 3
    assert read_sparameters(low).n_ports == 2
    assert read_sparameters(high).n_ports == 2


def test_cli_diplexer_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "diplexer",
            "--low-cutoff",
            "40M",
            "--high-cutoff",
            "30M",
            "--output",
            str(tmp_path / "bad.s3p"),
        ]
    )
    assert code == 2
    assert "error:" in capsys.readouterr().err
