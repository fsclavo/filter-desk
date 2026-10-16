"""L/Pi/T matching-network design (Phase 12)."""

from __future__ import annotations

import json

import pytest

from filterdesk.__main__ import main
from filterdesk.components_std import (
    MatchingError,
    MatchingTopology,
    design_matching,
)
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


@pytest.mark.parametrize(
    "topology",
    [MatchingTopology.L, MatchingTopology.PI, MatchingTopology.T],
)
def test_matching_matches_complex_load(topology: MatchingTopology) -> None:
    for rl, xl in ((25.0, 0.0), (100.0, 0.0), (25.0, -10.0), (73.0, 42.0)):
        design = design_matching(50.0, rl, xl, 7.1e6, topology, q=2.0)
        z = design.input_impedance_ohm
        assert z.real == pytest.approx(50.0, abs=1e-6)
        assert z.imag == pytest.approx(0.0, abs=1e-6)
        # Low-pass solution: series arms inductive, shunt arms capacitive.
        for el in design.elements:
            expected = "L" if el.role == ElementRole.SERIES else "C"
            assert el.kind == expected


def test_matching_element_roles_and_values() -> None:
    design = design_matching(50.0, 25.0, 0.0, 7.1e6, MatchingTopology.L)
    assert [e.role for e in design.elements] == [
        ElementRole.SHUNT,
        ElementRole.SERIES,
    ]
    for el in design.elements:
        assert el.value > 0.0


def test_matching_equal_resistance_cancels_reactance() -> None:
    # rs == rl with a reactive load: a single series element cancels it.
    design = design_matching(50.0, 50.0, 20.0, 7.1e6, MatchingTopology.L)
    assert len(design.elements) == 1
    assert design.elements[0].role == ElementRole.SERIES
    assert design.input_impedance_ohm.real == pytest.approx(50.0, abs=1e-6)
    assert design.input_impedance_ohm.imag == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize(
    "topology",
    [MatchingTopology.L, MatchingTopology.PI, MatchingTopology.T],
)
def test_matching_equal_resistance_reactive_load(
    topology: MatchingTopology,
) -> None:
    # rs == rl with a reactive load: for the T network the two shunt arms of the
    # back-to-back L-sections cancel, which used to divide by zero.
    design = design_matching(1.0, 1.0, 0.5, 1000.0, topology)
    z = design.input_impedance_ohm
    assert z.real == pytest.approx(1.0, abs=1e-6)
    assert z.imag == pytest.approx(0.0, abs=1e-6)


def test_matching_validation() -> None:
    with pytest.raises(MatchingError):
        design_matching(0.0, 25.0, 0.0, 7e6)
    with pytest.raises(MatchingError):
        design_matching(50.0, 25.0, 0.0, -1.0)
    with pytest.raises(MatchingError):
        design_matching(50.0, -5.0, 0.0, 7e6)
    with pytest.raises(MatchingError):
        # Q below the minimum for the ratio.
        design_matching(50.0, 25.0, 0.0, 7e6, MatchingTopology.PI, q=0.5)


def test_cli_match(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "match",
                "--z0",
                "50",
                "--rl",
                "25",
                "--xl",
                "-10",
                "--f",
                "7.1M",
                "--topology",
                "pi",
                "--q",
                "2",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "PI match" in out and "Zin = 50" in out


def test_cli_match_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["match", "--rl", "25", "--f", "7.1M", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["topology"] == "l"
    assert payload["input_impedance_ohm"][0] == pytest.approx(50.0, abs=1e-6)
    assert len(payload["elements"]) == 2


def test_matching_inserts_into_circuit() -> None:
    from filterdesk.domain import circuit_edit
    from filterdesk.domain.circuit import IdealCapacitor, IdealInductor

    circuit = synthesize(_spec()).circuit
    n = len(circuit.elements)
    design = design_matching(50.0, 25.0, -10.0, 100e6, MatchingTopology.L)
    elements: list[object] = []
    for e in design.elements:
        if e.kind == "L":
            elements.append(
                IdealInductor(
                    id="X", value_h=e.value, node_a="", node_b="", role=e.role
                )
            )
        else:
            elements.append(
                IdealCapacitor(
                    id="X", value_f=e.value, node_a="", node_b="", role=e.role
                )
            )
    new_circuit = circuit_edit.insert_elements(
        circuit, elements, at_input=True  # type: ignore[arg-type]
    )
    assert len(new_circuit.elements) == n + 2
