"""Unit tests for approximation g-values."""

from __future__ import annotations

import math

import pytest

from filterdesk.synthesis.families.butterworth import butterworth_g_values
from filterdesk.synthesis.families.chebyshev_i import (
    chebyshev_epsilon,
    chebyshev_type_i_g_values,
)


def test_butterworth_n5_table() -> None:
    g = butterworth_g_values(5)
    expected = [
        1.0,
        0.61803398875,
        1.61803398875,
        2.0,
        1.61803398875,
        0.61803398875,
        1.0,
    ]
    assert len(g) == 7
    for a, b in zip(g, expected, strict=True):
        assert abs(a - b) < 1e-9


@pytest.mark.parametrize(
    ("ap", "n", "expected"),
    [
        (0.1, 3, (1.03156, 1.14740, 1.03156)),
        (0.5, 3, (1.59628, 1.09669, 1.59628)),
        (0.1, 5, (1.14681, 1.37121, 1.97500, 1.37121, 1.14681)),
    ],
)
def test_chebyshev_table_anchors(
    ap: float, n: int, expected: tuple[float, ...]
) -> None:
    g = chebyshev_type_i_g_values(n, ap)
    assert g[0] == 1.0
    assert g[-1] == 1.0  # odd orders
    for got, exp in zip(g[1:-1], expected, strict=True):
        assert abs(got - exp) < 5e-5


def test_chebyshev_epsilon_0p01() -> None:
    eps = chebyshev_epsilon(0.01)
    assert abs(eps - math.sqrt(10 ** 0.001 - 1.0)) < 1e-15
