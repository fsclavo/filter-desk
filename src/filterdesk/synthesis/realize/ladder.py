"""Ladder topology realization from g-value or Cauer prototypes."""

from __future__ import annotations

import math

from filterdesk.domain.circuit import (
    ArmKind,
    Circuit,
    Element,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealSeriesLC,
    Port,
    series_node_path,
)
from filterdesk.domain.enums import ElementRole, FilterResponse, TopologyId
from filterdesk.domain.prototype import NormalizedArm, Prototype
from filterdesk.domain.specs import FilterSpec, SpecValidationError
from filterdesk.synthesis.cauer_extract import dual_arms, lp_arms_to_hp


def arm_kinds_for_topology(topology_id: TopologyId, order: int) -> list[ArmKind]:
    """Map topology + order to physical arm kinds for g1..gn."""
    if topology_id == TopologyId.LADDER_LP_SERIES_L_INPUT:
        return ["series_L" if k % 2 == 1 else "shunt_C" for k in range(1, order + 1)]
    if topology_id == TopologyId.LADDER_LP_SHUNT_C_INPUT:
        return ["shunt_C" if k % 2 == 1 else "series_L" for k in range(1, order + 1)]
    if topology_id == TopologyId.LADDER_HP_SERIES_C_INPUT:
        return ["series_C" if k % 2 == 1 else "shunt_L" for k in range(1, order + 1)]
    if topology_id == TopologyId.LADDER_HP_SHUNT_L_INPUT:
        return ["shunt_L" if k % 2 == 1 else "series_C" for k in range(1, order + 1)]
    if topology_id == TopologyId.LADDER_BP_SERIES_RES_INPUT:
        return [
            "series_series_LC" if k % 2 == 1 else "shunt_parallel_LC"
            for k in range(1, order + 1)
        ]
    if topology_id == TopologyId.LADDER_BP_SHUNT_RES_INPUT:
        return [
            "shunt_parallel_LC" if k % 2 == 1 else "series_series_LC"
            for k in range(1, order + 1)
        ]
    if topology_id == TopologyId.LADDER_BS_SERIES_TANK_INPUT:
        return [
            "series_parallel_LC" if k % 2 == 1 else "shunt_series_LC"
            for k in range(1, order + 1)
        ]
    if topology_id == TopologyId.LADDER_BS_SHUNT_TANK_INPUT:
        return [
            "shunt_series_LC" if k % 2 == 1 else "series_parallel_LC"
            for k in range(1, order + 1)
        ]
    raise SpecValidationError(f"unsupported topology: {topology_id}")


def scale_lp_hp_arm(
    kind: ArmKind, g_k: float, omega_c: float, z0: float
) -> tuple[str, float]:
    """Return (``C``|``L``, SI value) for one LP/HP ladder arm."""
    if kind == "series_L":
        return "L", g_k * z0 / omega_c
    if kind == "shunt_C":
        return "C", g_k / (omega_c * z0)
    if kind == "series_C":
        return "C", 1.0 / (omega_c * g_k * z0)
    if kind == "shunt_L":
        return "L", z0 / (omega_c * g_k)
    raise SpecValidationError(f"unknown LP/HP arm kind: {kind}")


def scale_resonator_arm(
    kind: ArmKind, g_k: float, omega0: float, bandwidth: float, z0: float
) -> tuple[float, float]:
    """Return ``(L_henry, C_farad)`` for one BP/BS resonator arm."""
    b = bandwidth
    w2 = omega0 * omega0
    if kind == "series_series_LC":
        return g_k * z0 / b, b / (w2 * g_k * z0)
    if kind == "shunt_parallel_LC":
        return b * z0 / (w2 * g_k), g_k / (b * z0)
    if kind == "series_parallel_LC":
        return g_k * z0 * b / w2, 1.0 / (g_k * z0 * b)
    if kind == "shunt_series_LC":
        return z0 / (g_k * b), g_k * b / (w2 * z0)
    raise SpecValidationError(f"unknown resonator arm kind: {kind}")


