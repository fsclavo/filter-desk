"""DesignSession branches: element edits, limits, persistence, helpers."""

from __future__ import annotations

from dataclasses import replace

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
from filterdesk.domain.enums import (
    ApproximationFamily as Fam,
)
from filterdesk.domain.enums import (
    CutoffDefinition as Cut,
)
from filterdesk.domain.enums import (
    ElementRole,
)
from filterdesk.domain.enums import (
    FilterResponse as Resp,
)
from filterdesk.domain.enums import (
    TopologyId as Topo,
)
from filterdesk.domain.overlays import MAX_LIMITS, MAX_MARKERS, LimitRegion, Marker
from filterdesk.domain.project import Project, ProjectMetadata
from filterdesk.domain.specs import FilterSpec
from filterdesk.montecarlo import MonteCarloConfig
from filterdesk.services.session import DEFAULT_TITLE, DesignSession

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


def test_session_element_lookup_and_updates() -> None:
    session = DesignSession()
    session.circuit = _circuit()
    assert session.lookup_element_value("R1") == pytest.approx(50.0)
    assert session.lookup_element_value("L1") == pytest.approx(1e-6)
    assert session.lookup_element_value("C1") == pytest.approx(1e-12)
    assert session.lookup_element_value("X1.L") == pytest.approx(2e-6)
    assert session.lookup_element_value("X1.C") == pytest.approx(2e-12)
    assert session.lookup_element_value("X3.Ls") == pytest.approx(4e-6)
    assert session.lookup_element_value("X3.Cp") == pytest.approx(5e-12)
    assert session.lookup_element_value("L2") == pytest.approx(8e-6)
    assert session.lookup_element_value("C2") == pytest.approx(8e-12)

    with pytest.raises(ValueError, match="Xn.L"):
        session.lookup_element_value("X1")
    with pytest.raises(ValueError, match="Xn.Ls"):
        session.lookup_element_value("X3")
    with pytest.raises(KeyError):
        session.lookup_element_value("missing")

    session.update_element_value("R1", 100.0)
    session.update_element_value("L1", 2e-6)
    session.update_element_value("C1", 2e-12)
    session.update_element_value("X1.L", 3e-6)
    session.update_element_value("X1.C", 3e-12)
    session.update_element_value("X2.L", 4e-6)
    session.update_element_value("X2.C", 4e-12)
    session.update_element_value("X3.Ls", 5e-6)
    session.update_element_value("X3.Cs", 5e-12)
    session.update_element_value("X3.Lp", 6e-6)
    session.update_element_value("X3.Cp", 6e-12)
    session.update_element_value("L2", 9e-6)
    session.update_element_value("C2", 9e-12)
    by_id = {el.id: el for el in session.circuit.elements}
    assert by_id["R1"].value_ohm == pytest.approx(100.0)
    assert by_id["X1"].value_h == pytest.approx(3e-6)
    assert by_id["X1"].value_f == pytest.approx(3e-12)
    assert by_id["X2"].value_h == pytest.approx(4e-6)
    assert by_id["X3"].series_l_h == pytest.approx(5e-6)
    assert by_id["X3"].parallel_c_f == pytest.approx(6e-12)
    assert by_id["L2"].series_resistance_ohm == pytest.approx(0.5)
    assert by_id["C2"].esl_h == pytest.approx(1e-9)

    with pytest.raises(ValueError, match="edit resonator"):
        session.update_element_value("X1", 3e-6)
    with pytest.raises(ValueError, match="edit Brune"):
        session.update_element_value("X3", 3e-6)
    with pytest.raises(ValueError, match="component value"):
        session.update_element_value("R1", 0.0)
    with pytest.raises(KeyError):
        session.update_element_value("missing", 1.0)


def test_session_tune_steps_and_tolerances() -> None:
    session = DesignSession()
    session.circuit = _circuit()
    assert session.step_fraction("X1.L") == DesignSession.DEFAULT_TUNE_STEP
    session.set_element_step("X1.L", 0.05)
    assert session.step_fraction("X1") == pytest.approx(0.05)
    with pytest.raises(ValueError, match="tune step"):
        session.set_element_step("L1", 0.0)

    assert session.nudged_value("L1", +1) == pytest.approx(1e-6 * 1.02)
    before = session.lookup_element_value("L1")
    new_value = session.nudge_element("L1", -1)
    assert new_value == pytest.approx(before * 0.98)
    assert session.lookup_element_value("L1") == pytest.approx(new_value)

    session.set_element_tolerance("L1", 5.0)
    assert session.element_tolerance("L1").tolerance_pct == pytest.approx(5.0)
    session.clear_element_tolerance("L1")
    assert session.element_tolerance("L1") is None
    session.clear_element_tolerance("missing")


