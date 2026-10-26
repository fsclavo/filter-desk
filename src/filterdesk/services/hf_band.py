"""HF receive-band filter workflow: requirements -> order search -> design.

The first product workflow is intentionally narrow: a Chebyshev-I band-pass
filter for an amateur HF allocation, with editable impedance/passband/rejection
requirements. It reuses the canonical spec/synthesis/analysis path.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import AnalysisResult
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
)
from filterdesk.domain.specs import FilterSpec, default_topology, validate_spec
from filterdesk.services.bands import Band, band_sweep
from filterdesk.synthesis import synthesize


class HfBandDesignError(ValueError):
    """Raised for an invalid HF-band design request."""


@dataclass(frozen=True, slots=True)
class HfBandRequest:
    band: Band
    z_source_ohm: float = 50.0
    z_load_ohm: float = 50.0
    passband_ripple_db: float = 0.1
    max_insertion_loss_db: float = 0.5
    min_stopband_attenuation_db: float = 30.0
    stopband_guard: float = 0.50
    max_order: int = 8

    def __post_init__(self) -> None:
        if self.z_source_ohm <= 0.0 or self.z_load_ohm <= 0.0:
            raise HfBandDesignError("impedances must be > 0")
        if self.passband_ripple_db <= 0.0:
            raise HfBandDesignError("passband ripple must be > 0")
        if self.max_insertion_loss_db <= 0.0:
            raise HfBandDesignError("max insertion loss must be > 0")
        if self.min_stopband_attenuation_db <= 0.0:
            raise HfBandDesignError("stopband attenuation must be > 0")
        if not 0.0 <= self.stopband_guard < 1.0:
            raise HfBandDesignError("stopband_guard must be in [0, 1)")
        if not 2 <= self.max_order <= 12:
            raise HfBandDesignError("max_order must be in 2..12")


@dataclass(frozen=True, slots=True)
class HfBandCandidate:
    order: int
    spec: FilterSpec
    passband_min_db: float
    stopband_low_db: float
    stopband_high_db: float
    passband_ok: bool
    stopband_ok: bool

    @property
    def ok(self) -> bool:
        return self.passband_ok and self.stopband_ok


@dataclass(frozen=True, slots=True)
class HfBandDesign:
    request: HfBandRequest
    selected: HfBandCandidate | None
    candidates: tuple[HfBandCandidate, ...]
    analysis: AnalysisResult | None
    notes: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.selected is not None


def _spec_for(request: HfBandRequest, order: int) -> FilterSpec:
    band = request.band
    allocation = band.high_hz - band.low_hz
    # Leave a small design margin so the entire allocation is in the passband.
    bandwidth = allocation * 1.20
    spec = FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.BAND_PASS,
        order=order,
        f_center_hz=band.center_hz,
        bandwidth_hz=bandwidth,
        passband_ripple_db=request.passband_ripple_db,
        z_source_ohm=request.z_source_ohm,
        z_load_ohm=request.z_load_ohm,
        topology_id=default_topology(FilterResponse.BAND_PASS),
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
    )
    validate_spec(spec)
    return spec


def _at_nearest(analysis: AnalysisResult, frequency_hz: float) -> float:
    index = int(np.argmin(np.abs(analysis.frequency_hz - frequency_hz)))
    return float(mag_db(analysis.s21)[index])


def _candidate(request: HfBandRequest, order: int) -> HfBandCandidate:
    spec = _spec_for(request, order)
    circuit = synthesize(spec).circuit
    sweep = band_sweep(request.band)
    # band_sweep covers 0.5*low .. 5*high; enough for both rejection points.
    analysis = analyze_circuit(circuit, sweep)
    band_mask = (
        (analysis.frequency_hz >= request.band.low_hz)
        & (analysis.frequency_hz <= request.band.high_hz)
    )
    if not np.any(band_mask):
        raise HfBandDesignError("selected band is outside the analysis sweep")
    passband_min = float(np.min(mag_db(analysis.s21)[band_mask]))
    span = request.band.high_hz - request.band.low_hz
    guard_hz = span * request.stopband_guard
    low_stop = max(request.band.low_hz - guard_hz, 1.0)
    high_stop = request.band.high_hz + guard_hz
    low_db = _at_nearest(analysis, low_stop)
    high_db = _at_nearest(analysis, high_stop)
    passband_ok = passband_min >= -request.max_insertion_loss_db
    stopband_ok = (
        low_db <= -request.min_stopband_attenuation_db
        and high_db <= -request.min_stopband_attenuation_db
    )
    return HfBandCandidate(
        order=order,
        spec=spec,
        passband_min_db=passband_min,
        stopband_low_db=low_db,
        stopband_high_db=high_db,
        passband_ok=passband_ok,
        stopband_ok=stopband_ok,
    )


def design_hf_band_filter(request: HfBandRequest) -> HfBandDesign:
    """Search the lowest Chebyshev-I BPF order meeting the request."""
    candidates: list[HfBandCandidate] = []
    selected: HfBandCandidate | None = None
    for order in range(2, request.max_order + 1):
        candidate = _candidate(request, order)
        candidates.append(candidate)
        if candidate.ok:
            selected = candidate
            break
    if selected is None:
        notes: tuple[str, ...] = (
            "no order up to the configured maximum met the requirements",
            "lower the rejection requirement, widen the guard or increase max_order",
        )
        return HfBandDesign(request, None, tuple(candidates), None, notes)
    analysis = analyze_circuit(
        synthesize(selected.spec).circuit,
        band_sweep(request.band),
    )
    notes = (
        f"Chebyshev-I BPF, order {selected.order}, "
        f"ripple {request.passband_ripple_db:g} dB",
        "passband includes a 20 % design-bandwidth margin",
        "snap to an E-series and re-analyze before building",
    )
    return HfBandDesign(request, selected, tuple(candidates), analysis, notes)


__all__ = [
    "HfBandCandidate",
    "HfBandDesign",
    "HfBandDesignError",
    "HfBandRequest",
    "design_hf_band_filter",
]
