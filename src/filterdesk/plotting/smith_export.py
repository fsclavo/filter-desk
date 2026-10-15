"""Matplotlib Smith-chart export from AnalysisResult."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from filterdesk.analysis.smith import smith_grid_polylines

if TYPE_CHECKING:
    from filterdesk.analysis.types import AnalysisResult
    from filterdesk.domain.overlays import Marker

_S11_COLOR = "#d62728"
_S22_COLOR = "#1f77b4"
_START_COLOR = "#2ca02c"
_STOP_COLOR = "#9467bd"
_MARKER_COLORS = (
    "#ff7f0e",
    "#17becf",
    "#bcbd22",
    "#e377c2",
    "#8c564b",
    "#7f7f7f",
    "#aec7e8",
    "#ffbb78",
)


def render_smith_figure(
    result: AnalysisResult,
    *,
    markers: Sequence[Marker] | None = None,
    title: str = "Smith chart — S11 / S22",
    figsize: tuple[float, float] = (6.0, 6.0),
) -> Figure:
    """Build a publication-style Smith chart figure (Agg canvas, no window)."""
    fig = Figure(figsize=figsize, constrained_layout=True)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_aspect("equal")
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.15, 1.15)
    ax.set_xlabel(r"Re($\Gamma$)")
    ax.set_ylabel(r"Im($\Gamma$)")
    ax.set_title(title)
    ax.axhline(0.0, color="#666666", linewidth=0.8, linestyle=":", zorder=0)
    ax.axvline(0.0, color="#666666", linewidth=0.8, linestyle=":", zorder=0)

    for i, (re, im) in enumerate(smith_grid_polylines()):
        lw = 1.0 if i == 0 else 0.7
        color = "#888888" if i == 0 else "#aaaaaa"
        ax.plot(re, im, color=color, linewidth=lw, zorder=1)

    s11 = np.asarray(result.s11, dtype=np.complex128)
    ax.plot(
        s11.real,
        s11.imag,
        color=_S11_COLOR,
        linewidth=1.8,
        label="S11",
        zorder=3,
    )
    s22 = np.asarray(result.s22, dtype=np.complex128)
    if s22.size == s11.size:
        ax.plot(
            s22.real,
            s22.imag,
            color=_S22_COLOR,
            linewidth=1.8,
            label="S22",
            zorder=3,
        )

    if s11.size:
        ax.scatter(
            [float(s11.real[0])],
            [float(s11.imag[0])],
            s=36,
            c=_START_COLOR,
            edgecolors="white",
            linewidths=0.8,
            zorder=4,
            label="S11 start",
        )
        ax.scatter(
            [float(s11.real[-1])],
            [float(s11.imag[-1])],
            s=36,
            c=_STOP_COLOR,
            edgecolors="white",
            linewidths=0.8,
            zorder=4,
            label="S11 stop",
        )

    freq = np.asarray(result.frequency_hz, dtype=float)
    if markers and freq.size and s11.size:
        for i, marker in enumerate(markers):
            idx = int(np.argmin(np.abs(freq - marker.frequency_hz)))
            g = s11[idx]
            color = _MARKER_COLORS[i % len(_MARKER_COLORS)]
            label = marker.label or marker.id
            ax.scatter(
                [float(g.real)],
                [float(g.imag)],
                s=42,
                c=color,
                edgecolors="white",
                linewidths=0.8,
                zorder=5,
                label=label,
            )

    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    return fig


def export_smith_chart(
    result: AnalysisResult,
    path: Path | str,
    *,
    markers: Sequence[Marker] | None = None,
    title: str = "Smith chart — S11 / S22",
    dpi: int = 150,
    figsize: tuple[float, float] = (6.0, 6.0),
) -> Path:
    """Render and write a Smith chart image (PNG/SVG/PDF from suffix)."""
    out = Path(path)
    suffix = out.suffix.lower()
    if suffix not in {".png", ".svg", ".pdf", ".jpg", ".jpeg", ".tif", ".tiff"}:
        raise ValueError(
            f"unsupported Smith export format '{out.suffix}' "
            "(use .png, .svg, .pdf, …)"
        )
    fig = render_smith_figure(
        result, markers=markers, title=title, figsize=figsize
    )
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=dpi, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)
    return out
