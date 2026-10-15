"""E-series tables and component snapping."""

from __future__ import annotations

import json

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.components_std import (
    ESeries,
    base_values,
    e_series_values,
    nearest_e_series,
)
from filterdesk.components_std.snap import (
    SnapStrategy,
    snap_circuit,
)
from filterdesk.domain.circuit import IdealCapacitor, IdealInductor
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.synthesis import synthesize


def _lp_spec(order: int = 4) -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.LOW_PASS,
        order=order,
        cutoff_hz=100e6,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.1,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
    )


def _bp_spec() -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_II,
        response=FilterResponse.BAND_PASS,
        order=5,
        f_center_hz=100e6,
        bandwidth_hz=10e6,
        stopband_attenuation_db=30.0,
        cutoff_definition=CutoffDefinition.STOPBAND_EDGE,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_BP_SERIES_RES_INPUT,
    )


@pytest.mark.parametrize(
    ("series", "count"),
    [
        (ESeries.E6, 6),
        (ESeries.E12, 12),
        (ESeries.E24, 24),
        (ESeries.E48, 48),
        (ESeries.E96, 96),
    ],
)
def test_base_values_sorted_in_decade(series: ESeries, count: int) -> None:
    base = base_values(series)
    assert len(base) == count
    assert list(base) == sorted(base)
    assert base[0] == pytest.approx(1.0)
    assert 1.0 <= base[-1] < 10.0


def test_e_series_values_spans_decades() -> None:
    values = e_series_values(ESeries.E6, decades=3)
    assert len(values) == 18
    assert values[0] == pytest.approx(1.0)
    assert values[6] == pytest.approx(10.0)
    assert values[-1] == pytest.approx(680.0)


@pytest.mark.parametrize(
    ("value", "series", "expected"),
    [
        (4.68e3, ESeries.E24, 4.7e3),
        (4.7e3, ESeries.E48, 4.64e3),
        (73.985e-9, ESeries.E96, 73.2e-9),
        (4.666e-11, ESeries.E24, 4.7e-11),
        (3.0, ESeries.E6, 3.3),
        (9.7e-9, ESeries.E24, 10e-9),
        (1.0, ESeries.E96, 1.0),
    ],
)
def test_nearest_e_series(
    value: float, series: ESeries, expected: float
) -> None:
    assert nearest_e_series(value, series) == pytest.approx(expected, rel=1e-12)


def test_nearest_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        nearest_e_series(0.0, ESeries.E24)


def test_snap_independent_produces_e_series_values() -> None:
    circuit = synthesize(_lp_spec()).circuit
    snapped, report = snap_circuit(circuit, ESeries.E24, SnapStrategy.INDEPENDENT)
    assert report.series is ESeries.E24
    assert report.entries
    for el in snapped.elements:
        if isinstance(el, IdealInductor):
            assert el.value_h == nearest_e_series(el.value_h, ESeries.E24)
        elif isinstance(el, IdealCapacitor):
            assert el.value_f == nearest_e_series(el.value_f, ESeries.E24)
    assert report.max_delta_pct <= 6.0
    # original untouched
    assert circuit.elements[0] is not snapped.elements[0]


def test_snap_l_only_and_c_only() -> None:
    circuit = synthesize(_lp_spec()).circuit
    l_only, _ = snap_circuit(circuit, ESeries.E24, SnapStrategy.L_ONLY)
    c_only, _ = snap_circuit(circuit, ESeries.E24, SnapStrategy.C_ONLY)
    for orig, l_el, c_el in zip(
        circuit.elements, l_only.elements, c_only.elements, strict=True
    ):
        if isinstance(orig, IdealInductor):
            assert l_el.value_h == nearest_e_series(orig.value_h, ESeries.E24)
            assert c_el.value_h == orig.value_h  # C_ONLY leaves L alone
        elif isinstance(orig, IdealCapacitor):
            assert l_el.value_f == orig.value_f  # L_ONLY leaves C alone
            assert c_el.value_f == nearest_e_series(orig.value_f, ESeries.E24)


def _resonances(circuit: object) -> list[float]:
    freqs: list[float] = []
    for el in circuit.elements:  # type: ignore[attr-defined]
        pairs: list[tuple[float, float]] = []
        if isinstance(el, IdealInductor | IdealCapacitor):
            continue
        if hasattr(el, "value_h") and hasattr(el, "value_f"):
            pairs.append((el.value_h, el.value_f))
        if hasattr(el, "series_l_h"):
            pairs.append((el.series_l_h, el.series_c_f))
            pairs.append((el.parallel_l_h, el.parallel_c_f))
        for l_h, c_f in pairs:
            freqs.append(1.0 / (2.0 * np.pi * np.sqrt(l_h * c_f)))
    return freqs


def test_preserve_resonances_beats_independent_e96() -> None:
    circuit = synthesize(_bp_spec()).circuit
    f0 = np.asarray(_resonances(circuit))

    independent, _ = snap_circuit(circuit, ESeries.E96, SnapStrategy.INDEPENDENT)
    preserve, _ = snap_circuit(
        circuit, ESeries.E96, SnapStrategy.PRESERVE_LC_RESONANCES
    )
    err_ind = np.max(np.abs(np.asarray(_resonances(independent)) / f0 - 1.0))
    err_pre = np.max(np.abs(np.asarray(_resonances(preserve)) / f0 - 1.0))
    assert err_pre < err_ind
    assert err_pre < 0.01


def test_session_snap_components() -> None:
    from filterdesk.services.session import DesignSession

    session = DesignSession()
    session.synthesize()
    report = session.snap_components(ESeries.E24, SnapStrategy.INDEPENDENT)
    assert report.entries
    assert session.circuit is not None
    assert session.analysis is None


def test_cli_snap_human(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "snap",
            "--family",
            "chebyshev_type_i",
            "--response",
            "low_pass",
            "--order",
            "4",
            "--cutoff",
            "100M",
            "--ripple",
            "0.1",
            "--series",
            "E24",
            "--strategy",
            "independent",
        ]
    )
    assert code == 0
    assert "Snap to E24" in capsys.readouterr().out


def test_cli_snap_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "snap",
            "--family",
            "chebyshev_type_i",
            "--response",
            "low_pass",
            "--order",
            "4",
            "--cutoff",
            "100M",
            "--ripple",
            "0.1",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["snap"]["series"] == "E24"
    assert payload["snap"]["entries"]
