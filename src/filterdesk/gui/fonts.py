"""Application font-size presets for the GUI."""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from filterdesk.gui.settings import FONT_SIZE_KEY, get_settings_store


class FontSize(StrEnum):
    SMALL = "small"
    DEFAULT = "default"
    LARGE = "large"
    EXTRA_LARGE = "extra_large"


_SCALES = {
    FontSize.SMALL: 0.9,
    FontSize.DEFAULT: 1.0,
    FontSize.LARGE: 1.15,
    FontSize.EXTRA_LARGE: 1.3,
}

_base_font: QFont | None = None


def font_size_from_code(raw: str) -> FontSize:
    """Parse a stored font-size code, falling back to ``DEFAULT``."""
    try:
        return FontSize(raw)
    except ValueError:
        return FontSize.DEFAULT


def _base(app: QApplication) -> QFont:
    global _base_font
    if _base_font is None:
        _base_font = QFont(app.font())
    return _base_font


def apply_font_size(app: QApplication, mode: FontSize) -> QFont:
    """Apply a preset relative to the platform's initial application font."""
    base = _base(app)
    font = QFont(base)
    point_size = base.pointSizeF()
    if point_size <= 0.0:
        point_size = 10.0
    font.setPointSizeF(max(6.0, point_size * _SCALES[mode]))
    app.setFont(font)
    return font


def apply_saved_font_size(app: QApplication) -> FontSize:
    """Apply the font size stored in QSettings and return the chosen preset."""
    raw = get_settings_store().get_str(
        FONT_SIZE_KEY, FontSize.DEFAULT.value
    )
    mode = font_size_from_code(raw)
    apply_font_size(app, mode)
    return mode


def reset_font_base() -> None:
    """Forget the captured base font (used by tests)."""
    global _base_font
    _base_font = None


__all__ = [
    "FontSize",
    "apply_font_size",
    "apply_saved_font_size",
    "font_size_from_code",
    "reset_font_base",
]
