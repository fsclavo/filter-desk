"""Light/dark application theme (palette + pyqtgraph colours)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pyqtgraph as pg
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class ThemeMode(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True, slots=True)
class ThemeColors:
    window: str
    window_text: str
    base: str
    alternate_base: str
    tooltip_base: str
    tooltip_text: str
    text: str
    button: str
    button_text: str
    highlight: str
    highlighted_text: str
    disabled_text: str
    placeholder: str
    link: str
    plot_background: str
    plot_foreground: str


LIGHT = ThemeColors(
    window="#f4f4f4",
    window_text="#202020",
    base="#ffffff",
    alternate_base="#f0f0f0",
    tooltip_base="#ffffdc",
    tooltip_text="#202020",
    text="#202020",
    button="#e9e9e9",
    button_text="#202020",
    highlight="#2a7de1",
    highlighted_text="#ffffff",
    disabled_text="#9a9a9a",
    placeholder="#8a8a8a",
    link="#1f6fbf",
    plot_background="#ffffff",
    plot_foreground="#202020",
)

DARK = ThemeColors(
    window="#2b2b2b",
    window_text="#e6e6e6",
    base="#1e1e1e",
    alternate_base="#262626",
    tooltip_base="#353535",
    tooltip_text="#e6e6e6",
    text="#e6e6e6",
    button="#353535",
    button_text="#e6e6e6",
    highlight="#3d7fbf",
    highlighted_text="#ffffff",
    disabled_text="#7a7a7a",
    placeholder="#8a8a8a",
    link="#6aa9e0",
    plot_background="#1e1e1e",
    plot_foreground="#cfcfcf",
)

_system_palette: QPalette | None = None
_system_style: str | None = None


def _capture_system(app: QApplication) -> None:
    global _system_palette, _system_style
    if _system_palette is None:
        _system_palette = QPalette(app.palette())
        _system_style = app.style().objectName()


def colors_from_palette(palette: QPalette) -> ThemeColors:
    def role(role: QPalette.ColorRole) -> str:
        return palette.color(role).name()

    return ThemeColors(
        window=role(QPalette.ColorRole.Window),
        window_text=role(QPalette.ColorRole.WindowText),
        base=role(QPalette.ColorRole.Base),
        alternate_base=role(QPalette.ColorRole.AlternateBase),
        tooltip_base=role(QPalette.ColorRole.ToolTipBase),
        tooltip_text=role(QPalette.ColorRole.ToolTipText),
        text=role(QPalette.ColorRole.Text),
        button=role(QPalette.ColorRole.Button),
        button_text=role(QPalette.ColorRole.ButtonText),
        highlight=role(QPalette.ColorRole.Highlight),
        highlighted_text=role(QPalette.ColorRole.HighlightedText),
        disabled_text=role(QPalette.ColorRole.WindowText),
        placeholder=role(QPalette.ColorRole.PlaceholderText),
        link=role(QPalette.ColorRole.Link),
        plot_background=role(QPalette.ColorRole.Base),
        plot_foreground=role(QPalette.ColorRole.Text),
    )


def build_palette(colors: ThemeColors) -> QPalette:
    """Build a full QPalette (active/inactive/disabled) from a theme."""
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: colors.window,
        QPalette.ColorRole.WindowText: colors.window_text,
        QPalette.ColorRole.Base: colors.base,
        QPalette.ColorRole.AlternateBase: colors.alternate_base,
        QPalette.ColorRole.ToolTipBase: colors.tooltip_base,
        QPalette.ColorRole.ToolTipText: colors.tooltip_text,
        QPalette.ColorRole.Text: colors.text,
        QPalette.ColorRole.Button: colors.button,
        QPalette.ColorRole.ButtonText: colors.button_text,
        QPalette.ColorRole.BrightText: colors.highlighted_text,
        QPalette.ColorRole.Highlight: colors.highlight,
        QPalette.ColorRole.HighlightedText: colors.highlighted_text,
        QPalette.ColorRole.PlaceholderText: colors.placeholder,
        QPalette.ColorRole.Link: colors.link,
        QPalette.ColorRole.LinkVisited: colors.link,
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Disabled, role, QColor(colors.disabled_text)
        )
    return palette


def apply_theme(app: QApplication, mode: ThemeMode) -> ThemeColors:
    """Apply ``mode`` to the application and return the resulting colours."""
    _capture_system(app)
    if mode is ThemeMode.LIGHT:
        app.setStyle("Fusion")
        app.setPalette(build_palette(LIGHT))
        colors = LIGHT
    elif mode is ThemeMode.DARK:
        app.setStyle("Fusion")
        app.setPalette(build_palette(DARK))
        colors = DARK
    else:
        if _system_style:
            app.setStyle(_system_style)
        if _system_palette is not None:
            app.setPalette(_system_palette)
        colors = colors_from_palette(app.palette())
    pg.setConfigOption("background", colors.plot_background)
    pg.setConfigOption("foreground", colors.plot_foreground)
    return colors


def apply_plot_theme(plot: pg.PlotWidget, colors: ThemeColors) -> None:
    """Recolour an existing pyqtgraph plot (background, axes, labels)."""
    plot.setBackground(colors.plot_background)
    plot_item = plot.getPlotItem()
    for name in ("left", "bottom"):
        axis = plot_item.getAxis(name)
        if axis is None:
            continue
        pen = pg.mkPen(colors.plot_foreground)
        axis.setPen(pen)
        axis.setTextPen(pen)
        label = getattr(axis, "label", None)
        if label is not None:
            label.setDefaultTextColor(QColor(colors.plot_foreground))


def colors_for_mode(mode: ThemeMode) -> ThemeColors:
    """Static colours for light/dark (system falls back to dark)."""
    return LIGHT if mode is ThemeMode.LIGHT else DARK


__all__ = [
    "DARK",
    "LIGHT",
    "ThemeColors",
    "ThemeMode",
    "apply_plot_theme",
    "apply_theme",
    "build_palette",
    "colors_for_mode",
    "colors_from_palette",
]
