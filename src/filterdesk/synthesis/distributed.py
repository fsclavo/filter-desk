"""Experimental microstrip stepped-impedance low-pass synthesis.

Orders 1–3 use the classical stepped-impedance approximation. Orders 4–5 use a
bounded numerical refinement against the lumped prototype and are accepted only
if the resulting response passes a fit gate. The model remains an ideal TEM
approximation: no dispersion, discontinuities, radiation or coupling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std.microstrip import (
    Substrate,
    design_microstrip,
    find_substrate,
)
from filterdesk.domain.circuit import (
    Circuit,
    IdealCapacitor,
    IdealInductor,
    MicrostripLineElement,
    series_node_path,
)
from filterdesk.domain.enums import ApproximationFamily, ElementRole, FilterResponse
from filterdesk.domain.specs import FilterSpec, validate_spec
from filterdesk.synthesis.api import synthesize

_C0 = 299_792_458.0
SUPPORTED_FAMILIES = frozenset(
    {ApproximationFamily.BUTTERWORTH, ApproximationFamily.CHEBYSHEV_TYPE_I}
)
MAX_ORDER = 5
OPTIMIZE_MIN_ORDER = 4
_MAX_PASSBAND_ERROR_DB = 1.5
_MAX_STOPBAND_PENALTY_DB = 6.0


class DistributedSynthesisError(ValueError):
    """The requested filter cannot be realized by the distributed method."""


@dataclass(frozen=True, slots=True)
class DistributedDesign:
    """A microstrip stepped-impedance realization plus provenance/warnings."""

    spec: FilterSpec
    circuit: Circuit
    substrate: Substrate
    electrical_length_deg: float
    warnings: tuple[str, ...] = ()
    meta: dict[str, object] = field(default_factory=dict)
    optimized: bool = False


def _validate_request(
    spec: FilterSpec,
    substrate: Substrate,
    electrical_length_deg: float,
    z0_min_ohm: float,
    z0_max_ohm: float,
) -> None:
    validate_spec(spec)
    if spec.response != FilterResponse.LOW_PASS:
        raise DistributedSynthesisError("distributed synthesis supports low-pass only")
    if spec.family not in SUPPORTED_FAMILIES:
        raise DistributedSynthesisError(
            "distributed synthesis supports Butterworth and Chebyshev-I low-pass"
        )
    if spec.order > MAX_ORDER:
        raise DistributedSynthesisError(
            f"distributed synthesis supports order <= {MAX_ORDER}; "
            "use a lumped design or reduce the order"
        )
    if not 5.0 <= electrical_length_deg <= 80.0:
        raise DistributedSynthesisError(
            "electrical_length_deg must be between 5 and 80 degrees"
        )
    if z0_min_ohm <= 0.0 or z0_max_ohm <= z0_min_ohm:
        raise DistributedSynthesisError("require 0 < z0_min_ohm < z0_max_ohm")
    if substrate.er < 1.0 or substrate.h_mm <= 0.0:
        raise DistributedSynthesisError("invalid substrate")


def _impedances_for(base: Circuit, cutoff_hz: float, angle_deg: float) -> list[float]:
    sin_theta = math.sin(math.radians(angle_deg))
    if sin_theta <= 1e-12:  # pragma: no cover - callers validate the angle
        raise DistributedSynthesisError("electrical length has zero sine")
    omega0 = 2.0 * math.pi * cutoff_hz
    out: list[float] = []
    for element in base.elements:
        if isinstance(element, IdealInductor) and element.role == ElementRole.SERIES:
            out.append(omega0 * element.value_h / sin_theta)
        elif isinstance(element, IdealCapacitor) and element.role == ElementRole.SHUNT:
            out.append(sin_theta / (omega0 * element.value_f))
        else:
            raise DistributedSynthesisError(
                "distributed synthesis needs a series-L / shunt-C low-pass ladder"
            )
    return out


def _line_value(
    z0_ohm: float,
    angle_deg: float,
    substrate: Substrate,
    cutoff_hz: float,
) -> tuple[float, float, float, float]:
    """Return (Z0, length_m, eeff, loss_db_per_m) for one microstrip section."""
    line = design_microstrip(z0_ohm, substrate, cutoff_hz)
    length_m = angle_deg / 360.0 * _C0 / (cutoff_hz * math.sqrt(line.eeff))
    return line.z0_ohm, length_m, line.eeff, line.loss_db_per_m


def _make_circuit(
    base: Circuit,
    substrate: Substrate,
    cutoff_hz: float,
    z0s: list[float],
    angles_deg: list[float],
) -> Circuit:
    lines: list[MicrostripLineElement] = []
    for index, (z0, angle) in enumerate(zip(z0s, angles_deg, strict=True), start=1):
        z0_actual, length_m, eeff, loss = _line_value(z0, angle, substrate, cutoff_hz)
        lines.append(
            MicrostripLineElement(
                id=f"TL{index}",
                z0_ohm=z0_actual,
                length_m=length_m,
                eeff=eeff,
                node_a="",
                node_b="",
                loss_db_per_m=loss,
                substrate=substrate.name,
                width_mm=design_microstrip(z0, substrate, cutoff_hz).width_mm,
                angle_deg=angle,
            )
        )
    nodes = series_node_path(len(lines))
    lines = [
        replace(line, node_a=nodes[index], node_b=nodes[index + 1])
        for index, line in enumerate(lines)
    ]
    return Circuit(
        elements=list(lines),
        port_in=base.port_in,
        port_out=base.port_out,
        ground=base.ground,
        topology_id=base.topology_id,
        meta={
            **base.meta,
            "realization": "microstrip_stepped_impedance",
            "substrate": substrate.name,
        },
        output_transformer_ratio=base.output_transformer_ratio,
        output_balun=None,
    )


def _refine_high_order(
    base: Circuit,
    spec: FilterSpec,
    substrate: Substrate,
    requested_angle: float,
    z0_min_ohm: float,
    z0_max_ohm: float,
) -> tuple[list[float], list[float], tuple[str, ...]]:
    from scipy.optimize import least_squares

    initial_z0 = _impedances_for(base, spec.cutoff_hz, requested_angle)
    initial_z0 = [min(max(value, z0_min_ohm), z0_max_ohm) for value in initial_z0]
    x0 = np.asarray(
        [
            value
            for pair in zip(
                initial_z0, [requested_angle] * len(initial_z0), strict=True
            )
            for value in pair
        ],
        dtype=float,
    )
    lower = np.asarray(
        [value for _ in initial_z0 for value in (z0_min_ohm, 5.0)],
        dtype=float,
    )
    upper = np.asarray(
        [value for _ in initial_z0 for value in (z0_max_ohm, 80.0)],
        dtype=float,
    )

    sweep = SweepConfig(
        f_start_hz=spec.cutoff_hz / 20.0,
        f_stop_hz=spec.cutoff_hz * 5.0,
        n_points=400,
        spacing=SweepSpacing.LOGARITHMIC,
    )
    f = sweep.frequencies_hz()
    target_db = np.asarray(
        np.maximum(np.abs(analyze_circuit(base, sweep, backend="abcd").s21), 1e-15),
        dtype=float,
    )
    target_db = 20.0 * np.log10(target_db)
    weights = np.where(f <= spec.cutoff_hz, 10.0, 1.0)

    def residual(x: np.ndarray) -> np.ndarray:
        z0s = np.asarray(x[0::2], dtype=float).tolist()
        angles = np.asarray(x[1::2], dtype=float).tolist()
        trial = _make_circuit(base, substrate, spec.cutoff_hz, z0s, angles)
        db = np.asarray(
            20.0
            * np.log10(
                np.maximum(
                    np.abs(analyze_circuit(trial, sweep, backend="abcd").s21),
                    1e-15,
                )
            ),
            dtype=float,
        )
        return np.asarray((db - target_db) * weights, dtype=float)

    solution = least_squares(
        residual,
        x0,
        bounds=(lower, upper),
        max_nfev=500,
        xtol=1e-8,
        ftol=1e-8,
        gtol=1e-8,
    )
    z0s = np.asarray(solution.x[0::2], dtype=float).tolist()
    angles = np.asarray(solution.x[1::2], dtype=float).tolist()
    trial = _make_circuit(base, substrate, spec.cutoff_hz, z0s, angles)
    dist_db = 20.0 * np.log10(
        np.maximum(np.abs(analyze_circuit(trial, sweep, backend="abcd").s21), 1e-15)
    )
    passband = (f >= spec.cutoff_hz / 10.0) & (f <= spec.cutoff_hz)
    passband_error = float(np.max(np.abs(dist_db[passband] - target_db[passband])))
    at_2fc = int(np.argmin(np.abs(f - 2.0 * spec.cutoff_hz)))
    stopband_penalty = float(dist_db[at_2fc] - target_db[at_2fc])
    if (
        passband_error > _MAX_PASSBAND_ERROR_DB
        or stopband_penalty > _MAX_STOPBAND_PENALTY_DB
    ):
        raise DistributedSynthesisError(
            "numerical distributed fit rejected: "
            f"passband error {passband_error:.2f} dB "
            f"(max {_MAX_PASSBAND_ERROR_DB:g}), "
            f"stopband penalty {stopband_penalty:.2f} dB "
            f"(max {_MAX_STOPBAND_PENALTY_DB:g}); "
            "widen the Z0 range, reduce the order or use a lumped design"
        )
    warnings = (
        "orders 4–5 use a bounded numerical fit; verify the board with Touchstone/VNA",
    )
    return z0s, angles, warnings


def design_distributed_lowpass(
    spec: FilterSpec,
    substrate: Substrate | str = "FR4",
    *,
    electrical_length_deg: float = 30.0,
    z0_min_ohm: float = 10.0,
    z0_max_ohm: float = 250.0,
) -> DistributedDesign:
    """Convert an LP prototype into alternating microstrip line sections.

    Orders 1–3 use the classical stepped-impedance formulas. Orders 4–5 use a
    bounded numerical fit and are accepted only when the response gate passes.
    """
    sub = find_substrate(substrate) if isinstance(substrate, str) else substrate
    _validate_request(spec, sub, electrical_length_deg, z0_min_ohm, z0_max_ohm)
    base = synthesize(spec).circuit
    requested_angle = electrical_length_deg
    optimised = spec.order >= OPTIMIZE_MIN_ORDER
    if optimised:
        z0s, angles, warnings = _refine_high_order(
            base, spec, sub, requested_angle, z0_min_ohm, z0_max_ohm
        )
        actual_angle = requested_angle
    else:
        actual_angle = requested_angle
        z0s = _impedances_for(base, spec.cutoff_hz, actual_angle)
        while actual_angle < 80.0 and any(
            z < z0_min_ohm or z > z0_max_ohm for z in z0s
        ):
            actual_angle = min(80.0, actual_angle + 1.0)
            z0s = _impedances_for(base, spec.cutoff_hz, actual_angle)
        if any(z < z0_min_ohm or z > z0_max_ohm for z in z0s):
            raise DistributedSynthesisError(
                "cannot fit the required line impedances inside "
                f"[{z0_min_ohm:g}, {z0_max_ohm:g}] by adjusting the electrical "
                "length; reduce the order, change the substrate or widen the range"
            )
        angles = [actual_angle] * len(z0s)
        warnings = ()
        if abs(actual_angle - requested_angle) > 1e-9:
            warnings = (
                f"electrical length adjusted from {requested_angle:g}° to "
                f"{actual_angle:g}° to keep Z0 in range",
            )

    circuit = _make_circuit(base, sub, spec.cutoff_hz, z0s, angles)
    extra_warnings: list[str] = []
    for index, line in enumerate(circuit.elements, start=1):
        if not isinstance(line, MicrostripLineElement):
            continue
        if line.width_mm < 0.15:
            extra_warnings.append(
                f"TL{index}: narrow trace ({line.width_mm:.3f} mm); "
                "verify fabrication tolerance"
            )
        elif line.width_mm > 20.0:
            extra_warnings.append(
                f"TL{index}: very wide trace ({line.width_mm:.2f} mm); "
                "check the substrate/connector transition"
            )
    circuit.meta["electrical_length_deg"] = actual_angle
    circuit.meta["angles_deg"] = list(angles)
    circuit.meta["optimized"] = optimised
    actual_impedances = [
        element.z0_ohm
        for element in circuit.elements
        if isinstance(element, MicrostripLineElement)
    ]
    return DistributedDesign(
        spec=spec,
        circuit=circuit,
        substrate=sub,
        electrical_length_deg=actual_angle,
        warnings=tuple(warnings) + tuple(extra_warnings),
        meta={
            "z0_ohm": actual_impedances,
            "angles_deg": list(angles),
            "approximation": (
                "numerically fitted stepped-impedance TEM"
                if optimised
                else "first-order stepped-impedance TEM"
            ),
            "confidence": "experimental",
            "optimized": optimised,
        },
        optimized=optimised,
    )


__all__ = [
    "DistributedDesign",
    "DistributedSynthesisError",
    "MAX_ORDER",
    "OPTIMIZE_MIN_ORDER",
    "SUPPORTED_FAMILIES",
    "design_distributed_lowpass",
]
