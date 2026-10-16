"""Default file-name mask from a filter specification."""

from __future__ import annotations

from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.naming import default_filename, default_stem
from filterdesk.domain.specs import FilterSpec


def _lp(**over: object) -> FilterSpec:
    base: dict[str, object] = {
        "family": ApproximationFamily.CHEBYSHEV_TYPE_I,
        "response": FilterResponse.LOW_PASS,
        "order": 7,
        "cutoff_hz": 140e6,
        "cutoff_definition": CutoffDefinition.RIPPLE_EDGE,
        "passband_ripple_db": 0.01,
        "z_source_ohm": 50.0,
        "z_load_ohm": 50.0,
        "topology_id": TopologyId.LADDER_LP_SERIES_L_INPUT,
    }
    base.update(over)
    return FilterSpec(**base)  # type: ignore[arg-type]


def test_lowpass_name() -> None:
    assert default_stem(_lp()) == "cheby1_LPF_n7_140MHz"
    assert (
        default_filename(_lp()) == "cheby1_LPF_n7_140MHz.filterdesk.json"
    )


def test_highpass_butterworth_name() -> None:
    spec = _lp(
        family=ApproximationFamily.BUTTERWORTH,
        response=FilterResponse.HIGH_PASS,
        order=5,
        cutoff_hz=7e6,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
        passband_ripple_db=None,
        topology_id=TopologyId.LADDER_HP_SERIES_C_INPUT,
    )
    assert default_stem(spec) == "butterworth_HPF_n5_7MHz"


def test_bandpass_includes_bandwidth() -> None:
    spec = FilterSpec(
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
    assert default_stem(spec) == "cheby1_BPF_n4_100MHz_bw20MHz"


def test_custom_suffix() -> None:
    assert default_filename(_lp(), suffix=".csv") == "cheby1_LPF_n7_140MHz.csv"
