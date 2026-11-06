"""DRC and Gerber export for routed coupled-line layouts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.services.coupled_layout import (
    CoupledLayout,
    LayoutMode,
    LayoutTrace,
    build_coupled_layout,
)
from filterdesk.services.coupled_line import (
    CoupledLineBpfConfig,
    design_coupled_line_bpf,
)
from filterdesk.services.coupled_pcb import (
    DrcRules,
    check_layout_drc,
    render_layout_gerber,
    write_layout_gerber,
)


def _design():
    return design_coupled_line_bpf(
        CoupledLineBpfConfig(
            center_hz=100e6,
            bandwidth_hz=10e6,
            order=3,
            family=ApproximationFamily.CHEBYSHEV_TYPE_I,
            ripple_db=0.1,
        ),
        SweepConfig(80e6, 120e6, 201, SweepSpacing.LINEAR),
        substrate="FR4",
    )


def _layout() -> CoupledLayout:
    return build_coupled_layout(_design(), LayoutMode.HAIRPIN)


def test_hairpin_layout_passes_default_drc() -> None:
    layout = _layout()
    assert layout.routed
    report = check_layout_drc(layout)
    assert report.ok
    assert report.violations == ()
    assert report.summary() == "DRC: no violations"


def test_edge_mode_is_rejected_but_interdigital_is_routed() -> None:
    design = _design()
    edge = check_layout_drc(build_coupled_layout(design, LayoutMode.EDGE))
    assert not edge.ok
    assert any(v.code == "not-routed" for v in edge.errors)
    interdigital = build_coupled_layout(design, LayoutMode.INTERDIGITAL)
    assert interdigital.routed
    assert interdigital.vias
    report = check_layout_drc(interdigital)
    assert report.ok


def test_drc_flags_width_and_gap() -> None:
    layout = CoupledLayout(
        mode=LayoutMode.HAIRPIN,
        width_mm=5.0,
        height_mm=5.0,
        traces=(
            LayoutTrace(0.0, 0.0, 2.0, 0.0, 0.10, "A", net="A"),
            LayoutTrace(0.0, 0.12, 2.0, 0.12, 0.20, "B", net="B"),
        ),
        section_lengths_mm=(),
        routed=True,
    )
    report = check_layout_drc(layout, DrcRules(min_width_mm=0.15, min_gap_mm=0.15))
    codes = {violation.code for violation in report.violations}
    assert "min-width" in codes
    assert "min-gap" in codes
    assert not report.ok
    assert "min-width" in report.summary()


def test_gerber_contains_copper_outline_and_drill() -> None:
    gerber = render_layout_gerber(_layout())
    assert gerber.copper.startswith("G04 FilterDesk")
    assert "%FSLAX46Y46*%" in gerber.copper
    assert "%MOMM*%" in gerber.copper
    assert "%ADD10C," in gerber.copper
    assert "D02*" in gerber.copper
    assert "D01*" in gerber.copper
    assert gerber.copper.rstrip().endswith("M02*")
    assert "Edge_Cuts" in gerber.outline or "board outline" in gerber.outline
    assert gerber.outline.count("D01*") >= 4
    assert gerber.drill.startswith("M48")
    assert gerber.drill.rstrip().endswith("M30")


def test_gerber_drill_with_holes() -> None:
    gerber = render_layout_gerber(
        _layout(), holes_mm=((5.0, 5.0, 3.2), (10.0, 5.0, 3.2))
    )
    assert "T1C3.200" in gerber.drill
    assert gerber.drill.count("X5.000Y5.000") == 1
    assert gerber.drill.count("X10.000Y5.000") == 1


def test_write_layout_gerber(tmp_path: Path) -> None:
    paths = write_layout_gerber(_layout(), tmp_path, stem="test-board")
    assert paths[0].name == "test-board-F_Cu.gbr"
    assert paths[1].name == "test-board-Edge_Cuts.gbr"
    assert paths[2].name == "test-board.drl"
    assert all(path.is_file() for path in paths)



def test_cli_writes_gerber_and_reports_drc(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "coupled.s2p"
    gerber_dir = tmp_path / "gerber"
    assert (
        main(
            [
                "coupled-line",
                "--center",
                "100M",
                "--bandwidth",
                "10M",
                "--order",
                "3",
                "--substrate",
                "FR4",
                "--output",
                str(output),
                "--gerber-dir",
                str(gerber_dir),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["routed"] is True
    assert payload["drc"] == "DRC: no violations"
    assert len(payload["gerber"]) == 3
    for path in payload["gerber"]:
        assert Path(path).is_file()


def test_cli_rejects_gerber_for_unrouted_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "coupled.s2p"
    assert (
        main(
            [
                "coupled-line",
                "--center",
                "100M",
                "--bandwidth",
                "10M",
                "--order",
                "3",
                "--output",
                str(output),
                "--layout",
                "edge",
                "--layout-output",
                str(tmp_path / "edge.svg"),
                "--gerber-dir",
                str(tmp_path / "gerber"),
            ]
        )
        == 2
    )
    assert "not-routed" in capsys.readouterr().err


def test_interdigital_gerber_flashes_vias_and_drills_holes() -> None:
    layout = build_coupled_layout(_design(), LayoutMode.INTERDIGITAL)
    gerber = render_layout_gerber(layout)
    assert layout.vias
    assert gerber.copper.count("D03*") == len(layout.vias)
    assert "T1C0.300" in gerber.drill
    hole_lines = [
        line for line in gerber.drill.splitlines() if line.startswith("X")
    ]
    assert len(hole_lines) == len(layout.vias)


def test_cli_interdigital_gerber(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "coupled.s2p"
    gerber_dir = tmp_path / "gerber"
    assert (
        main(
            [
                "coupled-line",
                "--center",
                "100M",
                "--bandwidth",
                "10M",
                "--order",
                "3",
                "--substrate",
                "FR4",
                "--layout",
                "interdigital",
                "--gerber-dir",
                str(gerber_dir),
                "--output",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["routed"] is True
    assert payload["drc"] == "DRC: no violations"
    assert len(payload["gerber"]) == 3
