"""System Monte-Carlo / yield analysis."""

from __future__ import annotations

import pytest

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.montecarlo import ToleranceDistribution
from filterdesk.services.diplexer import DiplexerConfig, design_diplexer
from filterdesk.services.duplexer import DuplexerConfig, design_duplexer
from filterdesk.services.system_montecarlo import (
    SystemMonteCarloConfig,
    analyze_system_montecarlo,
)


def _diplexer():
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


def test_diplexer_montecarlo_reports_yield() -> None:
    result = analyze_system_montecarlo(
        _diplexer(),
        SystemMonteCarloConfig(
            n_trials=20,
            tolerance_pct=2.0,
            seed=42,
            max_insertion_loss_db=3.0,
            max_out_of_band_db=-20.0,
        ),
    )
    assert result.n_trials == 20
    assert 0.0 <= result.yield_fraction <= 1.0
    assert result.insertion_max_db is not None
    assert result.out_of_band_max_db is not None
    assert result.isolation_min_db is None
    assert "yield" in result.summary()


def test_duplexer_montecarlo_reports_isolation_yield() -> None:
    design = design_duplexer(
        DuplexerConfig(
            tx_center_hz=145e6,
            tx_bandwidth_hz=1e6,
            rx_center_hz=147e6,
            rx_bandwidth_hz=1e6,
            order=6,
            family=ApproximationFamily.CHEBYSHEV_TYPE_I,
            ripple_db=0.1,
            min_isolation_db=60.0,
        ),
        SweepConfig(140e6, 152e6, 201, SweepSpacing.LOGARITHMIC),
    )
    result = analyze_system_montecarlo(
        design,
        SystemMonteCarloConfig(
            n_trials=20,
            tolerance_pct=1.0,
            distribution=ToleranceDistribution.NORMAL,
            seed=7,
            max_insertion_loss_db=3.0,
        ),
    )
    assert result.isolation_min_db is not None
    assert result.isolation_p50_db is not None
    assert result.isolation_target_db == 60.0
    assert result.isolation_failures >= 0
    assert result.out_of_band_max_db is None


def test_montecarlo_is_deterministic_with_seed() -> None:
    config = SystemMonteCarloConfig(
        n_trials=10, tolerance_pct=2.0, seed=123, max_out_of_band_db=-20.0
    )
    first = analyze_system_montecarlo(_diplexer(), config)
    second = analyze_system_montecarlo(_diplexer(), config)
    assert first == second


def test_montecarlo_validation() -> None:
    with pytest.raises(ValueError, match="n_trials"):
        SystemMonteCarloConfig(n_trials=0)
    with pytest.raises(ValueError, match="tolerance"):
        SystemMonteCarloConfig(tolerance_pct=-1.0)
