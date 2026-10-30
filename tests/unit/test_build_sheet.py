"""BOM / build-sheet export tests (Phase 12 #7)."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.harmonics import Harmonic, HarmonicReport
from filterdesk.analysis.stress import compute_stress
from filterdesk.components_std import ESeries
from filterdesk.domain.circuit import (
    Circuit,
    IdealInductor,
    IdealSeriesLC,
    NonIdealCapacitor,
    NonIdealInductor,
    Port,
    physical_components,
)
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    ElementRole,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.io.build_sheet import (
    BOM_COLUMNS,
    BuildSheetError,
    build_sheet_rows,
    render_bom_csv,
    render_build_sheet_html,
    render_build_sheet_markdown,
    write_build_sheet,
)
from filterdesk.synthesis import synthesize


def _spec() -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.BUTTERWORTH,
        response=FilterResponse.LOW_PASS,
        order=3,
        cutoff_hz=100e6,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
    )


def _ports() -> tuple[Port, Port]:
    return (
        Port(name="port1", node="in", impedance_ohm=50.0),
        Port(name="port2", node="out", impedance_ohm=50.0),
    )


def _series_lc_circuit() -> Circuit:
    port_in, port_out = _ports()
    return Circuit(
        elements=[
            IdealSeriesLC(
                "X1", 1e-6, 1e-12, "in", "out", ElementRole.SERIES
            )
        ],
        port_in=port_in,
        port_out=port_out,
    )


def test_physical_components_expand_compound_and_nonideal() -> None:
    port_in, port_out = _ports()
    circuit = Circuit(
        elements=[
            IdealSeriesLC("X1", 1e-6, 1e-12, "in", "n1", ElementRole.SERIES),
            NonIdealInductor(
                "L2",
                2e-6,
                "n1",
                "out",
                ElementRole.SHUNT,
                series_resistance_ohm=0.5,
                parallel_capacitance_f=1e-12,
            ),
            NonIdealCapacitor(
                "C3",
                3e-12,
                "out",
                "gnd",
                ElementRole.SHUNT,
                esr_ohm=0.1,
                esl_h=1e-9,
            ),
        ],
        port_in=port_in,
        port_out=port_out,
    )
    comps = physical_components(circuit)
    assert [c.ref for c in comps] == ["X1.L", "X1.C", "L2", "C3"]
    assert [c.kind for c in comps] == [
        "inductor",
        "capacitor",
        "inductor",
        "capacitor",
    ]
    assert comps[2].series_resistance_ohm == pytest.approx(0.5)
    assert comps[3].esr_ohm == pytest.approx(0.1)
    assert comps[3].esl_h == pytest.approx(1e-9)
    assert all(c.element_id for c in comps)


def test_rows_include_tolerances_and_stress() -> None:
    circuit = synthesize(_spec()).circuit
    base = build_sheet_rows(circuit)
    assert base
    ref = base[0].ref
    stress = compute_stress(circuit, power_w=10.0, frequency_hz=100e6)
    rows = build_sheet_rows(
        circuit, tolerances={ref: 5.0}, stress=stress
    )
    row = next(r for r in rows if r.ref == ref)
    assert row.tolerance_pct == pytest.approx(5.0)
    assert row.v_peak_v is not None and row.v_peak_v > 0.0
    assert row.i_peak_a is not None and row.i_peak_a > 0.0


def test_write_bom_csv(tmp_path: Path) -> None:
    circuit = synthesize(_spec()).circuit
    out = tmp_path / "bom.csv"
    returned = write_build_sheet(circuit, out)
    assert returned == out
    rows = list(csv.reader(out.read_text(encoding="utf-8").splitlines()))
    assert rows[0] == list(BOM_COLUMNS)
    expected = build_sheet_rows(circuit)
    assert len(rows) - 1 == len(expected)
    assert [r[0] for r in rows[1:]] == [r.ref for r in expected]


def test_write_build_sheet_markdown(tmp_path: Path) -> None:
    circuit = synthesize(_spec()).circuit
    out = tmp_path / "sheet.md"
    write_build_sheet(
        circuit,
        out,
        spec=_spec(),
        power_w=5.0,
        title="My filter",
        notes=["Use 1% parts.", "Toroid T50-2"],
    )
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# My filter")
    assert "## Specification" in text
    assert "## Bill of materials" in text
    assert "| Ref | Role | Type | Value |" in text
    assert "Forward power | 5 W" in text
    assert "- Use 1% parts." in text
    assert "- Toroid T50-2" in text


def test_build_sheet_includes_harmonic_rejection() -> None:
    report = HarmonicReport(
        fundamental_hz=100e6,
        fundamental_s21_db=-0.2,
        harmonics=(
            Harmonic(2, 200e6, -45.0, 44.8),
            Harmonic(3, 300e6, -62.0, 61.8),
        ),
    )
    text = render_build_sheet_markdown(
        build_sheet_rows(_series_lc_circuit()), harmonics=report
    )
    assert "## Harmonic rejection" in text
    assert "| 2 | 200 MHz | -45.000 dB | 44.8 dB |" in text
    assert "Worst harmonic: order 2 (44.8 dB)." in text

    html = render_build_sheet_html(
        build_sheet_rows(_series_lc_circuit()), harmonics=report
    )
    assert "<h2>Harmonic rejection</h2>" in html
    assert "<td>200 MHz</td>" in html
    assert "Worst harmonic: order 2" in html


def test_cli_build_sheet_includes_harmonics(
    tmp_path: Path,
) -> None:
    out = tmp_path / "tx_sheet.md"
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
            "7M",
            "--points",
            "256",
            "--harmonics",
            "--export-build-sheet",
            str(out),
        ]
    )
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "## Harmonic rejection" in text
    assert "Worst harmonic: order" in text


def test_html_renderer_escapes_text() -> None:
    circuit = _series_lc_circuit()
    html = render_build_sheet_html(
        build_sheet_rows(circuit),
        spec=_spec(),
        title="<bad>",
        notes=["a & b"],
    )
    assert "<table>" in html
    assert "&lt;bad&gt;" in html
    assert "a &amp; b" in html
    assert "<bad>" not in html


def test_markdown_renderer_without_spec_or_notes() -> None:
    text = render_build_sheet_markdown(build_sheet_rows(_series_lc_circuit()))
    assert text.startswith("# Filter build sheet")
    assert "## Specification" not in text
    assert "## Notes" not in text
    assert "X1.L" in text and "X1.C" in text


def test_unknown_suffix_raises(tmp_path: Path) -> None:
    with pytest.raises(BuildSheetError, match="unsupported"):
        write_build_sheet(_series_lc_circuit(), tmp_path / "sheet.pdf")


def test_cli_export_build_sheet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "cli_bom.md"
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
            "--power",
            "10",
            "--export-build-sheet",
            str(out),
        ]
    )
    assert code == 0
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "## Bill of materials" in text
    assert "Forward power | 10 W" in text
    assert "Wrote" in capsys.readouterr().err


def test_rows_snap_to_e_series() -> None:
    rows = build_sheet_rows(synthesize(_spec()).circuit, series=ESeries.E24)
    lc = [row for row in rows if row.kind in {"inductor", "capacitor"}]
    assert lc
    for row in lc:
        assert row.series == "E24"
        assert row.nearest_value is not None
        assert row.delta_pct is not None
        assert abs(row.delta_pct) < 50.0


def test_rows_group_identical_parts() -> None:
    port_in, port_out = _ports()
    circuit = Circuit(
        elements=[
            IdealInductor("L1", 1e-6, "in", "n1", ElementRole.SERIES),
            IdealInductor("L2", 1e-6, "n1", "out", ElementRole.SERIES),
        ],
        port_in=port_in,
        port_out=port_out,
    )
    assert len(build_sheet_rows(circuit)) == 2
    grouped = build_sheet_rows(circuit, group=True)
    assert len(grouped) == 1
    assert grouped[0].qty == 2
    assert grouped[0].ref == "L1, L2"


def test_rows_report_dcr_and_srf() -> None:
    port_in, port_out = _ports()
    inductance = 1e-6
    cp = 4e-12
    circuit = Circuit(
        elements=[
            NonIdealInductor(
                "L1",
                inductance,
                "in",
                "out",
                ElementRole.SERIES,
                series_resistance_ohm=0.25,
                parallel_capacitance_f=cp,
            )
        ],
        port_in=port_in,
        port_out=port_out,
    )
    row = build_sheet_rows(circuit)[0]
    assert row.dcr_ohm == pytest.approx(0.25)
    expected_srf = 1.0 / (2.0 * math.pi * math.sqrt(inductance * cp))
    assert row.srf_hz == pytest.approx(expected_srf)


def test_render_bom_csv_column_subset() -> None:
    rows = build_sheet_rows(synthesize(_spec()).circuit)
    text = render_bom_csv(rows, columns=("ref", "qty", "type", "value"))
    assert text.splitlines()[0] == "ref,qty,type,value"


def test_cli_build_sheet_series_and_group(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "bom.csv"
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
            "--export-build-sheet",
            str(out),
            "--bom-series",
            "E24",
            "--bom-group",
            "--bom-columns",
            "ref,qty,type,value,series,nearest_value,delta_pct",
        ]
    )
    assert code == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "ref,qty,type,value,series,nearest_value,delta_pct"
    assert len(lines) >= 2
    capsys.readouterr()
