"""E-series snapping and combined reanalysis for system designs."""

from __future__ import annotations

import pytest

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std import ESeries, nearest_e_series
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.services.diplexer import DiplexerConfig, design_diplexer
from filterdesk.services.system_snap import snap_system_design


def test_snap_system_recomputes_metrics_and_values() -> None:
    config = DiplexerConfig(
        low_cutoff_hz=30e6,
        high_cutoff_hz=40e6,
        order=5,
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        ripple_db=0.1,
    )
    design = design_diplexer(
        config, SweepConfig(1e6, 200e6, 1001, SweepSpacing.LOGARITHMIC)
    )
    before = design.metrics
    result = snap_system_design(design, ESeries.E24)
    assert result.changed
    assert result.series is ESeries.E24
    assert result.max_delta_pct >= 0.0
    assert result.design.metrics is not before
    assert result.design.network.n_ports == 3
    for circuit in (result.design.low_circuit, result.design.high_circuit):
        for element in circuit.elements:
            for value in (
                getattr(element, "value_h", None),
                getattr(element, "value_f", None),
            ):
                if value is None:
                    continue
                assert nearest_e_series(value, ESeries.E24) == pytest.approx(value)


def test_snap_system_duplexer_reports_target_state() -> None:
    from filterdesk.services.duplexer import DuplexerConfig, design_duplexer

    config = DuplexerConfig(
        tx_center_hz=145e6,
        tx_bandwidth_hz=1e6,
        rx_center_hz=147e6,
        rx_bandwidth_hz=1e6,
        order=6,
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        ripple_db=0.1,
        min_isolation_db=60.0,
    )
    design = design_duplexer(
        config, SweepConfig(140e6, 152e6, 1001, SweepSpacing.LOGARITHMIC)
    )
    result = snap_system_design(design, ESeries.E24)
    assert result.design.network.n_ports == 3
    assert result.design.metrics.worst_isolation_db is not None
    assert result.design.metrics.target_isolation_db == 60.0
    assert isinstance(result.design.metrics.meets_target, bool)


def test_snap_system_triplexer_rebuilds_four_port() -> None:
    from filterdesk.services.multiplexer import (
        MultiplexerBand,
        MultiplexerConfig,
        design_multiplexer,
    )

    config = MultiplexerConfig(
        bands=(
            MultiplexerBand("low", 14e6, 0.3e6),
            MultiplexerBand("mid", 21e6, 0.5e6),
            MultiplexerBand("high", 28e6, 0.5e6),
        ),
        order=5,
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        ripple_db=0.1,
    )
    design = design_multiplexer(
        config, SweepConfig(5e6, 40e6, 1001, SweepSpacing.LOGARITHMIC)
    )
    result = snap_system_design(design, ESeries.E24)
    assert result.design.network.n_ports == 4
    assert len(result.reports) == 3
    assert len(result.design.metrics.bands) == 3
    assert result.max_delta_pct >= 0.0
