"""Experimental microstrip stepped-impedance low-pass synthesis.

The lumped LP prototype is converted into a cascade of high-/low-impedance
microstrip lines.  This is a first-order distributed equivalent: it preserves
the Chebyshev/Butterworth low-pass shape for low orders but does not model
dispersion, discontinuities, radiation or coupling.  Use the normal Touchstone
and VNA flows to verify the fabricated board.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from filterdesk.components_std.microstrip import (
    MicrostripError,
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
MAX_ORDER = 3


class DistributedSynthesisError(ValueError):
    """The requested filter cannot be realized by the v1 distributed method."""


@dataclass(frozen=True, slots=True)
class DistributedDesign:
    """A microstrip stepped-impedance realization plus provenance/warnings."""

    spec: FilterSpec
    circuit: Circuit
    substrate: Substrate
    electrical_length_deg: float
    warnings: tuple[str, ...] = ()
    meta: dict[str, object] = field(default_factory=dict)


def _validate_request(
    spec: FilterSpec,
    substrate: Substrate,
    electrical_length_deg: float,
    z0_min_ohm: float,
    z0_max_ohm: float,
) -> None:
    validate_spec(spec)
    if spec.response != FilterResponse.LOW_PASS:
        raise DistributedSynthesisError("distributed v1 supports low-pass filters only")
    if spec.family not in SUPPORTED_FAMILIES:
        raise DistributedSynthesisError(
            "distributed v1 supports Butterworth and Chebyshev-I low-pass filters"
        )
    if spec.order > MAX_ORDER:
        raise DistributedSynthesisError(
            f"distributed v1 supports order <= {MAX_ORDER}; "
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


def design_distributed_lowpass(
    spec: FilterSpec,
    substrate: Substrate | str = "FR4",
    *,
    electrical_length_deg: float = 30.0,
    z0_min_ohm: float = 10.0,
    z0_max_ohm: float = 120.0,
) -> DistributedDesign:
    """Convert a low-order LP prototype into alternating microstrip lines.

    Series inductors become high-impedance lines; shunt capacitors become
    low-impedance lines.  At the cutoff frequency the line reactance/susceptance
    matches the lumped arm, using the standard stepped-impedance approximation.
    """
    sub = find_substrate(substrate) if isinstance(substrate, str) else substrate
    _validate_request(spec, sub, electrical_length_deg, z0_min_ohm, z0_max_ohm)
    base = synthesize(spec).circuit
    omega0 = 2.0 * math.pi * spec.cutoff_hz

    def impedances_for(angle_deg: float) -> list[float]:
        sin_theta = math.sin(math.radians(angle_deg))
        if sin_theta <= 1e-12:  # pragma: no cover - guarded above
            raise DistributedSynthesisError("electrical length has zero sine")
        out: list[float] = []
        for el in base.elements:
            if isinstance(el, IdealInductor) and el.role == ElementRole.SERIES:
                out.append(omega0 * el.value_h / sin_theta)
            elif isinstance(el, IdealCapacitor) and el.role == ElementRole.SHUNT:
                out.append(sin_theta / (omega0 * el.value_f))
            else:
                raise DistributedSynthesisError(
                    "distributed v1 needs a series-L / shunt-C low-pass ladder"
                )
        return out

    requested_angle = electrical_length_deg
    actual_angle = requested_angle
    impedances = impedances_for(actual_angle)
    while actual_angle < 80.0 and any(
        z < z0_min_ohm or z > z0_max_ohm for z in impedances
    ):
        actual_angle = min(80.0, actual_angle + 1.0)
        impedances = impedances_for(actual_angle)
    if any(z < z0_min_ohm or z > z0_max_ohm for z in impedances):
        raise DistributedSynthesisError(
            "cannot fit the required line impedances inside "
            f"[{z0_min_ohm:g}, {z0_max_ohm:g}] by adjusting the electrical "
            "length; reduce the order, change the substrate or widen the range"
        )
    warnings: list[str] = []
    if abs(actual_angle - requested_angle) > 1e-9:
        warnings.append(
            f"electrical length adjusted from {requested_angle:g}° to "
            f"{actual_angle:g}° to keep Z0 in range"
        )

    lines: list[MicrostripLineElement] = []
    actual_impedances: list[float] = []
    for index, z0 in enumerate(impedances, start=1):
        try:
            ms_line = design_microstrip(z0, sub, spec.cutoff_hz)
        except MicrostripError as exc:  # pragma: no cover - defensive
            raise DistributedSynthesisError(str(exc)) from exc
        length_m = (
            actual_angle / 360.0 * _C0 / (spec.cutoff_hz * math.sqrt(ms_line.eeff))
        )
        actual_impedances.append(ms_line.z0_ohm)
        if ms_line.width_mm < 0.15:
            warnings.append(
                f"TL{index}: narrow trace ({ms_line.width_mm:.3f} mm); "
                "verify fabrication tolerance"
            )
        elif ms_line.width_mm > 20.0:
            warnings.append(
                f"TL{index}: very wide trace ({ms_line.width_mm:.2f} mm); "
                "check the substrate/connector transition"
            )
        lines.append(
            MicrostripLineElement(
                id=f"TL{index}",
                z0_ohm=ms_line.z0_ohm,
                length_m=length_m,
                eeff=ms_line.eeff,
                node_a="",
                node_b="",
                loss_db_per_m=ms_line.loss_db_per_m,
                substrate=sub.name,
                width_mm=ms_line.width_mm,
                angle_deg=actual_angle,
            )
        )

    nodes = series_node_path(len(lines))
    for index, element in enumerate(lines):
        # Frozen dataclasses: rebuild with the actual ladder nodes.
        lines[index] = MicrostripLineElement(
            id=element.id,
            z0_ohm=element.z0_ohm,
            length_m=element.length_m,
            eeff=element.eeff,
            node_a=nodes[index],
            node_b=nodes[index + 1],
            loss_db_per_m=element.loss_db_per_m,
            substrate=element.substrate,
            width_mm=element.width_mm,
            angle_deg=element.angle_deg,
        )

    circuit = Circuit(
        elements=list(lines),
        port_in=base.port_in,
        port_out=base.port_out,
        ground=base.ground,
        topology_id=base.topology_id,
        meta={
            **base.meta,
            "realization": "microstrip_stepped_impedance",
            "substrate": sub.name,
            "electrical_length_deg": actual_angle,
        },
        output_transformer_ratio=base.output_transformer_ratio,
        output_balun=None,
    )
    return DistributedDesign(
        spec=spec,
        circuit=circuit,
        substrate=sub,
        electrical_length_deg=actual_angle,
        warnings=tuple(warnings),
        meta={
            "z0_ohm": actual_impedances,
            "approximation": "first-order stepped-impedance TEM",
            "confidence": "experimental",
        },
    )


__all__ = [
    "DistributedDesign",
    "DistributedSynthesisError",
    "MAX_ORDER",
    "SUPPORTED_FAMILIES",
    "design_distributed_lowpass",
]
