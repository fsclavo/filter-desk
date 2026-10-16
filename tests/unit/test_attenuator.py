"""Symmetric T/Pi resistive attenuator (Phase 12)."""

from __future__ import annotations

import json

import pytest

from filterdesk.__main__ import main
from filterdesk.components_std import (
    AttenuatorError,
    AttenuatorKind,
    design_attenuator,
)
from filterdesk.domain.circuit import IdealResistor
from filterdesk.domain.circuit_edit import insert_resistive_pad
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    ElementRole,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.synthesis import synthesize


def _spec() -> FilterSpec:
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


def test_tee_pad_6db() -> None:
    design = design_attenuator(6.0, 50.0, AttenuatorKind.TEE)
    assert design.r_series_ohm == pytest.approx(16.61, abs=0.05)
    assert design.r_shunt_ohm == pytest.approx(66.93, abs=0.05)


def test_pi_pad_6db() -> None:
    design = design_attenuator(6.0, 50.0, AttenuatorKind.PI)
    assert design.r_series_ohm == pytest.approx(37.35, abs=0.05)
    assert design.r_shunt_ohm == pytest.approx(150.48, abs=0.05)


def test_attenuator_validation() -> None:
    with pytest.raises(AttenuatorError):
        design_attenuator(0.0)
    with pytest.raises(AttenuatorError):
        design_attenuator(6.0, z0_ohm=-1.0)


def test_insert_tee_pad_at_input() -> None:
    circuit = synthesize(_spec()).circuit
    n = len(circuit.elements)
    design = design_attenuator(6.0, 50.0, AttenuatorKind.TEE)
    padded = insert_resistive_pad(
        circuit,
        kind="t",
        r_series_ohm=design.r_series_ohm,
        r_shunt_ohm=design.r_shunt_ohm,
        at_input=True,
    )
    assert len(padded.elements) == n + 3
    first3 = padded.elements[:3]
    assert all(isinstance(el, IdealResistor) for el in first3)
    assert [el.role for el in first3] == [
        ElementRole.SERIES,
        ElementRole.SHUNT,
        ElementRole.SERIES,
    ]


def test_insert_pi_pad_at_output() -> None:
    circuit = synthesize(_spec()).circuit
    design = design_attenuator(10.0, 50.0, AttenuatorKind.PI)
    padded = insert_resistive_pad(
        circuit,
        kind="pi",
        r_series_ohm=design.r_series_ohm,
        r_shunt_ohm=design.r_shunt_ohm,
        at_input=False,
    )
    last3 = padded.elements[-3:]
    assert [el.role for el in last3] == [
        ElementRole.SHUNT,
        ElementRole.SERIES,
        ElementRole.SHUNT,
    ]


def test_cli_attenuator(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["attenuator", "--db", "6", "--z0", "50", "--kind", "t"]) == 0
    out = capsys.readouterr().out
    assert "T pad" in out and "series R" in out


def test_cli_attenuator_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["attenuator", "--db", "6", "--kind", "pi", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "pi"
    assert payload["r_series_ohm"] == pytest.approx(37.35, abs=0.05)


def test_cli_attenuator_invalid(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["attenuator", "--db", "0"]) == 2
    assert "error:" in capsys.readouterr().err
