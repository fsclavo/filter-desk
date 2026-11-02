"""Direct NanoVNA sweep import dialog."""

from __future__ import annotations

from PySide6.QtCore import QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from filterdesk.analysis.types import SweepConfig
from filterdesk.domain.units import parse_si
from filterdesk.gui.i18n import tr
from filterdesk.gui.widgets import EngineeringLineEdit
from filterdesk.gui.workers import start_nanovna_thread
from filterdesk.services.nanovna import NanoVnaSweep, available_ports


class NanoVnaDialog(QDialog):
    """Select a serial port and read one S11/S21 sweep."""

    def __init__(
        self,
        parent: QWidget | None = None,
        sweep: SweepConfig | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("NanoVNA sweep"))
        self.setMinimumWidth(520)
        self._sweep: NanoVnaSweep | None = None
        self._thread: QThread | None = None
        self._port = QComboBox()
        self._refresh = QPushButton(tr("Refresh"))
        self._refresh.clicked.connect(self._refresh_ports)
        port_row = QWidget()
        port_layout = QHBoxLayout(port_row)
        port_layout.setContentsMargins(0, 0, 0, 0)
        port_layout.addWidget(self._port, 1)
        port_layout.addWidget(self._refresh)
        self._baud = QComboBox()
        for baud in (115200, 1500000):
            self._baud.addItem(str(baud), baud)
        self._start = EngineeringLineEdit()
        self._stop = EngineeringLineEdit()
        if sweep is not None:
            self._start.setText(f"{sweep.f_start_hz:g}")
            self._stop.setText(f"{sweep.f_stop_hz:g}")
        else:
            self._start.setText("1M")
            self._stop.setText("30M")
        self._points = QSpinBox()
        self._points.setRange(11, 1024)
        self._points.setValue(101)
        self._points.setToolTip(
            tr("Classic NanoVNA supports 101 points; H4/scan firmware supports more.")
        )
        self._status = QLabel("")
        self._status.setWordWrap(True)
        note = QLabel(
            tr(
                "Uses the NanoVNA's active calibration. Only S11/S21 are "
                "measured; S12/S22 are stored as zero."
            )
        )
        note.setWordWrap(True)
        form = QFormLayout()
        form.addRow(tr("Serial port"), port_row)
        form.addRow(tr("Baud rate"), self._baud)
        form.addRow(tr("Start frequency"), self._start)
        form.addRow(tr("Stop frequency"), self._stop)
        form.addRow(tr("Points"), self._points)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        self._read_button = buttons.addButton(
            tr("Read sweep"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self._read_button.clicked.connect(self._read)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(self._status)
        layout.addWidget(buttons)
        self._refresh_ports()

    @property
    def sweep(self) -> NanoVnaSweep | None:
        return self._sweep

    def _refresh_ports(self) -> None:
        current = self._port.currentData()
        self._port.clear()
        ports = available_ports()
        for port in ports:
            self._port.addItem(port.label, port.device)
        if not ports:
            self._port.addItem(tr("No serial ports found"), "")
            self._status.setText(
                tr("Connect the NanoVNA and press Refresh.")
            )
        elif current:
            index = self._port.findData(current)
            if index >= 0:
                self._port.setCurrentIndex(index)

    def _set_reading(self, reading: bool) -> None:
        for widget in (
            self._port,
            self._refresh,
            self._baud,
            self._start,
            self._stop,
            self._points,
            self._read_button,
        ):
            widget.setEnabled(not reading)

    def _read(self) -> None:
        port = self._port.currentData()
        if not port:
            QMessageBox.warning(
                self, tr("NanoVNA sweep"), tr("Select a serial port first.")
            )
            return
        try:
            start_hz = parse_si(self._start.text())
            stop_hz = parse_si(self._stop.text())
        except ValueError as exc:
            QMessageBox.warning(self, tr("NanoVNA sweep"), str(exc))
            return
        if stop_hz <= start_hz:
            QMessageBox.warning(
                self,
                tr("NanoVNA sweep"),
                tr("Stop frequency must be above start frequency."),
            )
            return
        baudrate = int(self._baud.currentData())
        self._set_reading(True)
        self._status.setText(tr("Reading sweep from NanoVNA…"))
        thread, _worker = start_nanovna_thread(
            str(port),
            baudrate,
            start_hz,
            stop_hz,
            int(self._points.value()),
            self._on_finished,
            self._on_failed,
        )
        self._thread = thread
        thread.finished.connect(self._on_thread_finished)
        thread.start()

    def _on_finished(self, result: object) -> None:
        if not isinstance(result, NanoVnaSweep):
            self._on_failed(tr("Unexpected NanoVNA result."))
            return
        self._sweep = result
        self.accept()

    def _on_thread_finished(self) -> None:
        self._thread = None

    def _on_failed(self, message: str) -> None:
        self._set_reading(False)
        self._status.setText(message)
        QMessageBox.critical(self, tr("NanoVNA sweep"), message)

    def closeEvent(self, event: QCloseEvent) -> None:
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.requestInterruption()
            thread.quit()
            if not thread.wait(2000):
                thread.terminate()
                thread.wait(1000)
            self._thread = None
        super().closeEvent(event)


__all__ = ["NanoVnaDialog"]
