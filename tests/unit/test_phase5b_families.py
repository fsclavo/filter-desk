"""Phase 5b family tests: Cheby II, elliptic, constant-k, m-derived."""

from __future__ import annotations

import numpy as np
from scipy import signal

from filterdesk.analysis.adapters.abcd_ladder import LadderABCDAnalyzer
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.synthesis import synthesize


def _lp_spec(
    family: ApproximationFamily,
    order: int,
    *,
    as_db: float | None = None,
    ap_db: float | None = None,
    m: float | None = None,
    cutoff_hz: float = 1e6,
) -> FilterSpec:
    return FilterSpec(
        family=family,
        response=FilterResponse.LOW_PASS,
        order=order,
        cutoff_hz=cutoff_hz,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
        cutoff_definition=(
            CutoffDefinition.STOPBAND_EDGE
            if family == ApproximationFamily.CHEBYSHEV_TYPE_II
            else (
                CutoffDefinition.RIPPLE_EDGE
                if family == ApproximationFamily.ELLIPTIC
                else CutoffDefinition.HALF_POWER_3DB
            )
        ),
        passband_ripple_db=ap_db,
        stopband_attenuation_db=as_db,
        m_parameter=m,
    )


def test_cheby2_matches_scipy_shape() -> None:
    spec = _lp_spec(
        ApproximationFamily.CHEBYSHEV_TYPE_II,
        5,
        as_db=40.0,
        cutoff_hz=1.0 / (2 * np.pi),
    )
    # cutoff_hz = ωs/(2π) with ωs=1 → fc = 1/(2π)
    result = synthesize(spec)
    assert result.prototype.arms is not None
    assert any(a.kind == "shunt_series_LC" for a in result.prototype.arms)

    sweep = SweepConfig(
        f_start_hz=0.01 / (2 * np.pi),
        f_stop_hz=3.0 / (2 * np.pi),
        n_points=64,
        spacing=SweepSpacing.LOGARITHMIC,
    )
    analysis = LadderABCDAnalyzer().analyze(result.circuit, sweep)
    z, p, k = signal.cheb2ap(5, 40)
    _, href = signal.freqs_zpk(z, p, k, worN=2 * np.pi * analysis.frequency_hz)
    err = np.max(
        np.abs(
            20 * np.log10(np.abs(analysis.s21) + 1e-30)
            - 20 * np.log10(np.abs(href) + 1e-30)
        )
    )
    assert err < 0.15


def test_elliptic_stopband_and_passband() -> None:
    spec = _lp_spec(
        ApproximationFamily.ELLIPTIC,
        5,
        ap_db=0.5,
        as_db=40.0,
        cutoff_hz=1.0 / (2 * np.pi),
    )
    result = synthesize(spec)
    sweep = SweepConfig(
        f_start_hz=0.01 / (2 * np.pi),
        f_stop_hz=3.0 / (2 * np.pi),
        n_points=128,
        spacing=SweepSpacing.LOGARITHMIC,
    )
    analysis = LadderABCDAnalyzer().analyze(result.circuit, sweep)
    z, p, k = signal.ellipap(5, 0.5, 40)
    _, href = signal.freqs_zpk(z, p, k, worN=2 * np.pi * analysis.frequency_hz)
    err = np.max(
        np.abs(
            20 * np.log10(np.abs(analysis.s21) + 1e-30)
            - 20 * np.log10(np.abs(href) + 1e-30)
        )
    )
    assert err < 0.25


def test_cheby2_order7_hp_user_case() -> None:
    """Regression: n=7 As=40 needs positive-element refinement (not exact Cauer)."""
    spec = FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_II,
        response=FilterResponse.HIGH_PASS,
        order=7,
        cutoff_hz=140e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_HP_SERIES_C_INPUT,
        cutoff_definition=CutoffDefinition.STOPBAND_EDGE,
        stopband_attenuation_db=40.0,
    )
    result = synthesize(spec)
    assert len(result.circuit.elements) == 7
    for el in result.circuit.elements:
        if hasattr(el, "value_h"):
            assert el.value_h > 0
        if hasattr(el, "value_f"):
            assert el.value_f > 0


