"""Phase 3 UX: undo/redo, markers, limits."""

from __future__ import annotations

from pathlib import Path

from filterdesk.analysis.limits_eval import evaluate_limit
from filterdesk.domain.circuit import IdealCapacitor, IdealInductor
from filterdesk.domain.overlays import LimitMetric, LimitRegion, Marker
from filterdesk.io.native import load_project, save_project
from filterdesk.services.session import DesignSession


def test_markers_limits_roundtrip(tmp_path: Path) -> None:
    session = DesignSession()
    session.synthesize_and_analyze()
    session.set_markers([Marker(id="M1", frequency_hz=140e6, label="fc")])
    session.set_limits(
        [
            LimitRegion(
                id="L1",
                metric=LimitMetric.S21_DB,
                f_low_hz=10e6,
                f_high_hz=50e6,
                y_max=-40.0,
            )
        ]
    )
    path = tmp_path / "ux.filterdesk.json"
    save_project(session.to_project(), path)
    loaded = load_project(path)
    session2 = DesignSession()
    session2.load_project(loaded, path=str(path))
    assert len(session2.markers) == 1
    assert session2.markers[0].frequency_hz == 140e6
    assert len(session2.limits) == 1
    assert session2.limits[0].y_max == -40.0


def test_limit_eval_pass_fail() -> None:
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.analysis is not None
    # Far below cutoff HP should have low S21 → pass if y_max=-20 in stopband
    lim = LimitRegion(
        id="L1",
        metric=LimitMetric.S21_DB,
        f_low_hz=1e6,
        f_high_hz=10e6,
        y_max=-20.0,
    )
    assert evaluate_limit(session.analysis, lim) is True
    # Impossible: require S21 > 10 dB somewhere in stopband
    lim_fail = LimitRegion(
        id="L2",
        metric=LimitMetric.S21_DB,
        f_low_hz=1e6,
        f_high_hz=10e6,
        y_min=10.0,
    )
    assert evaluate_limit(session.analysis, lim_fail) is False


def test_element_value_edit_roundtrip() -> None:
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    for el in session.circuit.elements:
        if isinstance(el, IdealCapacitor):
            el_id, old = el.id, el.value_f
            break
        if isinstance(el, IdealInductor):
            el_id, old = el.id, el.value_h
            break
    else:
        raise AssertionError("no L/C element")
    session.update_element_value(el_id, old * 1.1)
    assert abs(session.lookup_element_value(el_id) / (old * 1.1) - 1.0) < 1e-12
    session.update_element_value(el_id, old)
    assert abs(session.lookup_element_value(el_id) / old - 1.0) < 1e-12


def test_smith_limit_eval_and_roundtrip(tmp_path: Path) -> None:
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.analysis is not None
    # High-pass: deep stopband reflects almost all → |S11| near 1 (fail 0.5).
    lim_stop = LimitRegion(
        id="L1",
        metric=LimitMetric.S11_MAG,
        f_low_hz=1e6,
        f_high_hz=10e6,
        y_max=0.5,
    )
    assert evaluate_limit(session.analysis, lim_stop) is False
    # Well into the passband → |S11| small (pass 0.5).
    lim_pass = LimitRegion(
        id="L2",
        metric=LimitMetric.S11_MAG,
        f_low_hz=300e6,
        f_high_hz=1e9,
        y_max=0.5,
    )
    assert evaluate_limit(session.analysis, lim_pass) is True

    session.set_limits([lim_stop, lim_pass])
    path = tmp_path / "smith_limits.filterdesk.json"
    save_project(session.to_project(), path)
    loaded = load_project(path)
    session2 = DesignSession()
    session2.load_project(loaded, path=str(path))
    assert len(session2.limits) == 2
    assert session2.limits[0].metric == LimitMetric.S11_MAG
    assert session2.limits[0].y_max == 0.5


def test_project_extensions_empty_by_default() -> None:
    session = DesignSession()
    session.synthesize()
    proj = session.to_project()
    assert "markers" not in proj.extensions
    assert "limits" not in proj.extensions
