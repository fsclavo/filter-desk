"""Cross-backend validation matrix for the main synthesis topologies."""

from __future__ import annotations

import numpy as np
import pytest

from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import ApproximationFamily, FilterResponse
from filterdesk.domain.specs import (
    FilterSpec,
    default_cutoff_definition,
    default_topology,
)
from filterdesk.synthesis import synthesize

FC = 100e6


def _spec(
    family: ApproximationFamily,
    response: FilterResponse,
    order: int,
    *,
    z_source: float = 50.0,
    z_load: float = 50.0,
) -> FilterSpec:
    kwargs: dict[str, object] = {
        "family": family,
        "response": response,
        "order": order,
        "z_source_ohm": z_source,
        "z_load_ohm": z_load,
        "topology_id": default_topology(response),
        "cutoff_definition": default_cutoff_definition(family),
    }
    if response in (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP):
        kwargs.update(f_center_hz=FC, bandwidth_hz=20e6)
    else:
        kwargs["cutoff_hz"] = FC
    if family in (
        ApproximationFamily.CHEBYSHEV_TYPE_I,
        ApproximationFamily.ELLIPTIC,
    ):
        kwargs["passband_ripple_db"] = 0.1
    if family in (
        ApproximationFamily.CHEBYSHEV_TYPE_II,
        ApproximationFamily.ELLIPTIC,
    ):
        kwargs["stopband_attenuation_db"] = 40.0
    return FilterSpec(**kwargs)  # type: ignore[arg-type]


CASES = (
    (
        "butter_lp_asymmetric",
        ApproximationFamily.BUTTERWORTH,
        FilterResponse.LOW_PASS,
        3,
        50.0,
        75.0,
    ),
    (
        "butter_hp",
        ApproximationFamily.BUTTERWORTH,
        FilterResponse.HIGH_PASS,
        4,
        50.0,
        50.0,
    ),
    (
        "cheby1_lp_even",
        ApproximationFamily.CHEBYSHEV_TYPE_I,
        FilterResponse.LOW_PASS,
        4,
        50.0,
        50.0,
    ),
    (
        "cheby1_bp",
        ApproximationFamily.CHEBYSHEV_TYPE_I,
        FilterResponse.BAND_PASS,
        4,
        50.0,
        50.0,
    ),
    (
        "cheby1_bs",
        ApproximationFamily.CHEBYSHEV_TYPE_I,
        FilterResponse.BAND_STOP,
        4,
        50.0,
        50.0,
    ),
    (
        "cheby2_lp",
        ApproximationFamily.CHEBYSHEV_TYPE_II,
        FilterResponse.LOW_PASS,
        5,
        50.0,
        50.0,
    ),
    (
        "elliptic_lp",
        ApproximationFamily.ELLIPTIC,
        FilterResponse.LOW_PASS,
        5,
        50.0,
        50.0,
    ),
    (
        "bessel_lp",
        ApproximationFamily.BESSEL,
        FilterResponse.LOW_PASS,
        5,
        50.0,
        50.0,
    ),
    (
        "gaussian_lp",
        ApproximationFamily.GAUSSIAN,
        FilterResponse.LOW_PASS,
        5,
        50.0,
        50.0,
    ),
    (
        "legendre_lp",
        ApproximationFamily.LEGENDRE,
        FilterResponse.LOW_PASS,
        5,
        50.0,
        50.0,
    ),
)



@pytest.mark.parametrize(
    ("name", "family", "response", "order", "zs", "zl"), CASES
)
def test_abcd_skrf_and_passivity(
    name: str,
    family: ApproximationFamily,
    response: FilterResponse,
    order: int,
    zs: float,
    zl: float,
) -> None:
    del name
    spec = _spec(family, response, order, z_source=zs, z_load=zl)
    circuit = synthesize(spec).circuit
    sweep = SweepConfig(1e6, 1e9, 161, SweepSpacing.LOGARITHMIC)
    abcd = analyze_circuit(circuit, sweep, backend="abcd")
    skrf = analyze_circuit(circuit, sweep, backend="skrf")

    assert circuit.elements
    assert abcd.frequency_hz.shape == skrf.frequency_hz.shape == (161,)
    assert np.all(np.isfinite(abcd.s11))
    assert np.all(np.isfinite(abcd.s21))
    assert np.allclose(abcd.s11, skrf.s11, rtol=1e-8, atol=1e-8)
    assert np.allclose(abcd.s21, skrf.s21, rtol=1e-8, atol=1e-8)

    power = np.abs(abcd.s11) ** 2 + np.abs(abcd.s21) ** 2
    assert np.all(power <= 1.0 + 1e-6)
    if zs != zl:
        assert circuit.output_transformer_ratio != 1.0
