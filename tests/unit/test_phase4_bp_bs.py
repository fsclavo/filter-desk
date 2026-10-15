"""Phase 4 BP/BS and asymmetric-Z synthesis/analysis tests."""

from __future__ import annotations

import math

import numpy as np
import pytest

from filterdesk.analysis import (
    LadderABCDAnalyzer,
    ScikitRFAnalyzer,
    SweepConfig,
    SweepSpacing,
    mag_db,
)
from filterdesk.domain.circuit import IdealParallelLC, IdealSeriesLC
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec, SpecValidationError, validate_spec
from filterdesk.synthesis import synthesize


def _butter_bp(order: int = 3) -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.BUTTERWORTH,
        response=FilterResponse.BAND_PASS,
        order=order,
        f_center_hz=100e6,
        bandwidth_hz=20e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_BP_SERIES_RES_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )


def test_asymmetric_z_accepted() -> None:
    spec = FilterSpec(
        family=ApproximationFamily.BUTTERWORTH,
        response=FilterResponse.LOW_PASS,
        order=3,
        cutoff_hz=1e6,
        z_source_ohm=50.0,
        z_load_ohm=75.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )
    validate_spec(spec)
    result = synthesize(spec)
    assert result.circuit.port_in.impedance_ohm == 50.0
    assert result.circuit.port_out.impedance_ohm == 75.0
    assert abs(float(result.circuit.meta["z0_scale_ohm"]) - math.sqrt(50 * 75)) < 1e-9


def test_asymmetric_lp_passband_near_0db() -> None:
    spec = FilterSpec(
        family=ApproximationFamily.BUTTERWORTH,
        response=FilterResponse.LOW_PASS,
        order=3,
        cutoff_hz=1e6,
        z_source_ohm=50.0,
        z_load_ohm=75.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )
    circuit = synthesize(spec).circuit
    sweep = SweepConfig(1e4, 1e5, 101, SweepSpacing.LOGARITHMIC)
    result = LadderABCDAnalyzer().analyze(circuit, sweep)
    # Deep in passband — insertion loss should be small (not a perfect match).
    assert float(mag_db(result.s21).max()) > -0.5
    assert float(mag_db(result.s21).max()) < 0.05


def test_bandpass_resonators_and_center() -> None:
    spec = _butter_bp(3)
    result = synthesize(spec)
    assert len(result.circuit.elements) == 3
    assert isinstance(result.circuit.elements[0], IdealSeriesLC)
    assert isinstance(result.circuit.elements[1], IdealParallelLC)
    assert isinstance(result.circuit.elements[2], IdealSeriesLC)

    f0 = 100e6
    sweep = SweepConfig(f0 / 5, f0 * 5, 2001, SweepSpacing.LOGARITHMIC)
    analysis = LadderABCDAnalyzer().analyze(result.circuit, sweep)
    i = int(np.argmin(np.abs(analysis.frequency_hz - f0)))
    s21_db = float(mag_db(analysis.s21)[i])
    assert abs(s21_db) < 0.05

    # Rough -3 dB bandwidth check near geometric edges.
    f_high = 0.5 * (20e6 + math.sqrt((20e6) ** 2 + 4 * f0 * f0))
    f_low = f0 * f0 / f_high
    for edge in (f_low, f_high):
        j = int(np.argmin(np.abs(analysis.frequency_hz - edge)))
        assert abs(float(mag_db(analysis.s21)[j]) - (-3.01)) < 0.15


def test_bandpass_abcd_matches_skrf() -> None:
    spec = _butter_bp(3)
    circuit = synthesize(spec).circuit
    f0 = 100e6
    sweep = SweepConfig(f0 / 4, f0 * 4, 257, SweepSpacing.LOGARITHMIC)
    a = LadderABCDAnalyzer().analyze(circuit, sweep)
    b = ScikitRFAnalyzer().analyze(circuit, sweep)
    assert np.max(np.abs(a.s21 - b.s21)) < 1e-10


def test_bandstop_notch_at_center() -> None:
    spec = FilterSpec(
        family=ApproximationFamily.BUTTERWORTH,
        response=FilterResponse.BAND_STOP,
        order=3,
        f_center_hz=100e6,
        bandwidth_hz=20e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_BS_SERIES_TANK_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )
    circuit = synthesize(spec).circuit
    assert isinstance(circuit.elements[0], IdealParallelLC)
    assert isinstance(circuit.elements[1], IdealSeriesLC)

    f0 = 100e6
    sweep = SweepConfig(f0 / 10, f0 * 10, 2001, SweepSpacing.LOGARITHMIC)
    analysis = LadderABCDAnalyzer().analyze(circuit, sweep)
    i = int(np.argmin(np.abs(analysis.frequency_hz - f0)))
    assert float(mag_db(analysis.s21)[i]) < -40.0
    # Far from notch — near pass.
    for f in (f0 / 5, f0 * 5):
        j = int(np.argmin(np.abs(analysis.frequency_hz - f)))
        assert float(mag_db(analysis.s21)[j]) > -0.5


def test_bp_dual_topology_same_s21() -> None:
    base = dict(
        family=ApproximationFamily.BUTTERWORTH,
        response=FilterResponse.BAND_PASS,
        order=3,
        f_center_hz=50e6,
        bandwidth_hz=10e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )
    a = synthesize(
        FilterSpec(**base, topology_id=TopologyId.LADDER_BP_SERIES_RES_INPUT)
    ).circuit
    b = synthesize(
        FilterSpec(**base, topology_id=TopologyId.LADDER_BP_SHUNT_RES_INPUT)
    ).circuit
    sweep = SweepConfig(10e6, 200e6, 513, SweepSpacing.LOGARITHMIC)
    sa = LadderABCDAnalyzer().analyze(a, sweep)
    sb = LadderABCDAnalyzer().analyze(b, sweep)
    assert np.max(np.abs(mag_db(sa.s21) - mag_db(sb.s21))) < 1e-9


def test_cheby_bp_ripple_at_geometric_edge() -> None:
    f0 = 100e6
    bw = 20e6
    spec = FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.BAND_PASS,
        order=5,
        f_center_hz=f0,
        bandwidth_hz=bw,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_BP_SERIES_RES_INPUT,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.1,
    )
    circuit = synthesize(spec).circuit
    f_high = 0.5 * (bw + math.sqrt(bw * bw + 4 * f0 * f0))
    f_low = f0 * f0 / f_high
    sweep = SweepConfig(f_low / 2, f_high * 2, 4001, SweepSpacing.LOGARITHMIC)
    analysis = LadderABCDAnalyzer().analyze(circuit, sweep)
    for edge in (f_low, f_high):
        j = int(np.argmin(np.abs(analysis.frequency_hz - edge)))
        assert abs(float(mag_db(analysis.s21)[j]) - (-0.1)) < 0.02


def test_bp_rejects_cutoff_only() -> None:
    with pytest.raises(SpecValidationError):
        validate_spec(
            FilterSpec(
                family=ApproximationFamily.BUTTERWORTH,
                response=FilterResponse.BAND_PASS,
                order=3,
                cutoff_hz=100e6,
                z_source_ohm=50.0,
                z_load_ohm=50.0,
                topology_id=TopologyId.LADDER_BP_SERIES_RES_INPUT,
                cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
            )
        )
