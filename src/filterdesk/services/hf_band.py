"""Band-filter wizard: requirements -> candidate-order table -> design.

The guided workflow is deliberately limited to Chebyshev-I. It supports every
amateur/broadcast preset and all four filter kinds, reusing the canonical
spec/synthesis/analysis path. Quick presets remain in :mod:`filterdesk.services.bands`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import AnalysisResult
from filterdesk.domain.circuit import Circuit
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
)
from filterdesk.domain.specs import FilterSpec, default_topology, validate_spec
from filterdesk.services.bands import Band, BandKind, band_sweep
from filterdesk.synthesis import synthesize


class BandFilterDesignError(ValueError):
    """Raised for an invalid band-filter design request."""


_RESPONSE: dict[BandKind, FilterResponse] = {
    BandKind.LPF: FilterResponse.LOW_PASS,
    BandKind.HPF: FilterResponse.HIGH_PASS,
    BandKind.BPF: FilterResponse.BAND_PASS,
    BandKind.BSF: FilterResponse.BAND_STOP,
}


@dataclass(frozen=True, slots=True)
class BandFilterRequest:
    band: Band
    kind: BandKind = BandKind.BPF
    z_source_ohm: float = 50.0
    z_load_ohm: float = 50.0
    passband_ripple_db: float = 0.1
    max_insertion_loss_db: float = 0.5
    min_stopband_attenuation_db: float = 30.0
    stopband_guard: float = 0.50
    max_order: int = 12
    pass_edge_hz: float | None = None
    stop_edge_hz: float | None = None

    def __post_init__(self) -> None:
        if self.z_source_ohm <= 0.0 or self.z_load_ohm <= 0.0:
            raise BandFilterDesignError("impedances must be > 0")
        if self.passband_ripple_db <= 0.0:
            raise BandFilterDesignError("passband ripple must be > 0")
        if self.max_insertion_loss_db < self.passband_ripple_db:
            raise BandFilterDesignError(
                "max insertion loss must be >= passband ripple"
            )
        if self.min_stopband_attenuation_db <= 0.0:
            raise BandFilterDesignError("stopband attenuation must be > 0")
        if not 0.0 <= self.stopband_guard < 1.0:
            raise BandFilterDesignError("stopband_guard must be in [0, 1)")
        if not 2 <= self.max_order <= 12:
            raise BandFilterDesignError("max_order must be in 2..12")
        if self.kind in (BandKind.LPF, BandKind.HPF):
            pass_edge = self.pass_edge
            stop_edge = self.stop_edge
            if pass_edge <= 0.0 or stop_edge <= 0.0:
                raise BandFilterDesignError("pass/stop edges must be > 0")
            if self.kind is BandKind.LPF and stop_edge <= pass_edge:
                raise BandFilterDesignError(
                    "LPF stop edge must be above the pass edge"
                )
            if self.kind is BandKind.HPF and stop_edge >= pass_edge:
                raise BandFilterDesignError(
                    "HPF stop edge must be below the pass edge"
                )

    @property
    def pass_edge(self) -> float:
        if self.pass_edge_hz is not None:
            return self.pass_edge_hz
        if self.kind is BandKind.LPF:
            return self.band.high_hz
        if self.kind is BandKind.HPF:
            return self.band.low_hz
        raise BandFilterDesignError("pass edge applies only to LPF/HPF")

    @property
    def stop_edge(self) -> float:
        if self.stop_edge_hz is not None:
            return self.stop_edge_hz
        if self.kind is BandKind.LPF:
            return self.band.high_hz * 1.5
        if self.kind is BandKind.HPF:
            return self.band.low_hz / 1.5
        raise BandFilterDesignError("stop edge applies only to LPF/HPF")


@dataclass(frozen=True, slots=True)
class BandFilterCandidate:
    order: int
    spec: FilterSpec
    passband_min_db: float
    stopband_low_db: float | None
    stopband_high_db: float | None
    passband_ok: bool
    stopband_ok: bool
    harmonic_2f_db: float | None = None
    harmonic_3f_db: float | None = None

    @property
    def ok(self) -> bool:
        return self.passband_ok and self.stopband_ok


@dataclass(frozen=True, slots=True)
class BandFilterResponse:
    """Passband/stopband metrics for a concrete circuit."""

    passband_min_db: float
    stopband_low_db: float | None
    stopband_high_db: float | None
    passband_ok: bool
    stopband_ok: bool
    harmonic_2f_db: float | None = None
    harmonic_3f_db: float | None = None

    @property
    def ok(self) -> bool:
        return self.passband_ok and self.stopband_ok


@dataclass(frozen=True, slots=True)
class BandFilterDesign:
    request: BandFilterRequest
    selected: BandFilterCandidate | None
    candidates: tuple[BandFilterCandidate, ...]
    analysis: AnalysisResult | None
    notes: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.selected is not None


def _spec_for(request: BandFilterRequest, order: int) -> FilterSpec:
    band = request.band
    response = _RESPONSE[request.kind]
    common: dict[str, object] = {
        "family": ApproximationFamily.CHEBYSHEV_TYPE_I,
        "response": response,
        "order": order,
        "z_source_ohm": request.z_source_ohm,
        "z_load_ohm": request.z_load_ohm,
        "topology_id": default_topology(response),
        "cutoff_definition": CutoffDefinition.RIPPLE_EDGE,
        "passband_ripple_db": request.passband_ripple_db,
    }
    if request.kind is BandKind.LPF:
        common["cutoff_hz"] = request.pass_edge
    elif request.kind is BandKind.HPF:
        common["cutoff_hz"] = request.pass_edge
    else:
        span = band.high_hz - band.low_hz
        if request.kind is BandKind.BSF:
            # Wide broadcast notches need a narrower stopband so the guard
            # region remains in the passband; narrow allocations need extra
            # stopband width to meet rejection at both allocation edges.
            multiplier = 1.50 if span / band.center_hz > 0.15 else 2.00
        else:
            multiplier = 1.20
        common["f_center_hz"] = band.center_hz
        common["bandwidth_hz"] = span * multiplier
    spec = FilterSpec(**common)  # type: ignore[arg-type]
    validate_spec(spec)
    return spec


def _at_nearest(analysis: AnalysisResult, frequency_hz: float) -> float:
    index = int(np.argmin(np.abs(analysis.frequency_hz - frequency_hz)))
    return float(mag_db(analysis.s21)[index])


def _band_mask(analysis: AnalysisResult, band: Band) -> np.ndarray:
    return (analysis.frequency_hz >= band.low_hz) & (
        analysis.frequency_hz <= band.high_hz
    )


def _passband_min_db(
    request: BandFilterRequest,
    analysis: AnalysisResult,
    s21_db: np.ndarray,
) -> float:
    band = request.band
    if request.kind is BandKind.LPF:
        mask = analysis.frequency_hz <= request.pass_edge
    elif request.kind is BandKind.HPF:
        mask = analysis.frequency_hz >= request.pass_edge
    elif request.kind is BandKind.BPF:
        mask = _band_mask(analysis, band)
    else:
        span = band.high_hz - band.low_hz
        low_pass = max(band.low_hz - span * request.stopband_guard, 1.0)
        high_pass = band.high_hz + span * request.stopband_guard
        mask = (analysis.frequency_hz <= low_pass) | (
            analysis.frequency_hz >= high_pass
        )
    if not np.any(mask):
        raise BandFilterDesignError("passband is outside the analysis sweep")
    return float(np.min(s21_db[mask]))


def _stopband(
    request: BandFilterRequest,
    analysis: AnalysisResult,
) -> tuple[float | None, float | None]:
    band = request.band
    span = band.high_hz - band.low_hz
    guard_hz = span * request.stopband_guard
    if request.kind is BandKind.LPF:
        return None, _at_nearest(analysis, request.stop_edge)
    if request.kind is BandKind.HPF:
        return _at_nearest(analysis, request.stop_edge), None
    if request.kind is BandKind.BPF:
        return (
            _at_nearest(analysis, max(band.low_hz - guard_hz, 1.0)),
            _at_nearest(analysis, band.high_hz + guard_hz),
        )
    return (
        _at_nearest(analysis, band.low_hz),
        _at_nearest(analysis, band.high_hz),
    )


def evaluate_band_filter_response(
    request: BandFilterRequest,
    circuit: Circuit,
    *,
    analysis: AnalysisResult | None = None,
) -> BandFilterResponse:
    """Evaluate a synthesized/snapped circuit against the wizard limits."""
    result = analysis or analyze_circuit(circuit, band_sweep(request.band))
    s21_db = mag_db(result.s21)
    passband_min = _passband_min_db(request, result, s21_db)
    stop_low, stop_high = _stopband(request, result)
    passband_ok = passband_min >= -request.max_insertion_loss_db
    stopband_ok = all(
        value <= -request.min_stopband_attenuation_db
        for value in (stop_low, stop_high)
        if value is not None
    )
    harmonic_2f = harmonic_3f = None
    if request.kind is BandKind.LPF:
        harmonic_2f = _at_nearest(result, request.band.high_hz * 2.0)
        harmonic_3f = _at_nearest(result, request.band.high_hz * 3.0)
    return BandFilterResponse(
        passband_min,
        stop_low,
        stop_high,
        passband_ok,
        stopband_ok,
        harmonic_2f,
        harmonic_3f,
    )


def _candidate(request: BandFilterRequest, order: int) -> BandFilterCandidate:
    spec = _spec_for(request, order)
    circuit = synthesize(spec).circuit
    analysis = analyze_circuit(circuit, band_sweep(request.band))
    response = evaluate_band_filter_response(request, circuit, analysis=analysis)
    return BandFilterCandidate(
        order=order,
        spec=spec,
        passband_min_db=response.passband_min_db,
        stopband_low_db=response.stopband_low_db,
        stopband_high_db=response.stopband_high_db,
        passband_ok=response.passband_ok,
        stopband_ok=response.stopband_ok,
        harmonic_2f_db=response.harmonic_2f_db,
        harmonic_3f_db=response.harmonic_3f_db,
    )


def _candidate_orders(request: BandFilterRequest) -> range | tuple[int, ...]:
    orders = tuple(range(2, request.max_order + 1))
    if (
        request.kind in (BandKind.BPF, BandKind.BSF)
        and request.z_source_ohm == request.z_load_ohm
    ):
        return tuple(order for order in orders if order % 2 == 1)
    return orders


def _notes(
    request: BandFilterRequest, selected: BandFilterCandidate
) -> tuple[str, ...]:
    kind_label = {
        BandKind.LPF: "LPF",
        BandKind.HPF: "HPF",
        BandKind.BPF: "BPF",
        BandKind.BSF: "BSF",
    }[request.kind]
    notes = [
        f"Chebyshev-I {kind_label}, order {selected.order}, "
        f"ripple {request.passband_ripple_db:g} dB",
    ]
    if request.kind in (BandKind.BPF, BandKind.BSF):
        if request.z_source_ohm == request.z_load_ohm:
            notes.append(
                "odd orders only for equal ports (no ideal output transformer)"
            )
        notes.append(
            f"stopband guard {request.stopband_guard * 100.0:g} % of the band span"
        )
    if request.kind is BandKind.LPF:
        notes.append("harmonic rejection reported at 2x and 3x the upper band edge")
    notes.append("snap to an E-series and re-analyze before building")
    return tuple(notes)


def design_band_filter(request: BandFilterRequest) -> BandFilterDesign:
    """Search the lowest Chebyshev-I order meeting the request."""
    candidates: list[BandFilterCandidate] = []
    selected: BandFilterCandidate | None = None
    for order in _candidate_orders(request):
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
        return BandFilterDesign(request, None, tuple(candidates), None, notes)
    analysis = analyze_circuit(
        synthesize(selected.spec).circuit,
        band_sweep(request.band),
    )
    return BandFilterDesign(
        request,
        selected,
        tuple(candidates),
        analysis,
        _notes(request, selected),
    )


HfBandDesignError = BandFilterDesignError
HfBandRequest = BandFilterRequest
HfBandCandidate = BandFilterCandidate
HfBandDesign = BandFilterDesign
design_hf_band_filter = design_band_filter


__all__ = [
    "BandFilterCandidate",
    "BandFilterResponse",
    "BandFilterDesign",
    "BandFilterDesignError",
    "BandFilterRequest",
    "HfBandCandidate",
    "HfBandDesign",
    "HfBandDesignError",
    "HfBandRequest",
    "design_band_filter",
    "design_hf_band_filter",
    "evaluate_band_filter_response",
]
