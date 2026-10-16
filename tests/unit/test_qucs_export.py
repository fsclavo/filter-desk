"""Qucs `.sch` schematic export tests (Phase 10)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from filterdesk.__main__ import main
from filterdesk.domain.circuit import (
    Circuit,
    IdealBruneLC,
    IdealSeriesLC,
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
from filterdesk.io.qucs import qucs_schematic, write_qucs_schematic
from filterdesk.io.spice import SpiceExportError
from filterdesk.synthesis import synthesize

_WIRE = re.compile(r"^\s*<(-?\d+) (-?\d+) (-?\d+) (-?\d+) \"\"", re.MULTILINE)


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


def test_qucs_structure() -> None:
    circuit = synthesize(_spec()).circuit
    text = qucs_schematic(circuit)
    assert text.startswith("<Qucs Schematic 0.0.19>")
    assert "<Components>" in text and "</Components>" in text
    assert "<Wires>" in text and "</Wires>" in text
    assert '<Port P1 ' in text and '<Port P2 ' in text
    # Each shunt element adds a GND component.
    n_shunt = sum(
        1 for el in circuit.elements if el.role == ElementRole.SHUNT
    )
    assert text.count("<GND ") == n_shunt


def test_qucs_wires_orthogonal_and_nonzero() -> None:
    circuit = synthesize(_spec()).circuit
    text = qucs_schematic(circuit)
    wires = [(int(a), int(b), int(c), int(d)) for a, b, c, d in _WIRE.findall(text)]
    assert wires
    for x1, y1, x2, y2 in wires:
        assert (x1, y1) != (x2, y2)  # no zero-length wire
        assert x1 == x2 or y1 == y2  # orthogonal


def test_qucs_series_lc_expands_to_two_components() -> None:
    pin_in, pin_out = _ports()
    el = IdealSeriesLC(
        id="X1",
        value_h=1e-6,
        value_f=1e-12,
        node_a="in",
        node_b="out",
        role=ElementRole.SERIES,
    )
    text = qucs_schematic(Circuit(elements=[el], port_in=pin_in, port_out=pin_out))
    assert "<L X1L " in text
    assert "<C X1C " in text


def test_qucs_rejects_unsupported_arm() -> None:
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
        qucs_schematic(Circuit(elements=[el], port_in=pin_in, port_out=pin_out))


def test_write_qucs(tmp_path: Path) -> None:
    circuit = synthesize(_spec()).circuit
    out = tmp_path / "f.sch"
    assert write_qucs_schematic(circuit, out) == out
    assert out.read_text(encoding="utf-8").startswith("<Qucs Schematic")


def test_cli_analyze_export_qucs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "cli.sch"
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
            "--export-qucs",
            str(out),
        ]
    )
    capsys.readouterr()
    assert code == 0
    assert out.read_text(encoding="utf-8").startswith("<Qucs Schematic")
