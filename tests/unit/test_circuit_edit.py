"""B3.1 — ladder topology editing operations."""

from __future__ import annotations

import math

import pytest

from filterdesk.domain.circuit import IdealCapacitor, IdealInductor
from filterdesk.domain.circuit_edit import (
    CircuitEditError,
    rebuild_ladder,
    reference_frequency_hz,
)
from filterdesk.domain.enums import ElementRole
from filterdesk.services.session import DesignSession


def test_session_insert_and_delete_arm() -> None:
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    n = len(session.circuit.elements)
    first_id = session.circuit.elements[0].id
    session.insert_arm(
        role=ElementRole.SHUNT, kind="C", value_si=10e-12, before_id=first_id
    )
    assert session.circuit is not None
    assert len(session.circuit.elements) == n + 1
    ids = [el.id for el in session.circuit.elements]
    assert len(ids) == len(set(ids))
    # Still a valid, analyzable ladder.
    session.analyze()
    inserted_id = session.circuit.elements[0].id
    session.delete_arm(inserted_id)
    assert len(session.circuit.elements) == n


def test_convert_simple_arm_preserves_reactance() -> None:
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    cap = next(el for el in session.circuit.elements if isinstance(el, IdealCapacitor))
    idx = session.circuit.elements.index(cap)
    freq = reference_frequency_hz(session.circuit)
    assert freq is not None and freq > 0.0
    omega = 2.0 * math.pi * freq
    reactance = 1.0 / (omega * cap.value_f)

    session.change_arm_type(cap.id, "L")
    assert session.circuit is not None
    ind = session.circuit.elements[idx]
    assert isinstance(ind, IdealInductor)
    assert abs(omega * ind.value_h / reactance - 1.0) < 1e-9

    session.change_arm_type(ind.id, "C")
    assert session.circuit is not None
    cap2 = session.circuit.elements[idx]
    assert isinstance(cap2, IdealCapacitor)
    assert abs(cap2.value_f / cap.value_f - 1.0) < 1e-9


def test_delete_last_element_raises() -> None:
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    while len(session.circuit.elements) > 1:
        session.delete_arm(session.circuit.elements[0].id)
    with pytest.raises(CircuitEditError):
        session.delete_arm(session.circuit.elements[0].id)


def test_rebuild_ladder_is_idempotent_for_synthesized_circuit() -> None:
    session = DesignSession()
    session.synthesize()
    circuit = session.circuit
    assert circuit is not None
    rebuilt = rebuild_ladder(circuit, list(circuit.elements))
    assert [el.id for el in rebuilt.elements] == [el.id for el in circuit.elements]
    assert rebuilt.port_out.node == circuit.port_out.node
    for el in rebuilt.elements:
        if el.role == ElementRole.SHUNT:
            assert el.node_b == circuit.ground
