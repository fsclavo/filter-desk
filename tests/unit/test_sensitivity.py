"""Component sensitivity analysis."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.sensitivity import SensitivityError, sensitivity
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.circuit import Circuit, IdealInductor, Port
from filterdesk.domain.enums import ElementRole
from filterdesk.domain.overlays import LimitMetric, LimitRegion
from filterdesk.optimization.variables import tunable_params
from filterdesk.services.session import DesignSession


def test_sensitivity_ranks_and_preserves_circuit() -> None:
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.circuit is not None and session.sweep is not None
    before = [el for el in session.circuit.elements]
    report = sensitivity(session.circuit, session.sweep, relative_step_pct=0.5)

    assert len(report.rows) == len(tunable_params(session.circuit))
    assert [r.max_abs_db_per_pct for r in report.rows] == sorted(
        (r.max_abs_db_per_pct for r in report.rows), reverse=True
    )
    for row in report.rows:
        assert row.max_abs_db_per_pct > 0.0
        assert row.rms_db_per_pct >= 0.0
        assert report.frequency_hz[0] <= row.worst_frequency_hz
        assert row.worst_frequency_hz <= report.frequency_hz[-1]
        assert row.limit_margin_delta is None
        assert row.direction == 0
    # No mutation of the analysed circuit values.
    assert [el for el in session.circuit.elements] == before


def test_sensitivity_matches_analytic_series_inductor() -> None:
    inductance = 1e-6
    z0 = 50.0
    circuit = Circuit(
        elements=[
            IdealInductor(
                id="L1",
                value_h=inductance,
                node_a="in",
                node_b="out",
                role=ElementRole.SERIES,
            )
        ],
        port_in=Port("in", "in", z0),
        port_out=Port("out", "out", z0),
    )
    sweep = SweepConfig(1e6, 10e6, 128, SweepSpacing.LINEAR)
    report = sensitivity(circuit, sweep, relative_step_pct=0.01)
    row = report.rows[0]

    frequency = np.asarray(report.frequency_hz, dtype=float)
    omega = 2.0 * math.pi * frequency
    a = 2.0 * z0
    # d(|S21| dB)/dL * L * 0.01  (slope per +1 % of L)
    analytic = (
        -10.0
        / math.log(10.0)
        * (2.0 * omega**2 * inductance)
        / (a**2 + (omega * inductance) ** 2)
        * inductance
        * 0.01
    )
    magnitudes = np.abs(analytic)
    assert row.max_abs_db_per_pct == pytest.approx(
        float(np.max(magnitudes)), rel=1e-3
    )
    assert row.worst_frequency_hz == pytest.approx(
        float(frequency[int(np.argmax(magnitudes))])
    )


def test_sensitivity_with_limits_reports_direction() -> None:
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.circuit is not None and session.sweep is not None
    strict = LimitRegion(
        id="L1",
        metric=LimitMetric.S11_DB,
        f_low_hz=140e6,
        f_high_hz=200e6,
        y_max=-30.0,
    )
    report = sensitivity(
        session.circuit, session.sweep, limits=[strict], relative_step_pct=1.0
    )
    assert report.rows
    assert all(row.limit_margin_delta is not None for row in report.rows)
    assert any(row.direction != 0 for row in report.rows)


def test_sensitivity_band_restricts_worst_frequency() -> None:
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.circuit is not None and session.sweep is not None
    low, high = 130e6, 150e6
    report = sensitivity(session.circuit, session.sweep, band=(low, high))
    assert report.band == (low, high)
    for row in report.rows:
        assert low <= row.worst_frequency_hz <= high


def test_sensitivity_validation() -> None:
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.circuit is not None and session.sweep is not None
    with pytest.raises(SensitivityError):
        sensitivity(session.circuit, session.sweep, relative_step_pct=0.0)
    with pytest.raises(SensitivityError):
        sensitivity(session.circuit, session.sweep, band=(3e6, 1e6))


def test_cli_sensitivity(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "sensitivity",
            "--family",
            "chebyshev_type_i",
            "--response",
            "high_pass",
            "--order",
            "5",
            "--cutoff",
            "100M",
            "--ripple",
            "0.1",
            "--points",
            "128",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Component sensitivity" in out


def test_cli_sensitivity_json(
    capsys: pytest.CaptureFixture[str], tmp_path
) -> None:
    limits = tmp_path / "limits.json"
    limits.write_text(
        json.dumps(
            [
                {
                    "id": "pb",
                    "metric": "s21_db",
                    "f_low_hz": 100e6,
                    "f_high_hz": 200e6,
                    "y_min": 1.0,
                }
            ]
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "sensitivity",
            "--family",
            "chebyshev_type_i",
            "--response",
            "high_pass",
            "--order",
            "5",
            "--cutoff",
            "100M",
            "--ripple",
            "0.1",
            "--points",
            "128",
            "--limits",
            str(limits),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backend"] == "abcd"
    assert payload["components"]
    assert payload["components"][0]["limit_margin_delta"] is not None
