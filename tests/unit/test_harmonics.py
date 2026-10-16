"""Transmit harmonic readout (Phase 12)."""

from __future__ import annotations

import json

import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.harmonics import HarmonicError, compute_harmonics
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.synthesis import synthesize


def _result():  # type: ignore[no-untyped-def]
    spec = FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.LOW_PASS,
        order=5,
        cutoff_hz=100e6,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.1,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
    )
    circuit = synthesize(spec).circuit
    sweep = SweepConfig(1e6, 1e9, 4001, SweepSpacing.LOGARITHMIC)
    return analyze_circuit(circuit, sweep)


def test_compute_harmonics_lowpass() -> None:
    report = compute_harmonics(_result(), 50e6, max_order=5)
    assert report.fundamental_hz == pytest.approx(50e6)
    assert report.fundamental_s21_db == pytest.approx(0.0, abs=0.2)
    orders = [h.order for h in report.harmonics]
    assert orders == [2, 3, 4, 5]
    # A low-pass attenuates higher harmonics more.
    suppressions = [h.suppression_db for h in report.harmonics]
    assert suppressions == sorted(suppressions)
    assert report.min_suppression_db == pytest.approx(suppressions[0])
    assert report.worst_order == 2


def test_compute_harmonics_validation() -> None:
    with pytest.raises(HarmonicError):
        compute_harmonics(_result(), 0.0)
    with pytest.raises(HarmonicError):
        compute_harmonics(_result(), 50e6, max_order=1)


def test_cli_harmonics(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "analyze",
            "--band",
            "40m",
            "--points",
            "256",
            "--f-start",
            "3M",
            "--f-stop",
            "40M",
            "--harmonics-f0",
            "7.1M",
        ]
    )
    assert code == 0
    assert "Harmonics" in capsys.readouterr().out


def test_cli_harmonics_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "analyze",
            "--band",
            "40m",
            "--points",
            "256",
            "--f-start",
            "3M",
            "--f-stop",
            "40M",
            "--harmonics-f0",
            "7.1M",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["harmonics"]["fundamental_hz"] == pytest.approx(7.1e6)
    assert len(payload["harmonics"]["harmonics"]) >= 2
