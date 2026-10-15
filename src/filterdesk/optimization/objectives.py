"""Limit-residual objective for the optimizer (FR-P4)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.limits_eval import metric_trace
from filterdesk.analysis.types import AnalysisResult
from filterdesk.domain.overlays import LimitRegion


def limit_residuals(
    result: AnalysisResult, limits: list[LimitRegion]
) -> NDArray[np.float64]:
    """Per-sample limit violations (each >= 0) of the analysis.

    For each enabled limit with samples in band, emits one residual per in-band
    sample per bound: ``max(0, y_min - y)`` and/or ``max(0, y - y_max)``. A zero
    residual means the bound is satisfied at that frequency; the vector is empty
    only when no enabled limit has samples. The richer vector gives least-squares
    a usable gradient (unlike a single worst-point residual, which is kinked).
    """
    chunks: list[NDArray[np.float64]] = []
    f = np.asarray(result.frequency_hz, dtype=float)
    for limit in limits:
        if not limit.enabled:
            continue
        y = metric_trace(result, limit.metric)
        mask = (f >= limit.f_low_hz) & (f <= limit.f_high_hz)
        if not np.any(mask):
            continue
        band = np.asarray(y[mask], dtype=float)
        if limit.y_min is not None:
            chunks.append(np.clip(limit.y_min - band, 0.0, None))
        if limit.y_max is not None:
            chunks.append(np.clip(band - limit.y_max, 0.0, None))
    if not chunks:
        return np.empty(0, dtype=np.float64)
    return np.asarray(np.concatenate(chunks), dtype=np.float64)


def residual_norm(residuals: NDArray[np.float64]) -> float:
    """Euclidean norm of a residual vector (scalar cost)."""
    return float(np.sqrt(np.sum(np.asarray(residuals, dtype=float) ** 2)))
