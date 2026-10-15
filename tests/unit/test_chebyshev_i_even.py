"""Even-order Chebyshev Type I (modified, equal terminations)."""

from __future__ import annotations

import numpy as np
import pytest

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
from filterdesk.synthesis.families.chebyshev_i import (
    chebyshev_type_i_g_values,
    synthesize_chebyshev_i_prototype,
)


def _even_spec(order: int, ripple_db: float = 0.1) -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.LOW_PASS,
        order=order,
        cutoff_hz=100e6,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=ripple_db,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
    )


@pytest.mark.parametrize("order", [2, 4, 6, 8])
def test_even_g_values_load_ratio(order: int) -> None:
    # coth²(β/2) is independent of order; 0.1 dB table value is 1.3554.
    g = chebyshev_type_i_g_values(order, 0.1)
    assert len(g) == order + 2
    assert g[0] == 1.0
    assert abs(g[-1] - 1.35536) < 1e-4


@pytest.mark.parametrize("order", [2, 4, 6, 8])
def test_even_prototype_uses_symmetric_arms(order: int) -> None:
    proto = synthesize_chebyshev_i_prototype(order, 0.1)
    assert proto.arms is not None
    arms = proto.arms
    assert len(arms) == order
    values = [a.value for a in arms]
    assert all(v is not None and v > 0.0 for v in values)
    expected_kinds = ["series_L" if i % 2 == 0 else "shunt_C" for i in range(order)]
    assert [a.kind for a in arms] == expected_kinds
    for i in range(order // 2):
        assert values[i] == pytest.approx(values[order - 1 - i], rel=1e-3)


@pytest.mark.parametrize("order", [2, 4, 6, 8])
def test_even_order_equal_termination_ripple(order: int) -> None:
    ripple_db = 0.1
    result = synthesize(_even_spec(order, ripple_db))
    sweep = SweepConfig(
        f_start_hz=1e6,
        f_stop_hz=200e6,
        n_points=40001,
        spacing=SweepSpacing.LINEAR,
    )
    analysis = analyze_circuit(result.circuit, sweep)
    s21_db = 20.0 * np.log10(np.abs(analysis.s21) + 1e-30)
    in_band = analysis.frequency_hz <= 100e6
    assert s21_db[0] == pytest.approx(0.0, abs=0.01)
    assert s21_db[in_band].min() == pytest.approx(-ripple_db, abs=0.01)
    assert s21_db[in_band].max() == pytest.approx(0.0, abs=0.01)


def test_odd_order_still_uses_g_values() -> None:
    proto = synthesize_chebyshev_i_prototype(5, 0.1)
    assert proto.arms is None
    assert len(proto.g_values) == 7
    assert proto.g_values[-1] == 1.0


@pytest.mark.parametrize(
    ("response", "topology", "extra"),
    [
        (
            FilterResponse.HIGH_PASS,
            TopologyId.LADDER_HP_SERIES_C_INPUT,
            {"cutoff_hz": 100e6},
        ),
        (
            FilterResponse.BAND_PASS,
            TopologyId.LADDER_BP_SERIES_RES_INPUT,
            {"f_center_hz": 100e6, "bandwidth_hz": 20e6},
        ),
        (
            FilterResponse.BAND_STOP,
            TopologyId.LADDER_BS_SERIES_TANK_INPUT,
            {"f_center_hz": 100e6, "bandwidth_hz": 20e6},
        ),
    ],
)
def test_even_order_other_responses_synthesize(
    response: FilterResponse, topology: TopologyId, extra: dict[str, float]
) -> None:
    spec = FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=response,
        order=4,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.1,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=topology,
        **extra,
    )
    result = synthesize(spec)
    assert len(result.circuit.elements) == 4
