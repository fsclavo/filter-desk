"""Smith-chart geometry unit tests."""

from __future__ import annotations

import numpy as np

from filterdesk.analysis.smith import (
    gamma_circle,
    gamma_to_z,
    nearest_gamma_index,
    reactance_arc,
    resistance_circle,
    smith_grid_polylines,
    unit_circle,
    z_to_gamma,
)


def test_gamma_z_roundtrip() -> None:
    z = 1.5 + 0.8j
    g = z_to_gamma(z)
    z2 = gamma_to_z(g)
    assert abs(complex(z2) - z) < 1e-12


def test_matched_load_at_origin() -> None:
    assert abs(complex(z_to_gamma(1.0))) < 1e-15


def test_short_and_open() -> None:
    assert abs(complex(z_to_gamma(0.0)) + 1.0) < 1e-12
    g_open = complex(z_to_gamma(1e12))
    assert abs(g_open - 1.0) < 1e-6


def test_resistance_circle_r1_through_origin() -> None:
    # r=1 → center 0.5, radius 0.5 → passes through Γ=0
    re, im = resistance_circle(1.0, n=2048)
    d2 = re**2 + im**2
    assert float(np.min(d2)) < 1e-4


def test_unit_circle_radius() -> None:
    re, im = unit_circle()
    assert np.allclose(np.hypot(re, im), 1.0)


def test_gamma_circle_radius() -> None:
    re, im = gamma_circle(0.3, n=128)
    assert np.allclose(np.hypot(re, im), 0.3)


def test_reactance_arc_inside_unit_disk() -> None:
    re, im = reactance_arc(1.0, n=128)
    assert np.all(np.hypot(re, im) <= 1.0 + 1e-9)


def test_smith_grid_nonempty() -> None:
    lines = smith_grid_polylines()
    assert len(lines) >= 10
    for re, im in lines:
        assert re.size == im.size
        assert re.size > 0


def test_nearest_gamma_prefers_closer_trace() -> None:
    s11 = np.array([0.0 + 0.0j, 0.5 + 0.0j], dtype=np.complex128)
    s22 = np.array([0.0 + 0.8j, -0.5 + 0.0j], dtype=np.complex128)
    # Near S22[0]
    assert nearest_gamma_index(0.0 + 0.75j, s11, s22) == 0
    # Near S11[1]
    assert nearest_gamma_index(0.45 + 0.0j, s11, s22) == 1
