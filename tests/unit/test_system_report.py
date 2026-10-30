"""Combined system BOM/build-sheet export."""

from __future__ import annotations

from pathlib import Path

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.io.build_sheet import (
    render_multiplexer_bom_csv,
    write_multiplexer_build_sheet,
)
from filterdesk.services.diplexer import DiplexerConfig, design_diplexer
from filterdesk.services.report import system_report


def _design():
    config = DiplexerConfig(
        low_cutoff_hz=30e6,
        high_cutoff_hz=40e6,
        order=5,
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        ripple_db=0.1,
    )
    return design_diplexer(
        config, SweepConfig(1e6, 200e6, 401, SweepSpacing.LOGARITHMIC)
    )


def test_system_report_has_branches_and_metrics() -> None:
    report = system_report(_design())
    assert report.title == "LPF + HPF diplexer"
    assert [branch.label for branch in report.branches] == ["Low", "High"]
    keys = {key for key, _value in report.summary}
    assert "Low band" in keys
    assert "High insertion loss" in keys
    assert "Crossover" in keys
    assert any("combined network" in note for note in report.notes)


def test_combined_bom_markdown_csv_and_html(tmp_path: Path) -> None:
    report = system_report(_design())
    branches = [(branch.label, branch.circuit) for branch in report.branches]
    markdown_path = tmp_path / "system.md"
    write_multiplexer_build_sheet(
        branches,
        markdown_path,
        summary=report.summary,
        title=report.title,
        notes=report.notes,
    )
    markdown = markdown_path.read_text(encoding="utf-8")
    assert markdown.startswith("# LPF + HPF diplexer")
    assert "## System" in markdown
    assert "| Branch | Ref | Role |" in markdown
    assert "| Low |" in markdown and "| High |" in markdown
    assert "Low insertion loss" in markdown

    csv_path = tmp_path / "system.csv"
    write_multiplexer_build_sheet(branches, csv_path)
    csv_text = csv_path.read_text(encoding="utf-8")
    assert csv_text.splitlines()[0].startswith("branch,ref,qty,")
    assert "\nLow," in csv_text and "\nHigh," in csv_text

    html_path = tmp_path / "system.html"
    write_multiplexer_build_sheet(
        branches,
        html_path,
        summary=report.summary,
        title="<system>",
    )
    html = html_path.read_text(encoding="utf-8")
    assert "&lt;system&gt;" in html
    assert "<th>Branch</th>" in html
    assert "<td>Low</td>" in html and "<td>High</td>" in html


def test_combined_csv_branch_column_is_always_first() -> None:
    report = system_report(_design())
    branches = [(branch.label, branch.circuit) for branch in report.branches]
    text = render_multiplexer_bom_csv(branches, columns=("ref", "value"))
    assert text.splitlines()[0] == "branch,ref,value"
