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

from filterdesk.analysis.stress import StressReport
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
from filterdesk.domain.enums import ElementRole
from filterdesk.domain.units import format_engineering, parse_si
from filterdesk.gui.i18n import role_label, tr


def _base_element_id(ref: str) -> str:
    for suffix in (".Ls", ".Cs", ".Lp", ".Cp", ".L", ".C"):
        if ref.endswith(suffix):
            return ref[: -len(suffix)]
    return ref


def _parasitic_text(el: object) -> str:
    parts: list[str] = []
    if isinstance(el, NonIdealInductor):
        if el.series_resistance_ohm:
            parts.append(f"R={format_engineering(el.series_resistance_ohm, 'Ohm')}")
        if el.parallel_capacitance_f:
            parts.append(f"Cp={format_engineering(el.parallel_capacitance_f, 'F')}")
    elif isinstance(el, NonIdealCapacitor):
        if el.esr_ohm:
            parts.append(f"ESR={format_engineering(el.esr_ohm, 'Ohm')}")
        if el.esl_h:
            parts.append(f"ESL={format_engineering(el.esl_h, 'H')}")
    return "  ".join(parts)


class ComponentTablePanel(QWidget):
    value_edited = Signal(str, float)  # element_id, SI value
    element_selected = Signal(str)  # base element id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(
            [
                tr("Ref"),
                tr("Role"),
                tr("Type"),
                tr("Value"),
                tr("Parasitic"),
                tr("Tol"),
                tr("Vpk"),
                tr("Ipk"),
            ]
        )
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

    def set_circuit(
        self,
        circuit: Circuit | None,
        tolerances: dict[str, float] | None = None,
        stress: StressReport | None = None,
    ) -> None:
        self._updating = True
        self._block_sel = True
        self._table.setRowCount(0)
        if circuit is None:
            self._updating = False
            self._block_sel = False
            return
        tol = tolerances or {}

        def tol_text(key: str) -> str:
            return f"{tol[key]:g}%" if key in tol else ""

        by_ref = {e.ref: e for e in stress.entries} if stress is not None else {}

        def stress_cells(key: str) -> tuple[str, str]:
            entry = by_ref.get(key)
            if entry is None:
                return "", ""
            return f"{entry.v_peak_v:.3g}", f"{entry.i_peak_a:.3g}"

        for el in circuit.elements:
            vpk, ipk = stress_cells(el.id)
            if isinstance(el, (IdealSeriesLC, IdealParallelLC)):
                self._add_row(
                    f"{el.id}.L",
                    role_label(el.role),
                    "inductor",
                    format_engineering(el.value_h, "H", digits=6),
                    "",
                    tol_text(f"{el.id}.L"),
                    vpk,
                    ipk,
                )
                self._add_row(
                    f"{el.id}.C",
                    role_label(el.role),
                    "capacitor",
                    format_engineering(el.value_f, "F", digits=6),
                    "",
                    tol_text(f"{el.id}.C"),
                    vpk,
                    ipk,
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
                        role_label(el.role),
                        etype,
                        format_engineering(val, unit, digits=6),
                        "",
                        tol_text(ref),
                        vpk,
                        ipk,
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
            self._add_row(
                el.id,
                role_label(el.role),
                tr(el.element_type.value),
                value_text,
                _parasitic_text(el),
                tol_text(el.id),
                vpk,
                ipk,
            )
        if circuit.output_transformer_ratio != 1.0:
            self._add_row(
                "T1",
                role_label(ElementRole.SERIES),
                tr("transformer"),
                f"{circuit.output_transformer_ratio:.4g}:1",
                tr("ideal"),
            )
        if circuit.output_balun is not None:
            balun = circuit.output_balun
            self._add_row(
                "BAL1",
                role_label(ElementRole.SERIES),
                tr("balun"),
                balun.ratio_text,
                tr(balun.kind),
            )
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

    def _add_row(
        self,
        ref: str,
        role: str,
        etype: str,
        value: str,
        parasitic: str = "",
        tolerance: str = "",
        v_peak: str = "",
        i_peak: str = "",
    ) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        ref_item = QTableWidgetItem(ref)
        ref_item.setFlags(ref_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        role_item = QTableWidgetItem(role)
        role_item.setFlags(role_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        type_item = QTableWidgetItem(etype)
        type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        val_item = QTableWidgetItem(value)
        par_item = QTableWidgetItem(parasitic)
        par_item.setFlags(par_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        tol_item = QTableWidgetItem(tolerance)
        tol_item.setFlags(tol_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        v_item = QTableWidgetItem(v_peak)
        v_item.setFlags(v_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        i_item = QTableWidgetItem(i_peak)
        i_item.setFlags(i_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(row, 0, ref_item)
        self._table.setItem(row, 1, role_item)
        self._table.setItem(row, 2, type_item)
        self._table.setItem(row, 3, val_item)
        self._table.setItem(row, 4, par_item)
        self._table.setItem(row, 5, tol_item)
        self._table.setItem(row, 6, v_item)
        self._table.setItem(row, 7, i_item)

    def _on_cell_changed(self, row: int, column: int) -> None:
        if self._updating or column != 3:
            return
        ref_item = self._table.item(row, 0)
        val_item = self._table.item(row, 3)
        type_item = self._table.item(row, 2)
        if ref_item is None or val_item is None or type_item is None:
            return
        if ref_item.text() == "T1":
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
