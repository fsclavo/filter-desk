"""BOM / build-sheet export (Phase 12 #7).

Writes one row per physical part (compound elements expanded) as CSV, or a
human-readable build sheet as Markdown / HTML with the specification summary.
"""

from __future__ import annotations

import csv
import html
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from filterdesk.analysis.stress import StressReport
from filterdesk.domain.circuit import (
    Circuit,
    PhysicalComponent,
    physical_components,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.domain.units import format_engineering


class BuildSheetError(ValueError):
    """Raised for an unsupported output format."""


@dataclass(frozen=True, slots=True)
class BuildSheetRow:
    """One BOM line with optional tolerance and stress annotations."""

    ref: str
    role: str
    kind: str
    value: float
    unit: str
    value_text: str
    tolerance_pct: float | None = None
    parasitic: str = ""
    v_peak_v: float | None = None
    i_peak_a: float | None = None


BOM_COLUMNS: tuple[str, ...] = (
    "ref",
    "role",
    "type",
    "value",
    "value_si",
    "unit",
    "tolerance_pct",
    "parasitic",
    "v_peak_v",
    "i_peak_a",
)


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


def build_sheet_rows(
    circuit: Circuit,
    *,
    tolerances: Mapping[str, float] | None = None,
    stress: StressReport | None = None,
) -> list[BuildSheetRow]:
    """Expand ``circuit`` into BOM rows (optionally with tolerances and stress)."""
    tol = tolerances or {}
    by_ref = {e.ref: e for e in stress.entries} if stress is not None else {}
    rows: list[BuildSheetRow] = []
    for comp in physical_components(circuit):
        entry = by_ref.get(comp.ref)
        rows.append(
            BuildSheetRow(
                ref=comp.ref,
                role=comp.role,
                kind=comp.kind,
                value=comp.value,
                unit=comp.unit,
                value_text=format_engineering(comp.value, comp.unit, digits=6),
                tolerance_pct=tol.get(comp.ref),
                parasitic=_parasitic_text(comp),
                v_peak_v=entry.v_peak_v if entry is not None else None,
                i_peak_a=entry.i_peak_a if entry is not None else None,
            )
        )
    return rows


def _format_tolerance(value: float | None) -> str:
    return "" if value is None else f"{value:g}%"


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


def render_bom_csv(rows: Sequence[BuildSheetRow]) -> str:
    """Render a machine-readable BOM table (one row per physical part)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(BOM_COLUMNS)
    for row in rows:
        writer.writerow(
            [
                row.ref,
                row.role,
                row.kind,
                row.value_text,
                f"{row.value:.6g}",
                row.unit,
                "" if row.tolerance_pct is None else f"{row.tolerance_pct:g}",
                row.parasitic,
                "" if row.v_peak_v is None else f"{row.v_peak_v:.4g}",
                "" if row.i_peak_a is None else f"{row.i_peak_a:.4g}",
            ]
        )
    return buf.getvalue()


def _table_cells(row: BuildSheetRow) -> list[str]:
    return [
        row.ref,
        row.role,
        row.kind,
        row.value_text,
        _format_tolerance(row.tolerance_pct),
        row.parasitic,
        "" if row.v_peak_v is None else f"{row.v_peak_v:.4g}",
        "" if row.i_peak_a is None else f"{row.i_peak_a:.4g}",
    ]


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
        "| Ref | Role | Type | Value | Tol | Parasitic | Vpk | Ipk |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
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

    headers = ["Ref", "Role", "Type", "Value", "Tol", "Parasitic", "Vpk", "Ipk"]
    parts += ["<h2>Bill of materials</h2>", "<table>", "<tr>"]
    parts += [f"<th>{head}</th>" for head in headers]
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
) -> Path:
    """Write a build sheet, choosing the format from the file extension.

    ``.csv`` writes the BOM table only; ``.md``/``.markdown`` and
    ``.html``/``.htm`` include the specification summary and notes.
    """
    target = Path(path)
    rows = build_sheet_rows(circuit, tolerances=tolerances, stress=stress)
    suffix = target.suffix.lower()
    if suffix == ".csv":
        text = render_bom_csv(rows)
    elif suffix in {".md", ".markdown"}:
        text = render_build_sheet_markdown(
            rows, spec=spec, power_w=power_w, title=title, notes=notes
        )
    elif suffix in {".html", ".htm"}:
        text = render_build_sheet_html(
            rows, spec=spec, power_w=power_w, title=title, notes=notes
        )
    else:
        raise BuildSheetError(
            f"unsupported build-sheet extension {suffix!r} (use .csv, .md or .html)"
        )
    target.write_text(text, encoding="utf-8")
    return target
