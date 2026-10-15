"""Non-ideal (lossy / parasitic) element models (FR-P2)."""

from __future__ import annotations

import numpy as np
import pytest

from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std import (
    inductor_resistance_ohm_from_q,
    nonidealize_circuit,
)
from filterdesk.domain.circuit import (
    Circuit,
    IdealCapacitor,
    IdealInductor,
    NonIdealCapacitor,
    NonIdealInductor,
    Port,
)
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    ElementRole,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.project import circuit_from_mapping, circuit_to_mapping
from filterdesk.domain.specs import FilterSpec
from filterdesk.synthesis import synthesize

_TWO_PI = 2.0 * np.pi


def _one_element_circuit(element: object) -> Circuit:
    return Circuit(
        elements=[element],  # type: ignore[list-item]
        port_in=Port(name="in", node="in", impedance_ohm=50.0),
        port_out=Port(name="out", node="out", impedance_ohm=50.0),
    )


def _sweep() -> SweepConfig:
    return SweepConfig(
        f_start_hz=1e6,
        f_stop_hz=1e9,
        n_points=256,
        spacing=SweepSpacing.LOGARITHMIC,
    )


def test_inductor_self_resonant_frequency() -> None:
    ind = NonIdealInductor(
        id="L1",
        value_h=1e-6,
        node_a="in",
        node_b="out",
        role=ElementRole.SERIES,
        parallel_capacitance_f=1e-12,
    )
    assert ind.self_resonant_frequency_hz == pytest.approx(
        1.0 / (_TWO_PI * np.sqrt(1e-6 * 1e-12))
    )
    assert (
        NonIdealInductor(
            id="L1", value_h=1e-6, node_a="in", node_b="out", role=ElementRole.SERIES
        ).self_resonant_frequency_hz
        is None
    )


def test_capacitor_self_resonant_frequency() -> None:
    cap = NonIdealCapacitor(
        id="C1",
        value_f=1e-12,
        node_a="in",
        node_b="out",
        role=ElementRole.SERIES,
        esl_h=1e-9,
    )
    assert cap.self_resonant_frequency_hz == pytest.approx(
        1.0 / (_TWO_PI * np.sqrt(1e-9 * 1e-12))
    )
    assert (
        NonIdealCapacitor(
            id="C1", value_f=1e-12, node_a="in", node_b="out", role=ElementRole.SERIES
        ).self_resonant_frequency_hz
        is None
    )


def test_lossless_nonideal_matches_ideal_inductor() -> None:
    ideal = _one_element_circuit(
        IdealInductor(
            id="L1", value_h=1e-7, node_a="in", node_b="out", role=ElementRole.SERIES
        )
    )
    nonideal = _one_element_circuit(
        NonIdealInductor(
            id="L1", value_h=1e-7, node_a="in", node_b="out", role=ElementRole.SERIES
        )
    )
    a = analyze_circuit(ideal, _sweep())
    b = analyze_circuit(nonideal, _sweep())
    assert np.allclose(a.s21, b.s21)
    assert np.allclose(a.s11, b.s11)


def test_lossless_nonideal_matches_ideal_capacitor() -> None:
    ideal = _one_element_circuit(
        IdealCapacitor(
            id="C1", value_f=1e-12, node_a="in", node_b="out", role=ElementRole.SERIES
        )
    )
    nonideal = _one_element_circuit(
        NonIdealCapacitor(
            id="C1", value_f=1e-12, node_a="in", node_b="out", role=ElementRole.SERIES
        )
    )
    a = analyze_circuit(ideal, _sweep())
    b = analyze_circuit(nonideal, _sweep())
    assert np.allclose(a.s21, b.s21)


def test_inductor_q_resistance_and_extra_loss() -> None:
    assert inductor_resistance_ohm_from_q(1e-6, q=100.0, frequency_hz=1e6) == (
        pytest.approx(_TWO_PI * 1e6 * 1e-6 / 100.0)
    )
    with pytest.raises(ValueError):
        inductor_resistance_ohm_from_q(1e-6, q=0.0, frequency_hz=1e6)


def _lp_spec() -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.LOW_PASS,
        order=5,
        cutoff_hz=100e6,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.1,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
    )


def _passband_loss_db(circuit: Circuit) -> float:
    analysis = analyze_circuit(circuit, _sweep())
    s21_db = 20.0 * np.log10(np.abs(analysis.s21) + 1e-30)
    in_band = analysis.frequency_hz <= 100e6
    return float(s21_db[in_band].max())


def test_finite_q_adds_passband_loss() -> None:
    circuit = synthesize(_lp_spec()).circuit
    lossless = _passband_loss_db(circuit)
    assert lossless == pytest.approx(0.0, abs=0.05)

    lossy = nonidealize_circuit(circuit, inductor_q=100.0, q_frequency_hz=100e6)
    assert all(
        isinstance(el, NonIdealInductor)
        for el in lossy.elements
        if isinstance(el, IdealInductor)
    )
    assert _passband_loss_db(lossy) < lossless - 0.1


def test_capacitor_esr_adds_loss() -> None:
    circuit = synthesize(_lp_spec()).circuit
    lossless = _passband_loss_db(circuit)
    lossy = nonidealize_circuit(circuit, capacitor_esr_ohm=1.0)
    assert any(isinstance(el, NonIdealCapacitor) for el in lossy.elements)
    assert _passband_loss_db(lossy) < lossless


def test_nonidealize_requires_frequency_for_q() -> None:
    circuit = synthesize(_lp_spec()).circuit
    with pytest.raises(ValueError):
        nonidealize_circuit(circuit, inductor_q=100.0)


def test_project_roundtrip_preserves_nonideal() -> None:
    circuit = synthesize(_lp_spec()).circuit
    lossy = nonidealize_circuit(
        circuit,
        inductor_q=80.0,
        q_frequency_hz=100e6,
        capacitor_esr_ohm=0.5,
        capacitor_esl_h=1e-10,
    )
    restored = circuit_from_mapping(circuit_to_mapping(lossy))
    assert len(restored.elements) == len(lossy.elements)
    for orig, back in zip(lossy.elements, restored.elements, strict=True):
        assert type(orig) is type(back)
        if isinstance(orig, NonIdealInductor):
            assert back.series_resistance_ohm == pytest.approx(  # type: ignore[union-attr]
                orig.series_resistance_ohm
            )
            assert back.parallel_capacitance_f == pytest.approx(  # type: ignore[union-attr]
                orig.parallel_capacitance_f
            )
        if isinstance(orig, NonIdealCapacitor):
            assert back.esr_ohm == pytest.approx(orig.esr_ohm)  # type: ignore[union-attr]
            assert back.esl_h == pytest.approx(orig.esl_h)  # type: ignore[union-attr]
