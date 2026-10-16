"""SPICE / LTspice netlist export tests (Phase 10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.circuit import (
    Circuit,
    IdealBruneLC,
    IdealSeriesLC,
    NonIdealInductor,
    Port,
)
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    ElementRole,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.io.spice import (
    SpiceExportError,
    ltspice_asc,
    spice_netlist,
    write_ltspice_asc,
    write_spice_netlist,
)
from filterdesk.synthesis import synthesize


def _ports() -> tuple[Port, Port]:
    return (
        Port(name="port1", node="in", impedance_ohm=50.0),
        Port(name="port2", node="out", impedance_ohm=50.0),
    )


def _spec() -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.LOW_PASS,
        order=5,
        cutoff_hz=100e6,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.1,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
    )


def test_netlist_has_source_load_and_directives() -> None:
    circuit = synthesize(_spec()).circuit
    sweep = SweepConfig(1e6, 1e9, 101, SweepSpacing.LOGARITHMIC)
    text = spice_netlist(circuit, title="t", ac=sweep)
    assert "* t" in text
    assert "V1 V1_src 0 AC 1" in text
    assert "RV1s V1_src in 50" in text
    assert "Rload out 0 50" in text
    assert ".ac dec 101 1000000 1000000000" in text
    assert text.rstrip().endswith(".end")


def test_ground_is_zero_and_components_present() -> None:
    circuit = synthesize(_spec()).circuit
    text = spice_netlist(circuit)
    line_nodes = [
        ln.split() for ln in text.splitlines() if ln and not ln.startswith(("*", "."))
    ]
    # Every ideal L/C is a single primitive line.
    for el in circuit.elements:
        assert any(ln[0] == f"L{el.id}" or ln[0] == f"C{el.id}" for ln in line_nodes)
    assert " 0 " in text or " 0\n" in text


def test_series_lc_expands_to_two_primitives() -> None:
    pin, pout = _ports()
    el = IdealSeriesLC(
        id="X1",
        value_h=1e-6,
        value_f=1e-12,
        node_a="in",
        node_b="out",
        role=ElementRole.SERIES,
    )
    circuit = Circuit(elements=[el], port_in=pin, port_out=pout)
    text = spice_netlist(circuit)
    assert "LX1L in nc1 1e-06" in text
    assert "CX1C nc1 out 1e-12" in text


def test_nonideal_inductor_expands_loss_and_parasitic() -> None:
    pin, pout = _ports()
    el = NonIdealInductor(
        id="L1",
        value_h=1e-7,
        node_a="in",
        node_b="out",
        role=ElementRole.SERIES,
        series_resistance_ohm=0.5,
        parallel_capacitance_f=2e-12,
    )
    circuit = Circuit(elements=[el], port_in=pin, port_out=pout)
    text = spice_netlist(circuit)
    assert "LL1 in nc1" in text
    assert "RL1r nc1 out 0.5" in text
    assert "CL1cp in out 2e-12" in text


def test_zero_dcr_is_ideal() -> None:
    pin, pout = _ports()
    el = NonIdealInductor(
        id="L1", value_h=1e-7, node_a="in", node_b="out", role=ElementRole.SERIES
    )
    text = spice_netlist(Circuit(elements=[el], port_in=pin, port_out=pout))
    assert "LL1 in out 1e-07" in text
    assert "RL1r" not in text


def test_empty_circuit_raises() -> None:
    pin, pout = _ports()
    with pytest.raises(SpiceExportError):
        spice_netlist(Circuit(elements=[], port_in=pin, port_out=pout))


def test_write_spice_netlist(tmp_path: Path) -> None:
    circuit = synthesize(_spec()).circuit
    out = tmp_path / "f.net"
    path = write_spice_netlist(circuit, out)
    assert path == out
    assert out.read_text(encoding="utf-8").rstrip().endswith(".end")


def test_cli_analyze_export_spice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "cli.net"
    code = main(
        [
            "analyze",
            "--family",
            "butterworth",
            "--response",
            "low_pass",
            "--order",
            "3",
            "--cutoff",
            "100M",
            "--points",
            "32",
            "--export-spice",
            str(out),
        ]
    )
    capsys.readouterr()
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "Rload out 0 50" in text
    assert ".end" in text


def _sweep() -> SweepConfig:
    return SweepConfig(1e6, 1e9, 101, SweepSpacing.LOGARITHMIC)


def test_ltspice_asc_structure() -> None:
    circuit = synthesize(_spec()).circuit
    text = ltspice_asc(circuit, title="t", ac=_sweep())
    lines = text.splitlines()
    assert lines[0] == "Version 4"
    assert lines[1].startswith("SHEET 1")
    # V1 + Rsource + one symbol per ideal L/C + Rload.
    assert text.count("SYMBOL ") == len(circuit.elements) + 3
    assert "SYMATTR InstName V1" in text
    assert "SYMATTR Value AC 1" in text
    assert "SYMATTR InstName Rsource" in text
    assert "SYMATTR InstName Rload" in text
    # Net labels (FLAGs) include ground and the ladder nodes.
    assert " 0" in text
    assert "FLAG " in text
    assert ".ac dec 101" in text


def test_ltspice_asc_pins_have_matching_flags() -> None:
    pin = {
        "ind": [(16, 16), (16, 96)],
        "res": [(16, 16), (16, 96)],
        "cap": [(16, 0), (16, 64)],
        "voltage": [(0, 16), (0, 96)],
    }
    circuit = synthesize(_spec()).circuit
    lines = ltspice_asc(circuit).splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].startswith("SYMBOL "):
            i += 1
            continue
        _, symbol, cx, cy, _rot = lines[i].split()
        got: set[tuple[int, int]] = set()
        j = i + 1
        while j < len(lines) and not lines[j].startswith("SYMBOL "):
            if lines[j].startswith("FLAG "):
                parts = lines[j].split()
                got.add((int(parts[1]), int(parts[2])))
            j += 1
        expected = {(int(cx) + dx, int(cy) + dy) for dx, dy in pin[symbol]}
        assert got == expected
        i = j


def test_ltspice_asc_series_lc_expands_with_internal_node() -> None:
    pin_in, pin_out = _ports()
    el = IdealSeriesLC(
        id="X1",
        value_h=1e-6,
        value_f=1e-12,
        node_a="in",
        node_b="out",
        role=ElementRole.SERIES,
    )
    text = ltspice_asc(Circuit(elements=[el], port_in=pin_in, port_out=pin_out))
    assert "SYMATTR InstName X1L" in text
    assert "SYMATTR InstName X1C" in text
    assert " n_X1" in text  # internal node label


def test_ltspice_asc_rejects_unsupported_arm() -> None:
    pin_in, pin_out = _ports()
    el = IdealBruneLC(
        id="X1",
        series_l_h=1e-6,
        series_c_f=1e-12,
        parallel_l_h=1e-6,
        parallel_c_f=1e-12,
        node_a="in",
        node_b="out",
        role=ElementRole.SERIES,
    )
    with pytest.raises(SpiceExportError):
        ltspice_asc(Circuit(elements=[el], port_in=pin_in, port_out=pin_out))


def test_write_ltspice_asc(tmp_path: Path) -> None:
    circuit = synthesize(_spec()).circuit
    out = tmp_path / "f.asc"
    assert write_ltspice_asc(circuit, out) == out
    assert out.read_text(encoding="utf-8").startswith("Version 4")


def test_cli_analyze_export_asc(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "cli.asc"
    code = main(
        [
            "analyze",
            "--family",
            "butterworth",
            "--response",
            "low_pass",
            "--order",
            "3",
            "--cutoff",
            "100M",
            "--points",
            "32",
            "--export-asc",
            str(out),
        ]
    )
    capsys.readouterr()
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("Version 4")
    assert "SYMATTR InstName Rload" in text
