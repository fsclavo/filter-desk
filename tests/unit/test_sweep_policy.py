"""Suggested plotting ranges and the Auto sweep policy."""

from __future__ import annotations

import pytest

from filterdesk.analysis.metrics import band_edges
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
)
from filterdesk.domain.specs import FilterSpec, default_topology
from filterdesk.services.bands import BandKind, band_preset_spec, find_band
from filterdesk.services.session import (
    DesignSession,
    default_sweep_for_spec,
    is_default_sweep,
    suggested_sweep_for_spec,
)


def _linear(cutoff_hz: float, response: FilterResponse) -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=response,
        order=5,
        cutoff_hz=cutoff_hz,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=default_topology(response),
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.1,
    )


def test_low_pass_range_includes_harmonics() -> None:
    sweep = suggested_sweep_for_spec(_linear(140e6, FilterResponse.LOW_PASS))
    assert sweep.f_start_hz == pytest.approx(140e6 / 8.0)
    assert sweep.f_stop_hz == pytest.approx(140e6 * 8.0)
    assert sweep.f_stop_hz >= 3.0 * 140e6


def test_high_pass_range_is_asymmetric() -> None:
    sweep = suggested_sweep_for_spec(_linear(140e6, FilterResponse.HIGH_PASS))
    assert sweep.f_start_hz == pytest.approx(140e6 / 3.0)
    assert sweep.f_stop_hz == pytest.approx(140e6 * 8.0)


@pytest.mark.parametrize("kind", [BandKind.BPF, BandKind.BSF])
def test_band_ranges_use_edges(kind: BandKind) -> None:
    spec = band_preset_spec(find_band("2 m"), kind)
    low, high = band_edges(spec)
    sweep = suggested_sweep_for_spec(spec)
    assert sweep.f_start_hz == pytest.approx(low / 2.0)
    assert sweep.f_stop_hz == pytest.approx(high * 2.0)


def test_default_and_auto_detection() -> None:
    spec = _linear(140e6, FilterResponse.HIGH_PASS)
    sweep = default_sweep_for_spec(spec)
    assert is_default_sweep(spec, sweep)
    custom = SweepConfig(50e6, 1e9, sweep.n_points, SweepSpacing.LOGARITHMIC)
    assert not is_default_sweep(spec, custom)
    assert DesignSession().sweep == suggested_sweep_for_spec(DesignSession().spec)


def test_default_sweep_respects_point_count() -> None:
    spec = _linear(140e6, FilterResponse.LOW_PASS)
    sweep = suggested_sweep_for_spec(spec, n_points=4096)
    assert sweep.n_points == 4096
    assert is_default_sweep(spec, sweep)
