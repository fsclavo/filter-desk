"""Kirschning-Jansen microstrip dispersion limits."""

from __future__ import annotations

import numpy as np
import pytest

from filterdesk.analysis.adapters.abcd_ladder import _element_abcd
from filterdesk.analysis.microstrip_dispersion import dispersion_eeff_z0
from filterdesk.components_std.microstrip import design_microstrip, find_substrate
from filterdesk.domain.circuit import Circuit, MicrostripLineElement, Port
from filterdesk.domain.enums import ElementRole
from filterdesk.domain.project import circuit_from_mapping, circuit_to_mapping


def test_dispersion_limits_and_monotonicity() -> None:
    substrate = find_substrate("FR4")
    line = design_microstrip(50.0, substrate, 1e9)
    eeff, z0 = dispersion_eeff_z0(
        np.array([1e6, 1e9, 10e9]),
        z0_ohm=line.z0_ohm,
        eeff_static=line.eeff,
        er=substrate.er,
        height_mm=substrate.h_mm,
        width_mm=line.width_mm,
    )
    assert eeff[0] == pytest.approx(line.eeff, abs=1e-3)
    assert eeff[0] <= eeff[1] <= eeff[2] <= substrate.er
    assert z0[0] == pytest.approx(line.z0_ohm, abs=0.1)
    assert np.all(np.isfinite(z0))
    assert np.all(z0 > 0.0)


def test_dispersion_is_noop_without_geometry() -> None:
    eeff, z0 = dispersion_eeff_z0(
        np.array([1e6, 1e9]),
        z0_ohm=50.0,
        eeff_static=3.0,
        er=1.0,
        height_mm=0.0,
        width_mm=0.0,
    )
    assert np.allclose(eeff, 3.0)
    assert np.allclose(z0, 50.0)


def test_line_abcd_uses_dispersive_properties() -> None:
    base = dict(
        id="TL1",
        length_m=0.05,
        node_a="in",
        node_b="out",
        role=ElementRole.SERIES,
    )
    static = MicrostripLineElement(z0_ohm=50.0, eeff=3.0, **base)
    dispersive = MicrostripLineElement(
        z0_ohm=50.0,
        eeff=3.0,
        er=4.4,
        height_mm=1.6,
        width_mm=3.0,
        **base,
    )
    freq = np.array([1e6, 20e9])
    static_abcd = _element_abcd(static, 2.0 * np.pi * freq)
    dispersive_abcd = _element_abcd(dispersive, 2.0 * np.pi * freq)
    assert np.allclose(static_abcd[0], dispersive_abcd[0], atol=1e-3)
    assert not np.allclose(static_abcd[1], dispersive_abcd[1], atol=1e-3)


def test_dispersion_geometry_project_round_trip() -> None:
    line = MicrostripLineElement(
        id="TL1",
        z0_ohm=50.0,
        length_m=0.05,
        eeff=3.0,
        er=4.4,
        height_mm=1.6,
        width_mm=3.0,
        node_a="in",
        node_b="out",
    )
    circuit = Circuit([line], Port("P1", "in", 50.0), Port("P2", "out", 50.0))
    restored = circuit_from_mapping(circuit_to_mapping(circuit))
    restored_line = restored.elements[0]
    assert isinstance(restored_line, MicrostripLineElement)
    assert restored_line.er == pytest.approx(4.4)
    assert restored_line.height_mm == pytest.approx(1.6)
