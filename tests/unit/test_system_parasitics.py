"""System-level finite-Q / parasitic reanalysis."""

from __future__ import annotations

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.circuit import NonIdealCapacitor, NonIdealInductor
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.services.diplexer import DiplexerConfig, design_diplexer
from filterdesk.services.system_parasitics import (
    SystemParasiticsConfig,
    apply_system_parasitics,
)


def _design():
    config = DiplexerConfig(
        low_cutoff_hz=30e6,
        high_cutoff_hz=40e6,
        order=5,
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        ripple_db=0.1,
    )
    return design_diplexer(
        config, SweepConfig(1e6, 200e6, 1001, SweepSpacing.LOGARITHMIC)
    )


def test_apply_parasitics_rebuilds_and_converts_elements() -> None:
    design = _design()
    config = SystemParasiticsConfig(
        inductor_q=100.0,
        capacitor_esr_ohm=0.1,
        capacitor_esl_h=1e-9,
    )
    result = apply_system_parasitics(design, config)
    assert result.design.network.n_ports == 3
    assert result.design.metrics is not design.metrics
    for circuit in (result.design.low_circuit, result.design.high_circuit):
        assert any(isinstance(el, NonIdealInductor) for el in circuit.elements)
        assert any(isinstance(el, NonIdealCapacitor) for el in circuit.elements)


def test_identity_parasitics_keeps_design() -> None:
    design = _design()
    result = apply_system_parasitics(design, SystemParasiticsConfig())
    assert result.design is design


def test_parasitic_validation() -> None:
    import pytest

    with pytest.raises(ValueError, match="inductor_q"):
        SystemParasiticsConfig(inductor_q=0.0)
    with pytest.raises(ValueError, match="capacitor_esr"):
        SystemParasiticsConfig(capacitor_esr_ohm=-1.0)
