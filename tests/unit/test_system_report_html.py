"""Standalone HTML system report."""

from __future__ import annotations

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.services.diplexer import DiplexerConfig, design_diplexer
from filterdesk.services.system_report import (
    render_magnitude_png,
    render_system_report_html,
)


def _design():
    return design_diplexer(
        DiplexerConfig(
            low_cutoff_hz=30e6,
            high_cutoff_hz=40e6,
            order=5,
            family=ApproximationFamily.CHEBYSHEV_TYPE_I,
            ripple_db=0.1,
        ),
        SweepConfig(1e6, 200e6, 401, SweepSpacing.LOGARITHMIC),
    )


def test_magnitude_png_is_valid_png() -> None:
    png = render_magnitude_png(_design())
    assert png.startswith(b"\x89PNG")
    assert len(png) > 1000


def test_html_report_contains_summary_images_and_bom() -> None:
    html = render_system_report_html(
        _design(),
        schematic_images=(("Low", b"\x89PNG-low"), ("High", b"\x89PNG-high")),
        notes=["Test note."],
    )
    assert "<title>System report" in html
    assert "Low insertion loss" in html
    assert "Magnitude" in html
    assert "data:image/png;base64," in html
    assert "<h3>Low</h3>" in html and "<h3>High</h3>" in html
    assert "Bill of materials" in html
    assert "| Low |" not in html
    assert "<td>Low</td>" in html and "<td>High</td>" in html
    assert "Test note." in html
