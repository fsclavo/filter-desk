"""Phase 5 family synthesis/analysis tests."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import signal

from filterdesk.analysis.adapters.abcd_ladder import (
    LadderABCDAnalyzer,
    _element_abcd,
    abcd_to_s,
    cascade_abcd,
)
from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec, SpecValidationError, validate_spec
from filterdesk.synthesis import synthesize


def _lp_spec(family: ApproximationFamily, order: int, fc: float = 1e6) -> FilterSpec:
    return FilterSpec(
        family=family,
        response=FilterResponse.LOW_PASS,
        order=order,
        cutoff_hz=fc,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )


@pytest.mark.parametrize("order", [1, 2, 3, 5, 7, 10])
def test_bessel_minus_3db_at_cutoff(order: int) -> None:
    fc = 1e6
    circuit = synthesize(_lp_spec(ApproximationFamily.BESSEL, order, fc)).circuit
    sweep = SweepConfig(fc / 5, fc * 5, 2001, SweepSpacing.LOGARITHMIC)
    result = LadderABCDAnalyzer().analyze(circuit, sweep)
    i = int(np.argmin(np.abs(result.frequency_hz - fc)))
    assert abs(float(mag_db(result.s21)[i]) - (-3.0103)) < 0.05


@pytest.mark.parametrize("order", [3, 5, 7])
def test_bessel_matches_scipy_shape(order: int) -> None:
    """Normalized |S21| tracks scipy besselap(mag) over a log grid."""
    fc = 1e6
    circuit = synthesize(_lp_spec(ApproximationFamily.BESSEL, order, fc)).circuit
    w_norm = np.logspace(-1, 1, 64)
    freq = w_norm * fc
    omega = 2.0 * np.pi * freq
    abcd = cascade_abcd([_element_abcd(el, omega) for el in circuit.elements])
    s21 = abcd_to_s(abcd, 50.0, 50.0)[1]
    pred = mag_db(s21)
    pred = pred - pred[0]  # remove DC reference

    _z, poles, k = signal.besselap(order, norm="mag")
    _w, h = signal.freqs_zpk([], poles, k, worN=w_norm)
    h0 = signal.freqs_zpk([], poles, k, worN=[1e-9])[1][0]
    target = 20.0 * np.log10(np.abs(h / h0))
    assert float(np.max(np.abs(pred - target))) < 0.15


@pytest.mark.parametrize("order", [1, 3, 5, 8])
def test_gaussian_near_minus_3db(order: int) -> None:
    fc = 10e6
    circuit = synthesize(_lp_spec(ApproximationFamily.GAUSSIAN, order, fc)).circuit
    omega = np.array([2.0 * np.pi * fc])
    abcd = cascade_abcd([_element_abcd(el, omega) for el in circuit.elements])
    s21_db = float(mag_db(abcd_to_s(abcd, 50.0, 50.0)[1])[0])
    assert abs(s21_db - (-3.01)) < 1.5  # finite-order Gaussian approx


@pytest.mark.parametrize("order", [2, 3, 5, 7])
def test_legendre_synthesizes(order: int) -> None:
    result = synthesize(_lp_spec(ApproximationFamily.LEGENDRE, order, 5e6))
    assert len(result.circuit.elements) == order
    assert result.prototype.family == ApproximationFamily.LEGENDRE


def test_bessel_hp_and_bp_smoke() -> None:
    hp = FilterSpec(
        family=ApproximationFamily.BESSEL,
        response=FilterResponse.HIGH_PASS,
        order=5,
        cutoff_hz=100e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_HP_SERIES_C_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )
    assert len(synthesize(hp).circuit.elements) == 5
    bp = FilterSpec(
        family=ApproximationFamily.BESSEL,
        response=FilterResponse.BAND_PASS,
        order=3,
        f_center_hz=100e6,
        bandwidth_hz=20e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_BP_SERIES_RES_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )
    assert len(synthesize(bp).circuit.elements) == 3


def test_rejects_bessel_order_too_high() -> None:
    with pytest.raises(SpecValidationError, match="order 1..10"):
        validate_spec(_lp_spec(ApproximationFamily.BESSEL, 11))
