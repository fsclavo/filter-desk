"""Boundary / validation coverage for specs, sweeps and order caps."""

from __future__ import annotations

import pytest

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.specs import (
    SpecValidationError,
    filter_spec_from_mapping,
)

_BASE = {
    "family": "chebyshev_type_i",
    "response": "low_pass",
    "order": 5,
    "cutoff_hz": 100e6,
    "cutoff_definition": "ripple_edge",
    "passband_ripple_db": 0.1,
    "z_source_ohm": 50.0,
    "z_load_ohm": 50.0,
    "topology_id": "ladder_lp_series_l_input",
}


@pytest.mark.parametrize(
    "overrides",
    [
        {"f_start_hz": 0.0, "f_stop_hz": 1e9},
        {"f_start_hz": 1e9, "f_stop_hz": 1e6},
        {"f_start_hz": 1e6, "f_stop_hz": 1e6},
        {"f_start_hz": 1e6, "f_stop_hz": 1e9, "n_points": 1},
    ],
)
def test_sweep_config_rejects_invalid(overrides: dict[str, float]) -> None:
    kwargs: dict[str, object] = {
        "f_start_hz": 1e6,
        "f_stop_hz": 1e9,
        "n_points": 16,
        "spacing": SweepSpacing.LINEAR,
    }
    kwargs.update(overrides)
    with pytest.raises(ValueError):
        SweepConfig(**kwargs)  # type: ignore[arg-type]


def test_sweep_accepts_boundary_n_points() -> None:
    sweep = SweepConfig(1e6, 1e9, 2, SweepSpacing.LOGARITHMIC)
    assert sweep.frequencies_hz().shape[0] == 2


def test_order_zero_rejected() -> None:
    with pytest.raises(SpecValidationError):
        filter_spec_from_mapping({**_BASE, "order": 0})


@pytest.mark.parametrize("order", [11, 20])
def test_bessel_gaussian_order_caps(order: int) -> None:
    for family, definition in (
        ("bessel", "half_power_3db"),
        ("gaussian", "half_power_3db"),
    ):
        with pytest.raises(SpecValidationError):
            filter_spec_from_mapping(
                {
                    "family": family,
                    "response": "low_pass",
                    "order": order,
                    "cutoff_hz": 100e6,
                    "cutoff_definition": definition,
                    "z_source_ohm": 50.0,
                    "z_load_ohm": 50.0,
                    "topology_id": "ladder_lp_series_l_input",
                }
            )


def test_legendre_order_bounds() -> None:
    for order in (1, 10):
        with pytest.raises(SpecValidationError):
            filter_spec_from_mapping(
                {
                    "family": "legendre",
                    "response": "low_pass",
                    "order": order,
                    "cutoff_hz": 100e6,
                    "cutoff_definition": "half_power_3db",
                    "z_source_ohm": 50.0,
                    "z_load_ohm": 50.0,
                    "topology_id": "ladder_lp_series_l_input",
                }
            )


def test_chebyshev_i_requires_ripple_and_edge() -> None:
    with pytest.raises(SpecValidationError):
        filter_spec_from_mapping({**_BASE, "passband_ripple_db": None})
    with pytest.raises(SpecValidationError):
        filter_spec_from_mapping({**_BASE, "cutoff_definition": "half_power_3db"})


def test_band_response_requires_center_and_bandwidth() -> None:
    with pytest.raises(SpecValidationError):
        filter_spec_from_mapping(
            {
                "family": "chebyshev_type_i",
                "response": "band_pass",
                "order": 4,
                "cutoff_definition": "ripple_edge",
                "passband_ripple_db": 0.1,
                "z_source_ohm": 50.0,
                "z_load_ohm": 50.0,
                "topology_id": "ladder_bp_series_resonator_input",
            }
        )
