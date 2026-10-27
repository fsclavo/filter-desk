"""Edge cases in the ABCD/stress helpers (open and short arms)."""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from filterdesk.analysis.adapters.abcd_ladder import element_impedance_ohm
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.stress import compute_stress
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.circuit import (
    Circuit,
    IdealInductor,
    IdealParallelLC,
    IdealSeriesLC,
    Port,
)
from filterdesk.domain.enums import ElementRole

_F0 = 10e6
_L = 1e-6
_C = 1.0 / ((2.0 * math.pi * _F0) ** 2 * _L)


def _ports() -> tuple[Port, Port]:
    return (
        Port(name="p1", node="in", impedance_ohm=50.0),
        Port(name="p2", node="out", impedance_ohm=50.0),
    )


def test_open_shunt_resonator_has_infinite_impedance_without_warning() -> None:
    element = IdealParallelLC("X1", _L, _C, "out", "gnd", ElementRole.SHUNT)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        impedance = element_impedance_ohm(element, _F0)
    assert math.isinf(abs(impedance))
    assert math.isinf(impedance.real)
    assert impedance.imag == 0.0


def test_stress_with_open_shunt_is_finite() -> None:
    port_in, port_out = _ports()
    circuit = Circuit(
        elements=[
            IdealInductor("L1", 1e-6, "in", "out", ElementRole.SERIES),
            IdealParallelLC("X1", _L, _C, "out", "gnd", ElementRole.SHUNT),
        ],
        port_in=port_in,
        port_out=port_out,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        report = compute_stress(circuit, power_w=10.0, frequency_hz=_F0)
    shunt = next(entry for entry in report.entries if entry.ref == "X1")
    assert math.isinf(abs(shunt.impedance_ohm))
    assert shunt.i_peak_a == pytest.approx(0.0)
    assert math.isfinite(shunt.v_peak_v)
    for entry in report.entries:
        assert math.isfinite(entry.v_peak_v)
        assert math.isfinite(entry.i_peak_a)


def _series_circuit(element: object) -> Circuit:
    port_in, port_out = _ports()
    return Circuit(elements=[element], port_in=port_in, port_out=port_out)  # type: ignore[list-item]


def test_series_open_resonator_has_open_response_without_nan() -> None:
    circuit = _series_circuit(
        IdealParallelLC("X1", _L, _C, "in", "out", ElementRole.SERIES)
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = analyze_circuit(
            circuit, SweepConfig(_F0, 2.0 * _F0, 2, SweepSpacing.LINEAR)
        )
    assert not np.isnan(result.s11).any()
    assert not np.isnan(result.s21).any()
    assert abs(result.s21[0]) < 1e-6
    assert abs(result.s11[0]) > 0.999999


def test_series_short_resonator_passes_without_nan() -> None:
    circuit = _series_circuit(
        IdealSeriesLC("X1", _L, _C, "in", "out", ElementRole.SERIES)
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = analyze_circuit(
            circuit, SweepConfig(_F0, 2.0 * _F0, 2, SweepSpacing.LINEAR)
        )
    assert not np.isnan(result.s11).any()
    assert not np.isnan(result.s21).any()
    assert abs(result.s21[0]) > 0.999999
    assert abs(result.s11[0]) < 1e-6
