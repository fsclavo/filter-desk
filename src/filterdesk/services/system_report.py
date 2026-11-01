"""Standalone HTML system report with embedded magnitude and schematics."""

from __future__ import annotations

import base64
import html as html_mod
import io
from collections.abc import Sequence
from datetime import UTC, datetime

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from filterdesk import __version__
from filterdesk.io.build_sheet import render_multiplexer_bom_table_html
from filterdesk.services.diplexer import BandDiplexerDesign, DiplexerDesign
from filterdesk.services.duplexer import DuplexerDesign
from filterdesk.services.multiplexer import MultiplexerDesign
from filterdesk.services.report import system_report
from filterdesk.services.system_rebuild import SystemDesign


def render_magnitude_png(
    design: SystemDesign,
    *,
    width_in: float = 9.0,
    height_in: float = 4.8,
    dpi: int = 140,
) -> bytes:
    """Render the combined-system magnitude response as a PNG."""
    network = design.network
    frequencies = np.asarray(network.frequency_hz, dtype=float)
    fig = Figure(figsize=(width_in, height_in), dpi=dpi)
    _canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    labels, outputs = _output_curves(design)
    for label, values in zip(labels, outputs, strict=True):
        ax.semilogx(frequencies, _db(values), label=label)
    ax.semilogx(frequencies, _db(network.s[:, 0, 0]), label="S11 (input)")
    isolation = _isolation_curve(design)
    if isolation is not None:
        ax.semilogx(
            frequencies,
            _db(isolation),
            label="Worst isolation",
            linestyle="--",
            color="#666666",
        )
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Magnitude (dB)")
    ax.set_title("Magnitude")
    ax.set_ylim(-160.0, 5.0)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(loc="best", fontsize="small")
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight")
    return buffer.getvalue()


def render_system_report_html(
    design: SystemDesign,
    *,
    schematic_images: Sequence[tuple[str, bytes]] = (),
    notes: Sequence[str] = (),
    title: str | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Render a self-contained, printable HTML report."""
    report = system_report(design)
    heading = html_mod.escape(title or f"System report — {report.title}")
    timestamp = (generated_at or datetime.now(UTC)).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    magnitude = base64.b64encode(render_magnitude_png(design)).decode("ascii")
    summary_rows = "".join(
        f"<tr><th>{html_mod.escape(key)}</th><td>{html_mod.escape(value)}</td></tr>"
        for key, value in report.summary
    )
    branches = [(branch.label, branch.circuit) for branch in report.branches]
    bom_table = render_multiplexer_bom_table_html(branches)
    schematic_parts: list[str] = []
    for label, png in schematic_images:
        encoded = base64.b64encode(png).decode("ascii")
        schematic_parts.append(
            f"<h3>{html_mod.escape(label)}</h3>"
            f'<img class="schematic" src="data:image/png;base64,{encoded}" '
            f'alt="{html_mod.escape(label)} schematic">'
        )
    all_notes = list(report.notes) + list(notes)
    notes_html = "".join(
        f"<li>{html_mod.escape(note)}</li>" for note in all_notes
    )
    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            f"<title>{heading}</title>",
            "<style>",
            "body{font-family:sans-serif;margin:2rem;color:#111;max-width:1100px}",
            "h1{margin-bottom:.2rem}",
            ".meta{color:#666;margin-bottom:1.5rem}",
            "table{border-collapse:collapse;margin:.5rem 0 1.5rem}",
            "th,td{border:1px solid #999;padding:.3rem .5rem;text-align:left}",
            "th{background:#eee}",
            "img{max-width:100%;height:auto}",
            "img.schematic{border:1px solid #ddd;margin-bottom:1rem}",
            "li{margin:.2rem 0}",
            "@media print{body{margin:0} h2{page-break-after:avoid}}",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{heading}</h1>",
            f'<div class="meta">Generated {timestamp} · FilterDesk {__version__}</div>',
            "<h2>System</h2>",
            f"<table>{summary_rows}</table>",
            "<h2>Magnitude</h2>",
            f'<img src="data:image/png;base64,{magnitude}" alt="Magnitude response">',
            "<h2>Schematics</h2>" if schematic_parts else "",
            *schematic_parts,
            "<h2>Bill of materials</h2>",
            bom_table,
            "<h2>Assumptions and notes</h2>",
            f"<ul>{notes_html}</ul>",
            "</body>",
            "</html>",
            "",
        ]
    )


def _output_curves(
    design: SystemDesign,
) -> tuple[list[str], list[np.ndarray]]:
    network = design.network
    if isinstance(design, MultiplexerDesign):
        return (
            [band.label.capitalize() for band in design.bands],
            [network.s[:, index + 1, 0] for index in range(len(design.bands))],
        )
    if isinstance(design, DuplexerDesign):
        return (
            ["TX", "RX"],
            [network.s[:, 1, 0], network.s[:, 2, 0]],
        )
    return (
        ["Low", "High"],
        [network.s[:, 1, 0], network.s[:, 2, 0]],
    )


def _isolation_curve(design: SystemDesign) -> np.ndarray | None:
    network = design.network
    if isinstance(design, MultiplexerDesign):
        pairs = [
            np.abs(network.s[:, column, row])
            for row in range(1, network.n_ports)
            for column in range(row + 1, network.n_ports)
        ]
        return np.maximum.reduce(pairs) if pairs else None
    if isinstance(design, (DiplexerDesign, BandDiplexerDesign, DuplexerDesign)):
        return np.abs(network.s[:, 2, 1])
    return None


def _db(values: np.ndarray) -> np.ndarray:
    return np.asarray(
        20.0 * np.log10(np.maximum(np.abs(values), 1e-15)),
        dtype=np.float64,
    )


__all__ = ["render_magnitude_png", "render_system_report_html"]