def test_elliptic_order7_smoke() -> None:
    spec = _lp_spec(
        ApproximationFamily.ELLIPTIC,
        7,
        ap_db=0.5,
        as_db=40.0,
        cutoff_hz=1e6,
    )
    result = synthesize(spec)
    assert result.prototype.arms is not None
    assert all(a.is_positive for a in result.prototype.arms)
    spec = FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_II,
        response=FilterResponse.HIGH_PASS,
        order=3,
        cutoff_hz=10e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_HP_SERIES_C_INPUT,
        cutoff_definition=CutoffDefinition.STOPBAND_EDGE,
        stopband_attenuation_db=40.0,
    )
    result = synthesize(spec)
    assert len(result.circuit.elements) >= 3


def test_cheby2_even_order_matches_scipy() -> None:
    spec = _lp_spec(
        ApproximationFamily.CHEBYSHEV_TYPE_II,
        4,
        as_db=40.0,
        cutoff_hz=1.0 / (2 * np.pi),
    )
    result = synthesize(spec)
    assert result.prototype.arms is not None
    sweep = SweepConfig(
        f_start_hz=0.01 / (2 * np.pi),
        f_stop_hz=3.0 / (2 * np.pi),
        n_points=96,
        spacing=SweepSpacing.LOGARITHMIC,
    )
    analysis = LadderABCDAnalyzer().analyze(result.circuit, sweep)
    z, p, k = signal.cheb2ap(4, 40)
    _, href = signal.freqs_zpk(z, p, k, worN=2 * np.pi * analysis.frequency_hz)
    err = np.max(
        np.abs(
            20 * np.log10(np.abs(analysis.s21) + 1e-30)
            - 20 * np.log10(np.abs(href) + 1e-30)
        )
    )
    assert err < 0.6


def test_elliptic_even_order_matches_scipy() -> None:
    spec = _lp_spec(
        ApproximationFamily.ELLIPTIC,
        4,
        ap_db=0.5,
        as_db=40.0,
        cutoff_hz=1.0 / (2 * np.pi),
    )
    result = synthesize(spec)
    sweep = SweepConfig(
        f_start_hz=0.01 / (2 * np.pi),
        f_stop_hz=4.0 / (2 * np.pi),
        n_points=128,
        spacing=SweepSpacing.LOGARITHMIC,
    )
    analysis = LadderABCDAnalyzer().analyze(result.circuit, sweep)
    z, p, k = signal.ellipap(4, 0.5, 40)
    _, href = signal.freqs_zpk(z, p, k, worN=2 * np.pi * analysis.frequency_hz)
    err = float(
        np.max(
            np.abs(
                20 * np.log10(np.abs(analysis.s21) + 1e-30)
                - 20 * np.log10(np.abs(href) + 1e-30)
            )
        )
    )
    assert err < 0.75
    # First finite zero should produce deep notch (≥ As)
    wz = sorted(
        {
            abs(float(np.imag(zz)))
            for zz in z
            if abs(float(np.real(zz))) < 1e-8 and abs(float(np.imag(zz))) > 1e-8
        }
    )[0]
    s21_db = 20 * np.log10(np.abs(analysis.s21) + 1e-30)
    notch = float(
        np.interp(wz / (2 * np.pi), analysis.frequency_hz, s21_db)
    )
    assert notch <= -40.0


