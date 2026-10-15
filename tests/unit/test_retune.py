"""Retune (redesign-on-change) service (FR-U2)."""

from __future__ import annotations

import pytest

from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec, SpecValidationError
from filterdesk.services.retune import (
    RetuneRequest,
    nudge_value,
    retune_bandwidth,
    retune_center,
    retune_cutoff,
    retune_spec,
    scale_response,
)
from filterdesk.services.session import DesignSession


def _lp() -> FilterSpec:
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


def _bp() -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.BAND_PASS,
        order=4,
        cutoff_hz=0.0,
        f_center_hz=100e6,
        bandwidth_hz=20e6,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.1,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_BP_SERIES_RES_INPUT,
    )


def test_retune_cutoff_lp_preserves_family() -> None:
    spec = retune_cutoff(_lp(), 140e6)
    assert spec.cutoff_hz == pytest.approx(140e6)
    assert spec.family == ApproximationFamily.CHEBYSHEV_TYPE_I
    assert spec.order == 5


def test_retune_cutoff_rejects_band() -> None:
    with pytest.raises(SpecValidationError):
        retune_cutoff(_bp(), 140e6)


def test_retune_center_keeps_bandwidth() -> None:
    spec = retune_center(_bp(), 200e6)
    assert spec.f_center_hz == pytest.approx(200e6)
    assert spec.bandwidth_hz == pytest.approx(20e6)


def test_retune_center_rejects_lp() -> None:
    with pytest.raises(SpecValidationError):
        retune_center(_lp(), 140e6)


def test_retune_bandwidth() -> None:
    spec = retune_bandwidth(_bp(), 5e6)
    assert spec.bandwidth_hz == pytest.approx(5e6)
    assert spec.f_center_hz == pytest.approx(100e6)


def test_scale_response_lp() -> None:
    spec = scale_response(_lp(), 2.0)
    assert spec.cutoff_hz == pytest.approx(200e6)


def test_scale_response_bp_preserves_fractional_bandwidth() -> None:
    base = _bp()
    spec = scale_response(base, 0.5)
    assert spec.f_center_hz == pytest.approx(50e6)
    assert spec.bandwidth_hz == pytest.approx(10e6)
    assert spec.bandwidth_hz / spec.f_center_hz == pytest.approx(
        base.bandwidth_hz / base.f_center_hz
    )


def test_scale_response_rejects_nonpositive() -> None:
    with pytest.raises(SpecValidationError):
        scale_response(_lp(), 0.0)
    with pytest.raises(SpecValidationError):
        scale_response(_lp(), -1.0)


def test_retune_spec_invalid_cutoff_raises() -> None:
    with pytest.raises(SpecValidationError):
        retune_spec(_lp(), RetuneRequest(cutoff_hz=-1.0))


def test_retune_spec_impedances() -> None:
    spec = retune_spec(_lp(), RetuneRequest(z_source_ohm=75.0, z_load_ohm=75.0))
    assert spec.z_source_ohm == pytest.approx(75.0)
    assert spec.z_load_ohm == pytest.approx(75.0)


def test_session_retune_resynthesizes() -> None:
    session = DesignSession()
    session.set_spec(_lp())
    session.synthesize()
    session.retune(RetuneRequest(cutoff_hz=200e6))
    assert session.spec.cutoff_hz == pytest.approx(200e6)
    assert session.circuit is not None


def test_session_scale_response() -> None:
    session = DesignSession()
    session.set_spec(_bp())
    session.synthesize()
    session.scale_response(2.0)
    assert session.spec.f_center_hz == pytest.approx(200e6)
    assert session.spec.bandwidth_hz == pytest.approx(40e6)


def test_nudge_value() -> None:
    assert nudge_value(100.0, 0.02, 1) == pytest.approx(102.0)
    assert nudge_value(100.0, 0.02, -1) == pytest.approx(98.0)
    with pytest.raises(ValueError):
        nudge_value(100.0, 0.0, 1)
    with pytest.raises(ValueError):
        nudge_value(100.0, 0.5, 3)


def test_session_tune_step_and_nudge() -> None:
    session = DesignSession()
    session.set_spec(_lp())
    session.synthesize()
    assert session.circuit is not None
    l_id = next(el.id for el in session.circuit.elements if el.id.startswith("L"))
    assert session.step_fraction(l_id) == pytest.approx(session.DEFAULT_TUNE_STEP)
    session.set_element_step(l_id, 0.05)
    assert session.step_fraction(l_id) == pytest.approx(0.05)
    base = session.lookup_element_value(l_id)
    new = session.nudge_element(l_id, 1)
    assert new == pytest.approx(base * 1.05)
    assert session.lookup_element_value(l_id) == pytest.approx(new)
    assert session.nudged_value(l_id, -1) == pytest.approx(new * 0.95)
    with pytest.raises(ValueError):
        session.set_element_step(l_id, 0.0)
