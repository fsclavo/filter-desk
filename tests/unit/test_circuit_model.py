"""Circuit model helpers: physical rows, component table, node paths."""

from __future__ import annotations

import math

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
    physical_components,
    series_node_path,
)
from filterdesk.domain.enums import ElementRole, ElementType

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


def test_physical_components_expand_every_type() -> None:
    comps = physical_components(_circuit())
    assert [c.ref for c in comps] == [
        "R1",
        "L1",
        "C1",
        "X1.L",
        "X1.C",
        "X2.L",
        "X2.C",
        "X3.Ls",
        "X3.Cs",
        "X3.Lp",
        "X3.Cp",
        "X4.Ls",
        "X4.Cs",
        "X4.Lp",
        "X4.Cp",
        "L2",
        "C2",
    ]
    assert [c.kind for c in comps] == [
        "resistor",
        "inductor",
        "capacitor",
        "inductor",
        "capacitor",
        "inductor",
        "capacitor",
        "inductor",
        "capacitor",
        "inductor",
        "capacitor",
        "inductor",
        "capacitor",
        "inductor",
        "capacitor",
        "inductor",
        "capacitor",
    ]
    l2 = next(c for c in comps if c.ref == "L2")
    assert l2.series_resistance_ohm == pytest.approx(0.5)
    assert l2.parallel_capacitance_f == pytest.approx(1e-12)
    c2 = next(c for c in comps if c.ref == "C2")
    assert c2.esr_ohm == pytest.approx(0.1)
    assert c2.esl_h == pytest.approx(1e-9)


def test_component_table_covers_every_type() -> None:
    rows = {row["ref"]: row for row in _circuit().component_table()}
    assert rows["R1"]["value_Ohm"] == pytest.approx(50.0)
    assert rows["L1"]["value_H"] == pytest.approx(1e-6)
    assert rows["C1"]["value_F"] == pytest.approx(1e-12)
    assert rows["X1"]["value_H"] == pytest.approx(2e-6)
    assert rows["X1"]["value_F"] == pytest.approx(2e-12)
    assert rows["X3"]["series_L_H"] == pytest.approx(4e-6)
    assert rows["X3"]["parallel_C_F"] == pytest.approx(5e-12)
    assert rows["L2"]["series_R_Ohm"] == pytest.approx(0.5)
    assert rows["L2"]["parallel_C_F"] == pytest.approx(1e-12)
    assert rows["C2"]["esr_Ohm"] == pytest.approx(0.1)
    assert rows["C2"]["esl_H"] == pytest.approx(1e-9)


def test_series_node_path() -> None:
    assert series_node_path(0) == ["in"]
    assert series_node_path(1) == ["in", "out"]
    assert series_node_path(3) == ["in", "n1", "n2", "out"]


def test_element_types_and_self_resonance() -> None:
    assert IdealResistor("R", 1.0, "a", "b").element_type == ElementType.RESISTOR
    inductor = NonIdealInductor(
        "L", 1e-6, "a", "b", ElementRole.SERIES, parallel_capacitance_f=0.0
    )
    assert inductor.self_resonant_frequency_hz is None
    inductor_cp = NonIdealInductor(
        "L", 1e-6, "a", "b", ElementRole.SERIES, parallel_capacitance_f=1e-12
    )
    expected_l = 1.0 / (2.0 * math.pi * math.sqrt(1e-6 * 1e-12))
    assert inductor_cp.self_resonant_frequency_hz == pytest.approx(expected_l)

    capacitor = NonIdealCapacitor(
        "C", 1e-12, "a", "b", ElementRole.SHUNT, esl_h=0.0
    )
    assert capacitor.self_resonant_frequency_hz is None
    capacitor_esl = NonIdealCapacitor(
        "C", 1e-12, "a", "b", ElementRole.SHUNT, esl_h=1e-9
    )
    expected_c = 1.0 / (2.0 * math.pi * math.sqrt(1e-9 * 1e-12))
    assert capacitor_esl.self_resonant_frequency_hz == pytest.approx(expected_c)
