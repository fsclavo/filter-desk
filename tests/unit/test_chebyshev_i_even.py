"""Even-order Chebyshev Type I (classical prototype + output transformer)."""

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
from filterdesk.synthesis.families.chebyshev_i import (
    chebyshev_type_i_g_values,
    synthesize_chebyshev_i_prototype,
)

FC = 100e6


def _even_spec(order: int, ripple_db: float = 0.1) -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.LOW_PASS,
        order=order,
        cutoff_hz=FC,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=ripple_db,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
    )


def _ref_db(order: int, f: np.ndarray, response: FilterResponse) -> np.ndarray:
    z, p, k = signal.cheb1ap(order, 0.1)
    if response == FilterResponse.LOW_PASS:
        z, p, k = signal.lp2lp_zpk(z, p, k, wo=2 * np.pi * FC)
    elif response == FilterResponse.HIGH_PASS:
        z, p, k = signal.lp2hp_zpk(z, p, k, wo=2 * np.pi * FC)
    else:
        z, p, k = signal.lp2bp_zpk(
            z, p, k, wo=2 * np.pi * FC, bw=2 * np.pi * 20e6
        )
    _, h = signal.freqs_zpk(z, p, k, worN=2 * np.pi * f)
    return np.asarray(20 * np.log10(np.abs(h) + 1e-30), dtype=float)


@pytest.mark.parametrize("order", [2, 4, 6, 8])
def test_even_g_values_load_ratio(order: int) -> None:
    g = chebyshev_type_i_g_values(order, 0.1)
    assert len(g) == order + 2
    assert g[0] == 1.0
    assert abs(g[-1] - 1.35536) < 1e-4


@pytest.mark.parametrize("order", [2, 4, 6, 8])
def test_even_prototype_uses_classical_terminations(order: int) -> None:
    proto = synthesize_chebyshev_i_prototype(order, 0.1)
    assert proto.arms is None
    assert len(proto.g_values) == order + 2
    assert proto.load_ratio == pytest.approx(proto.g_values[-1])
    assert proto.load_ratio > 1.0


@pytest.mark.parametrize("order", [2, 4, 6, 8])
def test_even_order_response_matches_scipy(order: int) -> None:
    result = synthesize(_even_spec(order))
    assert result.circuit.output_transformer_ratio == pytest.approx(
        np.sqrt(result.prototype.load_ratio)
    )
    f = FC * np.logspace(-2, 1, 400)
    sweep = SweepConfig(float(f[0]), float(f[-1]), f.size, SweepSpacing.LOGARITHMIC)
    analysis = analyze_circuit(result.circuit, sweep)
    got = 20 * np.log10(np.abs(analysis.s21) + 1e-30)
    ref = _ref_db(order, analysis.frequency_hz, FilterResponse.LOW_PASS)
    mask = ref > -80.0
    assert np.max(np.abs(got[mask] - ref[mask])) < 0.15


@pytest.mark.parametrize("order", [2, 4, 6, 8])
def test_even_order_ripple_and_cutoff(order: int) -> None:
    ripple_db = 0.1
    result = synthesize(_even_spec(order, ripple_db))
    sweep = SweepConfig(1e6, 100e6, 40001, SweepSpacing.LINEAR)
    analysis = analyze_circuit(result.circuit, sweep)
    s21_db = 20 * np.log10(np.abs(analysis.s21) + 1e-30)
    assert s21_db.min() == pytest.approx(-ripple_db, abs=0.01)
    assert s21_db.max() == pytest.approx(0.0, abs=0.01)
    i = int(np.argmin(np.abs(analysis.frequency_hz - FC)))
    assert s21_db[i] == pytest.approx(-ripple_db, abs=0.02)


def test_odd_order_unchanged() -> None:
    proto = synthesize_chebyshev_i_prototype(5, 0.1)
    assert proto.arms is None
    assert proto.load_ratio == 1.0
    assert len(proto.g_values) == 7
    assert proto.g_values[-1] == 1.0
    result = synthesize(_even_spec(5))
    assert result.circuit.output_transformer_ratio == 1.0


@pytest.mark.parametrize(
    ("response", "topology", "extra"),
    [
        (
            FilterResponse.HIGH_PASS,
            TopologyId.LADDER_HP_SERIES_C_INPUT,
            {"cutoff_hz": FC},
        ),
        (
            FilterResponse.BAND_PASS,
            TopologyId.LADDER_BP_SERIES_RES_INPUT,
            {"f_center_hz": FC, "bandwidth_hz": 20e6},
        ),
        (
            FilterResponse.BAND_STOP,
            TopologyId.LADDER_BS_SERIES_TANK_INPUT,
            {"f_center_hz": FC, "bandwidth_hz": 20e6},
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
    assert result.circuit.output_transformer_ratio == pytest.approx(
        np.sqrt(result.prototype.load_ratio)
    )


def test_even_highpass_matches_scipy() -> None:
    spec = FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.HIGH_PASS,
        order=4,
        cutoff_hz=FC,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.1,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_HP_SERIES_C_INPUT,
    )
    result = synthesize(spec)
    f = FC * np.logspace(-2, 1, 400)
    sweep = SweepConfig(float(f[0]), float(f[-1]), f.size, SweepSpacing.LOGARITHMIC)
    analysis = analyze_circuit(result.circuit, sweep)
    got = 20 * np.log10(np.abs(analysis.s21) + 1e-30)
    ref = _ref_db(4, analysis.frequency_hz, FilterResponse.HIGH_PASS)
    mask = ref > -80.0
    assert np.max(np.abs(got[mask] - ref[mask])) < 0.15
