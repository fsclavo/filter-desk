"""Response limit region editor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from filterdesk.domain.overlays import MAX_LIMITS, LimitMetric, LimitRegion
from filterdesk.domain.units import format_engineering, parse_si
from filterdesk.gui.i18n import tr


@dataclass(frozen=True, slots=True)
class _LimitPreset:
    label: str
    metric: LimitMetric
    f_low_hz: float
    f_high_hz: float
    y_min: float | None
    y_max: float | None
    tag: str


_PRESETS: tuple[_LimitPreset, ...] = (
    _LimitPreset(
        "Passband |S21| min", LimitMetric.S21_DB, 1e6, 100e6, -0.5, None,
        "S21 passband",
    ),
    _LimitPreset(
        "Stopband |S21| max", LimitMetric.S21_DB, 1e6, 100e6, None, -40.0,
        "S21 stopband",
    ),
    _LimitPreset(
        "Return loss |S11| max", LimitMetric.S11_DB, 1e6, 100e6, None, -10.0,
        "return loss",
    ),
    _LimitPreset(
        "VSWR max", LimitMetric.VSWR, 1e6, 100e6, None, 2.0,
        "VSWR",
    ),
    _LimitPreset(
        "Smith |S11| max", LimitMetric.S11_MAG, 1e6, 1e9, None, 0.1,
        "|S11|",
    ),
    _LimitPreset(
        "Smith |S22| max", LimitMetric.S22_MAG, 1e6, 1e9, None, 0.1,
        "|S22|",
    ),
)



class LimitsPanel(QWidget):
    limits_changed = Signal(object)  # list[LimitRegion]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._limits: list[LimitRegion] = []
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            [
                "Id",
                tr("Metric"),
                tr("f_low"),
                tr("f_high"),
                tr("y_min"),
                tr("y_max"),
                tr("On"),
            ]
        )
        self._table.cellChanged.connect(self._on_cell_changed)
        self._updating = False

        btn_add = QToolButton()
        btn_add.setText(tr("Add limit"))
        btn_add.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(btn_add)
        for preset in _PRESETS:
            action = menu.addAction(tr(preset.label))
            action.triggered.connect(self._preset_handler(preset))
        btn_add.setMenu(menu)
        btn_add.setToolTip(
            tr(
                "Add a limit region preset, then edit the cells:\n"
                "Metric (s21_db, s11_db, vswr, s11_mag, s22_mag), f_low/f_high, "
                "y_min/y_max (blank = unbounded), On (yes/no).\n"
                "Enabled limits are drawn as bands and drive "
                "Design → Optimize to limits…"
            )
        )
        btn_del = QPushButton(tr("Delete"))
        btn_del.clicked.connect(self._delete_selected)
        btn_clear = QPushButton(tr("Clear"))
        btn_clear.clicked.connect(self._clear)

        row = QHBoxLayout()
        row.addWidget(btn_add)
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
            on_item = QTableWidgetItem(tr("yes") if lim.enabled else tr("no"))
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

    def _preset_handler(self, preset: _LimitPreset) -> Callable[[], None]:
        def run() -> None:
            self._add_preset(preset)

        return run

    def _add_preset(self, preset: _LimitPreset) -> None:
        if len(self._limits) >= MAX_LIMITS:
            return
        lim = LimitRegion(
            id=self._next_id(),
            metric=preset.metric,
            f_low_hz=preset.f_low_hz,
            f_high_hz=preset.f_high_hz,
            y_min=preset.y_min,
            y_max=preset.y_max,
            enabled=True,
            label=preset.tag,
        )
        self._limits.append(lim)
        self.set_limits(self._limits)
        self._select_row(len(self._limits) - 1)
        self._emit()

    def _select_row(self, row: int) -> None:
        if row < 0 or row >= self._table.rowCount():
            return
        self._table.selectRow(row)
        item = self._table.item(row, 0)
        if item is not None:
            self._table.scrollToItem(item)

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
