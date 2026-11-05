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

from filterdesk.components_std.manufacturer_model import ManufacturerModel, ModelPoint
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
    model: ManufacturerModel | None = None

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


_COILCRAFT_0603CS_SOURCE = (
    "https://www.coilcraft.com/getmedia/"
    "022eb894-7253-40d0-b07c-650d362fc80e/0603cs.pdf"
)
_COILCRAFT_0603CS_NOTE = (
    "Q vs frequency from Coilcraft 0603CS Document 195-2 (rev. 06/26/24). "
    "The lowest-frequency point is Qmin at the datasheet test frequency; "
    "900 MHz and 1.7 GHz points are typical. Verify the current datasheet."
)


def _coilcraft_0603cs(
    mpn: str,
    value_nh: float,
    q_min: float,
    q_test_mhz: float,
    srf_ghz: float,
    dcr_ohm: float,
    irms_ma: float,
    q_points: tuple[tuple[float, float], ...],
) -> LibraryPart:
    """Build one 0603CS part with its datasheet Q(f) curve."""
    return LibraryPart(
        f"coilcraft-{mpn.lower()}",
        "Coilcraft",
        mpn,
        "inductor",
        value_nh * 1e-9,
        "H",
        "0603",
        5.0,
        current_a=irms_ma / 1000.0,
        dcr_ohm=dcr_ohm,
        srf_hz=srf_ghz * 1e9,
        q_min=q_min,
        source=_COILCRAFT_0603CS_SOURCE,
        notes=(
            f"Q min {q_min:g} at {q_test_mhz:g} MHz; "
            "Irms is a 15 C rise reference; verify datasheet."
        ),
        model=ManufacturerModel(
            model_id=f"coilcraft-0603cs-q-{mpn.lower()}",
            source=_COILCRAFT_0603CS_SOURCE,
            confidence="datasheet",
            notes=_COILCRAFT_0603CS_NOTE,
            q_points=tuple(
                ModelPoint(frequency_hz, value)
                for frequency_hz, value in q_points
            ),
        ),
    )


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
    _coilcraft_0603cs(
        "0603CS-3N9XJRW", 3.9, 22, 250, 6.9, 0.08, 700,
        ((2.5e+08, 22), (9e+08, 49), (1.7e+09, 67)),
    ),
    _coilcraft_0603cs(
        "0603CS-6N8XJRW", 6.8, 27, 250, 5.8, 0.11, 700,
        ((2.5e+08, 27), (9e+08, 60), (1.7e+09, 81)),
    ),
    _coilcraft_0603cs(
        "0603CS-10NXJRW", 10, 31, 250, 4.8, 0.13, 700,
        ((2.5e+08, 31), (9e+08, 66), (1.7e+09, 83)),
    ),
    _coilcraft_0603cs(
        "0603CS-12NXJRW", 12, 35, 250, 4, 0.13, 700,
        ((2.5e+08, 35), (9e+08, 72), (1.7e+09, 83)),
    ),
    _coilcraft_0603cs(
        "0603CS-18NXJRW", 18, 35, 250, 3.1, 0.17, 700,
        ((2.5e+08, 35), (9e+08, 70), (1.7e+09, 69)),
    ),
    _coilcraft_0603cs(
        "0603CS-22NXJRW", 22, 38, 250, 3, 0.19, 700,
        ((2.5e+08, 38), (9e+08, 73), (1.7e+09, 71)),
    ),
    _coilcraft_0603cs(
        "0603CS-27NXJRW", 27, 40, 250, 2.8, 0.22, 600,
        ((2.5e+08, 40), (9e+08, 74), (1.7e+09, 65)),
    ),
    _coilcraft_0603cs(
        "0603CS-33NXJRW", 33, 40, 250, 2.3, 0.22, 600,
        ((2.5e+08, 40), (9e+08, 67), (1.7e+09, 42)),
    ),
    _coilcraft_0603cs(
        "0603CS-39NXJRW", 39, 40, 250, 2.2, 0.25, 600,
        ((2.5e+08, 40), (9e+08, 60), (1.7e+09, 40)),
    ),
    _coilcraft_0603cs(
        "0603CS-47NXJRW", 47, 38, 200, 2, 0.28, 600,
        ((2e+08, 38), (9e+08, 62), (1.7e+09, 35)),
    ),
    _coilcraft_0603cs(
        "0603CS-68NXJRW", 68, 37, 200, 1.7, 0.34, 600,
        ((2e+08, 37), (9e+08, 54), (1.7e+09, 21)),
    ),
    _coilcraft_0603cs(
        "0603CS-82NXJRW", 82, 34, 150, 1.7, 0.54, 400,
        ((1.5e+08, 34), (9e+08, 54), (1.7e+09, 21)),
    ),
    _coilcraft_0603cs(
        "0603CS-R10XJRW", 100, 34, 150, 1.4, 0.58, 400,
        ((1.5e+08, 34), (9e+08, 49)),
    ),
    _coilcraft_0603cs(
        "0603CS-R12XJRW", 120, 32, 150, 1.3, 0.65, 300,
        ((1.5e+08, 32), (9e+08, 39)),
    ),
    _coilcraft_0603cs(
        "0603CS-R15XJRW", 150, 28, 150, 0.99, 0.92, 280,
        ((1.5e+08, 28), (9e+08, 25)),
    ),
    _coilcraft_0603cs(
        "0603CS-R18XJRW", 180, 25, 100, 0.99, 1.25, 240,
        ((1e+08, 25), (9e+08, 22)),
    ),
    _coilcraft_0603cs(
        "0603CS-R22XJRW", 220, 25, 100, 0.9, 2.1, 200,
        ((1e+08, 25),),
    ),
    _coilcraft_0603cs(
        "0603CS-R27XJRW", 270, 26, 100, 0.83, 2.16, 170,
        ((1e+08, 26),),
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
                "" if part.model is None else part.model.model_id,
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
        "model": None if part.model is None else part.model.to_mapping(),
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
        model=(
            None
            if data.get("model") is None
            else ManufacturerModel.from_mapping(data["model"])
        ),
    )


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


__all__ = [
    "ComponentLibraryError",
    "LibraryPart",
    "ManufacturerModel",
    "STARTER_PARTS",
    "library_from_mapping",
    "library_to_mapping",
    "nearest_part",
    "read_component_library",
    "search_parts",
    "write_component_library",
]
