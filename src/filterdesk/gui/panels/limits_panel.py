"""Response limit region editor."""

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

from filterdesk.domain.overlays import MAX_LIMITS, LimitMetric, LimitRegion
from filterdesk.domain.units import format_engineering, parse_si


class LimitsPanel(QWidget):
    limits_changed = Signal(object)  # list[LimitRegion]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._limits: list[LimitRegion] = []
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Id", "Metric", "f_low", "f_high", "y_min", "y_max", "On"]
        )
        self._table.cellChanged.connect(self._on_cell_changed)
        self._updating = False

        btn_add = QPushButton("Add S21 max")
        btn_add.clicked.connect(self._add_default)
        btn_smith = QPushButton("Add Smith |S11|")
        btn_smith.clicked.connect(self._add_smith_s11)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._delete_selected)
        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._clear)

        row = QHBoxLayout()
        row.addWidget(btn_add)
        row.addWidget(btn_smith)
        row.addWidget(btn_del)
        row.addWidget(btn_clear)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self._table)
        self._status = QPushButton()  # reused as label-like status
        self._status.setFlat(True)
        self._status.setEnabled(False)
        layout.addWidget(self._status)

    def set_limits(self, limits: list[LimitRegion]) -> None:
        self._updating = True
        self._limits = list(limits)
        self._table.setRowCount(0)
        for lim in limits:
            r = self._table.rowCount()
            self._table.insertRow(r)
            id_item = QTableWidgetItem(lim.id)
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(r, 0, id_item)
            self._table.setItem(r, 1, QTableWidgetItem(lim.metric.value))
            self._table.setItem(
                r, 2, QTableWidgetItem(format_engineering(lim.f_low_hz, "Hz"))
            )
            self._table.setItem(
                r, 3, QTableWidgetItem(format_engineering(lim.f_high_hz, "Hz"))
            )
            self._table.setItem(
                r,
                4,
                QTableWidgetItem("" if lim.y_min is None else f"{lim.y_min:g}"),
            )
            self._table.setItem(
                r,
                5,
                QTableWidgetItem("" if lim.y_max is None else f"{lim.y_max:g}"),
            )
            on_item = QTableWidgetItem("yes" if lim.enabled else "no")
            self._table.setItem(r, 6, on_item)
        self._updating = False

    def set_pass_fail_text(self, text: str) -> None:
        self._status.setText(text)

    def limits(self) -> list[LimitRegion]:
        return list(self._limits)

    def _emit(self) -> None:
        self.limits_changed.emit(list(self._limits))

    def _next_id(self) -> str:
        used = {lim.id for lim in self._limits}
        for i in range(1, MAX_LIMITS + 2):
            lid = f"L{i}"
            if lid not in used:
                return lid
        return f"L{len(self._limits) + 1}"

    def _add_default(self) -> None:
        if len(self._limits) >= MAX_LIMITS:
            return
        lim = LimitRegion(
            id=self._next_id(),
            metric=LimitMetric.S21_DB,
            f_low_hz=1e6,
            f_high_hz=100e6,
            y_min=None,
            y_max=-40.0,
            enabled=True,
            label="S21 stopband",
        )
        self._limits.append(lim)
        self.set_limits(self._limits)
        self._emit()

    def _add_smith_s11(self) -> None:
        if len(self._limits) >= MAX_LIMITS:
            return
        lim = LimitRegion(
            id=self._next_id(),
            metric=LimitMetric.S11_MAG,
            f_low_hz=1e6,
            f_high_hz=1e9,
            y_min=None,
            y_max=0.1,
            enabled=True,
            label="|S11| <= 0.1",
        )
        self._limits.append(lim)
        self.set_limits(self._limits)
        self._emit()

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._updating or row < 0 or row >= len(self._limits):
            return
        lim = self._limits[row]
        try:
            def _cell(c: int) -> str:
                item = self._table.item(row, c)
                return "" if item is None else item.text().strip()

            metric = LimitMetric(_cell(1) or lim.metric.value)
            f_low = parse_si(_cell(2))
            f_high = parse_si(_cell(3))
            y_min_s = _cell(4)
            y_max_s = _cell(5)
            y_min = None if not y_min_s else float(y_min_s)
            y_max = None if not y_max_s else float(y_max_s)
            enabled = _cell(6).lower() not in ("no", "0", "false", "off")
            self._limits[row] = LimitRegion(
                id=lim.id,
                metric=metric,
                f_low_hz=f_low,
                f_high_hz=f_high,
                y_min=y_min,
                y_max=y_max,
                enabled=enabled,
                label=lim.label,
            )
        except Exception:
            self.set_limits(self._limits)
            return
        self._emit()

    def _delete_selected(self) -> None:
        rows = sorted(
            {idx.row() for idx in self._table.selectedIndexes()}, reverse=True
        )
        if not rows:
            return
        for r in rows:
            if 0 <= r < len(self._limits):
                del self._limits[r]
        self.set_limits(self._limits)
        self._emit()

    def _clear(self) -> None:
        self._limits = []
        self.set_limits(self._limits)
        self._emit()
