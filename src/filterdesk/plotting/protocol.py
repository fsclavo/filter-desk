"""Plot backend abstraction for static figure export (blueprint §24).

The GUI renders interactive curves with PyQtGraph directly; this protocol covers
the *static* rendering/export path so backends (e.g. Matplotlib) can be swapped
without touching callers.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from filterdesk.analysis.types import AnalysisResult
    from filterdesk.domain.overlays import Marker


@runtime_checkable
class PlotBackend(Protocol):
    """A backend able to render/export a Smith chart from an analysis result."""

    name: str

    def render_smith_chart(
        self,
        result: AnalysisResult,
        *,
        markers: Sequence[Marker] | None = None,
        title: str = "Smith chart — S11 / S22",
        figsize: tuple[float, float] = (6.0, 6.0),
    ) -> object:
        """Build an in-memory figure object (backend-specific)."""
        ...

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
        """Render and write a Smith chart image (format from path suffix)."""
        ...
