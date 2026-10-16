"""Limit-residual and composable objectives for the optimizer (FR-P4, §20)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.limits_eval import metric_trace
from filterdesk.analysis.types import AnalysisResult
from filterdesk.domain.overlays import LimitMetric, LimitRegion


@dataclass(frozen=True, slots=True)
class PassbandRipple:
    """Minimise peak-to-peak |S21| variation (dB) over a band."""

    f_low_hz: float
    f_high_hz: float
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class StopbandAttenuation:
    """Push the minimum in-band attenuation (dB) toward/above ``target_db``."""

    f_low_hz: float
    f_high_hz: float
    target_db: float
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class ReturnLoss:
    """Push the minimum in-band return loss (dB) toward/above ``target_db``."""

    f_low_hz: float
    f_high_hz: float
    target_db: float
    weight: float = 1.0


Objective = PassbandRipple | StopbandAttenuation | ReturnLoss


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


def _band(
    result: AnalysisResult, metric: LimitMetric, f_low_hz: float, f_high_hz: float
) -> NDArray[np.float64] | None:
    f = np.asarray(result.frequency_hz, dtype=float)
    mask = (f >= f_low_hz) & (f <= f_high_hz)
    if not np.any(mask):
        return None
    return np.asarray(metric_trace(result, metric)[mask], dtype=float)


def _objective_penalty(result: AnalysisResult, objective: Objective) -> float:
    weight: float = float(max(objective.weight, 0.0)) ** 0.5
    if isinstance(objective, PassbandRipple):
        band = _band(
            result, LimitMetric.S21_DB, objective.f_low_hz, objective.f_high_hz
        )
        if band is None:
            return 0.0
        ripple = float(np.max(band)) - float(np.min(band))
        return float(weight * ripple)
    if isinstance(objective, StopbandAttenuation):
        band = _band(
            result, LimitMetric.S21_DB, objective.f_low_hz, objective.f_high_hz
        )
        if band is None:
            return 0.0
        min_att = float(-np.max(band))  # |S21| dB are <= 0; attenuation = -dB
        return float(weight * max(0.0, objective.target_db - min_att))
    if isinstance(objective, ReturnLoss):
        band = _band(
            result, LimitMetric.S11_DB, objective.f_low_hz, objective.f_high_hz
        )
        if band is None:
            return 0.0
        min_rl = float(-np.max(band))
        return float(weight * max(0.0, objective.target_db - min_rl))
    return 0.0


def objective_residuals(
    result: AnalysisResult, objectives: list[Objective]
) -> NDArray[np.float64]:
    """Weighted (sqrt) per-objective penalties, each >= 0."""
    values = [_objective_penalty(result, obj) for obj in objectives]
    return np.asarray(values, dtype=np.float64)


def combined_residuals(
    result: AnalysisResult,
    limits: list[LimitRegion],
    objectives: list[Objective],
) -> NDArray[np.float64]:
    """Limit violations followed by objective penalties (combined residual vector)."""
    parts = [limit_residuals(result, limits)]
    if objectives:
        parts.append(objective_residuals(result, objectives))
    chunks = [p for p in parts if p.size]
    if not chunks:
        return np.empty(0, dtype=np.float64)
    return np.asarray(np.concatenate(chunks), dtype=np.float64)


def residual_norm(residuals: NDArray[np.float64]) -> float:
    """Euclidean norm of a residual vector (scalar cost)."""
    return float(np.sqrt(np.sum(np.asarray(residuals, dtype=float) ** 2)))
