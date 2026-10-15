"""Shared GUI widgets."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QWidget


class EngineeringLineEdit(QLineEdit):
    """Line edit for values like ``140M``, ``4.7p``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("e.g. 140M, 50, 10n")
