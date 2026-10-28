"""SPICE export for Guanella and Ruthroff TLTs."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from filterdesk.__main__ import main
from filterdesk.domain.circuit import BalunSpec
from filterdesk.io.spice import (
    SpiceExportError,
    tlt_spice_netlist,
    write_tlt_spice_netlist,
)


def _guanella() -> BalunSpec:
    return BalunSpec(
        kind="guanella",
        turns_ratio=0.5,
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=200.0,
        z0_line_ohm=100.0,
        length_m=0.05,
        velocity_factor=0.7,
        magnetizing_inductance_h=1e-5,
    )


def test_guanella_tlt_netlist_structure(tmp_path: Path) -> None:
    text = tlt_spice_netlist(_guanella())
    assert "TL1 in 0 outp mid1 Z0=100 TD=" in text
    assert "TL2 in 0 mid1 outm Z0=100 TD=" in text
    assert "Lcm mid1 0 1e-05" in text
    assert "Rload outp outm 200" in text
    out = tmp_path / "tlt.cir"
    assert write_tlt_spice_netlist(_guanella(), out) == out
    assert out.read_text(encoding="utf-8").startswith("* FilterDesk TLT")


def _ruthroff() -> BalunSpec:
    return BalunSpec(
        kind="ruthroff",
        turns_ratio=0.5,
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=200.0,
        z0_line_ohm=100.0,
        length_m=0.05,
        velocity_factor=0.7,
        magnetizing_inductance_h=1e-5,
    )


def test_ruthroff_tlt_netlist_structure(tmp_path: Path) -> None:
    text = tlt_spice_netlist(_ruthroff())
    assert "TL1 in 0 0 outm Z0=100 TD=" in text
    assert "Rload in outm 200" in text
    assert "bootstrap" in text
    out = tmp_path / "ruthroff.cir"
    assert write_tlt_spice_netlist(_ruthroff(), out) == out
    assert out.read_text(encoding="utf-8").startswith("* FilterDesk TLT")


def test_tlt_export_rejects_unsupported_kind() -> None:
    with pytest.raises(SpiceExportError, match="Guanella and Ruthroff"):
        tlt_spice_netlist(BalunSpec(kind="choke", turns_ratio=1.0))


def test_ruthroff_export_rejects_reverse_orientation() -> None:
    with pytest.raises(SpiceExportError, match="step-up"):
        tlt_spice_netlist(BalunSpec(kind="ruthroff", turns_ratio=2.0))


def test_cli_transformer_exports_guanella_spice(tmp_path: Path) -> None:
    out = tmp_path / "tlt.cir"
    code = main(
        [
            "transformer",
            "--kind",
            "guanella",
            "--z-low",
            "50",
            "--z-high",
            "200",
            "--core",
            "FT240-43",
            "--frequency",
            "3.5M",
            "--f-max",
            "30M",
            "--power",
            "100",
            "--export-spice",
            str(out),
        ]
    )
    assert code == 0
    assert out.is_file()
    assert "TL1 in 0" in out.read_text(encoding="utf-8")


def test_ruthroff_tlt_ngspice_low_frequency(tmp_path: Path) -> None:
    ngspice = shutil.which("ngspice")
    if ngspice is None:
        pytest.skip("ngspice is not installed")
    net = tlt_spice_netlist(_ruthroff())
    net = net.replace(
        ".end",
        ".ac lin 1 1Meg 1Meg\n.print ac v(in) v(outm)\n.end",
    )
    path = tmp_path / "ruthroff.cir"
    path.write_text(net, encoding="utf-8")
    output = subprocess.run(
        [ngspice, "-b", str(path)], check=True, capture_output=True, text=True
    )
    samples: list[tuple[float, complex]] = []
    for line_text in output.stdout.splitlines():
        parts = line_text.split()
        if len(parts) >= 4 and parts[0].isdigit():
            samples.append(
                (
                    float(parts[1]),
                    complex(float(parts[2].rstrip(",")), float(parts[3])),
                )
            )
    assert samples
    v_in = samples[0][1]
    v_outm = samples[1][1]
    assert abs(v_in) == pytest.approx(0.5, rel=0.02)
    assert abs(v_in - v_outm) == pytest.approx(1.0, rel=0.02)


def test_cli_transformer_exports_ruthroff_spice(tmp_path: Path) -> None:
    out = tmp_path / "ruthroff.cir"
    code = main(
        [
            "transformer",
            "--kind",
            "ruthroff",
            "--z-low",
            "50",
            "--z-high",
            "200",
            "--core",
            "FT240-43",
            "--frequency",
            "3.5M",
            "--f-max",
            "30M",
            "--power",
            "100",
            "--export-spice",
            str(out),
        ]
    )
    assert code == 0
    assert out.is_file()
    assert "TL1 in 0 0 outm" in out.read_text(encoding="utf-8")
