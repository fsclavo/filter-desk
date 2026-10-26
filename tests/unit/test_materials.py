"""Ferrite material/loss/thermal data."""

from __future__ import annotations

import pytest

from filterdesk.components_std.materials import (
    MATERIALS,
    bsat_at_temperature,
    core_loss_density_w_cm3,
    material_for,
    thermal_resistance_c_w,
)
from filterdesk.components_std.toroid import find_core


def test_material_catalog() -> None:
    assert {"31", "43", "52", "61"} <= set(MATERIALS)
    assert MATERIALS["43"].mu_i == 800.0
    assert MATERIALS["61"].curie_c > 250.0
    assert material_for("43") is MATERIALS["43"]
    assert material_for("unknown") is None
    for material in MATERIALS.values():
        assert material.loss_points
        assert material.loss_points[0][0] < material.loss_points[-1][0]


def test_complex_permeability_interpolation_and_loss() -> None:
    material = MATERIALS["43"]
    low = material.mu_at(1e6)
    high = material.mu_at(30e6)
    assert low[1] > 0.0 and high[1] > 0.0
    assert core_loss_density_w_cm3(material, 7e6, 0.01) > 0.0
    assert core_loss_density_w_cm3(material, 7e6, 0.0) == 0.0
    # 31 is the lossier low-HF mix at 3.5 MHz for the same flux.
    assert core_loss_density_w_cm3(
        MATERIALS["31"], 3.5e6, 0.01
    ) > core_loss_density_w_cm3(MATERIALS["43"], 3.5e6, 0.01)


def test_temperature_derating_and_thermal_resistance() -> None:
    material = MATERIALS["43"]
    cold = bsat_at_temperature(material, 25.0)
    hot = bsat_at_temperature(material, 100.0)
    assert cold == pytest.approx(material.bsat_t)
    assert 0.0 < hot < cold
    core = find_core("FT140-43")
    assert core.volume_cm3 > 0.0
    rth = thermal_resistance_c_w(core.od_mm, core.id_mm, core.height_mm)
    assert 5.0 < rth < 100.0


def test_new_power_cores_are_present() -> None:
    assert find_core("FT114-31").material == "31"
    assert find_core("FT140-31").material == "31"
    assert find_core("FT114-52").material == "52"
    assert find_core("FT350-61").material == "61"
    assert find_core("FT140-31").volume_cm3 > find_core("FT114-31").volume_cm3
