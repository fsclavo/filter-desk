"""Filter specification model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)

_ALL_POLE_3DB = frozenset(
    {
        ApproximationFamily.BUTTERWORTH,
        ApproximationFamily.BESSEL,
        ApproximationFamily.GAUSSIAN,
        ApproximationFamily.LEGENDRE,
    }
)


@dataclass(frozen=True, slots=True)
class FilterSpec:
    """Typed filter requirements (LP/HP/BP/BS; equal or asymmetric Z)."""

    family: ApproximationFamily
    response: FilterResponse
    order: int
    z_source_ohm: float
    z_load_ohm: float
    topology_id: TopologyId
    cutoff_definition: CutoffDefinition
    cutoff_hz: float = 0.0
    f_center_hz: float | None = None
    bandwidth_hz: float | None = None
    passband_ripple_db: float | None = None
    stopband_attenuation_db: float | None = None
    m_parameter: float | None = None


class SpecValidationError(ValueError):
    """Invalid or unsupported filter specification."""


def validate_spec(spec: FilterSpec) -> None:
    if spec.order < 1:
        raise SpecValidationError("order must be >= 1")
    if spec.z_source_ohm <= 0.0 or spec.z_load_ohm <= 0.0:
        raise SpecValidationError("impedances must be > 0")

    if spec.response in (FilterResponse.LOW_PASS, FilterResponse.HIGH_PASS):
        if spec.cutoff_hz <= 0.0:
            raise SpecValidationError("cutoff_hz must be > 0 for LP/HP")
        if spec.f_center_hz is not None or spec.bandwidth_hz is not None:
            raise SpecValidationError(
                "f_center_hz / bandwidth_hz apply only to BP/BS"
            )
    elif spec.response in (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP):
        if spec.f_center_hz is None or spec.f_center_hz <= 0.0:
            raise SpecValidationError("f_center_hz must be > 0 for BP/BS")
        if spec.bandwidth_hz is None or spec.bandwidth_hz <= 0.0:
            raise SpecValidationError("bandwidth_hz must be > 0 for BP/BS")
        f0 = spec.f_center_hz
        bw = spec.bandwidth_hz
        disc = bw * bw + 4.0 * f0 * f0
        f_high = 0.5 * (bw + disc**0.5)
        f_low = f0 * f0 / f_high
        if f_low <= 0.0 or f_high <= f_low:
            raise SpecValidationError("invalid f_center_hz / bandwidth_hz combination")
    else:
        raise SpecValidationError(f"unsupported response: {spec.response}")

    if spec.family == ApproximationFamily.CHEBYSHEV_TYPE_I:
        if spec.passband_ripple_db is None or spec.passband_ripple_db <= 0.0:
            raise SpecValidationError(
                "chebyshev_type_i requires passband_ripple_db > 0"
            )
        if spec.cutoff_definition != CutoffDefinition.RIPPLE_EDGE:
            raise SpecValidationError(
                "chebyshev_type_i requires cutoff_definition=ripple_edge (ADR-006)"
            )
        if spec.stopband_attenuation_db is not None:
            raise SpecValidationError(
                "chebyshev_type_i must not set stopband_attenuation_db"
            )
    elif spec.family == ApproximationFamily.CHEBYSHEV_TYPE_II:
        if (
            spec.stopband_attenuation_db is None
            or spec.stopband_attenuation_db <= 0.0
        ):
            raise SpecValidationError(
                "chebyshev_type_ii requires stopband_attenuation_db > 0"
            )
        if spec.cutoff_definition != CutoffDefinition.STOPBAND_EDGE:
            raise SpecValidationError(
                "chebyshev_type_ii requires cutoff_definition=stopband_edge "
                "(ADR-013)"
            )
        if spec.passband_ripple_db is not None:
            raise SpecValidationError(
                "chebyshev_type_ii must not set passband_ripple_db"
            )
    elif spec.family == ApproximationFamily.ELLIPTIC:
        if spec.passband_ripple_db is None or spec.passband_ripple_db <= 0.0:
            raise SpecValidationError("elliptic requires passband_ripple_db > 0")
        if (
            spec.stopband_attenuation_db is None
            or spec.stopband_attenuation_db <= 0.0
        ):
            raise SpecValidationError(
                "elliptic requires stopband_attenuation_db > 0"
            )
        if spec.stopband_attenuation_db <= spec.passband_ripple_db:
            raise SpecValidationError(
                "elliptic requires stopband_attenuation_db > passband_ripple_db"
            )
        if spec.cutoff_definition != CutoffDefinition.RIPPLE_EDGE:
            raise SpecValidationError(
                "elliptic requires cutoff_definition=ripple_edge (ADR-006)"
            )
        if spec.order < 2:
            raise SpecValidationError("elliptic requires order >= 2")
        if spec.order % 2 == 0:
            raise SpecValidationError(
                "even-order elliptic needs a transformer or unequal "
                "terminations; FilterDesk supports odd orders only (3, 5, 7, …)"
            )
    elif spec.family in _ALL_POLE_3DB:
        if spec.cutoff_definition != CutoffDefinition.HALF_POWER_3DB:
            raise SpecValidationError(
                f"{spec.family.value} requires cutoff_definition=half_power_3db"
            )
        if spec.passband_ripple_db is not None:
            raise SpecValidationError(
                f"{spec.family.value} must not set passband_ripple_db"
            )
        if spec.stopband_attenuation_db is not None:
            raise SpecValidationError(
                f"{spec.family.value} must not set stopband_attenuation_db"
            )
        if spec.family == ApproximationFamily.LEGENDRE and spec.order < 2:
            raise SpecValidationError("legendre requires order >= 2")
        if spec.family == ApproximationFamily.BESSEL and not (1 <= spec.order <= 10):
            raise SpecValidationError("bessel supports order 1..10")
        if spec.family == ApproximationFamily.GAUSSIAN and not (
            1 <= spec.order <= 10
        ):
            raise SpecValidationError("gaussian supports order 1..10")
        if spec.family == ApproximationFamily.LEGENDRE and not (
            2 <= spec.order <= 9
        ):
            raise SpecValidationError("legendre supports order 2..9")
    elif spec.family == ApproximationFamily.CONSTANT_K:
        if spec.cutoff_definition != CutoffDefinition.HALF_POWER_3DB:
            # Image cutoff; reuse half_power label as nominal image fc
            raise SpecValidationError(
                "constant_k requires cutoff_definition=half_power_3db "
                "(nominal image cutoff)"
            )
        if (
            spec.passband_ripple_db is not None
            or spec.stopband_attenuation_db is not None
        ):
            raise SpecValidationError(
                "constant_k must not set ripple / stopband attenuation"
            )
        if spec.m_parameter is not None:
            raise SpecValidationError("constant_k must not set m_parameter")
    elif spec.family == ApproximationFamily.M_DERIVED:
        if spec.cutoff_definition != CutoffDefinition.HALF_POWER_3DB:
            raise SpecValidationError(
                "m_derived requires cutoff_definition=half_power_3db "
                "(nominal image cutoff)"
            )
        if spec.m_parameter is None or not (0.0 < spec.m_parameter < 1.0):
            raise SpecValidationError("m_derived requires 0 < m_parameter < 1")
        if (
            spec.passband_ripple_db is not None
            or spec.stopband_attenuation_db is not None
        ):
            raise SpecValidationError(
                "m_derived must not set ripple / stopband attenuation"
            )
    else:
        raise SpecValidationError(f"unsupported family: {spec.family}")

    _validate_topology_matches_response(spec)


def _validate_topology_matches_response(spec: FilterSpec) -> None:
    groups: dict[FilterResponse, set[TopologyId]] = {
        FilterResponse.LOW_PASS: {
            TopologyId.LADDER_LP_SERIES_L_INPUT,
            TopologyId.LADDER_LP_SHUNT_C_INPUT,
        },
        FilterResponse.HIGH_PASS: {
            TopologyId.LADDER_HP_SERIES_C_INPUT,
            TopologyId.LADDER_HP_SHUNT_L_INPUT,
        },
        FilterResponse.BAND_PASS: {
            TopologyId.LADDER_BP_SERIES_RES_INPUT,
            TopologyId.LADDER_BP_SHUNT_RES_INPUT,
        },
        FilterResponse.BAND_STOP: {
            TopologyId.LADDER_BS_SERIES_TANK_INPUT,
            TopologyId.LADDER_BS_SHUNT_TANK_INPUT,
        },
    }
    allowed = groups[spec.response]
    if spec.topology_id not in allowed:
        raise SpecValidationError(
            f"topology {spec.topology_id.value} is not valid for {spec.response.value}"
        )


def default_topology(response: FilterResponse) -> TopologyId:
    mapping = {
        FilterResponse.LOW_PASS: TopologyId.LADDER_LP_SERIES_L_INPUT,
        FilterResponse.HIGH_PASS: TopologyId.LADDER_HP_SERIES_C_INPUT,
        FilterResponse.BAND_PASS: TopologyId.LADDER_BP_SERIES_RES_INPUT,
        FilterResponse.BAND_STOP: TopologyId.LADDER_BS_SERIES_TANK_INPUT,
    }
    if response not in mapping:
        raise SpecValidationError(f"unsupported response: {response}")
    return mapping[response]


def default_cutoff_definition(family: ApproximationFamily) -> CutoffDefinition:
    if family in (
        ApproximationFamily.CHEBYSHEV_TYPE_I,
        ApproximationFamily.ELLIPTIC,
    ):
        return CutoffDefinition.RIPPLE_EDGE
    if family == ApproximationFamily.CHEBYSHEV_TYPE_II:
        return CutoffDefinition.STOPBAND_EDGE
    if family in (
        *_ALL_POLE_3DB,
        ApproximationFamily.CONSTANT_K,
        ApproximationFamily.M_DERIVED,
    ):
        return CutoffDefinition.HALF_POWER_3DB
    raise SpecValidationError(f"unsupported family: {family}")


def geometric_mean_z0(z_source_ohm: float, z_load_ohm: float) -> float:
    """Legacy geometric-mean impedance (ADR-011; superseded by ADR-017)."""
    return float((z_source_ohm * z_load_ohm) ** 0.5)


def filter_spec_from_mapping(data: dict[str, Any]) -> FilterSpec:
    """Build a FilterSpec from a JSON-like mapping (golden / CLI)."""
    family = ApproximationFamily(str(data["family"]))
    response = FilterResponse(str(data["response"]))
    topology_raw = data.get("topology_id")
    topology = (
        TopologyId(str(topology_raw))
        if topology_raw is not None
        else default_topology(response)
    )
    cutoff_raw = data.get("cutoff_definition")
    cutoff_def = (
        CutoffDefinition(str(cutoff_raw))
        if cutoff_raw is not None
        else default_cutoff_definition(family)
    )
    ripple = data.get("passband_ripple_db")
    stop_att = data.get("stopband_attenuation_db")
    m_param = data.get("m_parameter")
    f_center = data.get("f_center_hz")
    bandwidth = data.get("bandwidth_hz")
    cutoff = float(data["cutoff_hz"]) if "cutoff_hz" in data else 0.0
    spec = FilterSpec(
        family=family,
        response=response,
        order=int(data["order"]),
        cutoff_hz=cutoff,
        f_center_hz=None if f_center is None else float(f_center),
        bandwidth_hz=None if bandwidth is None else float(bandwidth),
        z_source_ohm=float(data["z_source_ohm"]),
        z_load_ohm=float(data["z_load_ohm"]),
        topology_id=topology,
        cutoff_definition=cutoff_def,
        passband_ripple_db=None if ripple is None else float(ripple),
        stopband_attenuation_db=None if stop_att is None else float(stop_att),
        m_parameter=None if m_param is None else float(m_param),
    )
    validate_spec(spec)
    return spec


def filter_spec_to_mapping(spec: FilterSpec) -> dict[str, Any]:
    out: dict[str, Any] = {
        "family": spec.family.value,
        "response": spec.response.value,
        "order": spec.order,
        "cutoff_definition": spec.cutoff_definition.value,
        "z_source_ohm": spec.z_source_ohm,
        "z_load_ohm": spec.z_load_ohm,
        "topology_id": spec.topology_id.value,
    }
    if spec.response in (FilterResponse.LOW_PASS, FilterResponse.HIGH_PASS):
        out["cutoff_hz"] = spec.cutoff_hz
    else:
        out["f_center_hz"] = spec.f_center_hz
        out["bandwidth_hz"] = spec.bandwidth_hz
    if spec.passband_ripple_db is not None:
        out["passband_ripple_db"] = spec.passband_ripple_db
    if spec.stopband_attenuation_db is not None:
        out["stopband_attenuation_db"] = spec.stopband_attenuation_db
    if spec.m_parameter is not None:
        out["m_parameter"] = spec.m_parameter
    return out
