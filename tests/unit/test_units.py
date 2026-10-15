"""Tests for SI unit parsing."""

from __future__ import annotations

import pytest

from filterdesk.domain.units import parse_si


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("140M", 140e6),
        ("140 MHz", 140e6),
        ("10.7M", 10.7e6),
        ("50", 50.0),
        ("50 Ohm", 50.0),
        ("10n", 10e-9),
        ("10 nH", 10e-9),
        ("4.7pF", 4.7e-12),
        ("33e-9", 33e-9),
        ("1m", 1e-3),  # milli (lowercase m)
    ],
)
def test_parse_si(text: str, expected: float) -> None:
    assert abs(parse_si(text) - expected) / expected < 1e-12
