"""SPICE export for Guanella TLTs."""

from __future__ import annotations

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
    assert out.read_text(encoding="utf-8").startswith("* FilterDesk Guanella TLT")


def test_tlt_export_rejects_non_guanella() -> None:
    with pytest.raises(SpiceExportError, match="Guanella"):
        tlt_spice_netlist(BalunSpec(kind="ruthroff", turns_ratio=0.5))


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