def _is_series_kind(kind: ArmKind) -> bool:
    return kind.startswith("series")


def _scale_normalized_arm(
    arm: NormalizedArm, omega_c: float, z0: float
) -> tuple[ArmKind, float | None, float | None, float | None]:
    """Scale LP/HP normalized arm to SI. Returns kind, single, L, C."""
    kind = arm.kind
    if kind == "series_L":
        assert arm.value is not None
        return kind, arm.value * z0 / omega_c, None, None
    if kind == "shunt_C":
        assert arm.value is not None
        return kind, arm.value / (omega_c * z0), None, None
    if kind == "series_C":
        assert arm.value is not None
        return kind, arm.value / (omega_c * z0), None, None
    if kind == "shunt_L":
        assert arm.value is not None
        return kind, arm.value * z0 / omega_c, None, None
    if kind == "shunt_series_LC":
        assert arm.L is not None and arm.C is not None
        return kind, None, arm.L * z0 / omega_c, arm.C / (omega_c * z0)
    if kind == "series_parallel_LC":
        assert arm.L is not None and arm.C is not None
        return kind, None, arm.L * z0 / omega_c, arm.C / (omega_c * z0)
    raise SpecValidationError(f"cannot scale arm kind {kind} for LP/HP")


def _bp_from_L(
    L_n: float, omega0: float, bandwidth: float, z0: float
) -> tuple[float, float]:
    """LP series L → BP series resonator (L, C)."""
    return L_n * z0 / bandwidth, bandwidth / (omega0 * omega0 * L_n * z0)


def _bp_from_C(
    C_n: float, omega0: float, bandwidth: float, z0: float
) -> tuple[float, float]:
    """LP shunt C → BP parallel tank (L, C)."""
    return (
        bandwidth * z0 / (omega0 * omega0 * C_n),
        C_n / (bandwidth * z0),
    )


def _bs_from_L(
    L_n: float, omega0: float, bandwidth: float, z0: float
) -> tuple[float, float]:
    """LP series L → BS series parallel tank (L, C)."""
    return L_n * z0 * bandwidth / (omega0 * omega0), 1.0 / (L_n * z0 * bandwidth)


def _bs_from_C(
    C_n: float, omega0: float, bandwidth: float, z0: float
) -> tuple[float, float]:
    """LP shunt C → BS shunt series resonator (L, C)."""
    return z0 / (C_n * bandwidth), C_n * bandwidth / (omega0 * omega0 * z0)


def _scale_normalized_arm_resonator(
    arm: NormalizedArm,
    omega0: float,
    bandwidth: float,
    z0: float,
    *,
    band_stop: bool,
) -> tuple[ArmKind, float | None, float | None, float | None, dict[str, float] | None]:
    """Map LP prototype arms to BP/BS resonators / Brune sections.

    Returns ``(kind, single, L, C, brune_parts)`` where ``brune_parts`` is
    ``{series_l, series_c, parallel_l, parallel_c}`` for composite arms.
    """
    b = bandwidth
    w2 = omega0 * omega0
    if arm.kind == "series_L":
        assert arm.value is not None
        g = arm.value
        if band_stop:
            return "series_parallel_LC", None, g * z0 * b / w2, 1.0 / (g * z0 * b), None
        return "series_series_LC", None, g * z0 / b, b / (w2 * g * z0), None
    if arm.kind == "shunt_C":
        assert arm.value is not None
        g = arm.value
        if band_stop:
            return "shunt_series_LC", None, z0 / (g * b), g * b / (w2 * z0), None
        return "shunt_parallel_LC", None, b * z0 / (w2 * g), g / (b * z0), None
    if arm.kind == "shunt_series_LC":
        assert arm.L is not None and arm.C is not None
        if band_stop:
            # Z = Z_L_bs + Z_C_bs → parallel tank (from L) + series res (from C)
            lp, cp = _bs_from_L(arm.L, omega0, b, z0)
            ls, cs = _bs_from_C(arm.C, omega0, b, z0)
        else:
            ls, cs = _bp_from_L(arm.L, omega0, b, z0)
            lp, cp = _bp_from_C(arm.C, omega0, b, z0)
        parts = {
            "series_l": ls,
            "series_c": cs,
            "parallel_l": lp,
            "parallel_c": cp,
        }
        return "shunt_brune_LC", None, None, None, parts
    if arm.kind == "series_parallel_LC":
        assert arm.L is not None and arm.C is not None
        if band_stop:
            lp, cp = _bs_from_L(arm.L, omega0, b, z0)
            ls, cs = _bs_from_C(arm.C, omega0, b, z0)
        else:
            ls, cs = _bp_from_L(arm.L, omega0, b, z0)
            lp, cp = _bp_from_C(arm.C, omega0, b, z0)
        parts = {
            "series_l": ls,
            "series_c": cs,
            "parallel_l": lp,
            "parallel_c": cp,
        }
        return "series_dual_brune_LC", None, None, None, parts
    raise SpecValidationError(
        f"resonator transform not available for Cauer arm {arm.kind}"
    )


