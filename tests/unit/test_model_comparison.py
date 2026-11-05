"""Manufacturer model vs measured component-curve comparison."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from filterdesk.__main__ import main
from filterdesk.components_std import (
    STARTER_PARTS,
    ManufacturerModel,
    ModelPoint,
    write_component_library,
)
from filterdesk.services.model_comparison import (
    ModelComparisonError,
    compare_model_curve,
)


def _model() -> ManufacturerModel:
    return ManufacturerModel(
        model_id="test-model",
        q_points=(ModelPoint(1e6, 100.0), ModelPoint(10e6, 50.0)),
        esr_points=(ModelPoint(1e6, 0.1), ModelPoint(10e6, 1.0)),
    )


def test_q_model_comparison_metrics_and_extrapolation() -> None:
    measured = (
        ModelPoint(1e6, 110.0),
        ModelPoint(3.1622776601683795e6, 70.0),
        ModelPoint(20e6, 40.0),
    )
    comparison = compare_model_curve(
        _model(), measured, curve="q", part_mpn="TEST-1"
    )
    assert len(comparison.points) == 3
    assert comparison.overlap_points == 2
    assert comparison.extrapolated_points == 1
    assert comparison.model_min_hz == 1e6
    assert comparison.model_max_hz == 10e6
    assert comparison.points[0].predicted == pytest.approx(100.0)
    assert comparison.points[0].error == pytest.approx(-10.0)
    assert comparison.points[0].relative_error_pct == pytest.approx(
        10.0 / 110.0 * 100.0
    )
    assert comparison.points[1].predicted == pytest.approx(
        math.sqrt(100.0 * 50.0)
    )
    assert comparison.points[2].predicted == pytest.approx(50.0)
    assert comparison.points[2].extrapolated
    expected_rms = math.sqrt((10.0**2 + (math.sqrt(5000.0) - 70.0) ** 2) / 2)
    assert comparison.rms_error == pytest.approx(expected_rms)
    assert comparison.max_abs_error == pytest.approx(10.0)
    assert comparison.mean_abs_relative_error_pct == pytest.approx(
        (
            10.0 / 110.0 * 100.0
            + (math.sqrt(5000.0) - 70.0) / 70.0 * 100.0
        )
        / 2
    )
    assert "TEST-1 Q model vs measurement" in comparison.summary()
    assert "2 in model range" in comparison.summary()
    assert "RMS" in comparison.summary()


def test_esr_model_comparison() -> None:
    comparison = compare_model_curve(
        _model(),
        (ModelPoint(1e6, 0.12), ModelPoint(10e6, 0.8)),
        curve="esr",
        part_mpn="TEST-CAP",
    )
    assert comparison.curve == "esr"
    assert comparison.overlap_points == 2
    assert comparison.extrapolated_points == 0
    assert comparison.points[0].predicted == pytest.approx(0.1)
    assert comparison.points[1].predicted == pytest.approx(1.0)
    assert comparison.rms_error == pytest.approx(
        math.sqrt((0.02**2 + 0.2**2) / 2)
    )
    assert comparison.max_abs_error == pytest.approx(0.2)
    assert comparison.mean_abs_relative_error_pct == pytest.approx(
        ((0.02 / 0.12 * 100.0) + (0.2 / 0.8 * 100.0)) / 2
    )
    assert "TEST-CAP ESR model vs measurement" in comparison.summary()


def test_comparison_with_no_overlap_has_no_metrics() -> None:
    comparison = compare_model_curve(
        _model(), (ModelPoint(20e6, 40.0),), curve="q"
    )
    assert comparison.overlap_points == 0
    assert comparison.extrapolated_points == 1
    assert comparison.rms_error is None
    assert comparison.max_abs_error is None
    assert comparison.mean_abs_relative_error_pct is None
    assert "0 in model range" in comparison.summary()


def test_comparison_rejects_invalid_requests() -> None:
    with pytest.raises(ModelComparisonError, match="curve must be"):
        compare_model_curve(_model(), (ModelPoint(1e6, 1.0),), curve="other")
    with pytest.raises(ModelComparisonError, match="no q curve"):
        compare_model_curve(
            ManufacturerModel(esr_points=(ModelPoint(1e6, 0.1),)),
            (ModelPoint(1e6, 1.0),),
            curve="q",
        )
    with pytest.raises(ModelComparisonError, match="no points"):
        compare_model_curve(_model(), (), curve="q")



def test_cli_component_compare(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    library = tmp_path / "components.json"
    write_component_library(STARTER_PARTS, library)
    measured = tmp_path / "measured_q.csv"
    measured.write_text("250M,30\n900M,70\n", encoding="utf-8")
    assert (
        main(
            [
                "component-compare",
                "--library",
                str(library),
                "--part",
                "0603CS-10NXJRW",
                "--curve",
                "q",
                "--csv",
                str(measured),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["part"] == "0603CS-10NXJRW"
    assert payload["overlap_points"] == 2
    assert payload["extrapolated_points"] == 0
    assert payload["rms_error"] == pytest.approx(math.sqrt(8.5))
    assert payload["max_abs_error"] == pytest.approx(4.0)
    assert payload["mean_abs_relative_error_pct"] == pytest.approx(
        ((1.0 / 30.0 * 100.0) + (4.0 / 70.0 * 100.0)) / 2
    )
    assert len(payload["points"]) == 2
