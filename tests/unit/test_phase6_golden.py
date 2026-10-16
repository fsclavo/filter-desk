"""Phase 6 golden regressions: E24 snapping and finite-Q losses."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std import (
    ESeries,
    SnapStrategy,
    nearest_e_series,
    nonidealize_circuit,
    snap_circuit,
)
from filterdesk.domain.circuit import IdealCapacitor, IdealInductor
from filterdesk.domain.specs import filter_spec_from_mapping
from filterdesk.synthesis import synthesize

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "golden"


def _spec(case: str):  # type: ignore[no-untyped-def]
    data = json.loads((GOLDEN / case / "spec.json").read_text())
    return filter_spec_from_mapping(data)


def test_golden_e24_snapped_components() -> None:
    case = "cheby1_lp_n5_e24_snapped"
    folder = GOLDEN / case
    spec = _spec(case)
    snap_cfg = json.loads((folder / "snap.json").read_text())
    expected = json.loads((folder / "expected_snap.json").read_text())
    series = ESeries(snap_cfg["series"])
    strategy = SnapStrategy(snap_cfg["strategy"])

    circuit = synthesize(spec).circuit
    snapped, report = snap_circuit(circuit, series, strategy)
    assert report.max_delta_pct == np.float64(expected["max_delta_pct"]) or abs(
        report.max_delta_pct - float(expected["max_delta_pct"])
    ) <= 1e-9

    by_ref = {
        el.id: el
        for el in snapped.elements
        if isinstance(el, (IdealInductor, IdealCapacitor))
    }
    rel = float(expected["component_relative_tolerance"])
    for exp in expected["components"]:
        el = by_ref[exp["ref"]]
        if exp["type"] == "inductor":
            assert isinstance(el, IdealInductor)
            value = el.value_h
            ref_value = float(exp["value_H"])
        else:
            assert isinstance(el, IdealCapacitor)
            value = el.value_f
            ref_value = float(exp["value_F"])
        assert abs(value - ref_value) <= rel * max(abs(ref_value), 1e-30)
        # And every snapped part is exactly on the requested grid.
        assert value == nearest_e_series(value, series)


def test_golden_finite_q_loss() -> None:
    case = "butterworth_lp_n5_q100"
    folder = GOLDEN / case
    spec = _spec(case)
    nonideal = json.loads((folder / "nonideal.json").read_text())
    expected = json.loads((folder / "expected_nonideal.json").read_text())

    circuit = synthesize(spec).circuit
    lossy = nonidealize_circuit(circuit, **nonideal)
    # Every inductor gained a series resistance.
    assert any(el.series_resistance_ohm > 0 for el in lossy.elements)  # type: ignore[attr-defined]

    sweep_cfg = expected["sweep"]
    sweep = SweepConfig(
        f_start_hz=float(sweep_cfg["f_start_hz"]),
        f_stop_hz=float(sweep_cfg["f_stop_hz"]),
        n_points=int(sweep_cfg["n_points"]),
        spacing=SweepSpacing(sweep_cfg["spacing"]),
    )
    analysis = analyze_circuit(lossy, sweep)
    s21_db = mag_db(analysis.s21)
    f = analysis.frequency_hz
    tol = float(expected["tolerance_db"])
    metrics = expected["metrics"]

    i_cut = int(np.argmin(np.abs(f - 100e6)))
    band = f <= 100e6
    band_min = float(np.min(s21_db[band]))
    assert abs(float(s21_db[0]) - float(metrics["dc_s21_db"])) <= tol
    assert abs(float(s21_db[i_cut]) - float(metrics["s21_db_at_cutoff"])) <= tol
    assert abs(band_min - float(metrics["passband_s21_db_min"])) <= tol
    assert abs(-band_min - float(metrics["passband_il_db_max"])) <= tol
