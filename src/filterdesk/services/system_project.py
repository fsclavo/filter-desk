"""Versioned JSON project for the diplexer/duplexer/multiplexer designer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std import ESeries
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.services.system_parasitics import SystemParasiticsConfig

_FORMAT = "filterdesk.system"
_VERSION = 1
_KINDS = {"lp-hp", "bp-bp", "duplexer", "triplexer", "multiplexer"}


class SystemProjectError(ValueError):
    """Raised for an invalid or unsupported system project."""


@dataclass(frozen=True, slots=True)
class SystemBand:
    label: str
    center_hz: float
    bandwidth_hz: float


@dataclass(frozen=True, slots=True)
class SystemProject:
    kind: str
    order: int
    family: ApproximationFamily
    ripple_db: float | None
    stopband_attenuation_db: float | None
    z0_ohm: float
    sweep: SweepConfig
    snap_series: ESeries | None = None
    parasitics: SystemParasiticsConfig | None = None
    bands: tuple[SystemBand, ...] = ()
    low_cutoff_hz: float | None = None
    high_cutoff_hz: float | None = None
    tx_center_hz: float | None = None
    tx_bandwidth_hz: float | None = None
    rx_center_hz: float | None = None
    rx_bandwidth_hz: float | None = None
    min_isolation_db: float = 60.0
    max_insertion_loss_db: float = 3.0
    auto_order: bool = True
    max_order: int = 9

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise SystemProjectError(f"unsupported system kind: {self.kind!r}")
        if self.order < 1:
            raise SystemProjectError("order must be >= 1")
        if self.z0_ohm <= 0.0:
            raise SystemProjectError("z0_ohm must be > 0")
        if self.kind == "lp-hp":
            if self.low_cutoff_hz is None or self.high_cutoff_hz is None:
                raise SystemProjectError("lp-hp needs low/high cutoff")
            if self.high_cutoff_hz <= self.low_cutoff_hz:
                raise SystemProjectError("high cutoff must be above low cutoff")
        elif self.kind in {"bp-bp", "triplexer", "multiplexer"}:
            expected = (
                2
                if self.kind == "bp-bp"
                else 3
                if self.kind == "triplexer"
                else None
            )
            if len(self.bands) < 2:
                raise SystemProjectError("at least two bands are required")
            if expected is not None and len(self.bands) != expected:
                raise SystemProjectError(
                    f"{self.kind} needs exactly {expected} bands"
                )
        elif self.kind == "duplexer":
            if any(
                value is None
                for value in (
                    self.tx_center_hz,
                    self.tx_bandwidth_hz,
                    self.rx_center_hz,
                    self.rx_bandwidth_hz,
                )
            ):
                raise SystemProjectError("duplexer needs TX and RX center/bandwidth")


def system_project_to_mapping(project: SystemProject) -> dict[str, Any]:
    """Serialize a system project to a JSON-ready mapping."""
    return {
        "format": _FORMAT,
        "version": _VERSION,
        "kind": project.kind,
        "order": project.order,
        "family": project.family.value,
        "ripple_db": project.ripple_db,
        "stopband_attenuation_db": project.stopband_attenuation_db,
        "z0_ohm": project.z0_ohm,
        "sweep": {
            "f_start_hz": project.sweep.f_start_hz,
            "f_stop_hz": project.sweep.f_stop_hz,
            "n_points": project.sweep.n_points,
            "spacing": project.sweep.spacing.value,
        },
        "snap_series": (
            None if project.snap_series is None else project.snap_series.value
        ),
        "parasitics": _parasitics_to_mapping(project.parasitics),
        "bands": [
            {
                "label": band.label,
                "center_hz": band.center_hz,
                "bandwidth_hz": band.bandwidth_hz,
            }
            for band in project.bands
        ],
        "low_cutoff_hz": project.low_cutoff_hz,
        "high_cutoff_hz": project.high_cutoff_hz,
        "tx_center_hz": project.tx_center_hz,
        "tx_bandwidth_hz": project.tx_bandwidth_hz,
        "rx_center_hz": project.rx_center_hz,
        "rx_bandwidth_hz": project.rx_bandwidth_hz,
        "min_isolation_db": project.min_isolation_db,
        "max_insertion_loss_db": project.max_insertion_loss_db,
        "auto_order": project.auto_order,
        "max_order": project.max_order,
    }


def system_project_from_mapping(data: MappingLike) -> SystemProject:
    """Parse and validate a JSON-like system project mapping."""
    if data.get("format") != _FORMAT:
        raise SystemProjectError(f"unsupported format: {data.get('format')!r}")
    if data.get("version") != _VERSION:
        raise SystemProjectError(f"unsupported version: {data.get('version')!r}")
    try:
        sweep_data = data["sweep"]
        sweep = SweepConfig(
            f_start_hz=float(sweep_data["f_start_hz"]),
            f_stop_hz=float(sweep_data["f_stop_hz"]),
            n_points=int(sweep_data["n_points"]),
            spacing=SweepSpacing(str(sweep_data["spacing"])),
        )
        bands = tuple(
            SystemBand(
                label=str(band["label"]),
                center_hz=float(band["center_hz"]),
                bandwidth_hz=float(band["bandwidth_hz"]),
            )
            for band in data.get("bands", [])
        )
        snap_raw = data.get("snap_series")
        parasitics_raw = data.get("parasitics")
        project = SystemProject(
            kind=str(data["kind"]),
            order=int(data["order"]),
            family=ApproximationFamily(str(data["family"])),
            ripple_db=_optional_float(data.get("ripple_db")),
            stopband_attenuation_db=_optional_float(
                data.get("stopband_attenuation_db")
            ),
            z0_ohm=float(data["z0_ohm"]),
            sweep=sweep,
            snap_series=ESeries(str(snap_raw)) if snap_raw else None,
            parasitics=(
                _parasitics_from_mapping(parasitics_raw)
                if parasitics_raw
                else None
            ),
            bands=bands,
            low_cutoff_hz=_optional_float(data.get("low_cutoff_hz")),
            high_cutoff_hz=_optional_float(data.get("high_cutoff_hz")),
            tx_center_hz=_optional_float(data.get("tx_center_hz")),
            tx_bandwidth_hz=_optional_float(data.get("tx_bandwidth_hz")),
            rx_center_hz=_optional_float(data.get("rx_center_hz")),
            rx_bandwidth_hz=_optional_float(data.get("rx_bandwidth_hz")),
            min_isolation_db=float(data.get("min_isolation_db", 60.0)),
            max_insertion_loss_db=float(
                data.get("max_insertion_loss_db", 3.0)
            ),
            auto_order=bool(data.get("auto_order", True)),
            max_order=int(data.get("max_order", 9)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, SystemProjectError):
            raise
        raise SystemProjectError(f"invalid system project: {exc}") from exc
    return project


def read_system_project(path: Path | str) -> SystemProject:
    """Read a ``.fdsys.json`` system project from disk."""
    target = Path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemProjectError(f"cannot read {target}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemProjectError("system project root must be an object")
    return system_project_from_mapping(data)


def write_system_project(project: SystemProject, path: Path | str) -> Path:
    """Write a ``.fdsys.json`` system project."""
    target = Path(path)
    target.write_text(
        json.dumps(system_project_to_mapping(project), indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def _parasitics_to_mapping(
    config: SystemParasiticsConfig | None,
) -> dict[str, Any] | None:
    if config is None:
        return None
    return {
        "inductor_q": config.inductor_q,
        "inductor_dcr_ohm": config.inductor_dcr_ohm,
        "inductor_parallel_capacitance_f": (
            config.inductor_parallel_capacitance_f
        ),
        "inductor_srf_hz": config.inductor_srf_hz,
        "capacitor_esr_ohm": config.capacitor_esr_ohm,
        "capacitor_esl_h": config.capacitor_esl_h,
        "inductor_loss_model": config.inductor_loss_model,
    }


def _parasitics_from_mapping(data: MappingLike) -> SystemParasiticsConfig:
    return SystemParasiticsConfig(
        inductor_q=_optional_float(data.get("inductor_q")),
        inductor_dcr_ohm=float(data.get("inductor_dcr_ohm", 0.0)),
        inductor_parallel_capacitance_f=float(
            data.get("inductor_parallel_capacitance_f", 0.0)
        ),
        inductor_srf_hz=_optional_float(data.get("inductor_srf_hz")),
        capacitor_esr_ohm=float(data.get("capacitor_esr_ohm", 0.0)),
        capacitor_esl_h=float(data.get("capacitor_esl_h", 0.0)),
        inductor_loss_model=str(data.get("inductor_loss_model", "constant")),
    )


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


MappingLike = dict[str, Any]


__all__ = [
    "SystemBand",
    "SystemProject",
    "SystemProjectError",
    "read_system_project",
    "system_project_from_mapping",
    "system_project_to_mapping",
    "write_system_project",
]
