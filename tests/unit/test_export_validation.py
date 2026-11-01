"""Structural validation of LTspice/Qucs/SPICE exports."""

from __future__ import annotations

import pytest

from filterdesk.domain.enums import ApproximationFamily, FilterResponse
from filterdesk.domain.specs import (
    FilterSpec,
    default_cutoff_definition,
    default_topology,
)
from filterdesk.io.export_validation import (
    validate_exports,
    validate_ltspice_asc,
    validate_qucs_schematic,
)
from filterdesk.io.qucs import qucs_schematic
from filterdesk.io.spice import ltspice_asc
from filterdesk.synthesis import synthesize


def _spec(response: FilterResponse) -> FilterSpec:
    kwargs: dict[str, object] = {
        "family": ApproximationFamily.CHEBYSHEV_TYPE_I,
        "response": response,
        "order": 5,
        "z_source_ohm": 50.0,
        "z_load_ohm": 50.0,
        "topology_id": default_topology(response),
        "cutoff_definition": default_cutoff_definition(
            ApproximationFamily.CHEBYSHEV_TYPE_I
        ),
        "passband_ripple_db": 0.1,
    }
    if response in (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP):
        kwargs.update(f_center_hz=100e6, bandwidth_hz=20e6)
    else:
        kwargs["cutoff_hz"] = 100e6
    return FilterSpec(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "response",
    (
        FilterResponse.LOW_PASS,
        FilterResponse.HIGH_PASS,
        FilterResponse.BAND_PASS,
        FilterResponse.BAND_STOP,
    ),
)
def test_export_validation_matrix(response: FilterResponse) -> None:
    circuit = synthesize(_spec(response)).circuit
    report = validate_exports(circuit)
    assert report.ok, report.issues
    assert "ltspice:header" in report.checks
    assert "qucs:header" in report.checks
    assert "spice:netlist" in report.checks


def test_structural_failures_are_reported() -> None:
    circuit = synthesize(_spec(FilterResponse.LOW_PASS)).circuit
    assert not validate_ltspice_asc("not an asc", circuit).ok
    assert not validate_qucs_schematic("not qucs", circuit).ok
    asc = ltspice_asc(circuit).replace("Version 4", "Version 3", 1)
    assert not validate_ltspice_asc(asc, circuit).ok
    sch = qucs_schematic(circuit).replace("<Port P1", "<Broken P1", 1)
    assert not validate_qucs_schematic(sch, circuit).ok
