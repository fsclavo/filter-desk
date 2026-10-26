"""BOM / build-sheet export (Phase 12 #7).

Writes one row per physical part (compound elements expanded) as CSV, or a
human-readable build sheet as Markdown / HTML with the specification summary.

Rows can optionally be snapped to an E-series (nearest preferred value and the
relative change) and grouped by part (combined refs + quantity). Winding columns
are populated when a component carries winding metadata.
"""

from __future__ import annotations

import csv
import html
import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from filterdesk.analysis.stress import StressReport
from filterdesk.components_std import ESeries, nearest_e_series
from filterdesk.domain.circuit import (
    Circuit,
    PhysicalComponent,
    physical_components,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.domain.units import format_engineering


class BuildSheetError(ValueError):
    """Raised for an unsupported output format or column."""


@dataclass(frozen=True, slots=True)
class BuildSheetRow:
    """One BOM line with optional tolerance, stress and realization details."""

    ref: str
    role: str
    kind: str
    value: float
    unit: str
    value_text: str
    qty: int = 1
    tolerance_pct: float | None = None
    parasitic: str = ""
    v_peak_v: float | None = None
    i_peak_a: float | None = None
    series: str | None = None
    nearest_value: float | None = None
    delta_pct: float | None = None
    dcr_ohm: float | None = None
    srf_hz: float | None = None
    core: str = ""
    turns: int | None = None
    wire_awg: int | None = None


BOM_COLUMNS: tuple[str, ...] = (
    "ref",
    "qty",
    "role",
    "type",
    "value",
    "value_si",
    "unit",
    "series",
    "nearest_value",
    "delta_pct",
    "tolerance_pct",
    "parasitic",
    "dcr_ohm",
    "srf_hz",
    "core",
    "turns",
    "wire_awg",
    "v_peak_v",
    "i_peak_a",
)

#: Columns shown in the human-readable Markdown/HTML tables (kept compact).
_SHEET_COLUMNS: tuple[str, ...] = (
    "ref",
    "role",
    "type",
    "value",
    "tolerance_pct",
    "parasitic",
    "v_peak_v",
    "i_peak_a",
    "series",
    "nearest_value",
    "delta_pct",
    "dcr_ohm",
    "srf_hz",
    "core",
    "turns",
    "wire_awg",
)
_SHEET_HEADERS: tuple[str, ...] = (
    "Ref",
    "Role",
    "Type",
    "Value",
    "Tol",
    "Parasitic",
    "Vpk",
    "Ipk",
    "Series",
    "Nearest",
    "d%",
    "DCR",
    "SRF",
    "Core",
    "Turns",
    "AWG",
)


def _balun_value_text(comp: PhysicalComponent) -> str:
    winding = comp.winding
    if winding is None or winding.turns is None:
        return f"{comp.value:.4g}:1"
    secondary = winding.turns_secondary
    if secondary is None:
        return f"{winding.turns}T"
    if secondary >= winding.turns:
        turns = f"1:{secondary / winding.turns:.3g}"
    else:
        turns = f"{winding.turns / secondary:.3g}:1"
    impedance = (
        f"{winding.impedance_ratio:.4g}"
        if winding.impedance_ratio is not None
        else "?"
    )
    return f"{turns} turns / {impedance} Z"


def _parasitic_text(comp: PhysicalComponent) -> str:
    parts: list[str] = []
    if comp.series_resistance_ohm:
        parts.append(f"R={format_engineering(comp.series_resistance_ohm, 'Ohm')}")
    if comp.parallel_capacitance_f:
        parts.append(f"Cp={format_engineering(comp.parallel_capacitance_f, 'F')}")
    if comp.esr_ohm:
        parts.append(f"ESR={format_engineering(comp.esr_ohm, 'Ohm')}")
    if comp.esl_h:
        parts.append(f"ESL={format_engineering(comp.esl_h, 'H')}")
    return "  ".join(parts)


def _component_srf_hz(comp: PhysicalComponent) -> float | None:
    if comp.kind == "inductor" and comp.parallel_capacitance_f > 0.0:
        return 1.0 / (
            2.0 * math.pi * math.sqrt(comp.value * comp.parallel_capacitance_f)
        )
    if comp.kind == "capacitor" and comp.esl_h > 0.0:
        return 1.0 / (2.0 * math.pi * math.sqrt(comp.esl_h * comp.value))
    return None


def _nearest(value: float, series: ESeries) -> tuple[float, float]:
    snapped = nearest_e_series(value, series)
    delta_pct = 100.0 * (snapped - value) / value
    return snapped, delta_pct


def _group_key(row: BuildSheetRow) -> tuple[object, ...]:
    if row.series is not None and row.nearest_value is not None:
        part = (row.kind, row.series, round(row.nearest_value, 15))
    else:
        part = (row.kind, row.value_text, round(row.value, 15))
    return (part, row.tolerance_pct, row.core, row.turns, row.wire_awg)


def _max_optional(a: float | None, b: float | None) -> float | None:
    values = [value for value in (a, b) if value is not None]
    return max(values) if values else None


def _group_rows(rows: list[BuildSheetRow]) -> list[BuildSheetRow]:
    grouped: dict[tuple[object, ...], BuildSheetRow] = {}
    order: list[tuple[object, ...]] = []
    for row in rows:
        key = _group_key(row)
        if key not in grouped:
            grouped[key] = row
            order.append(key)
            continue
        existing = grouped[key]
        grouped[key] = replace(
            existing,
            ref=f"{existing.ref}, {row.ref}",
            qty=existing.qty + row.qty,
            v_peak_v=_max_optional(existing.v_peak_v, row.v_peak_v),
            i_peak_a=_max_optional(existing.i_peak_a, row.i_peak_a),
        )
    return [grouped[key] for key in order]


def build_sheet_rows(
    circuit: Circuit,
    *,
    tolerances: Mapping[str, float] | None = None,
    stress: StressReport | None = None,
    series: ESeries | None = None,
    group: bool = False,
) -> list[BuildSheetRow]:
    """Expand ``circuit`` into BOM rows (optionally snapped and grouped)."""
    tol = tolerances or {}
    by_ref = {e.ref: e for e in stress.entries} if stress is not None else {}
    rows: list[BuildSheetRow] = []
    for comp in physical_components(circuit):
        entry = by_ref.get(comp.ref)
        series_tag: str | None = None
        nearest: float | None = None
        delta: float | None = None
        if (
            series is not None
            and comp.kind in {"inductor", "capacitor"}
            and comp.value > 0.0
        ):
            series_tag = series.value
            nearest, delta = _nearest(comp.value, series)
        rows.append(
            BuildSheetRow(
                ref=comp.ref,
                role=comp.role,
                kind=comp.kind,
                value=comp.value,
                unit=comp.unit,
                value_text=(
                    (
                        _balun_value_text(comp)
                        if comp.kind == "balun"
                        else f"{comp.value:.4g}:1"
                    )
                    if comp.kind in {"transformer", "balun"}
                    else format_engineering(comp.value, comp.unit, digits=6)
                ),
                tolerance_pct=tol.get(comp.ref),
                parasitic=(
                    "ideal"
                    if comp.kind == "transformer"
                    else (
                        f"balun {comp.winding.material} {comp.winding.topology}"
                        if comp.kind == "balun" and comp.winding is not None
                        else _parasitic_text(comp)
                    )
                ),
                v_peak_v=entry.v_peak_v if entry is not None else None,
                i_peak_a=entry.i_peak_a if entry is not None else None,
                series=series_tag,
                nearest_value=nearest,
                delta_pct=delta,
                dcr_ohm=(
                    comp.series_resistance_ohm
                    if comp.kind == "inductor"
                    and comp.series_resistance_ohm > 0.0
                    else None
                ),
                srf_hz=(
                    comp.srf_hz
                    if comp.srf_hz is not None
                    else _component_srf_hz(comp)
                ),
                core=comp.winding.core if comp.winding is not None else "",
                turns=comp.winding.turns if comp.winding is not None else None,
                wire_awg=(
                    comp.winding.wire_awg if comp.winding is not None else None
                ),
            )
        )
    return _group_rows(rows) if group else rows


def _column_value(row: BuildSheetRow, column: str, *, human: bool = False) -> str:
    if column == "ref":
        return row.ref
    if column == "qty":
        return str(row.qty)
    if column == "role":
        return row.role
    if column == "type":
        return row.kind
    if column == "value":
        return row.value_text
    if column == "value_si":
        return f"{row.value:.6g}"
    if column == "unit":
        return row.unit
    if column == "series":
        return row.series or ""
    if column == "nearest_value":
        if row.nearest_value is None:
            return ""
        return (
            format_engineering(row.nearest_value, row.unit, digits=6)
            if human
            else f"{row.nearest_value:.6g}"
        )
    if column == "delta_pct":
        return "" if row.delta_pct is None else f"{row.delta_pct:+.2f}"
    if column == "tolerance_pct":
        return "" if row.tolerance_pct is None else f"{row.tolerance_pct:g}"
    if column == "parasitic":
        return row.parasitic
    if column == "dcr_ohm":
        return "" if row.dcr_ohm is None else f"{row.dcr_ohm:.4g}"
    if column == "srf_hz":
        if row.srf_hz is None:
            return ""
        return (
            format_engineering(row.srf_hz, "Hz", digits=6)
            if human
            else f"{row.srf_hz:.6g}"
        )
    if column == "core":
        return row.core
    if column == "turns":
        return "" if row.turns is None else str(row.turns)
    if column == "wire_awg":
        return "" if row.wire_awg is None else str(row.wire_awg)
    if column == "v_peak_v":
        return "" if row.v_peak_v is None else f"{row.v_peak_v:.4g}"
    if column == "i_peak_a":
        return "" if row.i_peak_a is None else f"{row.i_peak_a:.4g}"
    raise BuildSheetError(f"unknown column: {column!r}")


def summary_pairs(
    spec: FilterSpec | None,
    *,
    power_w: float = 0.0,
) -> list[tuple[str, str]]:
    """Specification rows for the build-sheet header (empty without a spec)."""
    if spec is None:
        return []
    pairs: list[tuple[str, str]] = [
        ("Family", spec.family.value),
        ("Response", spec.response.value),
        ("Order", str(spec.order)),
    ]
    if spec.cutoff_hz > 0.0:
        pairs.append(("Cutoff", format_engineering(spec.cutoff_hz, "Hz", digits=6)))
    if spec.f_center_hz is not None:
        pairs.append(
            ("Center", format_engineering(spec.f_center_hz, "Hz", digits=6))
        )
    if spec.bandwidth_hz is not None:
        pairs.append(
            ("Bandwidth", format_engineering(spec.bandwidth_hz, "Hz", digits=6))
        )
    pairs.append(("Source Z", format_engineering(spec.z_source_ohm, "Ohm")))
    pairs.append(("Load Z", format_engineering(spec.z_load_ohm, "Ohm")))
    if spec.passband_ripple_db is not None:
        pairs.append(("Passband ripple", f"{spec.passband_ripple_db:g} dB"))
    if spec.stopband_attenuation_db is not None:
        pairs.append(("Stopband attenuation", f"{spec.stopband_attenuation_db:g} dB"))
    if spec.m_parameter is not None:
        pairs.append(("m parameter", f"{spec.m_parameter:g}"))
    if power_w > 0.0:
        pairs.append(("Forward power", f"{power_w:g} W"))
    return pairs


def render_bom_csv(
    rows: Sequence[BuildSheetRow],
    *,
    columns: Sequence[str] | None = None,
) -> str:
    """Render a machine-readable BOM table (one row per physical part)."""
    selected = tuple(columns) if columns is not None else BOM_COLUMNS
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(selected)
    for row in rows:
        writer.writerow([_column_value(row, column) for column in selected])
    return buf.getvalue()


def _table_cells(row: BuildSheetRow) -> list[str]:
    return [_column_value(row, column, human=True) for column in _SHEET_COLUMNS]


def render_build_sheet_markdown(
    rows: Sequence[BuildSheetRow],
    *,
    spec: FilterSpec | None = None,
    power_w: float = 0.0,
    title: str = "",
    notes: Sequence[str] = (),
) -> str:
    """Render a Markdown build sheet (spec summary + BOM + notes)."""
    lines: list[str] = [f"# {title.strip() or 'Filter build sheet'}"]

    pairs = summary_pairs(spec, power_w=power_w)
    if pairs:
        lines += ["", "## Specification", "", "| Item | Value |", "| --- | --- |"]
        lines += [f"| {key} | {value} |" for key, value in pairs]

    lines += [
        "",
        "## Bill of materials",
        "",
        "| " + " | ".join(_SHEET_HEADERS) + " |",
        "| " + " | ".join("---" for _ in _SHEET_HEADERS) + " |",
    ]
    lines += ["| " + " | ".join(_table_cells(row)) + " |" for row in rows]

    if notes:
        lines += ["", "## Notes", ""]
        lines += [f"- {note}" for note in notes]

    lines.append("")
    return "\n".join(lines)


def render_build_sheet_html(
    rows: Sequence[BuildSheetRow],
    *,
    spec: FilterSpec | None = None,
    power_w: float = 0.0,
    title: str = "",
    notes: Sequence[str] = (),
) -> str:
    """Render a printable HTML build sheet (no external assets)."""
    heading = html.escape(title.strip() or "Filter build sheet")
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{heading}</title>",
        "<style>",
        "body{font-family:sans-serif;margin:2rem;color:#111}",
        "table{border-collapse:collapse;margin-top:.5rem}",
        "th,td{border:1px solid #999;padding:.3rem .5rem;text-align:left}",
        "th{background:#eee}",
        "h1{margin-bottom:.2rem}",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{heading}</h1>",
    ]

    pairs = summary_pairs(spec, power_w=power_w)
    if pairs:
        parts += ["<h2>Specification</h2>", "<table>"]
        parts += [
            f"<tr><th>{html.escape(key)}</th><td>{html.escape(value)}</td></tr>"
            for key, value in pairs
        ]
        parts.append("</table>")

    parts += ["<h2>Bill of materials</h2>", "<table>", "<tr>"]
    parts += [f"<th>{head}</th>" for head in _SHEET_HEADERS]
    parts += ["</tr>"]
    for row in rows:
        parts.append("<tr>")
        parts += [f"<td>{html.escape(cell)}</td>" for cell in _table_cells(row)]
        parts.append("</tr>")
    parts.append("</table>")

    if notes:
        parts.append("<h2>Notes</h2>")
        parts.append("<ul>")
        parts += [f"<li>{html.escape(note)}</li>" for note in notes]
        parts.append("</ul>")

    parts += ["</body>", "</html>", ""]
    return "\n".join(parts)


