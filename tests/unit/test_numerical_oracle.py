"""Independent SciPy analog-prototype oracle for LP/HP synthesis."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import signal

from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.synthesis import synthesize

_F0 = 100e6
_CASES = (
    (ApproximationFamily.BUTTERWORTH, {}, CutoffDefinition.HALF_POWER_3DB),
    (
        ApproximationFamily.CHEBYSHEV_TYPE_I,
        {"passband_ripple_db": 0.1},
        CutoffDefinition.RIPPLE_EDGE,
    ),
    (
        ApproximationFamily.CHEBYSHEV_TYPE_II,
        {"stopband_attenuation_db": 40.0},
        CutoffDefinition.STOPBAND_EDGE,
    ),
    (
        ApproximationFamily.ELLIPTIC,
        {"passband_ripple_db": 0.1, "stopband_attenuation_db": 40.0},
        CutoffDefinition.RIPPLE_EDGE,
    ),
)


def _direction(
    family: ApproximationFamily,
) -> tuple[object, object]:
    if family == ApproximationFamily.BUTTERWORTH:
        return lambda order: signal.butter(order, 1.0, "low", analog=True), (
            lambda order: signal.butter(order, 1.0, "high", analog=True)
        )
    if family == ApproximationFamily.CHEBYSHEV_TYPE_I:
        return lambda order: signal.cheby1(order, 0.1, 1.0, "low", analog=True), (
            lambda order: signal.cheby1(order, 0.1, 1.0, "high", analog=True)
        )
    if family == ApproximationFamily.CHEBYSHEV_TYPE_II:
        return lambda order: signal.cheby2(order, 40.0, 1.0, "low", analog=True), (
            lambda order: signal.cheby2(order, 40.0, 1.0, "high", analog=True)
        )
    return lambda order: signal.ellip(order, 0.1, 40.0, 1.0, "low", analog=True), (
        lambda order: signal.ellip(order, 0.1, 40.0, 1.0, "high", analog=True)
    )


@pytest.mark.parametrize(
    ("family", "kwargs", "cutoff_definition"),
    _CASES,
)
@pytest.mark.parametrize(
    "response", [FilterResponse.LOW_PASS, FilterResponse.HIGH_PASS]
)
@pytest.mark.parametrize("order", [3, 5])
def test_abcd_matches_scipy_analog_prototype(
    family: ApproximationFamily,
    kwargs: dict[str, float],
    cutoff_definition: CutoffDefinition,
    response: FilterResponse,
    order: int,
) -> None:
    spec = FilterSpec(
        family=family,
        response=response,
        order=order,
        cutoff_hz=_F0,
        cutoff_definition=cutoff_definition,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=(
            TopologyId.LADDER_LP_SERIES_L_INPUT
            if response == FilterResponse.LOW_PASS
            else TopologyId.LADDER_HP_SERIES_C_INPUT
        ),
        **kwargs,
    )
    sweep = SweepConfig(
        f_start_hz=1e6,
        f_stop_hz=500e6,
        n_points=1000,
        spacing=SweepSpacing.LOGARITHMIC,
    )
    result = analyze_circuit(synthesize(spec).circuit, sweep, backend="abcd")
    freq = sweep.frequencies_hz()
    normalized = freq / _F0
    low_factory, high_factory = _direction(family)
    factory = low_factory if response == FilterResponse.LOW_PASS else high_factory
    b, a = factory(order)
    _, expected = signal.freqs(b, a, normalized)
    got_db = 20.0 * np.log10(np.maximum(np.abs(result.s21), 1e-15))
    expected_db = 20.0 * np.log10(np.maximum(np.abs(expected), 1e-15))
    assert np.max(np.abs(got_db - expected_db)) < 1e-4
