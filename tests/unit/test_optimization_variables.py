"""Optimizer variable enumeration / replacement branches."""

from __future__ import annotations

import pytest

from filterdesk.domain.circuit import (
    Circuit,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealResistor,
    IdealSeriesLC,
    NonIdealCapacitor,
    NonIdealInductor,
    Port,
)
from filterdesk.domain.enums import ElementRole
from filterdesk.optimization.variables import apply_values, tunable_params

PORTS = (
    Port(name="port1", node="in", impedance_ohm=50.0),
    Port(name="port2", node="out", impedance_ohm=50.0),
)


def _circuit() -> Circuit:
    return Circuit(
        elements=[
            IdealResistor("R1", 50.0, "in", "out", ElementRole.SERIES),
            IdealInductor("L1", 1e-6, "in", "n1", ElementRole.SERIES),
            IdealCapacitor("C1", 1e-12, "n1", "gnd", ElementRole.SHUNT),
            IdealSeriesLC("X1", 2e-6, 2e-12, "n1", "out", ElementRole.SERIES),
            IdealParallelLC("X2", 3e-6, 3e-12, "out", "gnd", ElementRole.SHUNT),
            IdealBruneLC(
                "X3", 4e-6, 4e-12, 5e-6, 5e-12, "in", "out", ElementRole.SERIES
            ),
            IdealDualBruneLC(
                "X4", 6e-6, 6e-12, 7e-6, 7e-12, "in", "gnd", ElementRole.SHUNT
            ),
            NonIdealInductor(
                "L2",
                8e-6,
                "in",
                "out",
                ElementRole.SERIES,
                series_resistance_ohm=0.5,
                parallel_capacitance_f=1e-12,
            ),
            NonIdealCapacitor(
                "C2",
                8e-12,
                "out",
                "gnd",
                ElementRole.SHUNT,
                esr_ohm=0.1,
                esl_h=1e-9,
            ),
        ],
        port_in=PORTS[0],
        port_out=PORTS[1],
    )


def test_tunable_params_covers_all_element_types() -> None:
    params = tunable_params(_circuit())
    assert [(p.ref, p.field) for p in params] == [
        ("R1", "value_ohm"),
        ("L1", "value_h"),
        ("C1", "value_f"),
        ("X1.L", "value_h"),
        ("X1.C", "value_f"),
        ("X2.L", "value_h"),
        ("X2.C", "value_f"),
        ("X3.Ls", "series_l_h"),
        ("X3.Cs", "series_c_f"),
        ("X3.Lp", "parallel_l_h"),
        ("X3.Cp", "parallel_c_f"),
        ("X4.Ls", "series_l_h"),
        ("X4.Cs", "series_c_f"),
        ("X4.Lp", "parallel_l_h"),
        ("X4.Cp", "parallel_c_f"),
        ("L2", "value_h"),
        ("C2", "value_f"),
    ]


def test_apply_values_updates_every_element_type() -> None:
    circuit = _circuit()
    params = tunable_params(circuit)
    values = [p.value * 2.0 for p in params]
    updated = apply_values(circuit, params, values)
    by_id = {el.id: el for el in updated.elements}

    assert by_id["R1"].value_ohm == pytest.approx(100.0)
    assert by_id["L1"].value_h == pytest.approx(2e-6)
    assert by_id["C1"].value_f == pytest.approx(2e-12)
    assert by_id["X1"].value_h == pytest.approx(4e-6)
    assert by_id["X1"].value_f == pytest.approx(4e-12)
    assert by_id["X2"].value_h == pytest.approx(6e-6)
    assert by_id["X2"].value_f == pytest.approx(6e-12)
    assert by_id["X3"].series_l_h == pytest.approx(8e-6)
    assert by_id["X3"].series_c_f == pytest.approx(8e-12)
    assert by_id["X3"].parallel_l_h == pytest.approx(10e-6)
    assert by_id["X3"].parallel_c_f == pytest.approx(10e-12)
    assert by_id["X4"].series_l_h == pytest.approx(12e-6)
    assert by_id["X4"].parallel_c_f == pytest.approx(14e-12)
    assert by_id["L2"].value_h == pytest.approx(16e-6)
    assert by_id["L2"].series_resistance_ohm == pytest.approx(0.5)
    assert by_id["L2"].parallel_capacitance_f == pytest.approx(1e-12)
    assert by_id["C2"].value_f == pytest.approx(16e-12)
    assert by_id["C2"].esr_ohm == pytest.approx(0.1)
    assert by_id["C2"].esl_h == pytest.approx(1e-9)


def test_apply_values_no_params_keeps_circuit() -> None:
    circuit = _circuit()
    same = apply_values(circuit, [], [])
    assert same.elements == circuit.elements
    assert same.port_in == circuit.port_in


def test_apply_values_rejects_length_mismatch() -> None:
    circuit = _circuit()
    with pytest.raises(ValueError):
        apply_values(circuit, tunable_params(circuit), [1.0])
