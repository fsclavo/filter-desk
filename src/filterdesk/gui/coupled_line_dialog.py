"""Coupled-line bandpass filter design dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std.microstrip import list_substrates
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.units import parse_si
from filterdesk.gui.i18n import tr
from filterdesk.gui.widgets import EngineeringLineEdit
from filterdesk.io.touchstone import write_sparameters
from filterdesk.services.coupled_layout import (
    CoupledLayoutError,
    LayoutMode,
    build_coupled_layout,
    render_coupled_layout_svg,
)
from filterdesk.services.coupled_line import (
    CoupledLineBpfConfig,
    CoupledLineBpfDesign,
    CoupledLineError,
    design_coupled_line_bpf,
)


class CoupledLineDialog(QDialog):
    """Narrowband coupled-line BPF electrical synthesis."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Coupled-line BPF"))
        self.setMinimumWidth(680)
        self._design: CoupledLineBpfDesign | None = None
        self._center = EngineeringLineEdit()
        self._center.setText("100M")
        self._bandwidth = EngineeringLineEdit()
        self._bandwidth.setText("10M")
        self._order = QSpinBox()
        self._order.setRange(1, 9)
        self._order.setValue(3)
        self._family = QComboBox()
        self._family.addItem(
            tr("Chebyshev I"), ApproximationFamily.CHEBYSHEV_TYPE_I.value
        )
        self._family.addItem(tr("Butterworth"), ApproximationFamily.BUTTERWORTH.value)
        self._ripple = EngineeringLineEdit()
        self._ripple.setText("0.1")
        self._z0 = EngineeringLineEdit()
        self._z0.setText("50")
        self._substrate = QComboBox()
        for substrate in list_substrates():
            self._substrate.addItem(substrate.name, substrate.name)
        self._f_start = EngineeringLineEdit()
        self._f_start.setText("80M")
        self._f_stop = EngineeringLineEdit()
        self._f_stop.setText("120M")
        self._points = QSpinBox()
        self._points.setRange(101, 20_001)
        self._points.setValue(1001)
        self._summary = QLabel("-")
        self._summary.setWordWrap(True)
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            [
                tr("Section"),
                tr("Z0e (ohm)"),
                tr("Z0o (ohm)"),
                tr("Coupling"),
                tr("J/Y0"),
                tr("Width (mm)"),
                tr("Gap (mm)"),
            ]
        )
        self._layout_mode = QComboBox()
        for label, mode in (
            (tr("Edge-coupled"), LayoutMode.EDGE),
            (tr("Hairpin"), LayoutMode.HAIRPIN),
            (tr("Interdigital"), LayoutMode.INTERDIGITAL),
        ):
            self._layout_mode.addItem(label, mode.value)
        self._layout_widget = QSvgWidget()
        self._layout_widget.setMinimumHeight(220)
        self._layout_status = QLabel("")
        self._layout_status.setWordWrap(True)
        self._note = QLabel("")
        self._note.setWordWrap(True)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._design_button = QPushButton(tr("Design"))
        self._design_button.clicked.connect(self._run_design)
        self._export_button = QPushButton(tr("Export Touchstone…"))
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(self._export)
        self._export_layout_button = QPushButton(tr("Export layout SVG…"))
        self._export_layout_button.setEnabled(False)
        self._export_layout_button.clicked.connect(self._export_layout)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.addButton(self._design_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self._export_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(
            self._export_layout_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        form = QFormLayout()
        form.addRow(tr("Center frequency"), self._center)
        form.addRow(tr("Bandwidth"), self._bandwidth)
        form.addRow(tr("Order"), self._order)
        form.addRow(tr("Family"), self._family)
        form.addRow(tr("Ripple (dB)"), self._ripple)
        form.addRow(tr("Reference Z0 (Ohm)"), self._z0)
        form.addRow(tr("Substrate"), self._substrate)
        form.addRow(tr("Sweep start"), self._f_start)
        form.addRow(tr("Sweep stop"), self._f_stop)
        form.addRow(tr("Points"), self._points)
        form.addRow(tr("Layout sketch"), self._layout_mode)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._summary)
        layout.addWidget(self._table)
        layout.addWidget(self._layout_widget)
        layout.addWidget(self._layout_status)
        layout.addWidget(self._note)
        layout.addWidget(self._status)
        layout.addWidget(buttons)
        self._family.currentIndexChanged.connect(self._on_family_changed)
        self._layout_mode.currentIndexChanged.connect(self._update_layout)
        self._run_design()

    @property
    def design(self) -> CoupledLineBpfDesign | None:
        return self._design

    def _on_family_changed(self) -> None:
        chebyshev = (
            self._family.currentData()
            == ApproximationFamily.CHEBYSHEV_TYPE_I.value
        )
        self._ripple.setEnabled(chebyshev)
        self._run_design()

    def _run_design(self) -> None:
        try:
            family = ApproximationFamily(str(self._family.currentData()))
            config = CoupledLineBpfConfig(
                center_hz=parse_si(self._center.text()),
                bandwidth_hz=parse_si(self._bandwidth.text()),
                order=int(self._order.value()),
                family=family,
                ripple_db=(
                    parse_si(self._ripple.text())
                    if family is ApproximationFamily.CHEBYSHEV_TYPE_I
                    else None
                ),
                z0_ohm=parse_si(self._z0.text()),
            )
            sweep = SweepConfig(
                f_start_hz=parse_si(self._f_start.text()),
                f_stop_hz=parse_si(self._f_stop.text()),
                n_points=int(self._points.value()),
                spacing=SweepSpacing.LINEAR,
            )
            self._design = design_coupled_line_bpf(
                config, sweep, substrate=str(self._substrate.currentData())
            )
        except (CoupledLineError, ValueError) as exc:
            self._design = None
            self._table.setRowCount(0)
            self._summary.setText("-")
            self._note.setText("")
            self._status.setText(str(exc))
            self._export_button.setEnabled(False)
            self._export_layout_button.setEnabled(False)
            self._layout_widget.load(QByteArray())
            self._layout_status.setText("")
            return
        self._summary.setText(self._design.summary())
        self._table.setRowCount(len(self._design.sections))
        for row, section in enumerate(self._design.sections):
            values = (
                str(section.index),
                f"{section.z0e_ohm:.3f}",
                f"{section.z0o_ohm:.3f}",
                f"{section.coupling:.4f}",
                f"{section.j_norm:.4f}",
                "-" if section.width_mm is None else f"{section.width_mm:.3f}",
                "-" if section.gap_mm is None else f"{section.gap_mm:.3f}",
            )
            for column, value in enumerate(values):
                self._table.setItem(row, column, QTableWidgetItem(value))
        self._note.setText(" ".join(self._design.warnings))
        self._status.setText("")
        self._export_button.setEnabled(True)
        self._update_layout()

    def _update_layout(self) -> None:
        if self._design is None:
            self._layout_widget.load(QByteArray())
            self._layout_status.setText("")
            self._export_layout_button.setEnabled(False)
            return
        try:
            layout = build_coupled_layout(
                self._design, str(self._layout_mode.currentData())
            )
        except CoupledLayoutError as exc:
            self._layout_widget.load(QByteArray())
            self._layout_status.setText(str(exc))
            self._export_layout_button.setEnabled(False)
            return
        svg = render_coupled_layout_svg(layout)
        self._layout_widget.load(QByteArray(svg.encode("utf-8")))
        self._layout_status.setText(" ".join(layout.warnings))
        self._export_layout_button.setEnabled(True)

    def _export_layout(self) -> None:
        if self._design is None:
            return
        path, _selected = QFileDialog.getSaveFileName(
            self,
            tr("Export layout SVG"),
            "coupled_layout.svg",
            "SVG (*.svg);;All files (*)",
        )
        if not path:
            return
        if not Path(path).suffix:
            path += ".svg"
        try:
            layout = build_coupled_layout(
                self._design, str(self._layout_mode.currentData())
            )
            Path(path).write_text(
                render_coupled_layout_svg(layout), encoding="utf-8"
            )
        except (CoupledLayoutError, OSError) as exc:
            QMessageBox.critical(self, tr("Export failed"), str(exc))
            return
        self._status.setText(tr("Wrote {path}", path=path))

    def _export(self) -> None:
        if self._design is None:
            return
        path, _selected = QFileDialog.getSaveFileName(
            self,
            tr("Export coupled-line filter"),
            "coupled_line.s2p",
            "Touchstone (*.s2p);;All files (*)",
        )
        if not path:
            return
        if not Path(path).suffix:
            path += ".s2p"
        try:
            write_sparameters(self._design.network, path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, tr("Export failed"), str(exc))
            return
        self._status.setText(tr("Wrote {path}", path=path))


__all__ = ["CoupledLineDialog"]
