"""Conceptual coupled-line layout sketches."""

from __future__ import annotations

import pytest

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.services.coupled_layout import (
    CoupledLayoutError,
    LayoutMode,
    build_coupled_layout,
    render_coupled_layout_svg,
)
from filterdesk.services.coupled_line import (
    CoupledLineBpfConfig,
    design_coupled_line_bpf,
)


def _design(with_substrate: bool = True):
    config = CoupledLineBpfConfig(
        center_hz=100e6,
        bandwidth_hz=10e6,
        order=3,
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        ripple_db=0.1,
    )
    sweep = SweepConfig(
        f_start_hz=80e6,
        f_stop_hz=120e6,
        n_points=201,
        spacing=SweepSpacing.LINEAR,
    )
    return design_coupled_line_bpf(
        config, sweep, substrate="FR4" if with_substrate else None
    )


def test_layout_modes_have_traces_and_lengths() -> None:
    design = _design()
    for mode in LayoutMode:
        layout = build_coupled_layout(design, mode)
        assert layout.traces
        assert len(layout.section_lengths_mm) == 4
        assert all(length > 0 for length in layout.section_lengths_mm)
        assert layout.width_mm > 0
        assert layout.height_mm > 0
        assert mode.value in layout.summary()


def test_layout_svg_contains_traces() -> None:
    layout = build_coupled_layout(_design(), LayoutMode.HAIRPIN)
    svg = render_coupled_layout_svg(layout)
    assert svg.startswith("<?xml")
    assert "<svg" in svg
    assert svg.count("<line") == len(layout.traces)
    assert "not EM-validated" in svg


def test_layout_requires_geometry() -> None:
    with pytest.raises(CoupledLayoutError):
        build_coupled_layout(_design(with_substrate=False))
