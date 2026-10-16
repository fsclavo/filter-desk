"""Static / publication plotting helpers (Matplotlib)."""

from filterdesk.plotting.matplotlib_backend import MatplotlibBackend
from filterdesk.plotting.protocol import PlotBackend
from filterdesk.plotting.smith_export import (
    export_smith_chart,
    render_smith_figure,
)


def get_plot_backend(name: str = "matplotlib") -> PlotBackend:
    """Return the configured static plot backend (only Matplotlib for now)."""
    if name.lower() in {"matplotlib", "mpl"}:
        return MatplotlibBackend()
    raise ValueError(f"unknown plot backend: {name!r}")


__all__ = [
    "MatplotlibBackend",
    "PlotBackend",
    "export_smith_chart",
    "get_plot_backend",
    "render_smith_figure",
]
