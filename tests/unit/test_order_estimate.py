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


def test_bandpass_orders() -> None:
    common = dict(
        f_pass_low_hz=0.9e6,
        f_pass_high_hz=1.1e6,
        f_stop_low_hz=0.7e6,
        f_stop_high_hz=1.4e6,
        passband_attenuation_db=0.5,
        stopband_attenuation_db=40.0,
    )
    butter = estimate_minimum_order(
        ApproximationFamily.BUTTERWORTH, FilterResponse.BAND_PASS, **common
    )
    cheby = estimate_minimum_order(
        ApproximationFamily.CHEBYSHEV_TYPE_I, FilterResponse.BAND_PASS, **common
    )
    ellip = estimate_minimum_order(
        ApproximationFamily.ELLIPTIC, FilterResponse.BAND_PASS, **common
    )
    assert butter.order == 5
    assert cheby.order == 4
    assert ellip.order <= cheby.order
    assert butter.omega_ratio == pytest.approx(3.5)
    assert butter.f_pass_low_hz == pytest.approx(0.9e6)
    assert butter.f_stop_high_hz == pytest.approx(1.4e6)
    assert butter.natural_freq_low_hz is not None
    assert butter.natural_freq_high_hz is not None
    assert butter.natural_freq_low_hz < butter.natural_freq_high_hz


def test_bandstop_orders() -> None:
    common = dict(
        f_pass_low_hz=0.7e6,
        f_pass_high_hz=1.4e6,
        f_stop_low_hz=0.9e6,
        f_stop_high_hz=1.1e6,
        passband_attenuation_db=0.5,
        stopband_attenuation_db=40.0,
    )
    butter = estimate_minimum_order(
        ApproximationFamily.BUTTERWORTH, FilterResponse.BAND_STOP, **common
    )
    cheby = estimate_minimum_order(
        ApproximationFamily.CHEBYSHEV_TYPE_I, FilterResponse.BAND_STOP, **common
    )
    assert butter.order == 5
    assert cheby.order == 4
    assert cheby.order <= butter.order
    assert butter.omega_ratio == pytest.approx(3.5)


def test_band_rejects_missing_edges() -> None:
    with pytest.raises(OrderEstimateError):
        estimate_minimum_order(
            ApproximationFamily.BUTTERWORTH,
            FilterResponse.BAND_PASS,
            passband_attenuation_db=0.5,
            stopband_attenuation_db=40.0,
        )


def test_bandpass_rejects_bad_edge_order() -> None:
    with pytest.raises(OrderEstimateError):
        estimate_minimum_order(
            ApproximationFamily.BUTTERWORTH,
            FilterResponse.BAND_PASS,
            f_pass_low_hz=0.9e6,
            f_pass_high_hz=1.1e6,
            f_stop_low_hz=1.2e6,
            f_stop_high_hz=1.4e6,
            passband_attenuation_db=0.5,
            stopband_attenuation_db=40.0,
        )


def test_bandstop_rejects_bad_edge_order() -> None:
    with pytest.raises(OrderEstimateError):
        estimate_minimum_order(
            ApproximationFamily.BUTTERWORTH,
            FilterResponse.BAND_STOP,
            f_pass_low_hz=0.7e6,
            f_pass_high_hz=1.4e6,
            f_stop_low_hz=1.3e6,
            f_stop_high_hz=1.6e6,
            passband_attenuation_db=0.5,
            stopband_attenuation_db=40.0,
        )
