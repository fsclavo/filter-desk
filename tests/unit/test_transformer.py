"""Ideal output transformer and exact unequal-termination tests."""

from __future__ import annotations

import numpy as np
import pytest

from filterdesk.analysis.adapters.abcd_ladder import (
    _element_abcd,
    abcd_to_s,
    abcd_zin_zout,
    cascade_abcd,
    transformer_abcd,
)
from filterdesk.analysis.adapters.skrf_analyzer import ScikitRFAnalyzer
from filterdesk.analysis.compliance import check_spec_compliance
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.circuit import physical_components
from filterdesk.domain.enums import (
    ApproximationFamily as Fam,
)
from filterdesk.domain.enums import (
    CutoffDefinition as Cut,
)
from filterdesk.domain.enums import (
    FilterResponse as Resp,
)
from filterdesk.domain.enums import (
    TopologyId as Topo,
)
from filterdesk.domain.project import circuit_from_mapping, circuit_to_mapping
from filterdesk.domain.specs import FilterSpec
from filterdesk.io.build_sheet import write_build_sheet
from filterdesk.io.qucs import qucs_schematic
from filterdesk.io.spice import SpiceExportError, ltspice_asc, spice_netlist
from filterdesk.synthesis import synthesize

ZCUT = 100e6


def _spec(zs: float, zl: float) -> FilterSpec:
    return FilterSpec(
        family=Fam.BUTTERWORTH,
        response=Resp.LOW_PASS,
        order=3,
        cutoff_hz=ZCUT,
        z_source_ohm=zs,
        z_load_ohm=zl,
        topology_id=Topo.LADDER_LP_SERIES_L_INPUT,
        cutoff_definition=Cut.HALF_POWER_3DB,
    )


def _s21(circuit, f: np.ndarray) -> np.ndarray:
    omega = 2 * np.pi * np.asarray(f, dtype=float)
    abcd = cascade_abcd([_element_abcd(el, omega) for el in circuit.elements])
    if circuit.output_transformer_ratio != 1.0:
        abcd = abcd @ transformer_abcd(circuit.output_transformer_ratio, omega.size)
    return abcd_to_s(
        abcd, circuit.port_in.impedance_ohm, circuit.port_out.impedance_ohm
    )[1]


def test_transformer_impedance_ratio() -> None:
    zin, zout = abcd_zin_zout(transformer_abcd(2.0, 1), 50.0, 50.0)
    assert zin[0].real == pytest.approx(200.0)
    assert zout[0].real == pytest.approx(12.5)


def test_unequal_z_matches_equal_z_response() -> None:
    equal = synthesize(_spec(50.0, 50.0)).circuit
    asym = synthesize(_spec(50.0, 75.0)).circuit
    assert asym.output_transformer_ratio == pytest.approx(np.sqrt(50.0 / 75.0))
    for a, b in zip(equal.elements, asym.elements, strict=True):
        assert type(a) is type(b)
    f = np.logspace(6, 9, 201)
    assert np.max(np.abs(np.abs(_s21(asym, f)) - np.abs(_s21(equal, f)))) < 1e-12


def test_skrf_includes_output_transformer() -> None:
    circuit = synthesize(_spec(50.0, 75.0)).circuit
    sweep = SweepConfig(10e6, 1e9, 64, SweepSpacing.LOGARITHMIC)
    abcd = _s21(circuit, sweep.frequencies_hz())
    skrf = ScikitRFAnalyzer().analyze(circuit, sweep)
    assert np.max(np.abs(np.abs(skrf.s21) - np.abs(abcd))) < 1e-9


def test_transformer_persists_and_is_in_bom(tmp_path) -> None:
    circuit = synthesize(_spec(50.0, 75.0)).circuit
    restored = circuit_from_mapping(circuit_to_mapping(circuit))
    assert restored.output_transformer_ratio == pytest.approx(
        circuit.output_transformer_ratio
    )
    assert "T1" in [c.ref for c in physical_components(circuit)]
    table = {row["ref"]: row for row in circuit.component_table()}
    assert table["T1"]["type"] == "transformer"

    csv_path = tmp_path / "bom.csv"
    write_build_sheet(circuit, csv_path, spec=_spec(50.0, 75.0))
    text = csv_path.read_text(encoding="utf-8")
    assert "T1" in text and "transformer" in text

    md_path = tmp_path / "sheet.md"
    write_build_sheet(circuit, md_path, spec=_spec(50.0, 75.0))
    assert "0.8165:1" in md_path.read_text(encoding="utf-8")


def test_transformer_exports_fail_clearly() -> None:
    circuit = synthesize(_spec(50.0, 75.0)).circuit
    with pytest.raises(SpiceExportError, match="transformer"):
        spice_netlist(circuit)
    with pytest.raises(SpiceExportError, match="transformer"):
        ltspice_asc(circuit)
    with pytest.raises(SpiceExportError, match="transformer"):
        qucs_schematic(circuit)


def test_compliance_with_transformer() -> None:
    spec = _spec(50.0, 75.0)
    report = check_spec_compliance(spec, synthesize(spec).circuit, points=1200)
    assert report.ok, report.issues
    assert any("ideal output transformer" in note for note in report.notes)


def test_component_table_shows_transformer() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.panels.component_table import ComponentTablePanel

    app = QApplication.instance() or QApplication([])
    panel = ComponentTablePanel()
    panel.set_circuit(synthesize(_spec(50.0, 75.0)).circuit)
    rows = [
        (panel._table.item(row, 0).text(), panel._table.item(row, 2).text())
        for row in range(panel._table.rowCount())
    ]
    assert ("T1", "transformer") in rows
    panel.close()
    assert app is not None
