"""Winding diagram and build-sheet integration."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from filterdesk.components_std import winding_diagram, winding_diagram_for_spec
from filterdesk.domain.circuit import BalunSpec, Circuit, IdealResistor, Port
from filterdesk.io.build_sheet import write_build_sheet


def test_autotransformer_diagram_has_tap_and_connection() -> None:
    diagram = winding_diagram(
        kind="unun",
        topology="autotransformer",
        n_primary=3,
        n_secondary=21,
        total_turns=21,
        core="FT240-43",
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=2500.0,
    )
    ET.fromstring(diagram.svg)
    assert "TAP (3T)" in diagram.svg
    assert "Winding on toroid" not in diagram.svg
    assert "21T total" in diagram.svg
    assert any("tap at turn 3" in line for line in diagram.schedule)
    assert any("no galvanic isolation" in line for line in diagram.schedule)


def test_isolated_diagram_has_two_windings() -> None:
    diagram = winding_diagram(
        kind="unun",
        topology="isolated",
        n_primary=3,
        n_secondary=21,
        total_turns=24,
        core="FT240-43",
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=2500.0,
    )
    ET.fromstring(diagram.svg)
    assert "P 3T" in diagram.svg
    assert "S 21T" in diagram.svg
    assert any("Total copper turns: 24" in line for line in diagram.schedule)


def test_spec_diagram_and_build_sheet(tmp_path: Path) -> None:
    spec = BalunSpec(
        kind="unun",
        topology="autotransformer",
        turns_ratio=0.142857,
        total_turns=21,
        turns=3,
        core="FT240-43",
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=2500.0,
    )
    diagram = winding_diagram_for_spec(spec)
    assert "FT240-43" in diagram.svg

    circuit = Circuit(
        elements=[IdealResistor("R1", 0.0, "in", "out")],
        port_in=Port("in", "in", 50.0),
        port_out=Port("out", "out", 2500.0),
        output_balun=spec,
    )
    path = tmp_path / "build.md"
    write_build_sheet(circuit, path)
    assert path.exists()
    assert (tmp_path / "build_winding.svg").exists()
    text = path.read_text(encoding="utf-8")
    assert "## Winding diagram" in text
    assert "build_winding.svg" in text

    html_path = tmp_path / "build.html"
    write_build_sheet(circuit, html_path)
    html = html_path.read_text(encoding="utf-8")
    assert "<h2>Winding diagram</h2>" in html
    assert "<svg" in html


@pytest.mark.parametrize("kind", ["guanella", "ruthroff", "choke"])
def test_tlt_kinds_are_not_autotransformer_drawings(kind: str) -> None:
    diagram = winding_diagram(
        kind=kind,
        topology="autotransformer",
        n_primary=3,
        n_secondary=6,
        total_turns=6,
        core="FT240-43",
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=200.0,
        line_z0_ohm=100.0,
        line_length_m=0.5,
    )
    ET.fromstring(diagram.svg)
    assert "TAP" not in diagram.svg
    assert "Autotransformer" not in " ".join(diagram.schedule)
    assert kind.capitalize() in diagram.svg or kind.upper() in diagram.svg
    if kind == "guanella":
        assert "parallel" in " ".join(diagram.schedule)
    if kind == "ruthroff":
        assert "crossover" in " ".join(diagram.schedule)
    if kind == "choke":
        assert "bifilar" in " ".join(diagram.schedule)


def test_guanella_and_ruthroff_connect_differently() -> None:
    common = dict(
        topology="autotransformer",
        n_primary=3,
        n_secondary=6,
        total_turns=6,
        core="FT240-43",
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=200.0,
        line_z0_ohm=100.0,
        line_length_m=0.5,
    )
    guanella = winding_diagram(kind="guanella", **common)
    ruthroff = winding_diagram(kind="ruthroff", **common)
    assert guanella.svg != ruthroff.svg
    assert "Guanella" in guanella.svg and "Ruthroff" in ruthroff.svg


def test_invalid_turns_rejected() -> None:
    with pytest.raises(ValueError, match="turns"):
        winding_diagram(
            kind="unun",
            topology="autotransformer",
            n_primary=0,
            n_secondary=1,
            total_turns=1,
        )
