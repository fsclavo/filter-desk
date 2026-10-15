"""Order estimation unit tests."""

from __future__ import annotations

import pytest

from filterdesk.domain.enums import ApproximationFamily, FilterResponse
from filterdesk.synthesis.order_estimate import (
    OrderEstimateError,
    estimate_minimum_order,
    supports_order_estimation,
)


def test_butterworth_lp_known_order() -> None:
    # fp=1 MHz, fs=2 MHz, Ap=3, As=40 → N=7 (scipy.buttord)
    result = estimate_minimum_order(
        ApproximationFamily.BUTTERWORTH,
        FilterResponse.LOW_PASS,
        f_pass_hz=1e6,
        f_stop_hz=2e6,
        passband_attenuation_db=3.0,
        stopband_attenuation_db=40.0,
    )
    assert result.order == 7
    assert result.omega_ratio == pytest.approx(2.0)


def test_cheby1_lower_than_butterworth() -> None:
    butter = estimate_minimum_order(
        ApproximationFamily.BUTTERWORTH,
        FilterResponse.LOW_PASS,
        f_pass_hz=1e6,
        f_stop_hz=2e6,
        passband_attenuation_db=0.5,
        stopband_attenuation_db=40.0,
    )
    cheby = estimate_minimum_order(
        ApproximationFamily.CHEBYSHEV_TYPE_I,
        FilterResponse.LOW_PASS,
        f_pass_hz=1e6,
        f_stop_hz=2e6,
        passband_attenuation_db=0.5,
        stopband_attenuation_db=40.0,
    )
    assert cheby.order <= butter.order
    assert cheby.order == 5


def test_elliptic_lowest_order() -> None:
    result = estimate_minimum_order(
        ApproximationFamily.ELLIPTIC,
        FilterResponse.LOW_PASS,
        f_pass_hz=1e6,
        f_stop_hz=2e6,
        passband_attenuation_db=0.5,
        stopband_attenuation_db=40.0,
    )
    assert result.order == 4


def test_cheby2_and_highpass() -> None:
    lp = estimate_minimum_order(
        ApproximationFamily.CHEBYSHEV_TYPE_II,
        FilterResponse.LOW_PASS,
        f_pass_hz=1e6,
        f_stop_hz=2e6,
        passband_attenuation_db=0.5,
        stopband_attenuation_db=40.0,
    )
    assert lp.order == 5
    hp = estimate_minimum_order(
        ApproximationFamily.BUTTERWORTH,
        FilterResponse.HIGH_PASS,
        f_pass_hz=2e6,
        f_stop_hz=1e6,
        passband_attenuation_db=3.0,
        stopband_attenuation_db=40.0,
    )
    assert hp.order == 7
    assert hp.omega_ratio == pytest.approx(2.0)


def test_rejects_unsupported_family() -> None:
    with pytest.raises(OrderEstimateError):
        estimate_minimum_order(
            ApproximationFamily.BESSEL,
            FilterResponse.LOW_PASS,
            f_pass_hz=1e6,
            f_stop_hz=2e6,
            passband_attenuation_db=3.0,
            stopband_attenuation_db=40.0,
        )


def test_rejects_bad_lp_edges() -> None:
    with pytest.raises(OrderEstimateError):
        estimate_minimum_order(
            ApproximationFamily.BUTTERWORTH,
            FilterResponse.LOW_PASS,
            f_pass_hz=2e6,
            f_stop_hz=1e6,
            passband_attenuation_db=3.0,
            stopband_attenuation_db=40.0,
        )


def test_supports_flags() -> None:
    assert supports_order_estimation(ApproximationFamily.ELLIPTIC)
    assert not supports_order_estimation(ApproximationFamily.CONSTANT_K)
