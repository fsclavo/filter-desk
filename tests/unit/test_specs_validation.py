"""Specification validation and mapping branch tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from filterdesk.domain.enums import (
    ApproximationFamily as Fam,
)
from filterdesk.domain.enums import (
    CutoffDefinition as Cut,
)
from filterdesk.domain.enums import (
    FilterResponse as Resp,
)
from filterdesk.domain.enums import (
    TopologyId as Topo,
)
from filterdesk.domain.specs import (
    FilterSpec,
    SpecValidationError,
    default_cutoff_definition,
    default_topology,
    filter_spec_from_mapping,
    filter_spec_to_mapping,
    geometric_mean_z0,
    validate_spec,
)

BASE = FilterSpec(
    family=Fam.BUTTERWORTH,
    response=Resp.LOW_PASS,
    order=3,
    cutoff_hz=1e6,
    z_source_ohm=50.0,
    z_load_ohm=50.0,
    topology_id=Topo.LADDER_LP_SERIES_L_INPUT,
    cutoff_definition=Cut.HALF_POWER_3DB,
)


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"order": 0}, "order must be"),
        ({"z_source_ohm": 0.0}, "impedances must be"),
        ({"z_load_ohm": -1.0}, "impedances must be"),
        ({"cutoff_hz": 0.0}, "cutoff_hz must be"),
        ({"f_center_hz": 1e6}, "apply only to BP/BS"),
        (
            {"response": Resp.BAND_PASS, "f_center_hz": None, "bandwidth_hz": 1e6},
            "f_center_hz must be",
        ),
        (
            {"response": Resp.BAND_PASS, "f_center_hz": 1e6, "bandwidth_hz": None},
            "bandwidth_hz must be",
        ),
        (
            {
                "family": Fam.CHEBYSHEV_TYPE_I,
                "passband_ripple_db": None,
                "cutoff_definition": Cut.RIPPLE_EDGE,
            },
            "passband_ripple_db",
        ),
        (
            {
                "family": Fam.CHEBYSHEV_TYPE_I,
                "passband_ripple_db": 0.1,
                "cutoff_definition": Cut.HALF_POWER_3DB,
            },
            "cutoff_definition=ripple_edge",
        ),
        (
            {
                "family": Fam.CHEBYSHEV_TYPE_I,
                "passband_ripple_db": 0.1,
                "cutoff_definition": Cut.RIPPLE_EDGE,
                "stopband_attenuation_db": 40.0,
            },
            "must not set stopband",
        ),
        (
            {
                "family": Fam.CHEBYSHEV_TYPE_II,
                "stopband_attenuation_db": None,
                "cutoff_definition": Cut.STOPBAND_EDGE,
            },
            "stopband_attenuation_db",
        ),
        (
            {
                "family": Fam.CHEBYSHEV_TYPE_II,
                "stopband_attenuation_db": 40.0,
                "cutoff_definition": Cut.HALF_POWER_3DB,
            },
            "cutoff_definition=stopband_edge",
        ),
        (
            {
                "family": Fam.CHEBYSHEV_TYPE_II,
                "stopband_attenuation_db": 40.0,
                "cutoff_definition": Cut.STOPBAND_EDGE,
                "passband_ripple_db": 0.1,
            },
            "must not set passband",
        ),
        (
            {
                "family": Fam.ELLIPTIC,
                "passband_ripple_db": None,
                "stopband_attenuation_db": 40.0,
                "cutoff_definition": Cut.RIPPLE_EDGE,
                "order": 3,
            },
            "requires passband_ripple_db",
        ),
        (
            {
                "family": Fam.ELLIPTIC,
                "passband_ripple_db": 0.5,
                "stopband_attenuation_db": None,
                "cutoff_definition": Cut.RIPPLE_EDGE,
                "order": 3,
            },
            "requires stopband_attenuation_db",
        ),
        (
            {
                "family": Fam.ELLIPTIC,
                "passband_ripple_db": 0.5,
                "stopband_attenuation_db": 0.5,
                "cutoff_definition": Cut.RIPPLE_EDGE,
                "order": 3,
            },
            "stopband_attenuation_db > passband",
        ),
        (
            {
                "family": Fam.ELLIPTIC,
                "passband_ripple_db": 0.5,
                "stopband_attenuation_db": 40.0,
                "cutoff_definition": Cut.RIPPLE_EDGE,
                "order": 4,
            },
            "odd orders",
        ),
        (
            {
                "family": Fam.ELLIPTIC,
                "passband_ripple_db": 0.5,
                "stopband_attenuation_db": 40.0,
                "cutoff_definition": Cut.RIPPLE_EDGE,
                "order": 1,
            },
            "order >= 2",
        ),
        (
            {
                "family": Fam.ELLIPTIC,
                "passband_ripple_db": 0.5,
                "stopband_attenuation_db": 40.0,
                "cutoff_definition": Cut.HALF_POWER_3DB,
                "order": 3,
            },
            "cutoff_definition=ripple_edge",
        ),
        ({"cutoff_definition": Cut.RIPPLE_EDGE}, "requires cutoff_definition"),
        ({"passband_ripple_db": 0.1}, "must not set passband"),
        ({"stopband_attenuation_db": 40.0}, "must not set stopband"),
        (
            {
                "family": Fam.LEGENDRE,
                "order": 1,
                "cutoff_definition": Cut.HALF_POWER_3DB,
            },
            "legendre requires order >= 2",
        ),
        (
            {
                "family": Fam.LEGENDRE,
                "order": 10,
                "cutoff_definition": Cut.HALF_POWER_3DB,
            },
            "legendre supports order 2..9",
        ),
        (
            {
                "family": Fam.BESSEL,
                "order": 11,
                "cutoff_definition": Cut.HALF_POWER_3DB,
            },
            "bessel supports order 1..10",
        ),
        (
            {
                "family": Fam.GAUSSIAN,
                "order": 11,
                "cutoff_definition": Cut.HALF_POWER_3DB,
            },
            "gaussian supports order 1..10",
        ),
        (
            {"family": Fam.CONSTANT_K, "cutoff_definition": Cut.RIPPLE_EDGE},
            "constant_k requires",
        ),
        (
            {"family": Fam.CONSTANT_K, "passband_ripple_db": 0.1},
            "constant_k must not set ripple",
        ),
        (
            {"family": Fam.CONSTANT_K, "m_parameter": 0.6},
            "constant_k must not set m_parameter",
        ),
        (
            {"family": Fam.M_DERIVED, "cutoff_definition": Cut.RIPPLE_EDGE},
            "m_derived requires",
        ),
        ({"family": Fam.M_DERIVED}, "0 < m_parameter < 1"),
        ({"family": Fam.M_DERIVED, "m_parameter": 0.0}, "0 < m_parameter < 1"),
        ({"family": Fam.M_DERIVED, "m_parameter": 1.0}, "0 < m_parameter < 1"),
        (
            {"family": Fam.M_DERIVED, "m_parameter": 0.6, "passband_ripple_db": 0.1},
            "m_derived must not set ripple",
        ),
        (
            {"topology_id": Topo.LADDER_HP_SERIES_C_INPUT},
            "is not valid for low_pass",
        ),
    ],
)
def test_validate_spec_rejects_invalid(changes: dict[str, object], match: str) -> None:
    with pytest.raises(SpecValidationError, match=match):
        validate_spec(replace(BASE, **changes))  # type: ignore[arg-type]


def test_default_topology_and_cutoff() -> None:
    assert default_topology(Resp.LOW_PASS) == Topo.LADDER_LP_SERIES_L_INPUT
    assert default_topology(Resp.HIGH_PASS) == Topo.LADDER_HP_SERIES_C_INPUT
    assert default_topology(Resp.BAND_PASS) == Topo.LADDER_BP_SERIES_RES_INPUT
    assert default_topology(Resp.BAND_STOP) == Topo.LADDER_BS_SERIES_TANK_INPUT
    assert default_cutoff_definition(Fam.BUTTERWORTH) == Cut.HALF_POWER_3DB
    assert default_cutoff_definition(Fam.CHEBYSHEV_TYPE_I) == Cut.RIPPLE_EDGE
    assert default_cutoff_definition(Fam.CHEBYSHEV_TYPE_II) == Cut.STOPBAND_EDGE
    assert default_cutoff_definition(Fam.ELLIPTIC) == Cut.RIPPLE_EDGE
    assert default_cutoff_definition(Fam.CONSTANT_K) == Cut.HALF_POWER_3DB
    assert default_cutoff_definition(Fam.M_DERIVED) == Cut.HALF_POWER_3DB


def test_spec_mapping_roundtrip_and_defaults() -> None:
    mapping = filter_spec_to_mapping(BASE)
    assert mapping["family"] == "butterworth"
    assert "cutoff_hz" in mapping
    assert filter_spec_from_mapping(mapping) == BASE

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
    bp_mapping = filter_spec_to_mapping(bp)
    assert bp_mapping["f_center_hz"] == 100e6
    assert bp_mapping["bandwidth_hz"] == 20e6
    assert bp_mapping["passband_ripple_db"] == 0.1
    assert filter_spec_from_mapping(bp_mapping) == bp

    # Defaults: topology and cutoff definition omitted.
    minimal = {
        "family": "butterworth",
        "response": "high_pass",
        "order": 3,
        "cutoff_hz": 7e6,
        "z_source_ohm": 50.0,
        "z_load_ohm": 50.0,
    }
    spec = filter_spec_from_mapping(minimal)
    assert spec.topology_id == Topo.LADDER_HP_SERIES_C_INPUT
    assert spec.cutoff_definition == Cut.HALF_POWER_3DB


def test_spec_mapping_rejects_bad_topology() -> None:
    bad = filter_spec_to_mapping(BASE)
    bad["topology_id"] = Topo.LADDER_HP_SERIES_C_INPUT.value
    with pytest.raises(SpecValidationError, match="not valid"):
        filter_spec_from_mapping(bad)


def test_geometric_mean_z0() -> None:
    assert geometric_mean_z0(50.0, 50.0) == pytest.approx(50.0)
    assert geometric_mean_z0(50.0, 75.0) == pytest.approx((50.0 * 75.0) ** 0.5)