def _prepare_cauer_arms(
    spec: FilterSpec, prototype: Prototype
) -> tuple[NormalizedArm, ...]:
    assert prototype.arms is not None
    arms: tuple[NormalizedArm, ...] = prototype.arms
    series_first = spec.topology_id in (
        TopologyId.LADDER_LP_SERIES_L_INPUT,
        TopologyId.LADDER_HP_SERIES_C_INPUT,
        TopologyId.LADDER_BP_SERIES_RES_INPUT,
        TopologyId.LADDER_BS_SERIES_TANK_INPUT,
    )
    if not series_first:
        arms = dual_arms(arms)
    if spec.response == FilterResponse.HIGH_PASS:
        arms = lp_arms_to_hp(arms)
    elif spec.response == FilterResponse.LOW_PASS:
        pass
    elif spec.response in (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP):
        # Keep LP prototype arms; BP/BS element map applied at scale time.
        pass
    else:
        raise SpecValidationError(f"unsupported response: {spec.response}")
    return arms


def _append_element(
    elements: list[Element],
    *,
    index: int,
    kind: ArmKind,
    node_a: str,
    node_b: str,
    role: ElementRole,
    single: float | None,
    l_h: float | None,
    c_f: float | None,
    brune: dict[str, float] | None = None,
) -> None:
    if kind in ("series_L", "shunt_L"):
        assert single is not None
        elements.append(
            IdealInductor(
                id=f"L{index}",
                value_h=single,
                node_a=node_a,
                node_b=node_b,
                role=role,
            )
        )
    elif kind in ("series_C", "shunt_C"):
        assert single is not None
        elements.append(
            IdealCapacitor(
                id=f"C{index}",
                value_f=single,
                node_a=node_a,
                node_b=node_b,
                role=role,
            )
        )
    elif kind in ("series_series_LC", "shunt_series_LC"):
        assert l_h is not None and c_f is not None
        elements.append(
            IdealSeriesLC(
                id=f"X{index}",
                value_h=l_h,
                value_f=c_f,
                node_a=node_a,
                node_b=node_b,
                role=role,
            )
        )
    elif kind in ("series_parallel_LC", "shunt_parallel_LC"):
        assert l_h is not None and c_f is not None
        elements.append(
            IdealParallelLC(
                id=f"X{index}",
                value_h=l_h,
                value_f=c_f,
                node_a=node_a,
                node_b=node_b,
                role=role,
            )
        )
    elif kind in ("series_brune_LC", "shunt_brune_LC"):
        assert brune is not None
        elements.append(
            IdealBruneLC(
                id=f"X{index}",
                series_l_h=brune["series_l"],
                series_c_f=brune["series_c"],
                parallel_l_h=brune["parallel_l"],
                parallel_c_f=brune["parallel_c"],
                node_a=node_a,
                node_b=node_b,
                role=role,
            )
        )
    elif kind in ("series_dual_brune_LC", "shunt_dual_brune_LC"):
        assert brune is not None
        elements.append(
            IdealDualBruneLC(
                id=f"X{index}",
                series_l_h=brune["series_l"],
                series_c_f=brune["series_c"],
                parallel_l_h=brune["parallel_l"],
                parallel_c_f=brune["parallel_c"],
                node_a=node_a,
                node_b=node_b,
                role=role,
            )
        )
    else:
        raise SpecValidationError(f"unknown arm kind: {kind}")


