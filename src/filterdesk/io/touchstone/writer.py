"""Minimal Touchstone (.sNp / .s2p / .s1p) writers."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from filterdesk.analysis.multiport import SParameters
from filterdesk.analysis.types import AnalysisResult


def write_touchstone_s2p(
    result: AnalysisResult,
    path: Path | str,
    *,
    freq_unit: str = "HZ",
    comment: str | None = None,
) -> None:
    """Write a Touchstone 1.0 style .s2p (RI format, Hz).

    Format option line: ``# HZ S RI R <z0>``
    Assumes equal real reference impedance at both ports.
    """
    z0s = result.z0_source_ohm
    z0l = result.z0_load_ohm
    if abs(z0s - z0l) > 1e-9 * max(z0s, z0l):
        raise ValueError("Touchstone writer requires equal real port impedances")

    out = Path(path)
    lines: list[str] = [
        "! FilterDesk Touchstone export",
    ]
    if comment:
        lines.append(f"! {comment}")
    lines.append(f"! backend={result.backend}")
    lines.append(f"# {freq_unit} S RI R {z0s:.6g}")

    for i, f in enumerate(result.frequency_hz):
        s11 = result.s11[i]
        s21 = result.s21[i]
        s12 = result.s12[i]
        s22 = result.s22[i]
        lines.append(
            f"{float(f):.12g} "
            f"{s11.real:.12g} {s11.imag:.12g} "
            f"{s21.real:.12g} {s21.imag:.12g} "
            f"{s12.real:.12g} {s12.imag:.12g} "
            f"{s22.real:.12g} {s22.imag:.12g}"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_touchstone_snp(
    network: SParameters,
    path: Path | str,
    *,
    comment: str | None = None,
) -> None:
    """Write a generic Touchstone 1.0 ``.sNp`` in RI format and Hz."""
    out = Path(path)
    lines: list[str] = ["! FilterDesk Touchstone N-port export"]
    if comment:
        lines.append(f"! {comment}")
    if network.source:
        lines.append(f"! source={network.source}")
    lines.append(f"# HZ S RI R {network.z0_ohm:.12g}")
    ports = network.n_ports
    for index, frequency in enumerate(network.frequency_hz):
        values = [f"{float(frequency):.15g}"]
        for in_port in range(ports):
            for out_port in range(ports):
                value = complex(network.s[index, out_port, in_port])
                values.append(f"{value.real:.15g}")
                values.append(f"{value.imag:.15g}")
        lines.append(" ".join(values))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_touchstone_s1p(
    result: AnalysisResult,
    path: Path | str,
    *,
    use_s11: bool = True,
) -> None:
    """Write .s1p using S11 (default) or S22."""
    z0 = result.z0_source_ohm if use_s11 else result.z0_load_ohm
    s = result.s11 if use_s11 else result.s22
    out = Path(path)
    lines = [
        "! FilterDesk Touchstone 1-port export",
        f"# HZ S RI R {z0:.6g}",
    ]
    for f, val in zip(result.frequency_hz, s, strict=True):
        lines.append(f"{float(f):.12g} {val.real:.12g} {val.imag:.12g}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sample_s21_db_at(
    result: AnalysisResult, frequency_hz: float
) -> float:
    """Interpolate |S21| dB at a frequency (nearest neighbor)."""
    idx = int(np.argmin(np.abs(result.frequency_hz - frequency_hz)))
    mag = abs(result.s21[idx])
    return float(20.0 * np.log10(max(mag, 1e-30)))
