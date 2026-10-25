"""Theme palettes and plot theming."""

from __future__ import annotations

import pyqtgraph as pg
import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from filterdesk.gui.theme import (
    DARK,
    LIGHT,
    ThemeMode,
    apply_theme,
    build_palette,
    colors_for_mode,
    colors_from_palette,
)


@pytest.fixture()
def app() -> QApplication:
    instance = QApplication.instance() or QApplication([])
    return instance


def test_palettes_differ(app: QApplication) -> None:
    del app
    light = build_palette(LIGHT)
    dark = build_palette(DARK)
    assert light.color(QPalette.ColorRole.Window).name() == LIGHT.window
    assert dark.color(QPalette.ColorRole.Window).name() == DARK.window
    assert LIGHT.window != DARK.window
    assert (
        light.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text).name()
        == LIGHT.disabled_text
    )


def test_colors_from_palette(app: QApplication) -> None:
    del app
    colors = colors_from_palette(build_palette(LIGHT))
    assert colors.window == LIGHT.window
    assert colors.base == LIGHT.base
    assert colors.plot_background == LIGHT.base
    assert colors.plot_foreground == LIGHT.text


def test_colors_for_mode() -> None:
    assert colors_for_mode(ThemeMode.LIGHT) is LIGHT
    assert colors_for_mode(ThemeMode.DARK) is DARK
    assert colors_for_mode(ThemeMode.SYSTEM) is DARK


def test_apply_theme_sets_palette_and_pyqtgraph(app: QApplication) -> None:
    colors = apply_theme(app, ThemeMode.LIGHT)
    assert colors is LIGHT
    assert app.palette().color(QPalette.ColorRole.Window).name() == LIGHT.window
    assert str(pg.getConfigOption("background")) == LIGHT.plot_background

    colors = apply_theme(app, ThemeMode.DARK)
    assert colors is DARK
    assert app.palette().color(QPalette.ColorRole.Window).name() == DARK.window

    apply_theme(app, ThemeMode.SYSTEM)


def test_plot_panel_theme_background(app: QApplication) -> None:
    del app
    from filterdesk.gui.panels.plot_panel import PlotPanel

    panel = PlotPanel()
    panel.set_theme(LIGHT)
    assert panel._mag.backgroundBrush().color().name() == LIGHT.plot_background
    panel.set_theme(DARK)
    assert panel._mag.backgroundBrush().color().name() == DARK.plot_background
    panel.close()


def test_schematic_refresh_theme(app: QApplication) -> None:
    del app
    from filterdesk.gui.panels.schematic_view import SchematicPanel

    panel = SchematicPanel()
    panel.refresh_theme()
    panel.close()