def realize_ladder(spec: FilterSpec, prototype: Prototype) -> Circuit:
    """Realize an LP/HP/BP/BS ladder from a normalized prototype (ADR-011 Z0)."""
    if prototype.order != spec.order and prototype.arms is None:
        raise SpecValidationError("prototype order does not match specification")
    # Cauer/image prototypes encode structural order in arms; FilterSpec.order is
    # the family parameter (sections / approx order), which may differ from arm count.

    # Design the ladder for the source impedance and transform the actual load
    # at the output with an ideal transformer. This is exact for equal-R
    # prototypes (versus the old geometric-mean approximation).
    z0 = spec.z_source_ohm
    ladder_load = z0 * (
        1.0 if prototype.arms is not None else prototype.load_ratio
    )
    transformer_ratio = (
        1.0
        if abs(ladder_load - spec.z_load_ohm)
        <= 1e-12 * max(ladder_load, spec.z_load_ohm)
        else math.sqrt(ladder_load / spec.z_load_ohm)
    )
    is_resonator = spec.response in (
        FilterResponse.BAND_PASS,
        FilterResponse.BAND_STOP,
    )
    omega_c = 2.0 * math.pi * spec.cutoff_hz if not is_resonator else 0.0
    omega0 = 0.0
    bandwidth = 0.0
    if is_resonator:
        assert spec.f_center_hz is not None and spec.bandwidth_hz is not None
        omega0 = 2.0 * math.pi * spec.f_center_hz
        bandwidth = 2.0 * math.pi * spec.bandwidth_hz

    if prototype.arms is not None:
        return _realize_from_arms(
            spec, prototype, z0, omega_c, omega0, bandwidth, transformer_ratio
        )

    kinds = arm_kinds_for_topology(spec.topology_id, spec.order)
    section_g = prototype.section_g
    num_series = sum(1 for k in kinds if _is_series_kind(k))
    nodes_path = series_node_path(num_series)
    series_cursor = 0
    current_node = "in"
    elements: list[Element] = []

    for index, (kind, g_k) in enumerate(zip(kinds, section_g, strict=True), start=1):
        if _is_series_kind(kind):
            node_a = nodes_path[series_cursor]
            node_b = nodes_path[series_cursor + 1]
            series_cursor += 1
            current_node = node_b
            role = ElementRole.SERIES
        else:
            node_a = current_node
            node_b = "gnd"
            role = ElementRole.SHUNT

        if not is_resonator:
            etype, value = scale_lp_hp_arm(kind, g_k, omega_c, z0)
            ref = f"{etype}{index}"
            if etype == "C":
                elements.append(
                    IdealCapacitor(
                        id=ref,
                        value_f=value,
                        node_a=node_a,
                        node_b=node_b,
                        role=role,
                        g=g_k,
                    )
                )
            else:
                elements.append(
                    IdealInductor(
                        id=ref,
                        value_h=value,
                        node_a=node_a,
                        node_b=node_b,
                        role=role,
                        g=g_k,
                    )
                )
        else:
            l_h, c_f = scale_resonator_arm(kind, g_k, omega0, bandwidth, z0)
            ref = f"X{index}"
            if kind in ("series_series_LC", "shunt_series_LC"):
                elements.append(
                    IdealSeriesLC(
                        id=ref,
                        value_h=l_h,
                        value_f=c_f,
                        node_a=node_a,
                        node_b=node_b,
                        role=role,
                        g=g_k,
                    )
                )
            else:
                elements.append(
                    IdealParallelLC(
                        id=ref,
                        value_h=l_h,
                        value_f=c_f,
                        node_a=node_a,
                        node_b=node_b,
                        role=role,
                        g=g_k,
                    )
                )

    out_node = nodes_path[-1] if num_series > 0 else current_node
    return _circuit(
        spec, elements, out_node, z0, is_resonator, transformer_ratio
    )


