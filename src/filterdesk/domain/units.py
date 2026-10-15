"""Engineering-unit parsing and formatting (SI internally)."""

from __future__ import annotations

import re

_PREFIX: dict[str, float] = {
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "µ": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "K": 1e3,
    "M": 1e6,
    "G": 1e9,
    "T": 1e12,
}

# ELSIE-like: only M is case-sensitive (mega vs milli).
_SUFFIX_RE = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*"
    r"([fpnuµmkKMGT])?"
    r"(?:Hz|H|F|Ohm|ohm|Ω|s|S)?\s*$"
)


def parse_si(text: str) -> float:
    """Parse engineering values (``140M``, ``4.7pF``, ``33e-9``) to SI float."""
    raw = text.strip()
    if not raw:
        raise ValueError("empty numeric string")
    # Plain float / scientific without prefix letter after number
    try:
        return float(raw)
    except ValueError:
        pass
    match = _SUFFIX_RE.match(raw)
    if not match:
        raise ValueError(f"cannot parse engineering value: {text!r}")
    number = float(match.group(1))
    prefix = match.group(2)
    if prefix is None:
        return number
    if prefix not in _PREFIX:
        raise ValueError(f"unknown SI prefix: {prefix!r} in {text!r}")
    return number * _PREFIX[prefix]


def format_engineering(value: float, unit: str, digits: int = 8) -> str:
    """Format a positive SI value with a common engineering prefix."""
    if value == 0.0:
        return f"0 {unit}"
    sign = "-" if value < 0 else ""
    v = abs(value)
    table = (
        (1e12, "T"),
        (1e9, "G"),
        (1e6, "M"),
        (1e3, "k"),
        (1.0, ""),
        (1e-3, "m"),
        (1e-6, "u"),
        (1e-9, "n"),
        (1e-12, "p"),
        (1e-15, "f"),
    )
    for scale, prefix in table:
        if v >= scale:
            return f"{sign}{v / scale:.{digits}g} {prefix}{unit}".rstrip()
    return f"{sign}{v:.{digits}g} {unit}"
