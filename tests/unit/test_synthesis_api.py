"""Additional synthesis behavior tests."""

from __future__ import annotations

from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.synthesis import synthesize


def test_unequal_impedance_synthesizes() -> None:
    spec = FilterSpec(
        family=ApproximationFamily.BUTTERWORTH,
        response=FilterResponse.LOW_PASS,
        order=3,
        cutoff_hz=1e6,
        z_source_ohm=50.0,
        z_load_ohm=75.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )
    result = synthesize(spec)
    assert result.circuit.port_out.impedance_ohm == 75.0


def test_hp_shunt_l_input_dual_exists() -> None:
    spec = FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.HIGH_PASS,
        order=7,
        cutoff_hz=140e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_HP_SHUNT_L_INPUT,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.01,
    )
    result = synthesize(spec)
    assert result.circuit.elements[0].id == "L1"
    assert result.circuit.elements[0].role.value == "shunt"
