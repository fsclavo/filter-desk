"""Power-stress estimate (peak voltage/current per element) — Phase 12.

Ham-oriented rule-of-thumb for transmit filters: with forward power ``P`` into a
matched real ``Z0`` system, the through-line RMS current/voltage are
``I0 = sqrt(P/Z0)`` and ``V0 = sqrt(P*Z0)``. Each element's arm impedance at the
reference frequency then gives the peak stress:

- series arm: ``Vpk = sqrt(2)*I0*|Z|``, ``Ipk = sqrt(2)*I0``
- shunt arm:  ``Vpk = sqrt(2)*V0``,     ``Ipk = sqrt(2)*V0/|Z|``

This is an estimate (assumes a near-matched, low-loss filter), suitable for
choosing voltage/current ratings.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from filterdesk.analysis.adapters.abcd_ladder import element_impedance_ohm
from filterdesk.domain.circuit import (
    Circuit,
    MicrostripLineElement,
    MicrostripStubElement,
)
from filterdesk.domain.enums import ElementRole


class StressError(ValueError):
    """Raised when a stress estimate cannot be computed."""


@dataclass(frozen=True, slots=True)
class ElementStress:
    ref: str
    role: ElementRole
    impedance_ohm: complex
    v_peak_v: float
    i_peak_a: float


@dataclass(frozen=True, slots=True)
class StressReport:
    power_w: float
    z0_ohm: float
    frequency_hz: float
    entries: tuple[ElementStress, ...]

    @property
    def max_v_peak_v(self) -> float:
        return max((e.v_peak_v for e in self.entries), default=0.0)

    @property
    def max_i_peak_a(self) -> float:
        return max((e.i_peak_a for e in self.entries), default=0.0)

    @property
    def worst_voltage_ref(self) -> str | None:
        if not self.entries:
            return None
        return max(self.entries, key=lambda e: e.v_peak_v).ref

    @property
    def worst_current_ref(self) -> str | None:
        if not self.entries:
            return None
        return max(self.entries, key=lambda e: e.i_peak_a).ref


def compute_stress(
    circuit: Circuit,
    *,
    power_w: float,
    frequency_hz: float,
    z0_ohm: float | None = None,
) -> StressReport:
    """Estimate per-element peak voltage/current at ``frequency_hz``."""
    if power_w <= 0.0:
        raise StressError("power_w must be > 0")
    if frequency_hz <= 0.0:
        raise StressError("frequency_hz must be > 0")
    if not circuit.elements:
        raise StressError("circuit has no elements")
    if z0_ohm is None:
        zs = circuit.port_in.impedance_ohm
        zl = circuit.port_out.impedance_ohm
        z0_ohm = math.sqrt(zs * zl) if zs > 0.0 and zl > 0.0 else 50.0

    i0 = math.sqrt(power_w / z0_ohm)
    v0 = math.sqrt(power_w * z0_ohm)
    root2 = math.sqrt(2.0)

    entries: list[ElementStress] = []
    for el in circuit.elements:
        if isinstance(el, (MicrostripLineElement, MicrostripStubElement)):
            continue
        z = element_impedance_ohm(el, frequency_hz)
        magnitude = abs(z)
        if el.role == ElementRole.SERIES:
            i_peak = root2 * i0
            v_peak = root2 * i0 * magnitude
        else:
            v_peak = root2 * v0
            i_peak = root2 * v0 / magnitude if magnitude > 0.0 else math.inf
        entries.append(ElementStress(el.id, el.role, z, v_peak, i_peak))

    return StressReport(
        power_w=power_w,
        z0_ohm=z0_ohm,
        frequency_hz=frequency_hz,
        entries=tuple(entries),
    )


__all__ = ["ElementStress", "StressError", "StressReport", "compute_stress"]
