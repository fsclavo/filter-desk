"""Band metrics shared by design sweeps and reports.

A caller supplies the passband and/or stopband intervals of interest; the
helpers return the usual comparison figures (ripple, stopband attenuation,
return loss and group-delay ripple). Bands are ``(low_hz, high_hz)`` tuples.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.derived import group_delay_s, mag_db
from filterdesk.analysis.types import AnalysisResult
from filterdesk.domain.enums import FilterResponse
from filterdesk.domain.specs import FilterSpec

Band = tuple[float, float]


class BandMetricsError(ValueError):
    """Raised for an invalid band interval."""


@dataclass(frozen=True, slots=True)
class BandMetrics:
    """Response figures of merit over a passband and/or stopband."""

    passband_ripple_db: float | None = None
    stopband_attenuation_db: float | None = None
    min_return_loss_db: float | None = None
    group_delay_ripple_s: float | None = None


def _band(band: Band | None) -> Band | None:
    if band is None:
        return None
    low, high = float(band[0]), float(band[1])
    if low <= 0.0 or high <= low:
        raise BandMetricsError("bands need 0 < low < high (Hz)")
    return (low, high)


def _mask(frequency_hz: NDArray[np.floating], band: Band) -> NDArray[np.bool_]:
    return (frequency_hz >= band[0]) & (frequency_hz <= band[1])


def band_metrics(
    result: AnalysisResult,
    *,
    passband: Band | None = None,
    stopband: Band | None = None,
) -> BandMetrics:
    """Compute ripple/attenuation/return-loss/group-delay figures.

    ``stopband_attenuation_db`` is the *minimum* attenuation in the stopband
    (i.e. the weakest rejection point); ``min_return_loss_db`` is the weakest
    match in the passband.
    """
    f = np.asarray(result.frequency_hz, dtype=float)
    s21_db = np.asarray(mag_db(result.s21), dtype=float)
    pb = _band(passband)
    sb = _band(stopband)

    ripple: float | None = None
    return_loss: float | None = None
    gd_ripple: float | None = None
    if pb is not None:
        mask = _mask(f, pb)
        if np.any(mask):
            s21_band = s21_db[mask]
            ripple = float(np.max(s21_band) - np.min(s21_band))
            s11_band = np.asarray(mag_db(result.s11), dtype=float)[mask]
            return_loss = float(-np.max(s11_band))
            gd = np.asarray(
                group_delay_s(result.frequency_hz, result.s21), dtype=float
            )[mask]
            gd_ripple = float(np.max(gd) - np.min(gd))

    attenuation: float | None = None
    if sb is not None:
        mask = _mask(f, sb)
        if np.any(mask):
            attenuation = float(-np.max(s21_db[mask]))

    return BandMetrics(
        passband_ripple_db=ripple,
        stopband_attenuation_db=attenuation,
        min_return_loss_db=return_loss,
        group_delay_ripple_s=gd_ripple,
    )


def band_edges(spec: FilterSpec) -> tuple[float, float]:
    """Passband/stopband edges for LP/HP/BP/BS specs (Hz)."""
    if spec.response in (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP):
        assert spec.f_center_hz is not None and spec.bandwidth_hz is not None
        f0 = spec.f_center_hz
        bw = spec.bandwidth_hz
        f_high = 0.5 * (bw + math.sqrt(bw * bw + 4.0 * f0 * f0))
        return f0 * f0 / f_high, f_high
    return spec.cutoff_hz, spec.cutoff_hz


def default_bands(spec: FilterSpec) -> tuple[Band, Band]:
    """Reasonable pass/stop evaluation bands derived from the base spec."""
    low_edge, high_edge = band_edges(spec)
    if spec.response == FilterResponse.LOW_PASS:
        fc = spec.cutoff_hz
        return (fc / 20.0, fc), (fc * 2.0, fc * 20.0)
    if spec.response == FilterResponse.HIGH_PASS:
        fc = spec.cutoff_hz
        return (fc, fc * 20.0), (fc / 20.0, fc / 2.0)
    if spec.response == FilterResponse.BAND_PASS:
        return (low_edge, high_edge), (high_edge * 2.0, high_edge * 5.0)
    return (low_edge / 5.0, low_edge / 2.0), (low_edge, high_edge)


__all__ = [
    "Band",
    "BandMetrics",
    "BandMetricsError",
    "band_edges",
    "band_metrics",
    "default_bands",
]
