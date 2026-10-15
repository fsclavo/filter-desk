"""Plot markers and response limit regions (Phase 3 UX)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class LimitMetric(StrEnum):
    S21_DB = "s21_db"
    S11_DB = "s11_db"
    VSWR = "vswr"


@dataclass(frozen=True, slots=True)
class Marker:
    """Pinned frequency marker on response plots."""

    id: str
    frequency_hz: float
    label: str = ""

    def __post_init__(self) -> None:
        if self.frequency_hz <= 0.0:
            raise ValueError("marker frequency must be > 0")


@dataclass(frozen=True, slots=True)
class LimitRegion:
    """Rectangular pass/fail region in frequency × metric space."""

    id: str
    metric: LimitMetric
    f_low_hz: float
    f_high_hz: float
    y_min: float | None = None
    y_max: float | None = None
    enabled: bool = True
    label: str = ""

    def __post_init__(self) -> None:
        if self.f_low_hz <= 0.0 or self.f_high_hz <= 0.0:
            raise ValueError("limit frequencies must be > 0")
        if self.f_high_hz <= self.f_low_hz:
            raise ValueError("f_high_hz must be > f_low_hz")
        if self.y_min is None and self.y_max is None:
            raise ValueError("limit needs y_min and/or y_max")
        if (
            self.y_min is not None
            and self.y_max is not None
            and self.y_min > self.y_max
        ):
            raise ValueError("y_min must be <= y_max")


MAX_MARKERS = 8
MAX_LIMITS = 10


def markers_to_mapping(markers: list[Marker]) -> list[dict[str, Any]]:
    return [
        {
            "id": m.id,
            "frequency_hz": m.frequency_hz,
            "label": m.label,
        }
        for m in markers
    ]


def markers_from_mapping(rows: list[Any]) -> list[Marker]:
    out: list[Marker] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            Marker(
                id=str(row["id"]),
                frequency_hz=float(row["frequency_hz"]),
                label=str(row.get("label", "")),
            )
        )
    return out


def limits_to_mapping(limits: list[LimitRegion]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lim in limits:
        row: dict[str, Any] = {
            "id": lim.id,
            "metric": lim.metric.value,
            "f_low_hz": lim.f_low_hz,
            "f_high_hz": lim.f_high_hz,
            "enabled": lim.enabled,
            "label": lim.label,
        }
        if lim.y_min is not None:
            row["y_min"] = lim.y_min
        if lim.y_max is not None:
            row["y_max"] = lim.y_max
        rows.append(row)
    return rows


def limits_from_mapping(rows: list[Any]) -> list[LimitRegion]:
    out: list[LimitRegion] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        y_min = row.get("y_min")
        y_max = row.get("y_max")
        out.append(
            LimitRegion(
                id=str(row["id"]),
                metric=LimitMetric(str(row["metric"])),
                f_low_hz=float(row["f_low_hz"]),
                f_high_hz=float(row["f_high_hz"]),
                y_min=None if y_min is None else float(y_min),
                y_max=None if y_max is None else float(y_max),
                enabled=bool(row.get("enabled", True)),
                label=str(row.get("label", "")),
            )
        )
    return out
