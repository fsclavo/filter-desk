"""SPICE export branches for every element type and edge cases."""

from __future__ import annotations

from types import SimpleNamespace

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
from filterdesk.io.spice import SpiceExportError, spice_netlist

PORT_IN = Port(name="port1", node="in", impedance_ohm=50.0)
PORT_OUT = Port(name="port2", node="out", impedance_ohm=50.0)


def _all_elements() -> list[object]:
    return [
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
        NonIdealInductor("L3", 9e-6, "in", "out", ElementRole.SERIES),
        NonIdealCapacitor(
            "C2",
            8e-12,
            "out",
            "gnd",
            ElementRole.SHUNT,
            esr_ohm=0.1,
            esl_h=1e-9,
        ),
        NonIdealCapacitor("C3", 9e-12, "out", "gnd", ElementRole.SHUNT),
    ]


def test_spice_exports_every_element_type() -> None:
    circuit = Circuit(
        elements=_all_elements(),  # type: ignore[arg-type]
        port_in=PORT_IN,
        port_out=PORT_OUT,
    )
    net = spice_netlist(circuit)
    for token in (
        "RR1",
        "LL1",
        "CC1",
        "LX1L",
        "CX1C",
        "LX2L",
        "CX2C",
        "LX3Ls",
        "CX3Cs",
        "LX3Lp",
        "CX3Cp",
        "LX4Ls",
        "CX4Cs",
        "LX4Lp",
        "CX4Cp",
        "LL2",
        "RL2r",
        "CL2cp",
        "LL3",
        "CC2",
        "LC2l",
        "RC2r",
        "CC3",
        "RC3r",
    ):
        assert token in net


def test_spice_zero_source_impedance() -> None:
    port_in = Port(name="port1", node="in", impedance_ohm=0.0)
    circuit = Circuit(
        elements=[IdealInductor("L1", 1e-6, "in", "out", ElementRole.SERIES)],
        port_in=port_in,
        port_out=PORT_OUT,
    )
    net = spice_netlist(circuit)
    assert "V1 in 0 AC 1" in net
    assert "RV1s" not in net


def test_spice_empty_and_unsupported() -> None:
    with pytest.raises(SpiceExportError, match="no elements"):
        spice_netlist(Circuit(elements=[], port_in=PORT_IN, port_out=PORT_OUT))
    unknown = SimpleNamespace(id="U1", node_a="in", node_b="out")
    circuit = Circuit(
        elements=[unknown],  # type: ignore[list-item]
        port_in=PORT_IN,
        port_out=PORT_OUT,
    )
    with pytest.raises(SpiceExportError, match="unsupported element"):
        spice_netlist(circuit)
