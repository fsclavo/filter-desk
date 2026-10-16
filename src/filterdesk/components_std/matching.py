"""Reactance matching-network design (L / Pi / T) — Phase 12.

Matches a real source ``Z0`` to a complex load ``R + jX`` at a frequency using an
L (2 elements), Pi or T (3 elements) network. Networks are returned as arms with a
reactance (Ω); each reactance maps to an inductor (X>0) or capacitor (X<0) at the
design frequency. The default solution is the low-pass one.

The complex-load L-match is exact; Pi/T are built as two back-to-back L-sections
sharing a virtual resistance set by the loaded ``Q``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from filterdesk.domain.enums import ElementRole


class MatchingTopology(StrEnum):
    L = "l"
    PI = "pi"
    T = "t"


class MatchingError(ValueError):
    """Raised for an impossible or invalid matching request."""


@dataclass(frozen=True, slots=True)
class MatchingElement:
    role: ElementRole
    reactance_ohm: float
    kind: str  # "L" or "C"
    value: float  # henries or farads


@dataclass(frozen=True, slots=True)
class MatchingDesign:
    topology: MatchingTopology
    frequency_hz: float
    source_ohm: float
    load_r_ohm: float
    load_x_ohm: float
    q: float | None
    elements: tuple[MatchingElement, ...]
    input_impedance_ohm: complex


def _zin(arms: list[tuple[ElementRole, float]], zl: complex) -> complex:
    a, b, c, d = 1 + 0j, 0j, 0j, 1 + 0j
    for role, x in arms:
        if role == ElementRole.SERIES:
            z = 1j * x
            a, b, c, d = a, a * z + b, c, c * z + d
        else:
            y = 1.0 / (1j * x)
            a, b, c, d = a + b * y, b, c + d * y, d
    return (a * zl + b) / (c * zl + d)


def _l_solutions(
    rs: float, rl: float, xl: float
) -> list[list[tuple[ElementRole, float]]]:
    """L-match solutions (shunt placed on the larger-resistance side)."""
    if rs >= rl:
        if rl <= 0.0:
            raise MatchingError("load resistance must be > 0")
        s = math.sqrt(rl * (rs - rl))
        if s == 0.0:
            # rs == rl: cancel the load reactance with a single series element.
            return [[(ElementRole.SERIES, -xl)]] if xl != 0.0 else []
        out: list[list[tuple[ElementRole, float]]] = []
        for sign in (1.0, -1.0):
            xs = -xl + sign * s
            if xs == 0.0:
                continue
            xp = -rl * rs / (xl + xs)
            out.append([(ElementRole.SHUNT, xp), (ElementRole.SERIES, xs)])
        return out
    if rl == 0.0:
        raise MatchingError("load resistance must be > 0")
    denom = rl * rl + xl * xl
    gl = rl / denom
    bl = -xl / denom
    if gl > 1.0 / rs:
        return []
    xs = math.sqrt(rs / gl - rs * rs)
    out = []
    for sign in (1.0, -1.0):
        xsg = sign * xs
        inv_xp = bl - xsg / (rs * rs + xs * xs)
        if inv_xp == 0.0:
            continue
        out.append([(ElementRole.SERIES, xsg), (ElementRole.SHUNT, 1.0 / inv_xp)])
    return out


def _pick_lowpass(
    solutions: list[list[tuple[ElementRole, float]]],
) -> list[tuple[ElementRole, float]]:
    for arms in solutions:
        xs = next((x for r, x in arms if r == ElementRole.SERIES), 0.0)
        xp = next((x for r, x in arms if r == ElementRole.SHUNT), 0.0)
        if xs > 0.0 and xp < 0.0:
            return arms
    if not solutions:
        raise MatchingError("no matching solution for these impedances")
    return solutions[0]


def _series_x(arms: list[tuple[ElementRole, float]]) -> float | None:
    return next((x for r, x in arms if r == ElementRole.SERIES), None)


def _shunt_x(arms: list[tuple[ElementRole, float]]) -> float | None:
    return next((x for r, x in arms if r == ElementRole.SHUNT), None)


def _is_lowpass(arms: list[tuple[ElementRole, float]]) -> bool:
    """Series arms inductive (X>0), shunt arms capacitive (X<0)."""
    for role, x in arms:
        if role == ElementRole.SERIES:
            if x <= 0.0:
                return False
        elif x >= 0.0:
            return False
    return True


def _matches(
    arms: list[tuple[ElementRole, float]], rs: float, rl: float, xl: float
) -> bool:
    z_in = _zin(arms, complex(rl, xl))
    return abs(z_in - rs) <= 1e-6 * rs + 1e-6


def _order_lowpass_first(
    solutions: list[list[tuple[ElementRole, float]]],
) -> list[list[tuple[ElementRole, float]]]:
    ordered = list(solutions)
    for index, arms in enumerate(ordered):
        if _is_lowpass(arms):
            return [arms, *ordered[:index], *ordered[index + 1 :]]
    return ordered


def _select_arms(
    genuine: list[list[tuple[ElementRole, float]]],
    degenerate: list[list[tuple[ElementRole, float]]],
    rs: float,
    rl: float,
    xl: float,
    label: str,
) -> list[tuple[ElementRole, float]]:
    """Pick a candidate that actually matches the source (prefer low-pass).

    ``genuine`` are 3-element networks; ``degenerate`` are the cancellations
    where the middle element collapses (kept as a fallback).
    """
    matching = [arms for arms in genuine if _matches(arms, rs, rl, xl)]
    for arms in matching:
        if _is_lowpass(arms):
            return arms
    if matching:
        return matching[0]
    for arms in degenerate:
        if _matches(arms, rs, rl, xl):
            return arms
    raise MatchingError(f"no {label} matching solution for these impedances")


def _pi_arms(
    rs: float, rl: float, xl: float, rv: float
) -> list[tuple[ElementRole, float]]:
    genuine: list[list[tuple[ElementRole, float]]] = []
    degenerate: list[list[tuple[ElementRole, float]]] = []
    for a in _order_lowpass_first(_l_solutions(rs, rv, 0.0)):
        xp1 = _shunt_x(a)
        xs1 = _series_x(a)
        if xp1 is None or xs1 is None:
            continue
        for b in _order_lowpass_first(_l_solutions(rv, rl, xl)):
            xs2 = _series_x(b)
            xp2 = _shunt_x(b)
            if xs2 is None or xp2 is None:
                continue
            xs = xs1 + xs2
            if xs == 0.0:
                degenerate.append(
                    [(ElementRole.SHUNT, xp1), (ElementRole.SHUNT, xp2)]
                )
            else:
                genuine.append(
                    [
                        (ElementRole.SHUNT, xp1),
                        (ElementRole.SERIES, xs),
                        (ElementRole.SHUNT, xp2),
                    ]
                )
    return _select_arms(genuine, degenerate, rs, rl, xl, "Pi")


def _tee_arms(
    rs: float, rl: float, xl: float, rv: float
) -> list[tuple[ElementRole, float]]:
    genuine: list[list[tuple[ElementRole, float]]] = []
    degenerate: list[list[tuple[ElementRole, float]]] = []
    for a in _order_lowpass_first(_l_solutions(rs, rv, 0.0)):
        xs1 = _series_x(a)
        xp1 = _shunt_x(a)
        if xs1 is None or xp1 is None:
            continue
        for b in _order_lowpass_first(_l_solutions(rv, rl, xl)):
            xp2 = _shunt_x(b)
            xs2 = _series_x(b)
            if xp2 is None or xs2 is None:
                continue
            inv = 1.0 / xp1 + 1.0 / xp2
            if inv == 0.0:
                degenerate.append(
                    [(ElementRole.SERIES, xs1), (ElementRole.SERIES, xs2)]
                )
            else:
                genuine.append(
                    [
                        (ElementRole.SERIES, xs1),
                        (ElementRole.SHUNT, 1.0 / inv),
                        (ElementRole.SERIES, xs2),
                    ]
                )
    return _select_arms(genuine, degenerate, rs, rl, xl, "T")


def _q_min(rs: float, rl: float) -> float:
    lo, hi = min(rs, rl), max(rs, rl)
    if lo <= 0.0:
        raise MatchingError("impedances must be > 0")
    return math.sqrt(hi / lo - 1.0)


def _arms_for(
    rs: float, rl: float, xl: float, topology: MatchingTopology, q: float | None
) -> tuple[list[tuple[ElementRole, float]], float | None]:
    if topology == MatchingTopology.L:
        return _pick_lowpass(_l_solutions(rs, rl, xl)), None

    qmin = _q_min(rs, rl)
    if q is None:
        q = qmin + 0.5
    if q <= qmin:
        raise MatchingError(f"Q must be > {qmin:.3f} for this impedance ratio")

    if topology == MatchingTopology.PI:
        rv = max(rs, rl) / (1.0 + q * q)  # virtual series resistance
        return _pi_arms(rs, rl, xl, rv), q

    # TEE: virtual parallel resistance (middle shunt).
    rv = min(rs, rl) * (1.0 + q * q)
    return _tee_arms(rs, rl, xl, rv), q


def _to_elements(
    arms: list[tuple[ElementRole, float]], frequency_hz: float
) -> tuple[MatchingElement, ...]:
    omega = 2.0 * math.pi * frequency_hz
    elements: list[MatchingElement] = []
    for role, x in arms:
        if x == 0.0:
            continue  # collapsed element (short): nothing to place
        if x > 0.0:
            elements.append(MatchingElement(role, x, "L", x / omega))
        else:
            elements.append(MatchingElement(role, x, "C", -1.0 / (omega * x)))
    return tuple(elements)


def design_matching(
    source_ohm: float,
    load_r_ohm: float,
    load_x_ohm: float,
    frequency_hz: float,
    topology: MatchingTopology | str = MatchingTopology.L,
    q: float | None = None,
) -> MatchingDesign:
    """Design an L/Pi/T matching network (low-pass solution)."""
    if source_ohm <= 0.0:
        raise MatchingError("source_ohm must be > 0")
    if load_r_ohm <= 0.0:
        raise MatchingError("load_r_ohm must be > 0")
    if frequency_hz <= 0.0:
        raise MatchingError("frequency_hz must be > 0")
    topo = MatchingTopology(topology)
    if abs(source_ohm - load_r_ohm) < 1e-12 and abs(load_x_ohm) < 1e-12:
        raise MatchingError("load already matches the source")
    arms, used_q = _arms_for(source_ohm, load_r_ohm, load_x_ohm, topo, q)
    z_in = _zin(arms, complex(load_r_ohm, load_x_ohm))
    return MatchingDesign(
        topology=topo,
        frequency_hz=frequency_hz,
        source_ohm=source_ohm,
        load_r_ohm=load_r_ohm,
        load_x_ohm=load_x_ohm,
        q=used_q,
        elements=_to_elements(arms, frequency_hz),
        input_impedance_ohm=z_in,
    )


__all__ = [
    "MatchingDesign",
    "MatchingElement",
    "MatchingError",
    "MatchingTopology",
    "design_matching",
]