def write_build_sheet(
    circuit: Circuit,
    path: Path | str,
    *,
    spec: FilterSpec | None = None,
    tolerances: Mapping[str, float] | None = None,
    stress: StressReport | None = None,
    power_w: float = 0.0,
    title: str = "",
    notes: Sequence[str] = (),
    series: ESeries | None = None,
    group: bool = False,
    columns: Sequence[str] | None = None,
) -> Path:
    """Write a build sheet, choosing the format from the file extension.

    ``.csv`` writes the BOM table only; ``.md``/``.markdown`` and
    ``.html``/``.htm`` include the specification summary and notes. ``series``
    snaps L/C to an E-series; ``group`` merges identical parts by quantity.
    """
    target = Path(path)
    rows = build_sheet_rows(
        circuit,
        tolerances=tolerances,
        stress=stress,
        series=series,
        group=group,
    )
    suffix = target.suffix.lower()
    if suffix == ".csv":
        text = render_bom_csv(rows, columns=columns)
    elif suffix in {".md", ".markdown"}:
        text = render_build_sheet_markdown(
            rows,
            spec=spec,
            power_w=power_w,
            title=title,
            notes=notes,
        )
    elif suffix in {".html", ".htm"}:
        text = render_build_sheet_html(
            rows,
            spec=spec,
            power_w=power_w,
            title=title,
            notes=notes,
        )
    else:
        raise BuildSheetError(
            f"unsupported build-sheet extension {suffix!r} (use .csv, .md or .html)"
        )
    target.write_text(text, encoding="utf-8")
    return target


__all__ = [
    "BOM_COLUMNS",
    "BuildSheetError",
    "BuildSheetRow",
    "build_sheet_rows",
    "render_bom_csv",
    "render_build_sheet_html",
    "render_build_sheet_markdown",
    "summary_pairs",
    "write_build_sheet",
]
