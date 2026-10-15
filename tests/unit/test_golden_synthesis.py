"""Golden synthesis regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from filterdesk.domain.circuit import IdealCapacitor, IdealInductor
from filterdesk.domain.specs import filter_spec_from_mapping
from filterdesk.synthesis import synthesize

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_ROOT = ROOT / "golden"


def _assert_components_match(
    circuit_elements: list[object],
    expected: list[dict[str, object]],
    rel_tol: float,
) -> None:
    assert len(circuit_elements) == len(expected)
    for el, exp in zip(circuit_elements, expected, strict=True):
        assert el.id == exp["ref"]  # type: ignore[attr-defined]
        assert el.role.value == exp["role"]  # type: ignore[attr-defined]
        assert el.element_type.value == exp["type"]  # type: ignore[attr-defined]
        assert el.g is not None  # type: ignore[attr-defined]
        assert abs(el.g - float(exp["g"])) <= rel_tol * max(abs(float(exp["g"])), 1.0)  # type: ignore[attr-defined]
        if exp["type"] == "capacitor":
            assert isinstance(el, IdealCapacitor)
            ref = float(exp["value_F"])
            assert abs(el.value_f - ref) <= rel_tol * max(abs(ref), 1e-30)
        elif exp["type"] == "inductor":
            assert isinstance(el, IdealInductor)
            ref = float(exp["value_H"])
            assert abs(el.value_h - ref) <= rel_tol * max(abs(ref), 1e-30)
        else:
            pytest.fail(f"unexpected type {exp['type']}")


@pytest.mark.parametrize(
    "case",
    [
        "cheby1_hp_n7_0p01db_140mhz_50ohm",
        "butterworth_lp_n5_1mhz_50ohm",
    ],
)
def test_golden_synthesis(case: str) -> None:
    folder = GOLDEN_ROOT / case
    spec = filter_spec_from_mapping(json.loads((folder / "spec.json").read_text()))
    expected_proto = json.loads((folder / "expected_prototype.json").read_text())
    expected_comps = json.loads((folder / "expected_components.json").read_text())
    rel = float(expected_comps.get("component_relative_tolerance", 1e-9))

    result = synthesize(spec)

    for a, b in zip(result.prototype.g_values, expected_proto["g_values"], strict=True):
        assert abs(a - b) <= rel_tol_for(a, b, rel)

    _assert_components_match(result.circuit.elements, expected_comps["components"], rel)


def rel_tol_for(a: float, b: float, rel: float) -> float:
    return rel * max(abs(a), abs(b), 1.0)
