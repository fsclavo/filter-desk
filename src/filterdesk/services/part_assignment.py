"""Assign real library parts to physical BOM components."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from filterdesk.components_std import LibraryPart, nearest_part
from filterdesk.domain.circuit import Circuit, physical_components


class PartAssignmentError(ValueError):
    """Raised for invalid part assignment requests."""


@dataclass(frozen=True, slots=True)
class UnassignedPart:
    branch: str
    ref: str
    kind: str
    value_si: float
    reason: str


@dataclass(frozen=True, slots=True)
class PartAssignmentResult:
    assignments: dict[str, LibraryPart]
    unassigned: tuple[UnassignedPart, ...]
    max_delta_pct: float


def assign_nearest_parts(
    branches: Sequence[tuple[str, Circuit]],
    library: Sequence[LibraryPart],
    *,
    max_delta_pct: float = 10.0,
) -> PartAssignmentResult:
    """Assign the nearest same-kind part within ``max_delta_pct``.

    Keys are ``branch:ref`` (e.g. ``Low:C2``). Parts farther than the threshold
    are reported as unassigned instead of silently choosing a poor substitute.
    """
    if max_delta_pct < 0.0:
        raise PartAssignmentError("max_delta_pct must be >= 0")
    assignments: dict[str, LibraryPart] = {}
    unassigned: list[UnassignedPart] = []
    for label, circuit in branches:
        for part in physical_components(circuit):
            if part.kind not in {"inductor", "capacitor"}:
                continue
            nearest = nearest_part(list(library), kind=part.kind, value_si=part.value)
            key = f"{label}:{part.ref}"
            if nearest is None:
                unassigned.append(
                    UnassignedPart(
                        label,
                        part.ref,
                        part.kind,
                        part.value,
                        "no library part of this kind",
                    )
                )
                continue
            delta_pct = 100.0 * abs(nearest.value_si - part.value) / part.value
            if delta_pct > max_delta_pct:
                unassigned.append(
                    UnassignedPart(
                        label,
                        part.ref,
                        part.kind,
                        part.value,
                        f"nearest {nearest.mpn} is {delta_pct:.1f}% away",
                    )
                )
                continue
            assignments[key] = nearest
    return PartAssignmentResult(
        assignments=assignments,
        unassigned=tuple(unassigned),
        max_delta_pct=max_delta_pct,
    )


__all__ = [
    "PartAssignmentError",
    "PartAssignmentResult",
    "UnassignedPart",
    "assign_nearest_parts",
]
