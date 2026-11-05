"""Compare manufacturer Q/ESR model curves with measured component data."""

from __future__ import annotations

import math
from dataclasses import dataclass

from filterdesk.components_std.manufacturer_model import (
    ManufacturerModel,
    ModelPoint,
)


class ModelComparisonError(ValueError):
    """Raised when a model curve cannot be compared with a measurement."""


@dataclass(frozen=True, slots=True)
class ModelCurvePoint:
    frequency_hz: float
    measured: float
    predicted: float
    error: float
    relative_error_pct: float | None
    extrapolated: bool


@dataclass(frozen=True, slots=True)
class ModelCurveComparison:
    part_mpn: str
    curve: str
    model_id: str
    points: tuple[ModelCurvePoint, ...]
    model_min_hz: float
    model_max_hz: float
    rms_error: float | None
    max_abs_error: float | None
    mean_abs_relative_error_pct: float | None
    overlap_points: int
    extrapolated_points: int

    def summary(self) -> str:
        label = "Q" if self.curve == "q" else "ESR"
        subject = label if not self.part_mpn else f"{self.part_mpn} {label}"
        parts = [
            f"{subject} model vs measurement",
            f"{len(self.points)} points, {self.overlap_points} in model range",
        ]
        if self.rms_error is not None:
            parts.append(f"RMS {self.rms_error:.4g}")
        if self.max_abs_error is not None:
            parts.append(f"max |err| {self.max_abs_error:.4g}")
        if self.mean_abs_relative_error_pct is not None:
            parts.append(
                f"mean |rel err| {self.mean_abs_relative_error_pct:.3g} %"
            )
        return "; ".join(parts)


def compare_model_curve(
    model: ManufacturerModel,
    measured: tuple[ModelPoint, ...],
    *,
    curve: str,
    part_mpn: str = "",
) -> ModelCurveComparison:
    """Compare a model curve with measured ``ModelPoint`` data.

    The model is evaluated at each measured frequency using its log-log
    interpolation. Points outside the model's frequency range are flagged as
    extrapolated and excluded from the RMS/max/relative-error metrics.
    """
    if curve not in {"q", "esr"}:
        raise ModelComparisonError("curve must be 'q' or 'esr'")
    model_points = model.q_points if curve == "q" else model.esr_points
    if not model_points:
        raise ModelComparisonError(f"model has no {curve} curve")
    if not measured:
        raise ModelComparisonError("measurement curve has no points")

    getter = model.q_at if curve == "q" else model.esr_at
    model_min = min(point.frequency_hz for point in model_points)
    model_max = max(point.frequency_hz for point in model_points)
    points: list[ModelCurvePoint] = []
    for point in measured:
        predicted = getter(point.frequency_hz)
        if predicted is None:
            raise ModelComparisonError(
                f"model has no {curve} value at {point.frequency_hz:g} Hz"
            )
        error = predicted - point.value
        relative = (
            None
            if point.value == 0.0
            else abs(error) / abs(point.value) * 100.0
        )
        points.append(
            ModelCurvePoint(
                frequency_hz=point.frequency_hz,
                measured=point.value,
                predicted=predicted,
                error=error,
                relative_error_pct=relative,
                extrapolated=(
                    point.frequency_hz < model_min
                    or point.frequency_hz > model_max
                ),
            )
        )

    overlap = [point for point in points if not point.extrapolated]
    rms = (
        math.sqrt(sum(point.error**2 for point in overlap) / len(overlap))
        if overlap
        else None
    )
    max_abs = max((abs(point.error) for point in overlap), default=None)
    relative_values = [
        point.relative_error_pct
        for point in overlap
        if point.relative_error_pct is not None
    ]
    mean_relative = (
        sum(relative_values) / len(relative_values)
        if relative_values
        else None
    )
    return ModelCurveComparison(
        part_mpn=part_mpn,
        curve=curve,
        model_id=model.model_id,
        points=tuple(points),
        model_min_hz=model_min,
        model_max_hz=model_max,
        rms_error=rms,
        max_abs_error=max_abs,
        mean_abs_relative_error_pct=mean_relative,
        overlap_points=len(overlap),
        extrapolated_points=len(points) - len(overlap),
    )


__all__ = [
    "ModelComparisonError",
    "ModelCurveComparison",
    "ModelCurvePoint",
    "compare_model_curve",
]
