"""Manufacturer frequency-dependent Q/ESR model data.

Only datasheet/measured points are stored. Vendor SPICE files are not
redistributed; users can import their own model JSON.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from filterdesk.domain.units import parse_si


class ManufacturerModelError(ValueError):
    """Raised for invalid manufacturer model data."""


@dataclass(frozen=True, slots=True)
class ModelPoint:
    frequency_hz: float
    value: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.frequency_hz) or self.frequency_hz <= 0.0:
            raise ManufacturerModelError("model point frequency must be > 0")
        if not math.isfinite(self.value) or self.value < 0.0:
            raise ManufacturerModelError("model point value must be >= 0")


def read_curve_csv(path: Path | str) -> tuple[ModelPoint, ...]:
    """Read a two-column ``frequency,value`` curve from a CSV file.

    Comments start with ``#`` or ``!``. A first row containing ``freq``,
    ``value``, ``q`` or ``esr`` is treated as a header. Frequencies and values
    accept the same SI suffixes as the rest of the GUI/CLI (for example
    ``1M`` or ``100m``).
    """
    target = Path(path)
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ManufacturerModelError(f"cannot read {target}: {exc}") from exc

    points: list[ModelPoint] = []
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "!")):
            continue
        row = next(csv.reader([line]))
        if len(row) < 2:
            raise ManufacturerModelError(
                f"line {line_number}: expected frequency,value"
            )
        if not points and any(
            token in cell.lower()
            for cell in row
            for token in ("freq", "value", "q", "esr")
        ):
            continue
        try:
            frequency = parse_si(row[0])
            value = parse_si(row[1])
        except ValueError as exc:
            raise ManufacturerModelError(
                f"line {line_number}: {exc}"
            ) from exc
        try:
            points.append(ModelPoint(frequency, value))
        except ManufacturerModelError as exc:
            raise ManufacturerModelError(
                f"line {line_number}: {exc}"
            ) from exc

    if not points:
        raise ManufacturerModelError("curve CSV has no data rows")
    ordered = sorted(points, key=lambda point: point.frequency_hz)
    frequencies = [point.frequency_hz for point in ordered]
    if len(set(frequencies)) != len(frequencies):
        raise ManufacturerModelError("curve CSV has duplicate frequencies")
    return tuple(ordered)


def model_from_curve_csv(
    path: Path | str,
    *,
    model_id: str,
    curve: str,
    confidence: str = "measured",
    source: str = "",
    notes: str = "",
) -> ManufacturerModel:
    """Build a manufacturer model from a Q or ESR CSV curve."""
    if curve not in {"q", "esr"}:
        raise ManufacturerModelError("curve must be 'q' or 'esr'")
    points = read_curve_csv(path)
    return ManufacturerModel(
        model_id=model_id,
        source=source or str(path),
        confidence=confidence,
        notes=notes,
        q_points=points if curve == "q" else (),
        esr_points=points if curve == "esr" else (),
    )


def _interp_log(
    frequency_hz: float, points: tuple[ModelPoint, ...]
) -> float:
    if not points:
        raise ManufacturerModelError("no model points")
    ordered = sorted(points, key=lambda point: point.frequency_hz)
    if frequency_hz <= ordered[0].frequency_hz:
        return ordered[0].value
    if frequency_hz >= ordered[-1].frequency_hz:
        return ordered[-1].value
    for left, right in zip(ordered, ordered[1:], strict=True):
        if left.frequency_hz <= frequency_hz <= right.frequency_hz:
            if left.frequency_hz == right.frequency_hz:
                return left.value
            log_f = math.log10(frequency_hz)
            log_left = math.log10(left.frequency_hz)
            log_right = math.log10(right.frequency_hz)
            fraction = (log_f - log_left) / (log_right - log_left)
            # Interpolate in log(value) when both endpoints are positive;
            # otherwise fall back to linear value interpolation.
            if left.value > 0.0 and right.value > 0.0:
                log_value = math.log10(left.value) + fraction * (
                    math.log10(right.value) - math.log10(left.value)
                )
                return float(10.0**log_value)
            return left.value + fraction * (right.value - left.value)
    return ordered[-1].value  # pragma: no cover - loop always returns


@dataclass(frozen=True, slots=True)
class ManufacturerModel:
    model_id: str = ""
    source: str = ""
    confidence: str = "datasheet"
    notes: str = ""
    q_points: tuple[ModelPoint, ...] = ()
    esr_points: tuple[ModelPoint, ...] = ()

    def __post_init__(self) -> None:
        if self.confidence not in {"datasheet", "measured", "vendor", "estimated"}:
            raise ManufacturerModelError(
                f"unsupported model confidence: {self.confidence!r}"
            )
        for name, points in (
            ("q_points", self.q_points),
            ("esr_points", self.esr_points),
        ):
            frequencies = [point.frequency_hz for point in points]
            if frequencies != sorted(frequencies):
                raise ManufacturerModelError(f"{name} must be sorted by frequency")
            if len(set(frequencies)) != len(frequencies):
                raise ManufacturerModelError(f"{name} has duplicate frequencies")

    @property
    def has_curve(self) -> bool:
        return bool(self.q_points or self.esr_points)

    def q_at(self, frequency_hz: float) -> float | None:
        if not self.q_points:
            return None
        return _interp_log(frequency_hz, self.q_points)

    def esr_at(self, frequency_hz: float) -> float | None:
        if not self.esr_points:
            return None
        return _interp_log(frequency_hz, self.esr_points)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "source": self.source,
            "confidence": self.confidence,
            "notes": self.notes,
            "q_points": [
                [point.frequency_hz, point.value] for point in self.q_points
            ],
            "esr_points": [
                [point.frequency_hz, point.value] for point in self.esr_points
            ],
        }

    @classmethod
    def from_mapping(cls, data: Any) -> ManufacturerModel:
        if not isinstance(data, dict):
            raise ManufacturerModelError("model must be an object")
        try:
            q_points = tuple(
                ModelPoint(float(row[0]), float(row[1]))
                for row in data.get("q_points", [])
            )
            esr_points = tuple(
                ModelPoint(float(row[0]), float(row[1]))
                for row in data.get("esr_points", [])
            )
        except (TypeError, ValueError, IndexError) as exc:
            raise ManufacturerModelError(f"invalid model point: {exc}") from exc
        return cls(
            model_id=str(data.get("model_id", "")),
            source=str(data.get("source", "")),
            confidence=str(data.get("confidence", "datasheet")),
            notes=str(data.get("notes", "")),
            q_points=q_points,
            esr_points=esr_points,
        )


__all__ = [
    "ManufacturerModel",
    "ManufacturerModelError",
    "ModelPoint",
    "model_from_curve_csv",
    "read_curve_csv",
]
