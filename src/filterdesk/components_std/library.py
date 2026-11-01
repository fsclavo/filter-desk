"""Curated component catalog and versioned JSON import/export.

This is a catalog of real manufacturer part numbers with basic datasheet
values.  It is not a vendor SPICE/model redistribution: electrical model fields
that are not listed stay ``None`` and must be verified/imported by the user.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from filterdesk.domain.units import format_engineering

_FORMAT = "filterdesk.components"
_VERSION = 1
_KINDS = {"capacitor", "inductor"}


class ComponentLibraryError(ValueError):
    """Raised for an invalid component library document."""


@dataclass(frozen=True, slots=True)
class LibraryPart:
    id: str
    manufacturer: str
    mpn: str
    kind: str
    value_si: float
    unit: str
    package: str
    tolerance_pct: float | None = None
    voltage_v: float | None = None
    current_a: float | None = None
    dcr_ohm: float | None = None
    srf_hz: float | None = None
    q_min: float | None = None
    esr_ohm: float | None = None
    esl_h: float | None = None
    source: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.mpn.strip():
            raise ComponentLibraryError("part id and MPN must not be empty")
        if self.kind not in _KINDS:
            raise ComponentLibraryError(f"unsupported part kind: {self.kind!r}")
        if self.value_si <= 0.0:
            raise ComponentLibraryError("part value must be > 0")
        if self.tolerance_pct is not None and self.tolerance_pct < 0.0:
            raise ComponentLibraryError("tolerance must be >= 0")

    @property
    def value_text(self) -> str:
        return format_engineering(self.value_si, self.unit, digits=6)


# Curated starter catalog. Basic values from public manufacturer datasheets;
# model-level parasitics are intentionally left unset unless the datasheet
# provides a directly usable number.
STARTER_PARTS: tuple[LibraryPart, ...] = (
    LibraryPart(
        "murata-grm1885c1h100ja01d",
        "Murata",
        "GRM1885C1H100JA01D",
        "capacitor",
        10e-12,
        "F",
        "0603",
        5.0,
        50.0,
        q_min=1000.0,
        source="https://www.murata.com/en-global/products/productdetail?partno=GRM1885C1H100JA01D",
        notes="C0G/NP0; verify current datasheet.",
    ),
    LibraryPart(
        "murata-grm1885c1h220ja01d",
        "Murata",
        "GRM1885C1H220JA01D",
        "capacitor",
        22e-12,
        "F",
        "0603",
        5.0,
        50.0,
        q_min=1000.0,
        source="https://www.murata.com/en-global/products/productdetail?partno=GRM1885C1H220JA01D",
        notes="C0G/NP0; verify current datasheet.",
    ),
    LibraryPart(
        "murata-grm1885c1h470ja01d",
        "Murata",
        "GRM1885C1H470JA01D",
        "capacitor",
        47e-12,
        "F",
        "0603",
        5.0,
        50.0,
        q_min=1000.0,
        source="https://www.murata.com/en-global/products/productdetail?partno=GRM1885C1H470JA01D",
        notes="C0G/NP0; verify current datasheet.",
    ),
    LibraryPart(
        "murata-grm1885c1h101ja01d",
        "Murata",
        "GRM1885C1H101JA01D",
        "capacitor",
        100e-12,
        "F",
        "0603",
        5.0,
        50.0,
        q_min=1000.0,
        source="https://www.murata.com/en-global/products/productdetail?partno=GRM1885C1H101JA01D",
        notes="C0G/NP0; Q>=1000 at 1 MHz; verify current datasheet.",
    ),
    LibraryPart(
        "murata-grm1885c1h102ja01d",
        "Murata",
        "GRM1885C1H102JA01D",
        "capacitor",
        1e-9,
        "F",
        "0603",
        5.0,
        50.0,
        q_min=1000.0,
        source="https://www.murata.com/en-global/products/productdetail?partno=GRM1885C1H102JA01D",
        notes="C0G/NP0; verify current datasheet.",
    ),
    LibraryPart(
        "coilcraft-0603cs-10nxjrw",
        "Coilcraft",
        "0603CS-10NXJRW",
        "inductor",
        10e-9,
        "H",
        "0603",
        5.0,
        current_a=0.7,
        dcr_ohm=0.13,
        srf_hz=4.8e9,
        q_min=31.0,
        source="https://www.coilcraft.com/en-us/products/rf/ceramic-core-chip-inductors/0603-(1608)/0603cs/",
        notes="Q min at 250 MHz; Irms is a 15 C rise reference; verify datasheet.",
    ),
    LibraryPart(
        "coilcraft-0603cs-22nxjrw",
        "Coilcraft",
        "0603CS-22NXJRW",
        "inductor",
        22e-9,
        "H",
        "0603",
        5.0,
        current_a=0.7,
        dcr_ohm=0.19,
        srf_hz=3.0e9,
        q_min=38.0,
        source="https://www.coilcraft.com/en-us/products/rf/ceramic-core-chip-inductors/0603-(1608)/0603cs/",
        notes="Q min at 250 MHz; Irms is a 15 C rise reference; verify datasheet.",
    ),
    LibraryPart(
        "coilcraft-0603cs-47nxjrw",
        "Coilcraft",
        "0603CS-47NXJRW",
        "inductor",
        47e-9,
        "H",
        "0603",
        5.0,
        current_a=0.6,
        dcr_ohm=0.28,
        srf_hz=2.0e9,
        q_min=38.0,
        source="https://www.coilcraft.com/en-us/products/rf/ceramic-core-chip-inductors/0603-(1608)/0603cs/",
        notes="Q min at 250 MHz; Irms is a 15 C rise reference; verify datasheet.",
    ),
    LibraryPart(
        "coilcraft-0603cs-r10xjrw",
        "Coilcraft",
        "0603CS-R10XJRW",
        "inductor",
        100e-9,
        "H",
        "0603",
        5.0,
        current_a=0.4,
        dcr_ohm=0.58,
        srf_hz=1.4e9,
        q_min=34.0,
        source="https://www.coilcraft.com/en-us/products/rf/ceramic-core-chip-inductors/0603-(1608)/0603cs/",
        notes="Q min at 250 MHz; Irms is a 15 C rise reference; verify datasheet.",
    ),
    LibraryPart(
        "coilcraft-0603cs-r22xjrw",
        "Coilcraft",
        "0603CS-R22XJRW",
        "inductor",
        220e-9,
        "H",
        "0603",
        5.0,
        current_a=0.2,
        dcr_ohm=2.1,
        srf_hz=0.9e9,
        q_min=25.0,
        source="https://www.coilcraft.com/en-us/products/rf/ceramic-core-chip-inductors/0603-(1608)/0603cs/",
        notes="Q min at 250 MHz; Irms is a 15 C rise reference; verify datasheet.",
    ),
)


def search_parts(
    parts: tuple[LibraryPart, ...] | list[LibraryPart],
    *,
    kind: str | None = None,
    query: str = "",
) -> list[LibraryPart]:
    """Filter by kind and a case-insensitive MPN/manufacturer/package query."""
    needle = query.strip().lower().replace(" ", "")
    result: list[LibraryPart] = []
    for part in parts:
        if kind is not None and part.kind != kind:
            continue
        haystack = " ".join(
            (
                part.mpn,
                part.manufacturer,
                part.kind,
                part.package,
                part.value_text,
                part.notes,
            )
        ).lower().replace(" ", "")
        if needle and needle not in haystack:
            continue
        result.append(part)
    return sorted(result, key=lambda part: (part.kind, part.value_si, part.mpn))


def nearest_part(
    parts: tuple[LibraryPart, ...] | list[LibraryPart],
    *,
    kind: str,
    value_si: float,
) -> LibraryPart | None:
    """Return the closest same-kind part by absolute value."""
    candidates = [part for part in parts if part.kind == kind]
    if not candidates:
        return None
    return min(candidates, key=lambda part: abs(part.value_si - value_si))


def library_to_mapping(
    parts: tuple[LibraryPart, ...] | list[LibraryPart],
) -> dict[str, Any]:
    return {
        "format": _FORMAT,
        "version": _VERSION,
        "parts": [_part_to_mapping(part) for part in parts],
    }


def library_from_mapping(data: dict[str, Any]) -> tuple[LibraryPart, ...]:
    if data.get("format") != _FORMAT:
        raise ComponentLibraryError(f"unsupported format: {data.get('format')!r}")
    if data.get("version") != _VERSION:
        raise ComponentLibraryError(f"unsupported version: {data.get('version')!r}")
    raw_parts = data.get("parts")
    if not isinstance(raw_parts, list) or not raw_parts:
        raise ComponentLibraryError("library needs a non-empty 'parts' list")
    try:
        parts = tuple(_part_from_mapping(part) for part in raw_parts)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ComponentLibraryError):
            raise
        raise ComponentLibraryError(f"invalid component library: {exc}") from exc
    return parts


def read_component_library(path: Path | str) -> tuple[LibraryPart, ...]:
    target = Path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComponentLibraryError(f"cannot read {target}: {exc}") from exc
    if not isinstance(data, dict):
        raise ComponentLibraryError("library root must be an object")
    return library_from_mapping(data)


def write_component_library(
    parts: tuple[LibraryPart, ...] | list[LibraryPart], path: Path | str
) -> Path:
    target = Path(path)
    target.write_text(
        json.dumps(library_to_mapping(parts), indent=2) + "\n", encoding="utf-8"
    )
    return target


def _part_to_mapping(part: LibraryPart) -> dict[str, Any]:
    return {
        "id": part.id,
        "manufacturer": part.manufacturer,
        "mpn": part.mpn,
        "kind": part.kind,
        "value_si": part.value_si,
        "unit": part.unit,
        "package": part.package,
        "tolerance_pct": part.tolerance_pct,
        "voltage_v": part.voltage_v,
        "current_a": part.current_a,
        "dcr_ohm": part.dcr_ohm,
        "srf_hz": part.srf_hz,
        "q_min": part.q_min,
        "esr_ohm": part.esr_ohm,
        "esl_h": part.esl_h,
        "source": part.source,
        "notes": part.notes,
    }


def _part_from_mapping(data: dict[str, Any]) -> LibraryPart:
    return LibraryPart(
        id=str(data["id"]),
        manufacturer=str(data["manufacturer"]),
        mpn=str(data["mpn"]),
        kind=str(data["kind"]),
        value_si=float(data["value_si"]),
        unit=str(data["unit"]),
        package=str(data.get("package", "")),
        tolerance_pct=_optional_float(data.get("tolerance_pct")),
        voltage_v=_optional_float(data.get("voltage_v")),
        current_a=_optional_float(data.get("current_a")),
        dcr_ohm=_optional_float(data.get("dcr_ohm")),
        srf_hz=_optional_float(data.get("srf_hz")),
        q_min=_optional_float(data.get("q_min")),
        esr_ohm=_optional_float(data.get("esr_ohm")),
        esl_h=_optional_float(data.get("esl_h")),
        source=str(data.get("source", "")),
        notes=str(data.get("notes", "")),
    )


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


__all__ = [
    "ComponentLibraryError",
    "LibraryPart",
    "STARTER_PARTS",
    "library_from_mapping",
    "library_to_mapping",
    "nearest_part",
    "read_component_library",
    "search_parts",
    "write_component_library",
]
