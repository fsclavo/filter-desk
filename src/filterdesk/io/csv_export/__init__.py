"""CSV / two-column DAT trace export (Phase 10)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.derived import (
    group_delay_s,
    insertion_loss_db,
    mag_db,
    return_loss_db,
    vswr,
)
from filterdesk.analysis.types import AnalysisResult
from filterdesk.io.touchstone import TouchstoneData

#: Default CSV columns (order preserved in the output header).
COLUMNS: tuple[str, ...] = (
    "frequency_hz",
    "s21_db",
    "s11_db",
    "s22_db",
    "s21_mag",
    "s11_mag",
    "vswr",
    "group_delay_s",
    "il_db",
    "rl_db",
)


class CsvExportError(ValueError):
    """Raised for an unknown column or an empty trace."""


def _column(result: AnalysisResult, name: str) -> NDArray[np.float64]:
    if name == "frequency_hz":
        return np.asarray(result.frequency_hz, dtype=np.float64)
    if name == "s21_db":
        return np.asarray(mag_db(result.s21), dtype=np.float64)
    if name == "s11_db":
        return np.asarray(mag_db(result.s11), dtype=np.float64)
    if name == "s22_db":
        return np.asarray(mag_db(result.s22), dtype=np.float64)
    if name == "s12_db":
        return np.asarray(mag_db(result.s12), dtype=np.float64)
    if name == "s21_mag":
        return np.asarray(np.abs(result.s21), dtype=np.float64)
    if name == "s11_mag":
        return np.asarray(np.abs(result.s11), dtype=np.float64)
    if name == "s22_mag":
        return np.asarray(np.abs(result.s22), dtype=np.float64)
    if name == "vswr":
        return np.asarray(vswr(result), dtype=np.float64)
    if name == "group_delay_s":
        return np.asarray(
            group_delay_s(result.frequency_hz, result.s21), dtype=np.float64
        )
    if name == "il_db":
        return np.asarray(insertion_loss_db(result), dtype=np.float64)
    if name == "rl_db":
        return np.asarray(return_loss_db(result), dtype=np.float64)
    if name == "zin_ohm":
        return np.asarray(result.zin_ohm.real, dtype=np.float64)
    if name == "zout_ohm":
        return np.asarray(result.zout_ohm.real, dtype=np.float64)
    raise CsvExportError(f"unknown column: {name!r}")


def export_csv(
    result: AnalysisResult,
    path: Path | str,
    *,
    columns: tuple[str, ...] = COLUMNS,
    comment: str = "",
) -> Path:
    """Write an analysis result to a header-annotated CSV file."""
    if not columns:
        raise CsvExportError("at least one column is required")
    arrays = {name: _column(result, name) for name in columns}
    n = int(result.frequency_hz.shape[0])
    out = Path(path)
    lines: list[str] = []
    if comment:
        for line in comment.splitlines():
            lines.append(f"# {line}")
    lines.append(",".join(columns))
    for i in range(n):
        cells = [f"{arrays[name][i]:.10g}" for name in columns]
        lines.append(",".join(cells))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def export_dat(
    frequency_hz: NDArray[np.floating],
    values: NDArray[np.floating],
    path: Path | str,
    *,
    comment: str = "",
) -> Path:
    """Write a two-column (frequency, value) DAT trace."""
    f = np.asarray(frequency_hz, dtype=np.float64)
    v = np.asarray(values, dtype=np.float64)
    if f.shape != v.shape:
        raise CsvExportError("frequency and values must have the same length")
    if f.size == 0:
        raise CsvExportError("trace is empty")
    out = Path(path)
    lines: list[str] = []
    if comment:
        for line in comment.splitlines():
            lines.append(f"# {line}")
    for fi, vi in zip(f, v, strict=True):
        lines.append(f"{fi:.10g}\t{vi:.10g}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def analysis_from_touchstone(data: TouchstoneData) -> AnalysisResult:
    """Build an :class:`AnalysisResult` from 2-port ``TouchstoneData``."""
    frequency = np.asarray(data.frequency_hz, dtype=np.float64)
    s = np.asarray(data.s, dtype=np.complex128)
    z0 = float(data.z0_ohm)
    if s.ndim != 3 or s.shape[1:] != (2, 2):
        raise CsvExportError("only 2-port data can be exported")
    s11 = s[:, 0, 0]
    s21 = s[:, 1, 0]
    s12 = s[:, 0, 1]
    s22 = s[:, 1, 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        zin = z0 * (1.0 + s11) / (1.0 - s11)
        zout = z0 * (1.0 + s22) / (1.0 - s22)
    return AnalysisResult(
        frequency_hz=frequency,
        s11=s11,
        s21=s21,
        s12=s12,
        s22=s22,
        zin_ohm=zin,
        zout_ohm=zout,
        z0_source_ohm=z0,
        z0_load_ohm=z0,
        backend="touchstone",
    )
