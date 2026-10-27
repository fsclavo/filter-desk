"""Nodal power-stress analysis at one reference frequency.

The circuit is solved as a linear two-port network with a Thevenin source
(``port_in`` impedance and the requested available power) and the actual
``port_out`` load, including the boundary T1/BAL1.  Element voltages and
currents come from the nodal solution, so resonances and mismatch are
represented instead of assuming one common line current.

For a matched real ``Z0`` system at power ``P`` the familiar values are still
``I0 = sqrt(P/Z0)`` and ``V0 = sqrt(P*Z0)``; their peaks are ``sqrt(2)`` times
those RMS values.  The reported power is the source available power.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.adapters.abcd_ladder import (
    _element_abcd,
    balun_abcd,
    element_impedance_ohm,
)
from filterdesk.domain.circuit import (
    Circuit,
    MicrostripLineElement,
    MicrostripStubElement,
)
from filterdesk.domain.enums import ElementRole

_OPEN_ABS = 1e15
_SHORT_ABS = 1e-9
_SHORT_ADMITTANCE = 1e12


class StressError(ValueError):
    """Raised when a stress analysis cannot be computed."""


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


def _load_impedance(circuit: Circuit, frequency_hz: float) -> complex:
    """Load seen by the ladder, including ideal T1 or a boundary BAL1."""
    zl = complex(circuit.port_out.impedance_ohm)
    if circuit.output_balun is not None:
        a, b, c, d = balun_abcd(
            circuit.output_balun, np.array([frequency_hz], dtype=float)
        )[0]
        denominator = c * zl + d
        if abs(denominator) < 1e-15:
            raise StressError("boundary balun has a singular load transformation")
        return complex((a * zl + b) / denominator)
    ratio = circuit.output_transformer_ratio
    return zl * ratio * ratio


def _stamp_two_port(
    matrix: NDArray[np.complex128],
    index: dict[str, int],
    ground: str,
    node_a: str,
    node_b: str,
    y11: complex,
    y12: complex,
    y21: complex,
    y22: complex,
) -> None:
    ia = None if node_a == ground else index[node_a]
    ib = None if node_b == ground else index[node_b]
    if ia is not None:
        matrix[ia, ia] += y11
    if ib is not None:
        matrix[ib, ib] += y22
    if ia is not None and ib is not None:
        matrix[ia, ib] += y12
        matrix[ib, ia] += y21


def _stamp_admittance(
    matrix: NDArray[np.complex128],
    index: dict[str, int],
    ground: str,
    node_a: str,
    node_b: str,
    admittance: complex,
) -> None:
    _stamp_two_port(
        matrix,
        index,
        ground,
        node_a,
        node_b,
        admittance,
        -admittance,
        -admittance,
        admittance,
    )


def _node_voltage(
    voltages: NDArray[np.complex128],
    index: dict[str, int],
    ground: str,
    node: str,
) -> complex:
    return 0.0j if node == ground else complex(voltages[index[node]])


def _safe_admittance(z: complex) -> tuple[complex, bool]:
    """Return ``(Y, open)`` for a two-terminal impedance."""
    magnitude = abs(z)
    if magnitude > _OPEN_ABS:
        return 0.0j, True
    if magnitude < _SHORT_ABS:
        return complex(_SHORT_ADMITTANCE), False
    return 1.0 / z, False


def _line_admittances(
    a: complex, b: complex, c: complex, d: complex
) -> tuple[complex, complex, complex, complex]:
    if abs(b) < 1e-15:
        raise StressError("zero-length distributed line cannot be stress-analyzed")
    determinant = a * d - b * c
    return d / b, -determinant / b, -1.0 / b, a / b


def compute_stress(
    circuit: Circuit,
    *,
    power_w: float,
    frequency_hz: float,
    z0_ohm: float | None = None,
) -> StressReport:
    """Solve the circuit and return per-element peak voltage/current.

    ``power_w`` is the source *available* power.  The model is linear and
    frequency-domain; it includes the source/load impedances and the boundary
    T1/BAL1, but not thermal changes in component values.
    """
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

    node_names: list[str] = []
    for port in (circuit.port_in, circuit.port_out):
        if port.node != circuit.ground and port.node not in node_names:
            node_names.append(port.node)
    for element in circuit.elements:
        for node in (element.node_a, element.node_b):
            if node != circuit.ground and node not in node_names:
                node_names.append(node)
    if not node_names:
        raise StressError("circuit has no non-ground nodes")
    index = {name: i for i, name in enumerate(node_names)}
    matrix = np.zeros((len(node_names), len(node_names)), dtype=np.complex128)
    injections = np.zeros(len(node_names), dtype=np.complex128)

    rs = circuit.port_in.impedance_ohm
    if rs <= 0.0:
        raise StressError("port_in impedance must be > 0")
    source_rms = math.sqrt(4.0 * power_w * rs)
    _stamp_admittance(
        matrix, index, circuit.ground, circuit.port_in.node, circuit.ground, 1.0 / rs
    )
    injections[index[circuit.port_in.node]] += source_rms / rs

    load = _load_impedance(circuit, frequency_hz)
    load_y, load_open = _safe_admittance(load)
    if not load_open:
        _stamp_admittance(
            matrix, index, circuit.ground, circuit.port_out.node, circuit.ground, load_y
        )

    line_models: dict[str, tuple[complex, complex, complex, complex]] = {}
    stub_models: dict[str, complex] = {}
    lumped_models: dict[str, tuple[complex, complex, bool]] = {}
    for element in circuit.elements:
        if isinstance(element, MicrostripLineElement):
            omega = np.array([2.0 * math.pi * frequency_hz], dtype=float)
            abcd = _element_abcd(element, omega)[0]
            y11, y12, y21, y22 = _line_admittances(
                complex(abcd[0, 0]),
                complex(abcd[0, 1]),
                complex(abcd[1, 0]),
                complex(abcd[1, 1]),
            )
            _stamp_two_port(
                matrix,
                index,
                circuit.ground,
                element.node_a,
                element.node_b,
                y11,
                y12,
                y21,
                y22,
            )
            line_models[element.id] = (y11, y12, y21, y22)
        elif isinstance(element, MicrostripStubElement):
            omega = np.array([2.0 * math.pi * frequency_hz], dtype=float)
            abcd = _element_abcd(element, omega)[0]
            admittance = complex(abcd[1, 0])
            _stamp_admittance(
                matrix,
                index,
                circuit.ground,
                element.node_a,
                element.node_b,
                admittance,
            )
            stub_models[element.id] = admittance
        else:
            impedance = element_impedance_ohm(element, frequency_hz)
            admittance, open_circuit = _safe_admittance(impedance)
            if not open_circuit:
                _stamp_admittance(
                    matrix,
                    index,
                    circuit.ground,
                    element.node_a,
                    element.node_b,
                    admittance,
                )
            lumped_models[element.id] = (impedance, admittance, open_circuit)

    try:
        voltages = np.asarray(np.linalg.solve(matrix, injections), dtype=np.complex128)
    except np.linalg.LinAlgError as exc:
        raise StressError("stress nodal matrix is singular") from exc

    root2 = math.sqrt(2.0)
    entries: list[ElementStress] = []
    for element in circuit.elements:
        va = _node_voltage(voltages, index, circuit.ground, element.node_a)
        vb = _node_voltage(voltages, index, circuit.ground, element.node_b)
        if isinstance(element, MicrostripLineElement):
            y11, y12, y21, y22 = line_models[element.id]
            i1 = y11 * va + y12 * vb
            i2 = y21 * va + y22 * vb
            v_peak = root2 * max(abs(va), abs(vb))
            i_peak = root2 * max(abs(i1), abs(i2))
            impedance = complex(element.z0_ohm)
        elif isinstance(element, MicrostripStubElement):
            admittance = stub_models[element.id]
            voltage = va - vb
            current = admittance * voltage
            v_peak = root2 * abs(voltage)
            i_peak = root2 * abs(current)
            impedance = (
                complex(math.inf) if abs(admittance) < _SHORT_ABS else 1.0 / admittance
            )
        else:
            impedance, admittance, open_circuit = lumped_models[element.id]
            voltage = va - vb
            current = 0.0j if open_circuit else admittance * voltage
            v_peak = root2 * abs(voltage)
            i_peak = root2 * abs(current)
        entries.append(
            ElementStress(
                ref=element.id,
                role=element.role,
                impedance_ohm=impedance,
                v_peak_v=v_peak,
                i_peak_a=i_peak,
            )
        )

    return StressReport(
        power_w=power_w,
        z0_ohm=z0_ohm,
        frequency_hz=frequency_hz,
        entries=tuple(entries),
    )


__all__ = ["ElementStress", "StressError", "StressReport", "compute_stress"]
