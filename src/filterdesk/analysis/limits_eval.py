"""Pass/fail evaluation of limit regions against an analysis result."""

from __future__ import annotations

import numpy as np

from filterdesk.analysis.derived import mag_db, vswr
from filterdesk.analysis.types import AnalysisResult
from filterdesk.domain.overlays import LimitMetric, LimitRegion


def _metric_trace(result: AnalysisResult, metric: LimitMetric) -> np.ndarray:
    if metric == LimitMetric.S21_DB:
        return np.asarray(mag_db(result.s21), dtype=float)
    if metric == LimitMetric.S11_DB:
        return np.asarray(mag_db(result.s11), dtype=float)
    if metric == LimitMetric.VSWR:
        return np.asarray(vswr(result), dtype=float)
    if metric == LimitMetric.S11_MAG:
        return np.asarray(np.abs(result.s11), dtype=float)
    if metric == LimitMetric.S22_MAG:
        return np.asarray(np.abs(result.s22), dtype=float)
    raise ValueError(f"unknown metric: {metric}")


def metric_trace(result: AnalysisResult, metric: LimitMetric) -> np.ndarray:
    """Public wrapper around the metric extraction used for limit evaluation."""
    return _metric_trace(result, metric)


def evaluate_limit(result: AnalysisResult, limit: LimitRegion) -> bool | None:
    """Return True if pass, False if fail, None if no samples in band / disabled."""
    if not limit.enabled:
        return None
    f = np.asarray(result.frequency_hz, dtype=float)
    y = _metric_trace(result, limit.metric)
    mask = (f >= limit.f_low_hz) & (f <= limit.f_high_hz)
    if not np.any(mask):
        return None
    band = y[mask]
    if limit.y_min is not None and float(np.min(band)) < limit.y_min:
        return False
    if limit.y_max is not None and float(np.max(band)) > limit.y_max:
        return False
    return True


def evaluate_limits(
    result: AnalysisResult, limits: list[LimitRegion]
) -> dict[str, bool | None]:
    return {lim.id: evaluate_limit(result, lim) for lim in limits}
