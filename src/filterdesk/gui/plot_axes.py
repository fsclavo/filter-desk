"""Shared log-frequency plot helpers for PyQtGraph panels."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg


def plain_decimal(value: float) -> str:
    """Format a tick without scientific notation (unit lives in the axis label)."""
    if not np.isfinite(value):
        return ""
    if value == 0.0:
        return "0"
    mag = abs(value)
    if mag >= 100.0:
        text = f"{value:.0f}"
    elif mag >= 10.0:
        text = f"{value:.1f}"
    elif mag >= 1.0:
        text = f"{value:.2f}"
    elif mag >= 0.1:
        text = f"{value:.2f}"
    else:
        text = f"{value:.3f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


class FreqAxisItem(pg.AxisItem):  # type: ignore[misc]
    """Log-frequency axis: SI-prefixed unit in the label, plain tick numbers."""

    def logTickStrings(
        self, values: list[float], scale: float, spacing: float
    ) -> list[str]:
        del spacing
        return [plain_decimal((10.0 ** float(v)) * float(scale)) for v in values]


def freq_plot(title: str) -> pg.PlotWidget:
    """Create a plot with the shared SI/log-frequency bottom axis."""
    plot = pg.PlotWidget(
        title=title,
        axisItems={"bottom": FreqAxisItem(orientation="bottom")},
    )
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.setLabel("bottom", "Frequency", units="Hz")
    return plot


__all__ = ["FreqAxisItem", "freq_plot", "plain_decimal"]
