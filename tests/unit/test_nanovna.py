"""NanoVNA serial protocol, dialog and measurement integration."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.gui.i18n import Language, set_language
from filterdesk.io.touchstone import TouchstoneData
from filterdesk.services.nanovna import (
    NanoVnaError,
    NanoVnaPort,
    NanoVnaSweep,
    available_ports,
    read_nanovna_sweep,
)
from filterdesk.services.vna_measurement import VnaMeasurementMetadata


class _FakeSerial:
    instances: list[_FakeSerial] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.timeout = 0.5
        self.written: list[str] = []
        self._response = b""
        _FakeSerial.instances.append(self)

    def reset_input_buffer(self) -> None:
        return None

    def write(self, data: bytes) -> int:
        command = data.decode("ascii").strip()
        self.written.append(command)
        self._response = self._response_for(command)
        return len(data)

    def read_until(self, expected: bytes) -> bytes:
        return self._response + expected

    def close(self) -> None:
        return None

    def _response_for(self, command: str) -> bytes:
        if command == "":
            return b""
        if command == "version":
            return b"0.8.0\r\n"
        if command == "help":
            return b"scan sweep frequencies data version help\r\n"
        if command.startswith("sweep "):
            return b""
        if command == "frequencies":
            return self._frequencies(11)
        if command in ("data 0", "data 1"):
            offset = 0.0 if command == "data 0" else 1.0
            return "\r\n".join(
                f"{i + offset} {-(i + offset)}" for i in range(11)
            ).encode("ascii")
        if command.startswith("scan ") and command.endswith("0b001"):
            return self._frequencies(11)
        if command.startswith("scan ") and command.endswith("0b110"):
            return "\r\n".join(
                f"{i} {-i} {i + 1} {-(i + 1)}" for i in range(11)
            ).encode("ascii")
        return b""

    @staticmethod
    def _frequencies(points: int) -> bytes:
        return "\r\n".join(str(7_000_000 + i) for i in range(points)).encode(
            "ascii"
        )


class _ShortSweepSerial(_FakeSerial):
    def _response_for(self, command: str) -> bytes:
        if command == "frequencies":
            return b"7000000\r\n7001000\r\n7002000"
        if command in ("data 0", "data 1"):
            return b"1 0\r\n2 0\r\n3 0"
        return super()._response_for(command)


def test_available_ports_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "filterdesk.services.nanovna.list_ports.comports", lambda: []
    )
    assert available_ports() == []


def test_read_classic_sweep(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeSerial.instances.clear()
    monkeypatch.setattr("filterdesk.services.nanovna.serial.Serial", _FakeSerial)
    sweep = read_nanovna_sweep(
        "COM1", start_hz=7e6, stop_hz=7.3e6, points=11
    )
    assert sweep.method == "sweep"
    assert sweep.data.n_ports == 2
    assert sweep.data.n_points == 11
    assert sweep.data.s[0, 0, 0] == complex(0, 0)
    assert sweep.data.s[0, 1, 0] == complex(1, -1)
    assert "NanoVNA" in sweep.metadata.vna_model
    assert "S12/S22" in sweep.metadata.notes
    assert sweep.name.startswith("NanoVNA")


def test_scan_fallback_when_classic_returns_wrong_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "filterdesk.services.nanovna.serial.Serial", _ShortSweepSerial
    )
    sweep = read_nanovna_sweep(
        "COM1", start_hz=7e6, stop_hz=7.3e6, points=11
    )
    assert sweep.method == "scan"
    assert sweep.data.n_points == 11


def test_read_errors_are_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    class _SilentSerial(_FakeSerial):
        def read_until(self, expected: bytes) -> bytes:
            return b""

    monkeypatch.setattr("filterdesk.services.nanovna.serial.Serial", _SilentSerial)
    with pytest.raises(NanoVnaError, match="did not answer"):
        read_nanovna_sweep("COM1", start_hz=7e6, stop_hz=7.3e6, points=11)


def test_nanovna_dialog_lists_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    from filterdesk.gui import nanovna_dialog as module

    monkeypatch.setattr(
        module,
        "available_ports",
        lambda: [NanoVnaPort("COM7", "NanoVNA-H", "USB VID:PID", True)],
    )
    app = QApplication.instance() or QApplication([])
    dialog = module.NanoVnaDialog(
        sweep=SweepConfig(
            f_start_hz=7e6,
            f_stop_hz=7.3e6,
            n_points=101,
            spacing=SweepSpacing.LOGARITHMIC,
        )
    )
    assert dialog._port.currentData() == "COM7"
    from filterdesk.domain.units import parse_si

    assert parse_si(dialog._start.text()) == 7e6
    assert parse_si(dialog._stop.text()) == 7.3e6
    dialog.close()
    assert app is not None


def test_nanovna_dialog_titles_follow_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from filterdesk.gui import nanovna_dialog as module

    monkeypatch.setattr(module, "available_ports", lambda: [])
    app = QApplication.instance() or QApplication([])
    try:
        set_language(Language.ES)
        dialog = module.NanoVnaDialog()
        assert dialog._read_button.text() == "Leer barrido"
        dialog.close()
    finally:
        set_language(Language.EN)
    assert app is not None


def test_main_window_stores_nanovna_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    frequency = np.asarray([7.0e6, 7.1e6, 7.2e6])
    s = np.zeros((3, 2, 2), dtype=np.complex128)
    s[:, 0, 0] = 0.1
    s[:, 1, 0] = 0.9
    data = TouchstoneData(frequency_hz=frequency, s=s)
    sweep = NanoVnaSweep(
        data=data,
        port="COM1",
        firmware="0.8.0",
        method="sweep",
        metadata=VnaMeasurementMetadata(vna_model="NanoVNA (0.8.0)"),
    )
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: None)
    window = mw.MainWindow(DesignSession(), auto_run=False)
    window._on_nanovna_loaded(sweep)
    assert len(window._session.measurements) == 1
    assert window._session.measurements[0].name.startswith("NanoVNA")
    window.close()
    assert app is not None
