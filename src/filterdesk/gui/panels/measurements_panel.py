"""Measurement-history list and controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from filterdesk.gui.i18n import tr
from filterdesk.services.measurements import MeasurementRecord


class MeasurementsPanel(QWidget):
    import_requested = Signal()
    use_requested = Signal(int)
    details_requested = Signal(int)
    tune_requested = Signal(int)
    delete_requested = Signal(int)
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._records: list[MeasurementRecord] = []
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            [
                tr("Name"),
                tr("Source"),
                tr("Date"),
                tr("VNA"),
                tr("Calibration"),
                tr("Reference plane"),
            ]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.doubleClicked.connect(self._use_selected)
        btn_import = QPushButton(tr("Import…"))
        btn_import.clicked.connect(self.import_requested.emit)
        btn_use = QPushButton(tr("Use"))
        btn_use.clicked.connect(self._use_selected)
        btn_details = QPushButton(tr("Details…"))
        btn_details.clicked.connect(self._details_selected)
        btn_tune = QPushButton(tr("Tune…"))
        btn_tune.clicked.connect(self._tune_selected)
        btn_delete = QPushButton(tr("Delete"))
        btn_delete.clicked.connect(self._delete_selected)
        btn_clear = QPushButton(tr("Clear"))
        btn_clear.clicked.connect(self.clear_requested.emit)
        row = QHBoxLayout()
        row.addWidget(btn_import)
        row.addWidget(btn_use)
        row.addWidget(btn_details)
        row.addWidget(btn_tune)
        row.addWidget(btn_delete)
        row.addWidget(btn_clear)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self._table)

    def set_records(
        self, records: list[MeasurementRecord], active: int | None = None
    ) -> None:
        self._records = list(records)
        self._table.setRowCount(0)
        for record in records:
            row = self._table.rowCount()
            self._table.insertRow(row)
            metadata = record.metadata
            values = (
                record.name,
                record.source,
                metadata.measured_at,
                metadata.vna_model,
                metadata.calibration,
                metadata.reference_plane,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value or "—")
                item.setData(Qt.ItemDataRole.UserRole, row)
                self._table.setItem(row, column, item)
        if active is not None and 0 <= active < len(records):
            self._table.selectRow(active)

    def _selected_index(self) -> int | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        index = rows[0].row()
        return index if 0 <= index < len(self._records) else None

    def _use_selected(self) -> None:
        index = self._selected_index()
        if index is not None:
            self.use_requested.emit(index)

    def _details_selected(self) -> None:
        index = self._selected_index()
        if index is not None:
            self.details_requested.emit(index)

    def _tune_selected(self) -> None:
        index = self._selected_index()
        if index is not None:
            self.tune_requested.emit(index)

    def _delete_selected(self) -> None:
        index = self._selected_index()
        if index is not None:
            self.delete_requested.emit(index)


__all__ = ["MeasurementsPanel"]
