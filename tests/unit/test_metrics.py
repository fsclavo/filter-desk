"""Band metrics helpers."""

from __future__ import annotations

import numpy as np
import pytest

from filterdesk.analysis.metrics import BandMetricsError, band_metrics
from filterdesk.analysis.types import AnalysisResult


def _result() -> AnalysisResult:
    freq = np.array([1e6, 2e6, 3e6, 10e6, 11e6], dtype=float)
    s21_db = np.array([0.0, -0.5, -1.0, -40.0, -35.0])
    s11_db = np.array([-20.0, -10.0, -15.0, -10.0, -5.0])
    s21 = 10.0 ** (s21_db / 20.0) + 0j
    s11 = 10.0 ** (s11_db / 20.0) + 0j
    z = np.full(freq.shape, 50.0 + 0j)
    return AnalysisResult(
        frequency_hz=freq,
        s11=s11,
        s21=s21,
        s12=s21.copy(),
        s22=s11.copy(),
        zin_ohm=z,
        zout_ohm=z,
        z0_source_ohm=50.0,
        z0_load_ohm=50.0,
        backend="test",
    )


def test_band_metrics_passband_and_stopband() -> None:
    metrics = band_metrics(
        _result(), passband=(1e6, 3e6), stopband=(10e6, 11e6)
    )
    assert metrics.passband_ripple_db == pytest.approx(1.0)
    assert metrics.min_return_loss_db == pytest.approx(10.0)
    assert metrics.stopband_attenuation_db == pytest.approx(35.0)
    assert metrics.group_delay_ripple_s == pytest.approx(0.0)


def test_band_metrics_without_bands() -> None:
    metrics = band_metrics(_result())
    assert metrics.passband_ripple_db is None
    assert metrics.stopband_attenuation_db is None
    assert metrics.min_return_loss_db is None
    assert metrics.group_delay_ripple_s is None


def test_band_metrics_invalid_band() -> None:
    with pytest.raises(BandMetricsError):
        band_metrics(_result(), passband=(3e6, 1e6))
    with pytest.raises(BandMetricsError):
        band_metrics(_result(), stopband=(0.0, 1e6))
