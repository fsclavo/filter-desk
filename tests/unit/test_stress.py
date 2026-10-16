"""Power-stress estimate (Phase 12)."""

from __future__ import annotations

import json
import math

import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.stress import StressError, compute_stress
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.services.session import DesignSession
from filterdesk.synthesis import synthesize


def _spec() -> FilterSpec:
    return FilterSpec(
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


def test_compute_stress_formulas() -> None:
    circuit = synthesize(_spec()).circuit
    report = compute_stress(circuit, power_w=100.0, frequency_hz=100e6)
    i0 = math.sqrt(100.0 / 50.0)  # 1.414 A
    v0 = math.sqrt(100.0 * 50.0)  # 70.71 V
    by_ref = {e.ref: e for e in report.entries}
    # Series element: Vpk = sqrt(2)*I0*|Z|, Ipk = sqrt(2)*I0.
    series = next(e for e in report.entries if e.role.value == "series")
    assert series.i_peak_a == pytest.approx(math.sqrt(2) * i0)
    assert series.v_peak_v == pytest.approx(
        math.sqrt(2) * i0 * abs(series.impedance_ohm)
    )
    # Shunt element: Vpk = sqrt(2)*V0.
    shunt = next(e for e in report.entries if e.role.value == "shunt")
    assert shunt.v_peak_v == pytest.approx(math.sqrt(2) * v0)
    assert report.max_v_peak_v >= series.v_peak_v
    assert report.worst_voltage_ref in by_ref
    assert report.worst_current_ref in by_ref


def test_compute_stress_validation() -> None:
    circuit = synthesize(_spec()).circuit
    with pytest.raises(StressError):
        compute_stress(circuit, power_w=0.0, frequency_hz=100e6)
    with pytest.raises(StressError):
        compute_stress(circuit, power_w=100.0, frequency_hz=0.0)


def test_session_stress_none_when_power_off() -> None:
    session = DesignSession()
    session.set_spec(_spec())
    session.synthesize()
    assert session.compute_stress() is None
    session.power_w = 100.0
    report = session.compute_stress()
    assert report is not None
    assert report.frequency_hz == pytest.approx(100e6)


def test_stress_with_finite_q() -> None:
    from filterdesk.components_std import nonidealize_circuit

    circuit = nonidealize_circuit(
        synthesize(_spec()).circuit, inductor_q=100.0, q_frequency_hz=100e6
    )
    report = compute_stress(circuit, power_w=100.0, frequency_hz=100e6)
    assert len(report.entries) == 5
    assert all(e.v_peak_v > 0.0 and e.i_peak_a > 0.0 for e in report.entries)


def test_cli_analyze_power(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "analyze",
            "--family",
            "chebyshev_type_i",
            "--response",
            "low_pass",
            "--order",
            "5",
            "--cutoff",
            "7.5M",
            "--ripple",
            "0.1",
            "--points",
            "64",
            "--power",
            "100",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Power stress" in out and "Vpk=" in out


def test_cli_analyze_power_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "analyze",
            "--family",
            "chebyshev_type_i",
            "--response",
            "low_pass",
            "--order",
            "5",
            "--cutoff",
            "7.5M",
            "--ripple",
            "0.1",
            "--points",
            "64",
            "--power",
            "100",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stress"]["power_w"] == 100.0
    assert len(payload["stress"]["elements"]) == 5