def _realize_from_arms(
    spec: FilterSpec,
    prototype: Prototype,
    z0: float,
    omega_c: float,
    omega0: float,
    bandwidth: float,
    transformer_ratio: float = 1.0,
) -> Circuit:
    arms = _prepare_cauer_arms(spec, prototype)
    is_resonator = spec.response in (
        FilterResponse.BAND_PASS,
        FilterResponse.BAND_STOP,
    )
    kinds = [a.kind for a in arms]
    if is_resonator:
        # Remap kinds via scale helper
        pass
    num_series = sum(1 for k in kinds if _is_series_kind(k))
    nodes_path = series_node_path(num_series)
    series_cursor = 0
    current_node = "in"
    elements: list[Element] = []

    for index, arm in enumerate(arms, start=1):
        kind = arm.kind
        brune: dict[str, float] | None = None
        if is_resonator:
            kind, single, l_h, c_f, brune = _scale_normalized_arm_resonator(
                arm,
                omega0,
                bandwidth,
                z0,
                band_stop=spec.response == FilterResponse.BAND_STOP,
            )
        else:
            kind, single, l_h, c_f = _scale_normalized_arm(arm, omega_c, z0)

        if _is_series_kind(kind):
            node_a = nodes_path[series_cursor]
            node_b = nodes_path[series_cursor + 1]
            series_cursor += 1
            current_node = node_b
            role = ElementRole.SERIES
        else:
            node_a = current_node
            node_b = "gnd"
            role = ElementRole.SHUNT

        _append_element(
            elements,
            index=index,
            kind=kind,
            node_a=node_a,
            node_b=node_b,
            role=role,
            single=single,
            l_h=l_h,
            c_f=c_f,
            brune=brune,
        )

    out_node = nodes_path[-1] if num_series > 0 else current_node
    return _circuit(
        spec, elements, out_node, z0, is_resonator, transformer_ratio
    )


def _circuit(
    spec: FilterSpec,
    elements: list[Element],
    out_node: str,
    z0: float,
    is_resonator: bool,
    transformer_ratio: float = 1.0,
) -> Circuit:
    meta: dict[str, object] = {
        "family": spec.family.value,
        "response": spec.response.value,
        "order": spec.order,
        "cutoff_definition": spec.cutoff_definition.value,
        "z0_scale_ohm": z0,
        "output_transformer_ratio": transformer_ratio,
    }
    if is_resonator:
        meta["f_center_hz"] = spec.f_center_hz
        meta["bandwidth_hz"] = spec.bandwidth_hz
    else:
        meta["cutoff_hz"] = spec.cutoff_hz
    if spec.stopband_attenuation_db is not None:
        meta["stopband_attenuation_db"] = spec.stopband_attenuation_db
    if spec.m_parameter is not None:
        meta["m_parameter"] = spec.m_parameter

    return Circuit(
        elements=list(elements),
        port_in=Port(name="port1", node="in", impedance_ohm=spec.z_source_ohm),
        port_out=Port(name="port2", node=out_node, impedance_ohm=spec.z_load_ohm),
        ground="gnd",
        topology_id=spec.topology_id,
        meta=meta,
        output_transformer_ratio=transformer_ratio,
    )
