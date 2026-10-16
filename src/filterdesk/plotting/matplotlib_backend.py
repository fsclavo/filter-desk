"""Matplotlib implementation of the static plot backend."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from filterdesk.plotting.smith_export import (
    export_smith_chart,
    render_smith_figure,
)

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from filterdesk.analysis.types import AnalysisResult
    from filterdesk.domain.overlays import Marker


class MatplotlibBackend:
    """Static figure backend backed by Matplotlib (Agg canvas)."""

    name = "matplotlib"

    def render_smith_chart(
        self,
        result: AnalysisResult,
        *,
        markers: Sequence[Marker] | None = None,
        title: str = "Smith chart — S11 / S22",
        figsize: tuple[float, float] = (6.0, 6.0),
    ) -> Figure:
        return render_smith_figure(
            result, markers=markers, title=title, figsize=figsize
        )

    def save_smith_chart(
        self,
        result: AnalysisResult,
        path: Path | str,
        *,
        markers: Sequence[Marker] | None = None,
        title: str = "Smith chart — S11 / S22",
        dpi: int = 150,
        figsize: tuple[float, float] = (6.0, 6.0),
    ) -> Path:
        return export_smith_chart(
            result,
            path,
            markers=markers,
            title=title,
            dpi=dpi,
            figsize=figsize,
        )
