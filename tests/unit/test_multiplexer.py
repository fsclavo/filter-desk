"""Multi-band BPF multiplexer service and CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.io.touchstone import read_sparameters
from filterdesk.services.multiplexer import (
    MultiplexerBand,
    MultiplexerConfig,
    MultiplexerError,
    design_multiplexer,
)


def _bands() -> tuple[MultiplexerBand, ...]:
    return (
        MultiplexerBand("low", 14e6, 0.3e6),
        MultiplexerBand("mid", 21e6, 0.5e6),
        MultiplexerBand("high", 28e6, 0.5e6),
    )


def _config(**overrides: object) -> MultiplexerConfig:
    values: dict[str, object] = {
        "bands": _bands(),
        "order": 5,
        "family": ApproximationFamily.CHEBYSHEV_TYPE_I,
        "ripple_db": 0.1,
    }
    values.update(overrides)
    return MultiplexerConfig(**values)  # type: ignore[arg-type]


def _sweep() -> SweepConfig:
    return SweepConfig(5e6, 40e6, 4001, SweepSpacing.LOGARITHMIC)


def test_multiplexer_routes_three_bands() -> None:
    design = design_multiplexer(_config(), _sweep())
    assert design.network.n_ports == 4
    assert [band.label for band in design.bands] == ["low", "mid", "high"]
    assert len(design.metrics.bands) == 3
    for metrics in design.metrics.bands:
        assert metrics.insertion_loss_db is not None
        assert metrics.out_of_band_db is not None
        assert metrics.return_loss_db is not None
        assert metrics.insertion_loss_db > -0.5
        assert metrics.out_of_band_db < -60.0
        assert metrics.return_loss_db > 10.0
    assert len(design.metrics.crossovers_hz) == 2
    assert all(value is not None for value in design.metrics.crossovers_hz)
    assert design.analysis_for("mid") is not None
    assert design.analysis_for("missing") is None
    assert "crossovers" in design.summary()


def test_multiplexer_sorts_bands_by_frequency() -> None:
    config = _config(bands=tuple(reversed(_bands())))
    design = design_multiplexer(config, _sweep())
    assert [band.label for band in design.bands] == ["low", "mid", "high"]
    assert design.network.n_ports == 4


def test_multiplexer_validation() -> None:
    with pytest.raises(MultiplexerError, match="two bands"):
        MultiplexerConfig((MultiplexerBand("only", 14e6, 1e6),))
    with pytest.raises(MultiplexerError, match="unique"):
        MultiplexerConfig(
            (
                MultiplexerBand("same", 14e6, 1e6),
                MultiplexerBand("same", 21e6, 1e6),
            )
        )
    with pytest.raises(MultiplexerError, match="overlap"):
        design_multiplexer(
            _config(
                bands=(
                    MultiplexerBand("low", 14e6, 3e6),
                    MultiplexerBand("mid", 15e6, 3e6),
                    MultiplexerBand("high", 28e6, 0.5e6),
                )
            ),
            _sweep(),
        )
    with pytest.raises(MultiplexerError, match="sweep"):
        design_multiplexer(
            _config(), SweepConfig(13e6, 15e6, 101, SweepSpacing.LINEAR)
        )


def test_cli_triplexer_writes_four_port(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "triplexer.s4p"
    low = tmp_path / "low.s2p"
    mid = tmp_path / "mid.s2p"
    high = tmp_path / "high.s2p"
    bom = tmp_path / "triplexer_bom.md"
    code = main(
        [
            "triplexer",
            "--low-center",
            "14M",
            "--low-bw",
            "300k",
            "--mid-center",
            "21M",
            "--mid-bw",
            "500k",
            "--high-center",
            "28M",
            "--high-bw",
            "500k",
            "--order",
            "5",
            "--ripple",
            "0.1",
            "--f-start",
            "5M",
            "--f-stop",
            "40M",
            "--points",
            "1001",
            "--output",
            str(output),
            "--low-output",
            str(low),
            "--mid-output",
            str(mid),
            "--high-output",
            str(high),
            "--export-build-sheet",
            str(bom),
            "--bom-series",
            "E24",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["network"]["n_ports"] == 4
    assert [band["label"] for band in payload["bands"]] == ["low", "mid", "high"]
    assert len(payload["crossovers_hz"]) == 2
    assert read_sparameters(output).n_ports == 4
    assert read_sparameters(low).n_ports == 2
    assert read_sparameters(mid).n_ports == 2
    assert read_sparameters(high).n_ports == 2
    bom_text = bom.read_text(encoding="utf-8")
    assert "# 3-band BPF multiplexer" in bom_text
    assert "| Low |" in bom_text and "| Mid |" in bom_text and "| High |" in bom_text
    assert "Component values snapped to E24" in bom_text


def test_cli_multiplexer_handles_four_bands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "quad.s5p"
    bom = tmp_path / "quad_bom.md"
    code = main(
        [
            "multiplexer",
            "--band",
            "low:14M:300k",
            "--band",
            "mid:21M:500k",
            "--band",
            "high:28M:500k",
            "--band",
            "top:35M:500k",
            "--order",
            "5",
            "--ripple",
            "0.1",
            "--f-start",
            "5M",
            "--f-stop",
            "50M",
            "--points",
            "801",
            "--output",
            str(output),
            "--branch-output",
            f"low={tmp_path / 'low.s2p'}",
            "--export-build-sheet",
            str(bom),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["network"]["n_ports"] == 5
    assert [band["label"] for band in payload["bands"]] == [
        "low",
        "mid",
        "high",
        "top",
    ]
    assert read_sparameters(output).n_ports == 5
    assert read_sparameters(tmp_path / "low.s2p").n_ports == 2
    assert "| Top |" in bom.read_text(encoding="utf-8")


def test_cli_multiplexer_rejects_bad_band(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "multiplexer",
            "--band",
            "bad-spec",
            "--output",
            str(tmp_path / "bad.s2p"),
        ]
    )
    assert code == 2
    assert "error:" in capsys.readouterr().err
