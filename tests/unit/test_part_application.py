"""Apply assigned real parts to system circuits."""

from __future__ import annotations

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std import STARTER_PARTS
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.services.diplexer import DiplexerConfig, design_diplexer
from filterdesk.services.part_application import apply_assigned_parts
from filterdesk.services.part_assignment import assign_nearest_parts


def _design():
    return design_diplexer(
        DiplexerConfig(
            low_cutoff_hz=30e6,
            high_cutoff_hz=40e6,
            order=5,
            family=ApproximationFamily.CHEBYSHEV_TYPE_I,
            ripple_db=0.1,
        ),
        SweepConfig(1e6, 200e6, 201, SweepSpacing.LOGARITHMIC),
    )


def test_apply_assigned_parts_changes_values_and_reanalyzes() -> None:
    design = _design()
    assigned = assign_nearest_parts(
        [("Low", design.low_circuit), ("High", design.high_circuit)],
        STARTER_PARTS,
        max_delta_pct=100.0,
    )
    result = apply_assigned_parts(design, assigned.assignments)
    assert result.applied
    assert result.design.network.n_ports == 3
    assert result.design.metrics is not design.metrics
    assert result.design.low_circuit.elements
    assert not result.warnings


def test_composite_parts_get_value_with_warning() -> None:
    from filterdesk.services.multiplexer import (
        MultiplexerBand,
        MultiplexerConfig,
        design_multiplexer,
    )

    design = design_multiplexer(
        MultiplexerConfig(
            bands=(
                MultiplexerBand("low", 14e6, 0.3e6),
                MultiplexerBand("mid", 21e6, 0.5e6),
                MultiplexerBand("high", 28e6, 0.5e6),
            ),
            order=5,
            family=ApproximationFamily.CHEBYSHEV_TYPE_I,
            ripple_db=0.1,
        ),
        SweepConfig(5e6, 40e6, 201, SweepSpacing.LOGARITHMIC),
    )
    branches = [
        (band.label.capitalize(), circuit)
        for band, circuit in zip(design.bands, design.circuits, strict=True)
    ]
    assigned = assign_nearest_parts(branches, STARTER_PARTS, max_delta_pct=100.0)
    result = apply_assigned_parts(design, assigned.assignments)
    assert result.applied
    assert any("composite" in warning for warning in result.warnings)
