"""Shared tuning helpers for sensitivity and optimization.

Parameter enumeration/value replacement and residual/objective evaluation live
here so read-only sensitivity analysis does not depend on the optimizer engine
(import-linter contract).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.limits_eval import metric_trace
from filterdesk.analysis.types import AnalysisResult
from filterdesk.domain.circuit import (
    Circuit,
    Element,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealResistor,
    IdealSeriesLC,
    NonIdealCapacitor,
    NonIdealInductor,
)
from filterdesk.domain.overlays import LimitMetric, LimitRegion


@dataclass(frozen=True, slots=True)
class TunableParam:
    """One scalar component value the optimizer may vary."""

    ref: str
    element_id: str
    field: str
    value: float


def tunable_params(circuit: Circuit) -> list[TunableParam]:
    """Enumerate every reactive/R nominal value as an optimization variable."""
    params: list[TunableParam] = []
    for el in circuit.elements:
        if isinstance(el, IdealInductor):
            params.append(TunableParam(el.id, el.id, "value_h", el.value_h))
        elif isinstance(el, IdealCapacitor):
            params.append(TunableParam(el.id, el.id, "value_f", el.value_f))
        elif isinstance(el, IdealResistor):
            params.append(TunableParam(el.id, el.id, "value_ohm", el.value_ohm))
        elif isinstance(el, (IdealSeriesLC, IdealParallelLC)):
            params.append(
                TunableParam(f"{el.id}.L", el.id, "value_h", el.value_h)
            )
            params.append(
                TunableParam(f"{el.id}.C", el.id, "value_f", el.value_f)
            )
        elif isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
            params.extend(
                (
                    TunableParam(f"{el.id}.Ls", el.id, "series_l_h", el.series_l_h),
                    TunableParam(f"{el.id}.Cs", el.id, "series_c_f", el.series_c_f),
                    TunableParam(f"{el.id}.Lp", el.id, "parallel_l_h", el.parallel_l_h),
                    TunableParam(f"{el.id}.Cp", el.id, "parallel_c_f", el.parallel_c_f),
                )
            )
        elif isinstance(el, NonIdealInductor):
            params.append(TunableParam(el.id, el.id, "value_h", el.value_h))
        elif isinstance(el, NonIdealCapacitor):
            params.append(TunableParam(el.id, el.id, "value_f", el.value_f))
    return params


def _replace_element(el: Element, update: dict[str, float]) -> Element:
    if not update:
        return el
    if isinstance(el, IdealInductor):
        return replace(el, value_h=update.get("value_h", el.value_h))
    if isinstance(el, IdealCapacitor):
        return replace(el, value_f=update.get("value_f", el.value_f))
    if isinstance(el, IdealResistor):
        return replace(el, value_ohm=update.get("value_ohm", el.value_ohm))
    if isinstance(el, (IdealSeriesLC, IdealParallelLC)):
        return replace(
            el,
            value_h=update.get("value_h", el.value_h),
            value_f=update.get("value_f", el.value_f),
        )
    if isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
        return replace(
            el,
            series_l_h=update.get("series_l_h", el.series_l_h),
            series_c_f=update.get("series_c_f", el.series_c_f),
            parallel_l_h=update.get("parallel_l_h", el.parallel_l_h),
            parallel_c_f=update.get("parallel_c_f", el.parallel_c_f),
        )
    if isinstance(el, NonIdealInductor):
        return replace(el, value_h=update.get("value_h", el.value_h))
    if isinstance(el, NonIdealCapacitor):
        return replace(el, value_f=update.get("value_f", el.value_f))
    return el


def apply_values(
    circuit: Circuit,
    params: list[TunableParam],
    values: NDArray[np.floating] | list[float],
) -> Circuit:
    """Return a copy of ``circuit`` with each param set to its new value."""
    changes: dict[str, dict[str, float]] = {}
    for param, value in zip(params, values, strict=True):
        changes.setdefault(param.element_id, {})[param.field] = float(value)
    elements: list[Element] = [
        _replace_element(el, changes.get(el.id, {})) for el in circuit.elements
    ]
    return replace(circuit, elements=elements)


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


__all__ = [
    "Objective",
    "PassbandRipple",
    "ReturnLoss",
    "StopbandAttenuation",
    "TunableParam",
    "apply_values",
    "combined_residuals",
    "limit_residuals",
    "objective_residuals",
    "residual_norm",
    "tunable_params",
]