def test_session_no_circuit_errors() -> None:
    session = DesignSession()
    session.circuit = None
    with pytest.raises(ValueError):
        session.optimize()
    with pytest.raises(ValueError):
        session.sensitivity()
    with pytest.raises(ValueError):
        session.monte_carlo(MonteCarloConfig())
    with pytest.raises(ValueError):
        session.snap_components()
    with pytest.raises(ValueError):
        session.apply_nonideal()
    with pytest.raises(ValueError):
        session.lookup_element_value("L1")
    with pytest.raises(ValueError):
        session.update_element_value("L1", 1e-6)
    with pytest.raises(ValueError):
        session.insert_arm(role=ElementRole.SERIES, kind="L", value_si=1e-6)
    with pytest.raises(ValueError):
        session.delete_arm("L1")
    with pytest.raises(ValueError):
        session.change_arm_type("L1", "C")
    with pytest.raises(ValueError):
        session.summary_metrics()

    session.power_w = 0.0
    assert session.compute_stress() is None
    session.power_w = 1.0
    assert session.compute_stress() is None  # no circuit
    assert session.compute_harmonics() is None


def test_session_stress_and_harmonics_branches() -> None:
    session = DesignSession()
    session.synthesize()
    session.power_w = 10.0
    assert session.stress_frequency_hz() == pytest.approx(session.spec.cutoff_hz)
    assert session.compute_stress() is not None
    session.analysis = session.analyze()
    assert session.compute_harmonics() is not None
    session.harmonics_f0_hz = 7e6
    assert session.harmonics_reference_hz() == pytest.approx(7e6)

    # StressError → None (empty circuit)
    session.circuit = Circuit(elements=[], port_in=PORTS[0], port_out=PORTS[1])
    assert session.compute_stress() is None

    # BP uses the center frequency; a zero cutoff yields None.
    bp = FilterSpec(
        family=Fam.CHEBYSHEV_TYPE_I,
        response=Resp.BAND_PASS,
        order=4,
        f_center_hz=100e6,
        bandwidth_hz=20e6,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=Topo.LADDER_BP_SERIES_RES_INPUT,
        cutoff_definition=Cut.RIPPLE_EDGE,
        passband_ripple_db=0.1,
    )
    session.set_spec(bp)
    assert session.stress_frequency_hz() == pytest.approx(100e6)
    session.spec = replace(session.spec, response=Resp.LOW_PASS, cutoff_hz=0.0)
    assert session.stress_frequency_hz() is None
    session.analysis = None
    session.harmonics_f0_hz = None
    assert session.compute_harmonics() is None


def test_session_limits_and_markers() -> None:
    session = DesignSession()
    markers = [Marker(f"m{i}", 1e6) for i in range(MAX_MARKERS)]
    session.set_markers(markers)
    assert len(session.markers) == MAX_MARKERS
    with pytest.raises(ValueError, match="at most"):
        session.set_markers([*markers, Marker("extra", 1e6)])

    limits = [
        LimitRegion(f"l{i}", "s21_db", 1e6, 2e6, y_max=0.0)
        for i in range(MAX_LIMITS)
    ]
    session.set_limits(limits)
    assert len(session.limits) == MAX_LIMITS
    with pytest.raises(ValueError, match="at most"):
        session.set_limits(
            [*limits, LimitRegion("extra", "s21_db", 1e6, 2e6, y_max=0.0)]
        )


def test_session_load_project_branches() -> None:
    session = DesignSession()
    with pytest.raises(ValueError, match="no specification"):
        session.load_project(Project())

    spec = session.spec
    session.load_project(Project(specification=spec))
    assert session.circuit is not None
    assert session.title == DEFAULT_TITLE

    legacy = Project(
        specification=spec,
        circuit=_circuit(),
        metadata=ProjectMetadata(title="Milestone Chebyshev HP"),
        extensions={
            "markers": "bad",
            "limits": 3,
            "element_steps": {"L1": "bad", "C1": 2},
            "element_tolerances": {
                "L1": "bad",
                "C1": {"tolerance_pct": 2.0, "distribution": "uniform"},
                "C2": {"tolerance_pct": "bad"},
            },
            "power_w": "bad",
            "harmonics_f0_hz": "bad",
        },
    )
    session.load_project(legacy)
    assert session.title == DEFAULT_TITLE
    assert session.markers == [] and session.limits == []
    assert session.element_steps == {"C1": 2.0}
    assert "C1" in session.element_tolerances and "L1" not in session.element_tolerances
    assert session.power_w == 0.0
    assert session.harmonics_f0_hz is None
    assert session.dirty is False


def test_session_change_arm_type_without_reference() -> None:
    session = DesignSession()
    session.circuit = Circuit(
        elements=[IdealInductor("L1", 1e-6, "in", "out", ElementRole.SERIES)],
        port_in=PORTS[0],
        port_out=PORTS[1],
    )
    with pytest.raises(ValueError, match="reference frequency"):
        session.change_arm_type("L1", "C")
