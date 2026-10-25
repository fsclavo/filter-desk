"""Harmonic readout panel (Phase 12)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from filterdesk.analysis.harmonics import HarmonicReport
from filterdesk.domain.units import format_engineering, parse_si
from filterdesk.gui.i18n import tr
from filterdesk.gui.widgets import EngineeringLineEdit


class HarmonicsPanel(QWidget):
    """Edit the fundamental and show |S21|/suppression at harmonics."""

    f0_changed = Signal(float)  # Hz; 0 means "auto (band landmark)"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._f0 = EngineeringLineEdit()
        self._f0.setPlaceholderText(tr("auto (band landmark)"))
        btn_auto = QPushButton(tr("Use landmark"))
        btn_auto.clicked.connect(self._use_landmark)
        row = QHBoxLayout()
        row.addWidget(QLabel("f0"))
        row.addWidget(self._f0)
        row.addWidget(btn_auto)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            [
                tr("Harmonic"),
                tr("Frequency"),
                "|S21| (dB)",
                tr("Suppression (dB)"),
            ]
        )
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self._table)

        self._f0.editingFinished.connect(self._on_editing_finished)

    def _use_landmark(self) -> None:
        self._f0.clear()
        self.f0_changed.emit(0.0)

    def _on_editing_finished(self) -> None:
        text = self._f0.text().strip()
        if not text:
            self.f0_changed.emit(0.0)
            return
        try:
            self.f0_changed.emit(parse_si(text))
        except ValueError:
            return

    def set_report(self, report: HarmonicReport | None) -> None:
        self._table.setRowCount(0)
        if report is None:
            return
        rows: list[tuple[str, float, float, float | None]] = [
            (
                "f0",
                report.fundamental_hz,
                report.fundamental_s21_db,
                None,
            )
        ]
        rows += [
            (f"{h.order}f", h.frequency_hz, h.s21_db, h.suppression_db)
            for h in report.harmonics
        ]
        for label, freq, db, suppression in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(label))
            self._table.setItem(
                r, 1, QTableWidgetItem(format_engineering(freq, "Hz", digits=6))
            )
            self._table.setItem(r, 2, QTableWidgetItem(f"{db:.2f}"))
            self._table.setItem(
                r,
                3,
                QTableWidgetItem("—" if suppression is None else f"{suppression:.2f}"),
            )

    def f0_text(self) -> str:
        return self._f0.text()
