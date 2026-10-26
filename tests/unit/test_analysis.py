"""Analysis engine unit and golden tests."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from filterdesk.analysis import (
    LadderABCDAnalyzer,
    ScikitRFAnalyzer,
    SweepConfig,
    SweepSpacing,
    mag_db,
)
from filterdesk.analysis.derived import group_delay_s, vswr
from filterdesk.domain.specs import filter_spec_from_mapping
from filterdesk.io.touchstone import write_touchstone_s2p
from filterdesk.synthesis import synthesize

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "golden"


def test_butterworth_lp_minus_3db_at_cutoff() -> None:
    folder = GOLDEN / "butterworth_lp_n5_1mhz_50ohm"
    spec = filter_spec_from_mapping(json.loads((folder / "spec.json").read_text()))
    circuit = synthesize(spec).circuit
    sweep = SweepConfig(1e5, 1e7, 2001, SweepSpacing.LOGARITHMIC)
    result = LadderABCDAnalyzer().analyze(circuit, sweep)
    i = int(np.argmin(np.abs(result.frequency_hz - 1e6)))
    s21_db = float(mag_db(result.s21)[i])
    assert abs(s21_db - (-3.0102999566398116)) < 0.01


def test_cheby_hp_ripple_edge() -> None:
    folder = GOLDEN / "cheby1_hp_n7_0p01db_140mhz_50ohm"
    spec = filter_spec_from_mapping(json.loads((folder / "spec.json").read_text()))
    circuit = synthesize(spec).circuit
    fc = 140e6
    sweep = SweepConfig(fc / 20, fc * 20, 4001, SweepSpacing.LOGARITHMIC)
    result = LadderABCDAnalyzer().analyze(circuit, sweep)
    i = int(np.argmin(np.abs(result.frequency_hz - fc)))
    s21_db = float(mag_db(result.s21)[i])
    assert abs(s21_db - (-0.01)) < 0.001
    # Passband above fc stays within ripple corridor (odd order: 0 to -Ap)
    mask = result.frequency_hz >= fc
    pb = mag_db(result.s21)[mask]
    assert float(pb.min()) >= -0.01 - 0.002
    assert float(pb.max()) <= 0.002


def test_abcd_matches_skrf_milestone() -> None:
    folder = GOLDEN / "cheby1_hp_n7_0p01db_140mhz_50ohm"
    spec = filter_spec_from_mapping(json.loads((folder / "spec.json").read_text()))
    circuit = synthesize(spec).circuit
    fc = 140e6
    sweep = SweepConfig(fc / 10, fc * 10, 513, SweepSpacing.LOGARITHMIC)
    a = LadderABCDAnalyzer().analyze(circuit, sweep)
    b = ScikitRFAnalyzer().analyze(circuit, sweep)
    assert np.max(np.abs(a.s21 - b.s21)) < 1e-12
    assert np.max(np.abs(a.s11 - b.s11)) < 1e-12


def test_skrf_supports_unequal_ports() -> None:
    spec = filter_spec_from_mapping(
        {
            "family": "butterworth",
            "response": "low_pass",
            "order": 5,
            "cutoff_hz": 100e6,
            "cutoff_definition": "half_power_3db",
            "z_source_ohm": 50.0,
            "z_load_ohm": 75.0,
            "topology_id": "ladder_lp_series_l_input",
        }
    )
    circuit = synthesize(spec).circuit
    sweep = SweepConfig(1e6, 1e9, 257, SweepSpacing.LOGARITHMIC)
    a = LadderABCDAnalyzer().analyze(circuit, sweep)
    b = ScikitRFAnalyzer().analyze(circuit, sweep)
    assert np.max(np.abs(a.s21 - b.s21)) < 1e-9
    assert np.max(np.abs(a.s11 - b.s11)) < 1e-9
    assert np.max(np.abs(a.s22 - b.s22)) < 1e-9
    assert np.max(np.abs(a.zin_ohm - b.zin_ohm)) < 1e-6


@pytest.mark.parametrize(
    "case",
    [
        "cheby1_bp_n4_100m_bw20m",
        "cheby1_bs_n5_100m_bw20m",
        "butterworth_lp_n3_50_to_75_100mhz",
        "cheby1_lp_n4_0p1db_100mhz_50ohm",
    ],
)
def test_abcd_matches_skrf_band(case: str) -> None:
    folder = GOLDEN / case
    spec = filter_spec_from_mapping(json.loads((folder / "spec.json").read_text()))
    circuit = synthesize(spec).circuit
    sweep = SweepConfig(1e6, 2e9, 257, SweepSpacing.LOGARITHMIC)
    a = LadderABCDAnalyzer().analyze(circuit, sweep)
    b = ScikitRFAnalyzer().analyze(circuit, sweep)
    for sp in ("s11", "s21", "s12", "s22"):
        assert np.max(np.abs(getattr(a, sp) - getattr(b, sp))) < 1e-6


def test_abcd_matches_skrf_nonideal() -> None:
    from filterdesk.components_std import nonidealize_circuit

    spec = filter_spec_from_mapping(
        {
            "family": "butterworth",
            "response": "low_pass",
            "order": 5,
            "cutoff_hz": 100e6,
            "cutoff_definition": "half_power_3db",
            "z_source_ohm": 50.0,
            "z_load_ohm": 50.0,
            "topology_id": "ladder_lp_series_l_input",
        }
    )
    circuit = nonidealize_circuit(
        synthesize(spec).circuit,
        inductor_q=100.0,
        q_frequency_hz=100e6,
        inductor_parallel_capacitance_f=0.2e-12,
        capacitor_esr_ohm=0.1,
        capacitor_esl_h=0.5e-9,
    )
    sweep = SweepConfig(1e6, 1e9, 257, SweepSpacing.LOGARITHMIC)
    a = LadderABCDAnalyzer().analyze(circuit, sweep)
    b = ScikitRFAnalyzer().analyze(circuit, sweep)
    for sp in ("s11", "s21", "s12", "s22"):
        assert np.max(np.abs(getattr(a, sp) - getattr(b, sp))) < 1e-6


@pytest.mark.parametrize(
    "case",
    [
        "cheby1_hp_n7_0p01db_140mhz_50ohm",
        "butterworth_lp_n5_1mhz_50ohm",
        "cheby1_bp_n4_100m_bw20m",
        "cheby1_bs_n5_100m_bw20m",
        "butterworth_lp_n3_50_to_75_100mhz",
        "cheby1_lp_n4_0p1db_100mhz_50ohm",
    ],
)
def test_golden_metric_checkpoints(case: str) -> None:
    folder = GOLDEN / case
    metrics = json.loads((folder / "expected_metrics.json").read_text())
    assert metrics["status"] == "phase_2"
    spec = filter_spec_from_mapping(json.loads((folder / "spec.json").read_text()))
    circuit = synthesize(spec).circuit
    sw = metrics["sweep"]
    sweep = SweepConfig(
        f_start_hz=float(sw["f_start_hz"]),
        f_stop_hz=float(sw["f_stop_hz"]),
        n_points=int(sw["n_points"]),
        spacing=SweepSpacing(sw["spacing"]),
    )
    result = LadderABCDAnalyzer().analyze(circuit, sweep)
    tol = float(metrics["tolerances"]["s21_db_abs"])
    for cp in metrics["checkpoints"]:
        i = int(np.argmin(np.abs(result.frequency_hz - float(cp["frequency_hz"]))))
        got = float(mag_db(result.s21)[i])
        assert abs(got - float(cp["s21_db"])) <= tol


def test_group_delay_and_vswr_finite() -> None:
    folder = GOLDEN / "butterworth_lp_n5_1mhz_50ohm"
    spec = filter_spec_from_mapping(json.loads((folder / "spec.json").read_text()))
    circuit = synthesize(spec).circuit
    sweep = SweepConfig(1e5, 1e7, 501, SweepSpacing.LINEAR)
    result = LadderABCDAnalyzer().analyze(circuit, sweep)
    gd = group_delay_s(result.frequency_hz, result.s21)
    vs = vswr(result)
    assert np.all(np.isfinite(gd))
    assert np.all(vs >= 1.0)
    assert math.isfinite(float(vs[0]))


def test_touchstone_s2p_roundtrip_header(tmp_path: Path) -> None:
    folder = GOLDEN / "butterworth_lp_n5_1mhz_50ohm"
    spec = filter_spec_from_mapping(json.loads((folder / "spec.json").read_text()))
    circuit = synthesize(spec).circuit
    sweep = SweepConfig(1e5, 1e7, 11, SweepSpacing.LINEAR)
    result = LadderABCDAnalyzer().analyze(circuit, sweep)
    path = tmp_path / "out.s2p"
    write_touchstone_s2p(result, path)
    text = path.read_text(encoding="utf-8")
    assert "# HZ S RI R 50" in text
    assert len(text.strip().splitlines()) >= 12
