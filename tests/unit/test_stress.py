"""Power-stress estimate (Phase 12)."""

from __future__ import annotations

import json
import math

import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.stress import (
    StressError,
    compute_stress,
    compute_stress_sweep,
)
from filterdesk.domain.circuit import Circuit, IdealCapacitor, IdealResistor, Port
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    ElementRole,
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


def test_compute_stress_series_resistor_matches_nodal_reference() -> None:
    circuit = Circuit(
        [IdealResistor("R1", 50.0, "in", "out")],
        Port("P1", "in", 50.0),
        Port("P2", "out", 50.0),
    )
    report = compute_stress(circuit, power_w=100.0, frequency_hz=1e6)
    # Source available power 100 W, Rs=50, R=50, load=50.
    source_rms = math.sqrt(4.0 * 100.0 * 50.0)
    current_rms = source_rms / (50.0 + 50.0 + 50.0)
    resistor_rms = current_rms * 50.0
    entry = report.entries[0]
    assert entry.i_peak_a == pytest.approx(math.sqrt(2.0) * current_rms)
    assert entry.v_peak_v == pytest.approx(math.sqrt(2.0) * resistor_rms)
    assert report.max_v_peak_v == pytest.approx(entry.v_peak_v)
    assert report.max_i_peak_a == pytest.approx(entry.i_peak_a)


def test_bpf_stress_at_center_is_not_constant_arm_current() -> None:
    from filterdesk.services.bands import BandKind, band_preset_spec, find_band

    spec = band_preset_spec(find_band("40m"), BandKind.BPF)
    circuit = synthesize(spec).circuit
    report = compute_stress(
        circuit, power_w=100.0, frequency_hz=float(spec.f_center_hz)
    )
    # At resonance the series LC arms are nearly shorts and the parallel tanks
    # are nearly opens; the exact nodal values are close to 100 Vpk / 2 A.
    assert report.max_v_peak_v == pytest.approx(100.0, abs=0.5)
    assert report.max_i_peak_a == pytest.approx(2.0, abs=0.01)
    assert all(math.isfinite(e.v_peak_v) for e in report.entries)
    assert all(math.isfinite(e.i_peak_a) for e in report.entries)


def test_stress_sweep_reports_worst_voltage_and_current_points() -> None:
    circuit = Circuit(
        [
            IdealResistor("R1", 50.0, "in", "out"),
            IdealCapacitor("C1", 1e-9, "out", "gnd", ElementRole.SHUNT),
        ],
        Port("P1", "in", 50.0),
        Port("P2", "out", 50.0),
        ground="gnd",
    )
    report = compute_stress_sweep(
        circuit,
        power_w=100.0,
        frequencies_hz=(1e3, 1e6, 1e9),
        reference_hz=1e6,
    )
    assert report.is_sweep
    assert report.points == 3
    assert report.sweep_start_hz == pytest.approx(1e3)
    assert report.sweep_stop_hz == pytest.approx(1e9)
    assert report.frequency_hz == pytest.approx(1e6)
    by_ref = {entry.ref: entry for entry in report.entries}
    capacitor = by_ref["C1"]
    assert capacitor.voltage_frequency_hz == pytest.approx(1e3)
    assert capacitor.current_frequency_hz == pytest.approx(1e9)
    assert capacitor.v_peak_v == pytest.approx(66.667, abs=0.1)
    assert capacitor.i_peak_a == pytest.approx(2.0, abs=0.01)


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
    session.analyze()
    assert session.compute_stress() is None
    session.power_w = 100.0
    report = session.compute_stress()
    assert report is not None
    assert report.frequency_hz == pytest.approx(100e6)
    assert report.is_sweep
    assert 2 <= report.points <= 26


def test_stress_supports_distributed_and_output_transformer() -> None:
    from dataclasses import replace

    from filterdesk.synthesis.distributed import design_distributed_lowpass

    design = design_distributed_lowpass(replace(_spec(), order=3), "FR4")
    report = compute_stress(design.circuit, power_w=100.0, frequency_hz=100e6)
    assert len(report.entries) == len(design.circuit.elements)
    assert all(math.isfinite(e.v_peak_v) for e in report.entries)
    assert all(math.isfinite(e.i_peak_a) for e in report.entries)

    with_t1 = replace(synthesize(_spec()).circuit, output_transformer_ratio=1.5)
    t1_report = compute_stress(with_t1, power_w=100.0, frequency_hz=100e6)
    assert t1_report.entries
    assert all(math.isfinite(e.v_peak_v) for e in t1_report.entries)


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
    assert payload["stress"]["points"] > 1
    assert payload["stress"]["sweep_start_hz"] is not None
    assert len(payload["stress"]["elements"]) == 5
