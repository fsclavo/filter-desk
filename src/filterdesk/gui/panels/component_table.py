"""Editable component table with selection sync."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QTableWidgetSelectionRange,
    QVBoxLayout,
    QWidget,
)

from filterdesk.domain.circuit import (
    Circuit,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealSeriesLC,
    NonIdealCapacitor,
    NonIdealInductor,
)
from filterdesk.domain.units import format_engineering, parse_si


def _base_element_id(ref: str) -> str:
    for suffix in (".Ls", ".Cs", ".Lp", ".Cp", ".L", ".C"):
        if ref.endswith(suffix):
            return ref[: -len(suffix)]
    return ref


class ComponentTablePanel(QWidget):
    value_edited = Signal(str, float)  # element_id, SI value
    element_selected = Signal(str)  # base element id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Ref", "Role", "Type", "Value"])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
        )
        self._table.cellChanged.connect(self._on_cell_changed)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        self._updating = False
        self._block_sel = False

    def set_circuit(self, circuit: Circuit | None) -> None:
        self._updating = True
        self._block_sel = True
        self._table.setRowCount(0)
        if circuit is None:
            self._updating = False
            self._block_sel = False
            return
        for el in circuit.elements:
            if isinstance(el, (IdealSeriesLC, IdealParallelLC)):
                self._add_row(
                    f"{el.id}.L",
                    el.role.value,
                    "inductor",
                    format_engineering(el.value_h, "H", digits=6),
                )
                self._add_row(
                    f"{el.id}.C",
                    el.role.value,
                    "capacitor",
                    format_engineering(el.value_f, "F", digits=6),
                )
                continue
            if isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
                for ref, val, unit, etype in (
                    (f"{el.id}.Ls", el.series_l_h, "H", "inductor"),
                    (f"{el.id}.Cs", el.series_c_f, "F", "capacitor"),
                    (f"{el.id}.Lp", el.parallel_l_h, "H", "inductor"),
                    (f"{el.id}.Cp", el.parallel_c_f, "F", "capacitor"),
                ):
                    self._add_row(
                        ref,
                        el.role.value,
                        etype,
                        format_engineering(val, unit, digits=6),
                    )
                continue
            if isinstance(el, IdealCapacitor):
                value_text = format_engineering(el.value_f, "F", digits=6)
            elif isinstance(el, IdealInductor):
                value_text = format_engineering(el.value_h, "H", digits=6)
            elif isinstance(el, NonIdealInductor):
                value_text = format_engineering(el.value_h, "H", digits=6)
            elif isinstance(el, NonIdealCapacitor):
                value_text = format_engineering(el.value_f, "F", digits=6)
            else:
                value_text = format_engineering(el.value_ohm, "Ohm", digits=6)
            self._add_row(el.id, el.role.value, el.element_type.value, value_text)
        self._updating = False
        self._block_sel = False

    def select_element(self, element_id: str) -> None:
        """Select all rows belonging to a base element id (e.g. X3 → X3.L + X3.C)."""
        base = _base_element_id(element_id)
        self._block_sel = True
        self._table.clearSelection()
        first_row: int | None = None
        last_col = self._table.columnCount() - 1
        for row in range(self._table.rowCount()):
            ref_item = self._table.item(row, 0)
            if ref_item is None:
                continue
            ref = ref_item.text()
            if ref == base or _base_element_id(ref) == base:
                self._table.setRangeSelected(
                    QTableWidgetSelectionRange(row, 0, row, last_col),
                    True,
                )
                if first_row is None:
                    first_row = row
        if first_row is not None:
            item = self._table.item(first_row, 0)
            if item is not None:
                self._table.scrollToItem(item)
        self._block_sel = False

    def _add_row(self, ref: str, role: str, etype: str, value: str) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        ref_item = QTableWidgetItem(ref)
        ref_item.setFlags(ref_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        role_item = QTableWidgetItem(role)
        role_item.setFlags(role_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        type_item = QTableWidgetItem(etype)
        type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        val_item = QTableWidgetItem(value)
        self._table.setItem(row, 0, ref_item)
        self._table.setItem(row, 1, role_item)
        self._table.setItem(row, 2, type_item)
        self._table.setItem(row, 3, val_item)

    def _on_cell_changed(self, row: int, column: int) -> None:
        if self._updating or column != 3:
            return
        ref_item = self._table.item(row, 0)
        val_item = self._table.item(row, 3)
        type_item = self._table.item(row, 2)
        if ref_item is None or val_item is None or type_item is None:
            return
        try:
            value = parse_si(val_item.text())
        except ValueError:
            return
        self.value_edited.emit(ref_item.text(), value)

    def _on_selection_changed(self) -> None:
        if self._block_sel or self._updating:
            return
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        ref_item = self._table.item(rows[0].row(), 0)
        if ref_item is None:
            return
        self.element_selected.emit(_base_element_id(ref_item.text()))
