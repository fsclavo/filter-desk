"""Property-based tests for core invariants (hypothesis)."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std import (
    ESeries,
    MatchingError,
    MatchingTopology,
    design_matching,
    nearest_e_series,
)
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.domain.units import format_engineering, parse_si
from filterdesk.synthesis import synthesize

_SETTINGS = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@_SETTINGS
@given(
    st.floats(
        min_value=1e-15, max_value=1e12, allow_nan=False, allow_infinity=False
    )
)
def test_units_roundtrip(value: float) -> None:
    text = format_engineering(value, "H", digits=12)
    assert parse_si(text) == pytest.approx(value, rel=1e-9)


@_SETTINGS
@given(
    st.sampled_from(list(ESeries)),
    st.floats(min_value=1e-12, max_value=1e9, allow_nan=False, allow_infinity=False),
)
def test_nearest_e_series_idempotent(series: ESeries, value: float) -> None:
    once = nearest_e_series(value, series)
    twice = nearest_e_series(once, series)
    assert once == pytest.approx(twice, rel=1e-12)


@_SETTINGS
@given(
    z0=st.floats(min_value=1.0, max_value=1000.0),
    rl=st.floats(min_value=0.5, max_value=5000.0),
    xl=st.floats(min_value=-5000.0, max_value=5000.0),
    f=st.floats(min_value=1e3, max_value=1e10),
    topology=st.sampled_from(list(MatchingTopology)),
)
def test_matching_network_matches_source(
    z0: float, rl: float, xl: float, f: float, topology: MatchingTopology
) -> None:
    assume(abs(rl - z0) > 1e-6 or abs(xl) > 1e-6)  # not already matched
    try:
        design = design_matching(z0, rl, xl, f, topology)
    except MatchingError:
        assume(False)  # infeasible corner -> skipped
    z_in = design.input_impedance_ohm
    assert abs(z_in - z0) <= 1e-6 * z0 + 1e-6


@_SETTINGS
@given(
    order=st.integers(min_value=1, max_value=9),
    ripple=st.floats(min_value=0.001, max_value=2.0),
)
def test_analysis_reciprocal_and_passive(order: int, ripple: float) -> None:
    spec = FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.LOW_PASS,
        order=order,
        cutoff_hz=100e6,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=ripple,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
    )
    circuit = synthesize(spec).circuit
    sweep = SweepConfig(1e6, 1e9, 64, SweepSpacing.LOGARITHMIC)
    result = analyze_circuit(circuit, sweep)
    # Reciprocal two-port (tolerance accounts for deep-stopband numeric noise).
    assert np.allclose(result.s12, result.s21, atol=1e-6)
    # Passive network: no power gain.
    for s in (result.s11, result.s21, result.s12, result.s22):
        assert float(np.max(np.abs(s))) <= 1.0 + 1e-6
