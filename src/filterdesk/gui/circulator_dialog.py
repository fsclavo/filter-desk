"""Circulator / isolator design dialog."""

from __future__ import annotations

from pathlib import Path

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
    QVBoxLayout,
    QWidget,
)

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.units import parse_si
from filterdesk.gui.i18n import tr
from filterdesk.gui.widgets import EngineeringLineEdit
from filterdesk.io.touchstone import write_sparameters
from filterdesk.services.circulator import (
    CirculatorConfig,
    CirculatorDesign,
    CirculatorError,
    IsolatorDesign,
    design_circulator,
    design_isolator,
)


class CirculatorDialog(QDialog):
    """First-order ideal circulator/isolator model with Touchstone export."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Circulator / isolator"))
        self.setMinimumWidth(540)
        self._design: CirculatorDesign | IsolatorDesign | None = None
        self._mode = QComboBox()
        self._mode.addItem(tr("Circulator (3 ports)"), "circulator")
        self._mode.addItem(tr("Isolator (2 ports)"), "isolator")
        self._insertion_loss = EngineeringLineEdit()
        self._insertion_loss.setText("0.5")
        self._isolation = EngineeringLineEdit()
        self._isolation.setText("30")
        self._return_loss = EngineeringLineEdit()
        self._return_loss.setText("20")
        self._z0 = EngineeringLineEdit()
        self._z0.setText("50")
        self._f_start = EngineeringLineEdit()
        self._f_start.setText("100M")
        self._f_stop = EngineeringLineEdit()
        self._f_stop.setText("200M")
        self._points = QSpinBox()
        self._points.setRange(11, 20_001)
        self._points.setValue(401)
        self._summary = QLabel("-")
        self._summary.setWordWrap(True)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._design_button = QPushButton(tr("Design"))
        self._design_button.clicked.connect(self._run_design)
        self._export_button = QPushButton(tr("Export Touchstone…"))
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(self._export)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.addButton(
            self._design_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        buttons.addButton(
            self._export_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        form = QFormLayout()
        form.addRow(tr("Type"), self._mode)
        form.addRow(tr("Insertion loss (dB)"), self._insertion_loss)
        form.addRow(tr("Isolation (dB)"), self._isolation)
        form.addRow(tr("Return loss (dB)"), self._return_loss)
        form.addRow(tr("Reference Z0 (Ohm)"), self._z0)
        form.addRow(tr("Sweep start"), self._f_start)
        form.addRow(tr("Sweep stop"), self._f_stop)
        form.addRow(tr("Points"), self._points)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._summary)
        layout.addWidget(self._status)
        layout.addWidget(buttons)
        self._mode.currentIndexChanged.connect(self._invalidate)
        self._run_design()

    @property
    def design(self) -> CirculatorDesign | IsolatorDesign | None:
        return self._design

    def _invalidate(self) -> None:
        self._design = None
        self._export_button.setEnabled(False)
        self._summary.setText("-")
        self._status.setText("")

    def _run_design(self) -> None:
        try:
            config = CirculatorConfig(
                insertion_loss_db=parse_si(self._insertion_loss.text()),
                isolation_db=parse_si(self._isolation.text()),
                return_loss_db=parse_si(self._return_loss.text()),
                z0_ohm=parse_si(self._z0.text()),
            )
            sweep = SweepConfig(
                f_start_hz=parse_si(self._f_start.text()),
                f_stop_hz=parse_si(self._f_stop.text()),
                n_points=int(self._points.value()),
                spacing=SweepSpacing.LOGARITHMIC,
            )
            self._design = (
                design_circulator(config, sweep)
                if self._mode.currentData() == "circulator"
                else design_isolator(config, sweep)
            )
        except (CirculatorError, ValueError) as exc:
            self._design = None
            self._export_button.setEnabled(False)
            self._summary.setText("-")
            self._status.setText(str(exc))
            return
        self._summary.setText(self._design.summary())
        self._status.setText(
            tr(
                "First-order model: phase, bandwidth, power and ferrite bias "
                "are not simulated."
            )
        )
        self._export_button.setEnabled(True)

    def _export(self) -> None:
        if self._design is None:
            return
        ports = self._design.network.n_ports
        path, _selected = QFileDialog.getSaveFileName(
            self,
            tr("Export circulator/isolator"),
            f"{self._mode.currentData()}.s{ports}p",
            f"Touchstone (*.s{ports}p);;All files (*)",
        )
        if not path:
            return
        if not Path(path).suffix:
            path += f".s{ports}p"
        try:
            write_sparameters(self._design.network, path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, tr("Export failed"), str(exc))
            return
        self._status.setText(tr("Wrote {path}", path=path))


__all__ = ["CirculatorDialog"]