def test_cheby2_bp_matches_scipy_shape() -> None:
    """LP→BP of Cheby II Cauer ladder vs scipy.lp2bp_zpk."""
    f0 = 1e6
    bw = 0.2e6
    spec = FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_II,
        response=FilterResponse.BAND_PASS,
        order=5,
        f_center_hz=f0,
        bandwidth_hz=bw,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_BP_SERIES_RES_INPUT,
        cutoff_definition=CutoffDefinition.STOPBAND_EDGE,
        stopband_attenuation_db=40.0,
    )
    result = synthesize(spec)
    assert any(
        type(el).__name__
        in (
            "IdealBruneLC",
            "IdealDualBruneLC",
            "IdealSeriesLC",
            "IdealParallelLC",
        )
        for el in result.circuit.elements
    )
    sweep = SweepConfig(
        f_start_hz=f0 / 5.0,
        f_stop_hz=f0 * 5.0,
        n_points=96,
        spacing=SweepSpacing.LOGARITHMIC,
    )
    analysis = LadderABCDAnalyzer().analyze(result.circuit, sweep)
    z, p, k = signal.cheb2ap(5, 40)
    z_bp, p_bp, k_bp = signal.lp2bp_zpk(
        z, p, k, wo=2 * np.pi * f0, bw=2 * np.pi * bw
    )
    _, href = signal.freqs_zpk(
        z_bp, p_bp, k_bp, worN=2 * np.pi * analysis.frequency_hz
    )
    s21_db = 20 * np.log10(np.abs(analysis.s21) + 1e-30)
    href_db = 20 * np.log10(np.abs(href) + 1e-30)
    # Normalize peak to compare shape (terminations / scale)
    s21_db = s21_db - float(np.max(s21_db))
    href_db = href_db - float(np.max(href_db))
    err = float(np.max(np.abs(s21_db - href_db)))
    assert err < 1.5


def test_elliptic_bp_and_bs_synthesize() -> None:
    bp = FilterSpec(
        family=ApproximationFamily.ELLIPTIC,
        response=FilterResponse.BAND_PASS,
        order=5,
        f_center_hz=100e6,
        bandwidth_hz=20e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_BP_SERIES_RES_INPUT,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.5,
        stopband_attenuation_db=40.0,
    )
    bp_r = synthesize(bp)
    assert any(type(el).__name__ == "IdealBruneLC" for el in bp_r.circuit.elements)

    bs = FilterSpec(
        family=ApproximationFamily.ELLIPTIC,
        response=FilterResponse.BAND_STOP,
        order=5,
        f_center_hz=100e6,
        bandwidth_hz=20e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_BS_SERIES_TANK_INPUT,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.5,
        stopband_attenuation_db=40.0,
    )
    bs_r = synthesize(bs)
    assert len(bs_r.circuit.elements) >= 3


def test_m_derived_bp_smoke() -> None:
    spec = FilterSpec(
        family=ApproximationFamily.M_DERIVED,
        response=FilterResponse.BAND_PASS,
        order=2,
        f_center_hz=100e6,
        bandwidth_hz=20e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_BP_SERIES_RES_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
        m_parameter=0.6,
    )
    result = synthesize(spec)
    assert any(type(el).__name__ == "IdealBruneLC" for el in result.circuit.elements)


def test_constant_k_and_m_derived_synthesize() -> None:
    ck = synthesize(_lp_spec(ApproximationFamily.CONSTANT_K, 2, cutoff_hz=1e6))
    assert ck.prototype.arms is not None
    assert len(ck.circuit.elements) >= 3

    md = synthesize(
        _lp_spec(ApproximationFamily.M_DERIVED, 2, m=0.6, cutoff_hz=1e6)
    )
    assert md.prototype.arms is not None
    assert any(
        type(el).__name__ in ("IdealSeriesLC", "IdealParallelLC")
        for el in md.circuit.elements
    )


def test_constant_k_bp_smoke() -> None:
    spec = FilterSpec(
        family=ApproximationFamily.CONSTANT_K,
        response=FilterResponse.BAND_PASS,
        order=2,
        f_center_hz=100e6,
        bandwidth_hz=20e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_BP_SERIES_RES_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )
    result = synthesize(spec)
    assert len(result.circuit.elements) >= 3
