"""LC TX/RX duplexer service and CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.io.touchstone import read_sparameters
from filterdesk.services.duplexer import (
    DuplexerConfig,
    DuplexerError,
    design_duplexer,
)


def _config(**overrides: object) -> DuplexerConfig:
    values: dict[str, object] = {
        "tx_center_hz": 145e6,
        "tx_bandwidth_hz": 1e6,
        "rx_center_hz": 147e6,
        "rx_bandwidth_hz": 1e6,
        "family": ApproximationFamily.CHEBYSHEV_TYPE_I,
        "ripple_db": 0.1,
        "min_isolation_db": 60.0,
    }
    values.update(overrides)
    return DuplexerConfig(**values)  # type: ignore[arg-type]


def _sweep() -> SweepConfig:
    return SweepConfig(140e6, 152e6, 4001, SweepSpacing.LOGARITHMIC)


def test_duplexer_searches_order_for_isolation() -> None:
    design = design_duplexer(_config(), _sweep())
    assert design.network.n_ports == 3
    assert design.selected_order == 6
    assert design.attempted_orders == (3, 4, 5, 6)
    metrics = design.metrics
    assert metrics.meets_target
    assert metrics.worst_isolation_db is not None
    assert metrics.worst_isolation_db >= 60.0
    assert metrics.tx_insertion_loss_db is not None
    assert metrics.rx_insertion_loss_db is not None
    assert metrics.tx_insertion_loss_db > -0.5
    assert metrics.rx_insertion_loss_db > -0.5
    assert metrics.tx_return_loss_db is not None
    assert metrics.rx_return_loss_db is not None
    assert metrics.tx_return_loss_db > 10.0
    assert metrics.rx_return_loss_db > 10.0
    assert "met" in design.summary()


def test_duplexer_reports_missed_target() -> None:
    design = design_duplexer(
        _config(order=3, min_isolation_db=200.0), _sweep()
    )
    assert design.selected_order == 3
    assert not design.metrics.meets_target
    assert design.metrics.worst_isolation_db is not None
    assert design.metrics.worst_isolation_db < 200.0
    assert "NOT met" in design.metrics.summary()


def test_duplexer_validation() -> None:
    with pytest.raises(DuplexerError, match="overlap"):
        design_duplexer(
            _config(rx_center_hz=145.5e6, rx_bandwidth_hz=2e6), _sweep()
        )
    with pytest.raises(DuplexerError, match="sweep"):
        design_duplexer(
            _config(), SweepConfig(144e6, 146e6, 101, SweepSpacing.LINEAR)
        )
    with pytest.raises(DuplexerError, match="max_order"):
        _config(min_order=7, max_order=3)


def test_cli_duplexer_writes_three_port(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "duplexer.s3p"
    tx = tmp_path / "tx.s2p"
    rx = tmp_path / "rx.s2p"
    code = main(
        [
            "duplexer",
            "--tx-center",
            "145M",
            "--tx-bw",
            "1M",
            "--rx-center",
            "147M",
            "--rx-bw",
            "1M",
            "--min-isolation",
            "60",
            "--f-start",
            "140M",
            "--f-stop",
            "152M",
            "--points",
            "2001",
            "--output",
            str(output),
            "--tx-output",
            str(tx),
            "--rx-output",
            str(rx),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["network"]["n_ports"] == 3
    assert payload["selected_order"] == 6
    assert payload["attempted_orders"] == [3, 4, 5, 6]
    assert payload["metrics"]["meets_target"] is True
    assert payload["metrics"]["worst_isolation_db"] >= 60.0
    assert read_sparameters(output).n_ports == 3
    assert read_sparameters(tx).n_ports == 2
    assert read_sparameters(rx).n_ports == 2


def test_cli_duplexer_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "duplexer",
            "--tx-center",
            "145M",
            "--tx-bw",
            "4M",
            "--rx-center",
            "145.5M",
            "--rx-bw",
            "4M",
            "--output",
            str(tmp_path / "bad.s3p"),
        ]
    )
    assert code == 2
    assert "error:" in capsys.readouterr().err
