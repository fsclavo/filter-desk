"""Coaxial stub notch calculator."""

from __future__ import annotations

import json

import pytest

from filterdesk.__main__ import main
from filterdesk.components_std import (
    CoaxStubError,
    CoaxStubKind,
    design_coax_stub,
)


def test_quarter_wave_open_stub_at_2m() -> None:
    design = design_coax_stub(
        50.0, 146e6, 0.66, kind=CoaxStubKind.OPEN_QUARTER
    )
    wavelength = 0.66 * 299_792_458.0 / 146e6
    assert design.length_m == pytest.approx(wavelength / 4.0)
    assert design.electrical_length_deg == 90.0
    assert design.length_m * 1000.0 == pytest.approx(338.8, abs=0.2)


def test_half_wave_shorted_stub_at_70cm() -> None:
    design = design_coax_stub(
        50.0, 435e6, 0.66, kind=CoaxStubKind.SHORT_HALF
    )
    wavelength = 0.66 * 299_792_458.0 / 435e6
    assert design.length_m == pytest.approx(wavelength / 2.0)
    assert design.electrical_length_deg == 180.0
    assert design.length_m * 1000.0 == pytest.approx(227.4, abs=0.2)


def test_loss_estimate() -> None:
    design = design_coax_stub(50.0, 146e6, 0.7, loss_db_per_m=0.2)
    assert design.loss_db == pytest.approx(design.length_m * 0.2)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"z0_ohm": 0.0}, "Z0"),
        ({"frequency_hz": 0.0}, "frequency"),
        ({"velocity_factor": 0.0}, "velocity"),
        ({"velocity_factor": 1.1}, "velocity"),
        ({"loss_db_per_m": -0.1}, "loss"),
    ],
)
def test_validation(kwargs, message: str) -> None:
    base = {
        "z0_ohm": 50.0,
        "frequency_hz": 146e6,
        "velocity_factor": 0.66,
    }
    base.update(kwargs)
    with pytest.raises(CoaxStubError, match=message):
        design_coax_stub(**base, kind=CoaxStubKind.OPEN_QUARTER)  # type: ignore[arg-type]


def test_cli_coax_stub_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "coax-stub",
                "--frequency",
                "146M",
                "--z0",
                "50",
                "--vf",
                "0.66",
                "--kind",
                "open_quarter",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "open_quarter"
    assert payload["electrical_length_deg"] == 90.0
    assert payload["length_m"] == pytest.approx(0.3388, abs=0.0002)


def test_cable_preset_and_loss_interpolation() -> None:
    from filterdesk.components_std import coax_stub_response, find_coax_cable

    cable = find_coax_cable("rg-58")
    design = design_coax_stub(50.0, 146e6, 0.66, cable=cable)
    assert design.cable is cable
    assert design.z0_ohm == pytest.approx(cable.z0_ohm)
    assert design.velocity_factor == pytest.approx(cable.velocity_factor)
    assert design.loss_db_per_m == pytest.approx(cable.loss_db_per_m(146e6))

    response = coax_stub_response(design)
    assert response.notch_depth_db > 20.0
    assert response.bandwidth_3db_hz is not None
    assert response.bandwidth_3db_hz > 0.0
    assert response.loaded_q is not None and response.loaded_q > 0.0


def test_loss_is_frequency_dependent_for_cable() -> None:
    from filterdesk.components_std import find_coax_cable

    cable = find_coax_cable("LMR-400")
    assert cable.loss_db_per_m(100e6) < cable.loss_db_per_m(1e9)
    with pytest.raises(CoaxStubError, match="unknown"):
        find_coax_cable("NO-SUCH-CABLE")


def test_cli_coax_cable_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "coax-stub",
                "--frequency",
                "146M",
                "--cable",
                "RG-58",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["cable"] == "RG-58"
    assert payload["notch_depth_db"] > 20.0
    assert payload["bandwidth_3db_hz"] > 0.0
    assert payload["loaded_q"] > 0.0
