"""Marker list editor."""

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

from filterdesk.domain.overlays import MAX_MARKERS, Marker
from filterdesk.domain.units import format_engineering, parse_si


class MarkersPanel(QWidget):
    markers_changed = Signal(object)  # list[Marker]
    add_at_cursor_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._markers: list[Marker] = []
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Id", "Frequency", "Label"])
        self._table.cellChanged.connect(self._on_cell_changed)
        self._updating = False

        btn_add = QPushButton("Add at cursor")
        btn_add.clicked.connect(self.add_at_cursor_requested.emit)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._delete_selected)
        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._clear)

        row = QHBoxLayout()
        row.addWidget(btn_add)
        row.addWidget(btn_del)
        row.addWidget(btn_clear)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self._table)

    def set_markers(self, markers: list[Marker]) -> None:
        self._updating = True
        self._markers = list(markers)
        self._table.setRowCount(0)
        for m in markers:
            r = self._table.rowCount()
            self._table.insertRow(r)
            id_item = QTableWidgetItem(m.id)
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(r, 0, id_item)
            self._table.setItem(
                r, 1, QTableWidgetItem(format_engineering(m.frequency_hz, "Hz"))
            )
            self._table.setItem(r, 2, QTableWidgetItem(m.label))
        self._updating = False

    def markers(self) -> list[Marker]:
        return list(self._markers)

    def _emit(self) -> None:
        self.markers_changed.emit(list(self._markers))

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._updating or row < 0 or row >= len(self._markers):
            return
        m = self._markers[row]
        try:
            if col == 1:
                item = self._table.item(row, 1)
                assert item is not None
                freq = parse_si(item.text())
                self._markers[row] = Marker(id=m.id, frequency_hz=freq, label=m.label)
            elif col == 2:
                item = self._table.item(row, 2)
                label = "" if item is None else item.text()
                self._markers[row] = Marker(
                    id=m.id, frequency_hz=m.frequency_hz, label=label
                )
            else:
                return
        except Exception:
            self.set_markers(self._markers)
            return
        self._emit()

    def _delete_selected(self) -> None:
        rows = sorted(
            {idx.row() for idx in self._table.selectedIndexes()}, reverse=True
        )
        if not rows:
            return
        for r in rows:
            if 0 <= r < len(self._markers):
                del self._markers[r]
        self.set_markers(self._markers)
        self._emit()

    def _clear(self) -> None:
        self._markers = []
        self.set_markers(self._markers)
        self._emit()

    def can_add(self) -> bool:
        return len(self._markers) < MAX_MARKERS

    def next_id(self) -> str:
        used = {m.id for m in self._markers}
        for i in range(1, MAX_MARKERS + 2):
            mid = f"M{i}"
            if mid not in used:
                return mid
        return f"M{len(self._markers) + 1}"
