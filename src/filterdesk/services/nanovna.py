"""Minimal direct NanoVNA sweep reader.

The NanoVNA-Saver project is GPL-3.0; this module is an independent client for
the documented console protocol and does not contain code copied from it.

Only S11/S21 are measured by a NanoVNA 2-port sweep. S12/S22 are left at zero
and the active device calibration is assumed to be valid.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import serial
from numpy.typing import NDArray
from serial.tools import list_ports

from filterdesk.io.touchstone import TouchstoneData
from filterdesk.services.vna_measurement import VnaMeasurementMetadata

_PROMPT = b"ch>"
_LIKELY = (
    "nanovna",
    "ch340",
    "cp210",
    "ft232",
    "usb serial",
    "ttyacm",
    "ttyusb",
    "usb-serial",
)


class NanoVnaError(RuntimeError):
    """Raised when a NanoVNA cannot be opened or read."""


@dataclass(frozen=True, slots=True)
class NanoVnaPort:
    device: str
    description: str
    hwid: str
    likely: bool = False

    @property
    def label(self) -> str:
        if self.description:
            return f"{self.description} ({self.device})"
        return self.device


@dataclass(frozen=True, slots=True)
class NanoVnaSweep:
    data: TouchstoneData
    port: str
    firmware: str
    method: str
    metadata: VnaMeasurementMetadata

    @property
    def name(self) -> str:
        f = self.data.frequency_hz
        return f"NanoVNA {f[0] / 1e6:.3f}-{f[-1] / 1e6:.3f} MHz"


def available_ports() -> list[NanoVnaPort]:
    """List serial ports, with likely NanoVNA adapters first."""
    ports: list[NanoVnaPort] = []
    for item in list_ports.comports():
        haystack = f"{item.description or ''} {item.hwid or ''}".lower()
        ports.append(
            NanoVnaPort(
                device=item.device,
                description=item.description or "",
                hwid=item.hwid or "",
                likely=any(token in haystack for token in _LIKELY),
            )
        )
    return sorted(ports, key=lambda port: (not port.likely, port.device))


class _NanoVnaSerial:
    def __init__(self, port: str, baudrate: int, timeout: float) -> None:
        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=timeout,
                write_timeout=2.0,
            )
        except (OSError, serial.SerialException) as exc:
            raise NanoVnaError(f"cannot open {port}: {exc}") from exc
        self._sync()

    def __enter__(self) -> _NanoVnaSerial:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._serial.close()
        except serial.SerialException:
            pass

    def _sync(self) -> None:
        self._serial.reset_input_buffer()
        self._serial.timeout = 1.0
        self._serial.write(b"\r")
        self._serial.read_until(_PROMPT)

    def command(self, command: str, timeout: float = 5.0) -> list[str]:
        try:
            self._serial.reset_input_buffer()
            self._serial.timeout = timeout
            self._serial.write(f"{command}\r".encode("ascii"))
            raw = self._serial.read_until(_PROMPT)
        except (OSError, serial.SerialException) as exc:
            raise NanoVnaError(f"NanoVNA command failed ({command}): {exc}") from exc
        if not raw.endswith(_PROMPT):
            raise NanoVnaError(f"NanoVNA did not answer command: {command}")
        text = raw[: -len(_PROMPT)].decode("ascii", errors="replace")
        lines = [line.strip() for line in text.splitlines()]
        return [
            line
            for line in lines
            if line and line != command and not line.startswith("ch>")
        ]


def _floats(lines: list[str]) -> NDArray[np.float64]:
    values: list[float] = []
    for line in lines:
        for token in line.replace(",", " ").split():
            try:
                values.append(float(token))
            except ValueError:
                continue
    return np.asarray(values, dtype=np.float64)


def _pairs(lines: list[str]) -> NDArray[np.complex128]:
    values: list[complex] = []
    for line in lines:
        parts = line.replace(",", " ").split()
        if len(parts) < 2:
            continue
        try:
            values.append(complex(float(parts[0]), float(parts[1])))
        except ValueError:
            continue
    return np.asarray(values, dtype=np.complex128)


def _quads(
    lines: list[str],
) -> tuple[NDArray[np.complex128], NDArray[np.complex128]]:
    s11: list[complex] = []
    s21: list[complex] = []
    for line in lines:
        parts = line.replace(",", " ").split()
        if len(parts) < 4:
            continue
        try:
            s11.append(complex(float(parts[0]), float(parts[1])))
            s21.append(complex(float(parts[2]), float(parts[3])))
        except ValueError:
            continue
    return (
        np.asarray(s11, dtype=np.complex128),
        np.asarray(s21, dtype=np.complex128),
    )


def _firmware(client: _NanoVnaSerial) -> tuple[str, str]:
    version_lines = client.command("version")
    firmware = version_lines[0] if version_lines else "unknown"
    help_text = " ".join(client.command("help")).lower()
    return firmware, help_text


def _read_classic(
    client: _NanoVnaSerial, start_hz: int, stop_hz: int, points: int
) -> tuple[NDArray[np.float64], NDArray[np.complex128], NDArray[np.complex128]]:
    client.command(f"sweep {start_hz} {stop_hz} {points}", timeout=10.0)
    frequencies = _floats(client.command("frequencies"))
    s11 = _pairs(client.command("data 0"))
    s21 = _pairs(client.command("data 1"))
    if len(frequencies) != points or len(s11) != points or len(s21) != points:
        raise NanoVnaError(
            f"classic sweep returned {len(frequencies)}/{len(s11)}/{len(s21)} "
            f"points (expected {points})"
        )
    return frequencies, s11, s21


def _read_scan_mask(
    client: _NanoVnaSerial, start_hz: int, stop_hz: int, points: int
) -> tuple[NDArray[np.float64], NDArray[np.complex128], NDArray[np.complex128]]:
    frequencies = _floats(
        client.command(f"scan {start_hz} {stop_hz} {points} 0b001", timeout=10.0)
    )
    lines = client.command(f"scan {start_hz} {stop_hz} {points} 0b110", timeout=10.0)
    s11, s21 = _quads(lines)
    if len(frequencies) != points or len(s11) != points or len(s21) != points:
        raise NanoVnaError(
            f"scan returned {len(frequencies)}/{len(s11)}/{len(s21)} "
            f"points (expected {points})"
        )
    return frequencies, s11, s21


def read_nanovna_sweep(
    port: str,
    *,
    baudrate: int = 115200,
    start_hz: float,
    stop_hz: float,
    points: int = 101,
    timeout: float = 0.5,
) -> NanoVnaSweep:
    """Read one S11/S21 sweep from a NanoVNA over a serial port."""
    if not port:
        raise NanoVnaError("a serial port is required")
    if baudrate <= 0:
        raise NanoVnaError("baud rate must be positive")
    if start_hz <= 0.0 or stop_hz <= start_hz:
        raise NanoVnaError("sweep requires 0 < start < stop")
    if not 11 <= points <= 1024:
        raise NanoVnaError("points must be between 11 and 1024")
    start = int(round(start_hz))
    stop = int(round(stop_hz))
    with _NanoVnaSerial(port, baudrate, timeout) as client:
        firmware, help_text = _firmware(client)
        errors: list[str] = []
        try:
            frequencies, s11, s21 = _read_classic(client, start, stop, points)
            method = "sweep"
        except NanoVnaError as exc:
            errors.append(str(exc))
            if "scan" not in help_text:
                raise NanoVnaError("; ".join(errors)) from exc
            try:
                frequencies, s11, s21 = _read_scan_mask(
                    client, start, stop, points
                )
                method = "scan"
            except NanoVnaError as scan_exc:
                errors.append(str(scan_exc))
                raise NanoVnaError("; ".join(errors)) from scan_exc
    s = np.zeros((points, 2, 2), dtype=np.complex128)
    s[:, 0, 0] = s11
    s[:, 1, 0] = s21
    data = TouchstoneData(
        frequency_hz=np.asarray(frequencies, dtype=np.float64),
        s=s,
        z0_ohm=50.0,
        source=None,
        comments=[
            "Direct NanoVNA sweep; S12/S22 were not measured.",
        ],
    )
    metadata = VnaMeasurementMetadata(
        vna_model=f"NanoVNA ({firmware})",
        calibration="device calibration (assumed; not independently verified)",
        reference_plane="NanoVNA port",
        measured_at=datetime.now(UTC).isoformat(timespec="seconds"),
        notes=(
            f"Read directly from {port} using {method}; "
            "S11/S21 measured, S12/S22 not measured."
        ),
    )
    return NanoVnaSweep(
        data=data,
        port=port,
        firmware=firmware,
        method=method,
        metadata=metadata,
    )


__all__ = [
    "NanoVnaError",
    "NanoVnaPort",
    "NanoVnaSweep",
    "available_ports",
    "read_nanovna_sweep",
]
