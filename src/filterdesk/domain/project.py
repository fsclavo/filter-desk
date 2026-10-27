"""Project document model (native FilterDesk file)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.circuit import (
    BalunSpec,
    Circuit,
    Element,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealResistor,
    IdealSeriesLC,
    MicrostripLineElement,
    MicrostripStubElement,
    NonIdealCapacitor,
    NonIdealInductor,
    Port,
    WindingSpec,
)
from filterdesk.domain.enums import ElementRole, MicrostripStubKind, TopologyId
from filterdesk.domain.specs import (
    FilterSpec,
    filter_spec_from_mapping,
    filter_spec_to_mapping,
)

FORMAT_VERSION = 2


def _opt_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _opt_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _winding_to_mapping(winding: WindingSpec) -> dict[str, object]:
    return {
        "kind": winding.kind,
        "core": winding.core,
        "material": winding.material,
        "turns": winding.turns,
        "turns_secondary": winding.turns_secondary,
        "topology": winding.topology,
        "impedance_ratio": winding.impedance_ratio,
        "wire_awg": winding.wire_awg,
        "wire_bare_mm": winding.wire_bare_mm,
        "wire_overall_mm": winding.wire_overall_mm,
    }


def _winding_from_mapping(data: dict[str, Any]) -> WindingSpec:
    return WindingSpec(
        kind=str(data.get("kind", "")),
        core=str(data.get("core", "")),
        material=str(data.get("material", "")),
        turns=_opt_int(data.get("turns")),
        turns_secondary=_opt_int(data.get("turns_secondary")),
        topology=str(data.get("topology", "")),
        impedance_ratio=_opt_float(data.get("impedance_ratio")),
        wire_awg=_opt_int(data.get("wire_awg")),
        wire_bare_mm=_opt_float(data.get("wire_bare_mm")),
        wire_overall_mm=_opt_float(data.get("wire_overall_mm")),
    )


@dataclass(slots=True)
class ProjectMetadata:
    title: str = "Untitled"
    author: str = ""
    app_version: str = ""
    notes: str = ""


@dataclass(slots=True)
class Project:
    """Canonical project document (ADR-004)."""

    specification: FilterSpec | None = None
    circuit: Circuit | None = None
    sweep: SweepConfig | None = None
    metadata: ProjectMetadata = field(default_factory=ProjectMetadata)
    extensions: dict[str, Any] = field(default_factory=dict)
    format_version: int = FORMAT_VERSION


def _balun_to_mapping(balun: BalunSpec) -> dict[str, object]:
    return {
        "kind": balun.kind,
        "topology": balun.topology,
        "turns_ratio": balun.turns_ratio,
        "total_turns": balun.total_turns,
        "z_unbalanced_ohm": balun.z_unbalanced_ohm,
        "z_balanced_ohm": balun.z_balanced_ohm,
        "z0_line_ohm": balun.z0_line_ohm,
        "length_m": balun.length_m,
        "velocity_factor": balun.velocity_factor,
        "loss_db_per_m": balun.loss_db_per_m,
        "leakage_h": balun.leakage_h,
        "shunt_c_f": balun.shunt_c_f,
        "core_loss_ohm": balun.core_loss_ohm,
        "common_mode_impedance_ohm": balun.common_mode_impedance_ohm,
        "magnetizing_inductance_h": balun.magnetizing_inductance_h,
        "winding_option": balun.winding_option,
        "dcr_primary_ohm": balun.dcr_primary_ohm,
        "dcr_secondary_ohm": balun.dcr_secondary_ohm,
        "core": balun.core,
        "turns": balun.turns,
        "wire_awg": balun.wire_awg,
    }


def _balun_from_mapping(data: dict[str, Any]) -> BalunSpec:
    return BalunSpec(
        kind=str(data.get("kind", "ideal")),
        topology=str(data.get("topology", "autotransformer")),
        turns_ratio=float(data.get("turns_ratio", 1.0)),
        total_turns=_opt_int(data.get("total_turns")) or 0,
        z_unbalanced_ohm=float(data.get("z_unbalanced_ohm", 0.0)),
        z_balanced_ohm=float(data.get("z_balanced_ohm", 0.0)),
        z0_line_ohm=float(data.get("z0_line_ohm", 50.0)),
        length_m=float(data.get("length_m", 0.0)),
        velocity_factor=float(data.get("velocity_factor", 1.0)),
        loss_db_per_m=float(data.get("loss_db_per_m", 0.0)),
        leakage_h=float(data.get("leakage_h", 0.0)),
        shunt_c_f=float(data.get("shunt_c_f", 0.0)),
        core_loss_ohm=_opt_float(data.get("core_loss_ohm")),
        common_mode_impedance_ohm=float(data.get("common_mode_impedance_ohm", 0.0)),
        magnetizing_inductance_h=float(data.get("magnetizing_inductance_h", 0.0)),
        winding_option=str(data.get("winding_option", "")),
        dcr_primary_ohm=_opt_float(data.get("dcr_primary_ohm")),
        dcr_secondary_ohm=_opt_float(data.get("dcr_secondary_ohm")),
        core=str(data.get("core", "")),
        turns=_opt_int(data.get("turns")),
        wire_awg=_opt_int(data.get("wire_awg")),
    )


def circuit_to_mapping(circuit: Circuit) -> dict[str, Any]:
    elements: list[dict[str, Any]] = []
    for el in circuit.elements:
        row: dict[str, Any] = {
            "id": el.id,
            "role": el.role.value,
            "type": el.element_type.value,
            "node_a": el.node_a,
            "node_b": el.node_b,
            "g": el.g,
        }
        if isinstance(el, IdealCapacitor):
            row["value_F"] = el.value_f
        elif isinstance(el, IdealInductor):
            row["value_H"] = el.value_h
        elif isinstance(el, (IdealSeriesLC, IdealParallelLC)):
            row["value_H"] = el.value_h
            row["value_F"] = el.value_f
        elif isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
            row["series_L_H"] = el.series_l_h
            row["series_C_F"] = el.series_c_f
            row["parallel_L_H"] = el.parallel_l_h
            row["parallel_C_F"] = el.parallel_c_f
        elif isinstance(el, NonIdealInductor):
            row["value_H"] = el.value_h
            row["series_R_Ohm"] = el.series_resistance_ohm
            row["parallel_C_F"] = el.parallel_capacitance_f
            if el.q_ref is not None:
                row["q_ref"] = el.q_ref
            if el.q_frequency_hz is not None:
                row["q_frequency_hz"] = el.q_frequency_hz
            if el.srf_hz is not None:
                row["srf_hz"] = el.srf_hz
            if el.loss_model != "constant":
                row["loss_model"] = el.loss_model
            if el.dc_current_a:
                row["dc_current_A"] = el.dc_current_a
            if el.saturation_current_a is not None:
                row["i_sat_A"] = el.saturation_current_a
            if el.winding is not None:
                row["winding"] = _winding_to_mapping(el.winding)
        elif isinstance(el, NonIdealCapacitor):
            row["value_F"] = el.value_f
            row["esr_Ohm"] = el.esr_ohm
            row["esl_H"] = el.esl_h
        elif isinstance(el, MicrostripLineElement):
            row["z0_Ohm"] = el.z0_ohm
            row["length_m"] = el.length_m
            row["eeff"] = el.eeff
            row["loss_db_per_m"] = el.loss_db_per_m
            row["substrate"] = el.substrate
            row["width_mm"] = el.width_mm
            row["angle_deg"] = el.angle_deg
        elif isinstance(el, MicrostripStubElement):
            row["z0_Ohm"] = el.z0_ohm
            row["length_m"] = el.length_m
            row["eeff"] = el.eeff
            row["loss_db_per_m"] = el.loss_db_per_m
            row["stub_kind"] = el.stub_kind.value
            row["substrate"] = el.substrate
            row["width_mm"] = el.width_mm
            row["angle_deg"] = el.angle_deg
        else:
            row["value_Ohm"] = el.value_ohm
        elements.append(row)
    return {
        "topology_id": (
            None if circuit.topology_id is None else circuit.topology_id.value
        ),
        "ground": circuit.ground,
        "port_in": {
            "name": circuit.port_in.name,
            "node": circuit.port_in.node,
            "impedance_ohm": circuit.port_in.impedance_ohm,
        },
        "port_out": {
            "name": circuit.port_out.name,
            "node": circuit.port_out.node,
            "impedance_ohm": circuit.port_out.impedance_ohm,
        },
        "elements": elements,
        "meta": circuit.meta,
        "output_transformer_ratio": circuit.output_transformer_ratio,
        "output_balun": (
            None
            if circuit.output_balun is None
            else _balun_to_mapping(circuit.output_balun)
        ),
    }


def circuit_from_mapping(data: dict[str, Any]) -> Circuit:
    elements: list[Element] = []
    for row in data["elements"]:
        role = ElementRole(str(row["role"]))
        etype = str(row["type"])
        gid = row.get("g")
        g = None if gid is None else float(gid)
        if etype == "capacitor":
            elements.append(
                IdealCapacitor(
                    id=str(row["id"]),
                    value_f=float(row["value_F"]),
                    node_a=str(row["node_a"]),
                    node_b=str(row["node_b"]),
                    role=role,
                    g=g,
                )
            )
        elif etype == "inductor":
            elements.append(
                IdealInductor(
                    id=str(row["id"]),
                    value_h=float(row["value_H"]),
                    node_a=str(row["node_a"]),
                    node_b=str(row["node_b"]),
                    role=role,
                    g=g,
                )
            )
        elif etype == "resistor":
            elements.append(
                IdealResistor(
                    id=str(row["id"]),
                    value_ohm=float(row["value_Ohm"]),
                    node_a=str(row["node_a"]),
                    node_b=str(row["node_b"]),
                    role=role,
                    g=g,
                )
            )
        elif etype == "series_lc":
            elements.append(
                IdealSeriesLC(
                    id=str(row["id"]),
                    value_h=float(row["value_H"]),
                    value_f=float(row["value_F"]),
                    node_a=str(row["node_a"]),
                    node_b=str(row["node_b"]),
                    role=role,
                    g=g,
                )
            )
        elif etype == "parallel_lc":
            elements.append(
                IdealParallelLC(
                    id=str(row["id"]),
                    value_h=float(row["value_H"]),
                    value_f=float(row["value_F"]),
                    node_a=str(row["node_a"]),
                    node_b=str(row["node_b"]),
                    role=role,
                    g=g,
                )
            )
        elif etype == "brune_lc":
            elements.append(
                IdealBruneLC(
                    id=str(row["id"]),
                    series_l_h=float(row["series_L_H"]),
                    series_c_f=float(row["series_C_F"]),
                    parallel_l_h=float(row["parallel_L_H"]),
                    parallel_c_f=float(row["parallel_C_F"]),
                    node_a=str(row["node_a"]),
                    node_b=str(row["node_b"]),
                    role=role,
                    g=g,
                )
            )
        elif etype == "dual_brune_lc":
            elements.append(
                IdealDualBruneLC(
                    id=str(row["id"]),
                    series_l_h=float(row["series_L_H"]),
                    series_c_f=float(row["series_C_F"]),
                    parallel_l_h=float(row["parallel_L_H"]),
                    parallel_c_f=float(row["parallel_C_F"]),
                    node_a=str(row["node_a"]),
                    node_b=str(row["node_b"]),
                    role=role,
                    g=g,
                )
            )
        elif etype == "nonideal_inductor":
            winding_raw = row.get("winding")
            winding = (
                _winding_from_mapping(winding_raw)
                if isinstance(winding_raw, dict)
                else None
            )
            elements.append(
                NonIdealInductor(
                    id=str(row["id"]),
                    value_h=float(row["value_H"]),
                    node_a=str(row["node_a"]),
                    node_b=str(row["node_b"]),
                    role=role,
                    series_resistance_ohm=float(row.get("series_R_Ohm", 0.0)),
                    parallel_capacitance_f=float(row.get("parallel_C_F", 0.0)),
                    g=g,
                    q_ref=_opt_float(row.get("q_ref")),
                    q_frequency_hz=_opt_float(row.get("q_frequency_hz")),
                    srf_hz=_opt_float(row.get("srf_hz")),
                    loss_model=str(row.get("loss_model", "constant")),
                    dc_current_a=float(row.get("dc_current_A", 0.0)),
                    saturation_current_a=_opt_float(row.get("i_sat_A")),
                    winding=winding,
                )
            )
        elif etype == "nonideal_capacitor":
            elements.append(
                NonIdealCapacitor(
                    id=str(row["id"]),
                    value_f=float(row["value_F"]),
                    node_a=str(row["node_a"]),
                    node_b=str(row["node_b"]),
                    role=role,
                    esr_ohm=float(row.get("esr_Ohm", 0.0)),
                    esl_h=float(row.get("esl_H", 0.0)),
                    g=g,
                )
            )
        elif etype == "microstrip_line":
            elements.append(
                MicrostripLineElement(
                    id=str(row["id"]),
                    z0_ohm=float(row["z0_Ohm"]),
                    length_m=float(row["length_m"]),
                    eeff=float(row["eeff"]),
                    node_a=str(row["node_a"]),
                    node_b=str(row["node_b"]),
                    role=role,
                    loss_db_per_m=float(row.get("loss_db_per_m", 0.0)),
                    substrate=str(row.get("substrate", "")),
                    width_mm=float(row.get("width_mm", 0.0)),
                    angle_deg=float(row.get("angle_deg", 0.0)),
                    g=g,
                )
            )
        elif etype == "microstrip_stub":
            elements.append(
                MicrostripStubElement(
                    id=str(row["id"]),
                    z0_ohm=float(row["z0_Ohm"]),
                    length_m=float(row["length_m"]),
                    eeff=float(row["eeff"]),
                    stub_kind=MicrostripStubKind(str(row.get("stub_kind", "open"))),
                    node_a=str(row["node_a"]),
                    node_b=str(row["node_b"]),
                    role=role,
                    loss_db_per_m=float(row.get("loss_db_per_m", 0.0)),
                    substrate=str(row.get("substrate", "")),
                    width_mm=float(row.get("width_mm", 0.0)),
                    angle_deg=float(row.get("angle_deg", 0.0)),
                    g=g,
                )
            )
        else:
            raise ValueError(f"unknown element type: {etype}")
    topo_raw = data.get("topology_id")
    topology = TopologyId(str(topo_raw)) if topo_raw else None
    pin = data["port_in"]
    pout = data["port_out"]
    return Circuit(
        elements=list(elements),
        port_in=Port(
            name=str(pin["name"]),
            node=str(pin["node"]),
            impedance_ohm=float(pin["impedance_ohm"]),
        ),
        port_out=Port(
            name=str(pout["name"]),
            node=str(pout["node"]),
            impedance_ohm=float(pout["impedance_ohm"]),
        ),
        ground=str(data.get("ground", "gnd")),
        topology_id=topology,
        meta=dict(data.get("meta") or {}),
        output_transformer_ratio=float(data.get("output_transformer_ratio", 1.0)),
        output_balun=(
            None
            if data.get("output_balun") is None
            else _balun_from_mapping(data["output_balun"])
        ),
    )


def sweep_to_mapping(sweep: SweepConfig) -> dict[str, Any]:
    return {
        "f_start_hz": sweep.f_start_hz,
        "f_stop_hz": sweep.f_stop_hz,
        "n_points": sweep.n_points,
        "spacing": sweep.spacing.value,
    }


def sweep_from_mapping(data: dict[str, Any]) -> SweepConfig:
    return SweepConfig(
        f_start_hz=float(data["f_start_hz"]),
        f_stop_hz=float(data["f_stop_hz"]),
        n_points=int(data.get("n_points", 2048)),
        spacing=SweepSpacing(str(data.get("spacing", SweepSpacing.LOGARITHMIC.value))),
    )


def project_to_mapping(project: Project) -> dict[str, Any]:
    out: dict[str, Any] = {
        "format_version": project.format_version,
        "metadata": {
            "title": project.metadata.title,
            "author": project.metadata.author,
            "app_version": project.metadata.app_version,
            "notes": project.metadata.notes,
        },
        "extensions": project.extensions,
    }
    if project.specification is not None:
        out["specification"] = filter_spec_to_mapping(project.specification)
    if project.circuit is not None:
        out["circuit"] = circuit_to_mapping(project.circuit)
    if project.sweep is not None:
        out["analysis"] = {"sweep": sweep_to_mapping(project.sweep)}
    return out


def project_from_mapping(data: dict[str, Any]) -> Project:
    version = int(data.get("format_version", FORMAT_VERSION))
    if version > FORMAT_VERSION:
        raise ValueError(f"unsupported format_version {version} (max {FORMAT_VERSION})")
    meta_raw = data.get("metadata") or {}
    meta = ProjectMetadata(
        title=str(meta_raw.get("title", "Untitled")),
        author=str(meta_raw.get("author", "")),
        app_version=str(meta_raw.get("app_version", "")),
        notes=str(meta_raw.get("notes", "")),
    )
    spec = None
    if "specification" in data and data["specification"] is not None:
        spec = filter_spec_from_mapping(data["specification"])
    circuit = None
    if "circuit" in data and data["circuit"] is not None:
        circuit = circuit_from_mapping(data["circuit"])
    sweep = None
    analysis = data.get("analysis") or {}
    if "sweep" in analysis:
        sweep = sweep_from_mapping(analysis["sweep"])
    return Project(
        specification=spec,
        circuit=circuit,
        sweep=sweep,
        metadata=meta,
        extensions=dict(data.get("extensions") or {}),
        format_version=version,
    )
