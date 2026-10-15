"""Retune (redesign-on-change) a filter specification (FR-U2).

Tuning frequencies / impedances re-runs synthesis for the same family, order and
topology. The helpers here only produce a **new validated spec**; the caller
(session/GUI) re-synthesizes and re-analyzes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from filterdesk.domain.enums import FilterResponse
from filterdesk.domain.specs import (
    FilterSpec,
    SpecValidationError,
    filter_spec_from_mapping,
    filter_spec_to_mapping,
)

_BAND = (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP)


@dataclass(frozen=True, slots=True)
class RetuneRequest:
    """Fields to override on the current spec (``None`` = keep)."""

    cutoff_hz: float | None = None
    f_center_hz: float | None = None
    bandwidth_hz: float | None = None
    z_source_ohm: float | None = None
    z_load_ohm: float | None = None


def retune_spec(spec: FilterSpec, request: RetuneRequest) -> FilterSpec:
    """Apply the non-``None`` request fields and validate the result."""
    mapping: dict[str, Any] = filter_spec_to_mapping(spec)
    if request.cutoff_hz is not None:
        mapping["cutoff_hz"] = request.cutoff_hz
    if request.f_center_hz is not None:
        mapping["f_center_hz"] = request.f_center_hz
    if request.bandwidth_hz is not None:
        mapping["bandwidth_hz"] = request.bandwidth_hz
    if request.z_source_ohm is not None:
        mapping["z_source_ohm"] = request.z_source_ohm
    if request.z_load_ohm is not None:
        mapping["z_load_ohm"] = request.z_load_ohm
    return filter_spec_from_mapping(mapping)


def retune_cutoff(spec: FilterSpec, cutoff_hz: float) -> FilterSpec:
    """Change the LP/HP cutoff frequency."""
    if spec.response in _BAND:
        raise SpecValidationError("retune_cutoff applies to LP/HP only")
    return retune_spec(spec, RetuneRequest(cutoff_hz=cutoff_hz))


def retune_center(spec: FilterSpec, f_center_hz: float) -> FilterSpec:
    """Move a BP/BS center frequency, keeping the current bandwidth."""
    if spec.response not in _BAND:
        raise SpecValidationError("retune_center applies to BP/BS only")
    return retune_spec(spec, RetuneRequest(f_center_hz=f_center_hz))


def retune_bandwidth(spec: FilterSpec, bandwidth_hz: float) -> FilterSpec:
    """Change a BP/BS bandwidth, keeping the current center."""
    if spec.response not in _BAND:
        raise SpecValidationError("retune_bandwidth applies to BP/BS only")
    return retune_spec(spec, RetuneRequest(bandwidth_hz=bandwidth_hz))


def scale_response(spec: FilterSpec, factor: float) -> FilterSpec:
    """Scale all frequency landmarks by ``factor`` (constant relative shape).

    LP/HP scale the cutoff; BP/BS scale center **and** bandwidth together, so the
    fractional bandwidth is preserved.
    """
    if factor <= 0.0:
        raise SpecValidationError("scale factor must be > 0")
    if spec.response in _BAND:
        assert spec.f_center_hz is not None and spec.bandwidth_hz is not None
        return retune_spec(
            spec,
            RetuneRequest(
                f_center_hz=spec.f_center_hz * factor,
                bandwidth_hz=spec.bandwidth_hz * factor,
            ),
        )
    return retune_spec(spec, RetuneRequest(cutoff_hz=spec.cutoff_hz * factor))


def nudge_value(value: float, step_fraction: float, direction: int) -> float:
    """Multiplicative single-step tune: ``value · (1 + direction·step)``.

    ``direction`` is ``+1`` (up) or ``-1`` (down); the result must stay positive.
    """
    if step_fraction <= 0.0:
        raise ValueError("step_fraction must be > 0")
    if direction not in (-1, 1):
        raise ValueError("direction must be +1 or -1")
    new_value = value * (1.0 + direction * step_fraction)
    if new_value <= 0.0:
        raise ValueError("tuned value would not be positive")
    return new_value
