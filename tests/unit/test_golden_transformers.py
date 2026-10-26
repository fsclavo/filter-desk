"""Golden fixtures for output-transformer and classical even-order designs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from filterdesk.analysis.adapters.abcd_ladder import LadderABCDAnalyzer
from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.circuit import IdealCapacitor, IdealInductor
from filterdesk.domain.specs import filter_spec_from_mapping
from filterdesk.io.build_sheet import build_sheet_rows
from filterdesk.synthesis import synthesize

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_ROOT = ROOT / "golden"

CASES = (
    "butterworth_lp_n3_50_to_75_100mhz",
    "cheby1_lp_n4_0p1db_100mhz_50ohm",
)


@pytest.mark.parametrize("case", CASES)
def test_golden_transformer_synthesis(case: str) -> None:
    folder = GOLDEN_ROOT / case
    spec = filter_spec_from_mapping(json.loads((folder / "spec.json").read_text()))
    expected_proto = json.loads((folder / "expected_prototype.json").read_text())
    expected = json.loads((folder / "expected_components.json").read_text())
    tolerance = float(expected.get("component_relative_tolerance", 1e-9))

    result = synthesize(spec)
    circuit = result.circuit
    assert result.prototype.load_ratio == pytest.approx(
        float(expected_proto["load_ratio"]), rel=tolerance
    )
    for got, ref in zip(
        result.prototype.g_values, expected_proto["g_values"], strict=True
    ):
        assert got == pytest.approx(float(ref), rel=tolerance)
    assert circuit.output_transformer_ratio == pytest.approx(
        float(expected["output_transformer_ratio"]), rel=tolerance
    )

    assert len(circuit.elements) == len(expected["components"])
    for el, row in zip(circuit.elements, expected["components"], strict=True):
        assert el.id == row["ref"]
        assert el.role.value == row["role"]
        assert el.element_type.value == row["type"]
        assert el.g == pytest.approx(float(row["g"]), rel=tolerance)
        if isinstance(el, IdealCapacitor):
            assert el.value_f == pytest.approx(float(row["value_F"]), rel=tolerance)
        elif isinstance(el, IdealInductor):
            assert el.value_h == pytest.approx(float(row["value_H"]), rel=tolerance)
        else:
            pytest.fail(f"unexpected element {el}")


@pytest.mark.parametrize("case", CASES)
def test_golden_transformer_response(case: str) -> None:
    folder = GOLDEN_ROOT / case
    spec = filter_spec_from_mapping(json.loads((folder / "spec.json").read_text()))
    metrics = json.loads((folder / "expected_metrics.json").read_text())
    circuit = synthesize(spec).circuit
    sw = metrics["sweep"]
    sweep = SweepConfig(
        float(sw["f_start_hz"]),
        float(sw["f_stop_hz"]),
        int(sw["n_points"]),
        SweepSpacing(sw["spacing"]),
    )
    result = LadderABCDAnalyzer().analyze(circuit, sweep)
    s21 = mag_db(result.s21)
    s11 = mag_db(result.s11)
    tol21 = float(metrics["tolerances"]["s21_db_abs"])
    tol11 = float(metrics["tolerances"]["s11_db_abs"])
    for cp in metrics["checkpoints"]:
        i = int(abs(result.frequency_hz - float(cp["frequency_hz"])).argmin())
        assert abs(float(s21[i]) - float(cp["s21_db"])) <= tol21
        assert abs(float(s11[i]) - float(cp["s11_db"])) <= tol11


@pytest.mark.parametrize("case", CASES)
def test_golden_transformer_bom(case: str) -> None:
    folder = GOLDEN_ROOT / case
    spec = filter_spec_from_mapping(json.loads((folder / "spec.json").read_text()))
    expected = json.loads((folder / "expected_bom.json").read_text())
    rows = build_sheet_rows(synthesize(spec).circuit)
    assert [
        {
            "ref": row.ref,
            "kind": row.kind,
            "value_text": row.value_text,
            "parasitic": row.parasitic,
            "tolerance_pct": row.tolerance_pct,
        }
        for row in rows
    ] == expected
    assert any(row["kind"] == "transformer" for row in expected)
