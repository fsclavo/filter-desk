"""LPF+HPF and BPF+BPF diplexers on the N-port parallel-branch model."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.metrics import band_edges
from filterdesk.analysis.multiport import SParameters
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import AnalysisResult, SweepConfig
from filterdesk.domain.circuit import Circuit
from filterdesk.domain.enums import (
    ApproximationFamily,
    FilterResponse,
)
from filterdesk.domain.specs import (
    FilterSpec,
    SpecValidationError,
    default_cutoff_definition,
    default_topology,
    validate_spec,
)
from filterdesk.synthesis import synthesize
from filterdesk.synthesis.api import SynthesisResult


class DiplexerError(ValueError):
    """Raised when a diplexer cannot be designed or evaluated."""


@dataclass(frozen=True, slots=True)
class DiplexerConfig:
    """Requirements shared by the low-pass and high-pass branches."""

    low_cutoff_hz: float
    high_cutoff_hz: float
    order: int = 5
    family: ApproximationFamily = ApproximationFamily.CHEBYSHEV_TYPE_I
    ripple_db: float | None = None
    stopband_attenuation_db: float | None = None
    z0_ohm: float = 50.0

    def __post_init__(self) -> None:
        if self.low_cutoff_hz <= 0.0 or self.high_cutoff_hz <= 0.0:
            raise DiplexerError("cutoff frequencies must be > 0")
        if self.high_cutoff_hz <= self.low_cutoff_hz:
            raise DiplexerError("high_cutoff_hz must be above low_cutoff_hz")
        if self.z0_ohm <= 0.0:
            raise DiplexerError("z0_ohm must be > 0")
        if self.order < 1:
            raise DiplexerError("order must be >= 1")


@dataclass(frozen=True, slots=True)
class BandDiplexerConfig:
    """Requirements for two band-pass branches with separate passbands."""

    low_center_hz: float
    high_center_hz: float
    low_bandwidth_hz: float
    high_bandwidth_hz: float
    order: int = 5
    family: ApproximationFamily = ApproximationFamily.CHEBYSHEV_TYPE_I
    ripple_db: float | None = None
    stopband_attenuation_db: float | None = None
    z0_ohm: float = 50.0

    def __post_init__(self) -> None:
        for name, value in (
            ("low_center_hz", self.low_center_hz),
            ("high_center_hz", self.high_center_hz),
            ("low_bandwidth_hz", self.low_bandwidth_hz),
            ("high_bandwidth_hz", self.high_bandwidth_hz),
        ):
            if value <= 0.0:
                raise DiplexerError(f"{name} must be > 0")
        if self.high_center_hz <= self.low_center_hz:
            raise DiplexerError("high_center_hz must be above low_center_hz")
        if self.z0_ohm <= 0.0:
            raise DiplexerError("z0_ohm must be > 0")
        if self.order < 1:
            raise DiplexerError("order must be >= 1")


@dataclass(frozen=True, slots=True)
class DiplexerMetrics:
    low_band_hz: tuple[float, float]
    high_band_hz: tuple[float, float]
    low_insertion_loss_db: float | None
    low_out_of_band_db: float | None
    low_return_loss_db: float | None
    high_insertion_loss_db: float | None
    high_out_of_band_db: float | None
    high_return_loss_db: float | None
    crossover_hz: float | None

    def summary(self) -> str:
        def value(number: float | None, unit: str = "dB") -> str:
            return "n/a" if number is None else f"{number:.2f} {unit}"

        return (
            f"Low path: IL {value(self.low_insertion_loss_db)}, "
            f"rejection {value(self.low_out_of_band_db)}, "
            f"RL {value(self.low_return_loss_db)}; "
            f"high path: IL {value(self.high_insertion_loss_db)}, "
            f"rejection {value(self.high_out_of_band_db)}, "
            f"RL {value(self.high_return_loss_db)}; "
            f"crossover {value(self.crossover_hz, 'Hz')}"
        )


@dataclass(frozen=True, slots=True)
class DiplexerDesign:
    config: DiplexerConfig
    low_spec: FilterSpec
    high_spec: FilterSpec
    low_circuit: Circuit
    high_circuit: Circuit
    low_analysis: AnalysisResult
    high_analysis: AnalysisResult
    network: SParameters
    metrics: DiplexerMetrics


@dataclass(frozen=True, slots=True)
class BandDiplexerDesign:
    config: BandDiplexerConfig
    low_spec: FilterSpec
    high_spec: FilterSpec
    low_circuit: Circuit
    high_circuit: Circuit
    low_analysis: AnalysisResult
    high_analysis: AnalysisResult
    network: SParameters
    metrics: DiplexerMetrics


def diplexer_specs(config: DiplexerConfig) -> tuple[FilterSpec, FilterSpec]:
    """Build the low-pass and high-pass branch specifications."""
    low = _branch_spec(
        config,
        FilterResponse.LOW_PASS,
        config.low_cutoff_hz,
    )
    high = _branch_spec(
        config,
        FilterResponse.HIGH_PASS,
        config.high_cutoff_hz,
    )
    return low, high


def band_diplexer_specs(
    config: BandDiplexerConfig,
) -> tuple[FilterSpec, FilterSpec]:
    """Build two band-pass specifications and reject overlapping passbands."""
    low = _band_spec(config, config.low_center_hz, config.low_bandwidth_hz)
    high = _band_spec(config, config.high_center_hz, config.high_bandwidth_hz)
    low_low, low_high = band_edges(low)
    high_low, high_high = band_edges(high)
    if high_low <= low_high:
        raise DiplexerError(
            "band-pass passbands overlap: "
            f"low ends at {low_high:.6g} Hz, high starts at {high_low:.6g} Hz"
        )
    return low, high


def make_bandpass_spec(
    *,
    family: ApproximationFamily,
    order: int,
    center_hz: float,
    bandwidth_hz: float,
    z0_ohm: float,
    ripple_db: float | None = None,
    stopband_attenuation_db: float | None = None,
) -> FilterSpec:
    """Build and validate one band-pass branch specification."""
    ripple = ripple_db
    stopband = stopband_attenuation_db
    if family in (
        ApproximationFamily.CHEBYSHEV_TYPE_I,
        ApproximationFamily.ELLIPTIC,
    ):
        if ripple is None:
            ripple = 0.1
        stopband = stopband if family == ApproximationFamily.ELLIPTIC else None
    elif family == ApproximationFamily.CHEBYSHEV_TYPE_II:
        if stopband is None:
            raise DiplexerError(
                "chebyshev_type_ii requires stopband_attenuation_db"
            )
        ripple = None
    else:
        ripple = None
        stopband = None
    spec = FilterSpec(
        family=family,
        response=FilterResponse.BAND_PASS,
        order=order,
        f_center_hz=center_hz,
        bandwidth_hz=bandwidth_hz,
        z_source_ohm=z0_ohm,
        z_load_ohm=z0_ohm,
        topology_id=default_topology(FilterResponse.BAND_PASS),
        cutoff_definition=default_cutoff_definition(family),
        passband_ripple_db=ripple,
        stopband_attenuation_db=stopband,
    )
    try:
        validate_spec(spec)
    except SpecValidationError as exc:
        raise DiplexerError(str(exc)) from exc
    return spec


def _band_spec(
    config: BandDiplexerConfig,
    center_hz: float,
    bandwidth_hz: float,
) -> FilterSpec:
    return make_bandpass_spec(
        family=config.family,
        order=config.order,
        center_hz=center_hz,
        bandwidth_hz=bandwidth_hz,
        z0_ohm=config.z0_ohm,
        ripple_db=config.ripple_db,
        stopband_attenuation_db=config.stopband_attenuation_db,
    )


def _branch_spec(
    config: DiplexerConfig,
    response: FilterResponse,
    cutoff_hz: float,
) -> FilterSpec:
    family = config.family
    ripple = config.ripple_db
    stopband = config.stopband_attenuation_db
    if family in (
        ApproximationFamily.CHEBYSHEV_TYPE_I,
        ApproximationFamily.ELLIPTIC,
    ):
        if ripple is None:
            ripple = 0.1
        stopband = stopband if family == ApproximationFamily.ELLIPTIC else None
    elif family == ApproximationFamily.CHEBYSHEV_TYPE_II:
        if stopband is None:
            raise DiplexerError(
                "chebyshev_type_ii requires stopband_attenuation_db"
            )
        ripple = None
    else:
        ripple = None
        stopband = None
    spec = FilterSpec(
        family=family,
        response=response,
        order=config.order,
        cutoff_hz=cutoff_hz,
        z_source_ohm=config.z0_ohm,
        z_load_ohm=config.z0_ohm,
        topology_id=default_topology(response),
        cutoff_definition=default_cutoff_definition(family),
        passband_ripple_db=ripple,
        stopband_attenuation_db=stopband,
    )
    try:
        validate_spec(spec)
    except SpecValidationError as exc:
        raise DiplexerError(str(exc)) from exc
    return spec


def design_diplexer(
    config: DiplexerConfig,
    sweep: SweepConfig,
    *,
    backend: str = "abcd",
) -> DiplexerDesign:
    """Synthesize both branches, analyze them and build the common 3-port."""
    low_spec, high_spec = diplexer_specs(config)
    low_synthesis, high_synthesis, low_analysis, high_analysis, network = (
        _analyze_branches(low_spec, high_spec, sweep, backend)
    )
    metrics = evaluate_diplexer(network, config)
    return DiplexerDesign(
        config=config,
        low_spec=low_spec,
        high_spec=high_spec,
        low_circuit=low_synthesis.circuit,
        high_circuit=high_synthesis.circuit,
        low_analysis=low_analysis,
        high_analysis=high_analysis,
        network=network,
        metrics=metrics,
    )


def design_band_diplexer(
    config: BandDiplexerConfig,
    sweep: SweepConfig,
    *,
    backend: str = "abcd",
) -> BandDiplexerDesign:
    """Synthesize two BPF branches and build the common 3-port."""
    low_spec, high_spec = band_diplexer_specs(config)
    low_edges = band_edges(low_spec)
    high_edges = band_edges(high_spec)
    if sweep.f_start_hz > low_edges[0] or sweep.f_stop_hz < high_edges[1]:
        raise DiplexerError(
            "sweep must cover both band-pass passbands: "
            f"{low_edges[0]:.6g}–{high_edges[1]:.6g} Hz"
        )
    low_synthesis, high_synthesis, low_analysis, high_analysis, network = (
        _analyze_branches(low_spec, high_spec, sweep, backend)
    )
    metrics = evaluate_diplexer_bands(network, low_edges, high_edges)
    return BandDiplexerDesign(
        config=config,
        low_spec=low_spec,
        high_spec=high_spec,
        low_circuit=low_synthesis.circuit,
        high_circuit=high_synthesis.circuit,
        low_analysis=low_analysis,
        high_analysis=high_analysis,
        network=network,
        metrics=metrics,
    )


def _analyze_branches(
    low_spec: FilterSpec,
    high_spec: FilterSpec,
    sweep: SweepConfig,
    backend: str,
) -> tuple[
    SynthesisResult, SynthesisResult, AnalysisResult, AnalysisResult, SParameters
]:
    try:
        low_synthesis = synthesize(low_spec)
        high_synthesis = synthesize(high_spec)
        low_analysis = analyze_circuit(
            low_synthesis.circuit, sweep, backend=backend
        )
        high_analysis = analyze_circuit(
            high_synthesis.circuit, sweep, backend=backend
        )
    except (SpecValidationError, ValueError) as exc:
        raise DiplexerError(str(exc)) from exc
    low_network = SParameters.from_analysis(low_analysis)
    high_network = SParameters.from_analysis(high_analysis)
    network = SParameters.parallel_branches((low_network, high_network))
    return (
        low_synthesis,
        high_synthesis,
        low_analysis,
        high_analysis,
        network,
    )


def evaluate_diplexer(
    network: SParameters, config: DiplexerConfig
) -> DiplexerMetrics:
    """Compute passband insertion loss, rejection, return loss and crossover."""
    if network.n_ports != 3:
        raise DiplexerError("diplexer evaluation needs a 3-port network")
    low_band = (float(network.frequency_hz[0]), config.low_cutoff_hz)
    high_band = (config.high_cutoff_hz, float(network.frequency_hz[-1]))
    return evaluate_diplexer_bands(network, low_band, high_band)


def evaluate_diplexer_bands(
    network: SParameters,
    low_band: tuple[float, float],
    high_band: tuple[float, float],
) -> DiplexerMetrics:
    """Evaluate a 3-port diplexer over explicit low/high passbands."""
    if network.n_ports != 3:
        raise DiplexerError("diplexer evaluation needs a 3-port network")
    frequencies = network.frequency_hz
    low_mask = (frequencies >= low_band[0]) & (frequencies <= low_band[1])
    high_mask = (frequencies >= high_band[0]) & (frequencies <= high_band[1])

    low_to_low = _db(network.s[:, 1, 0])
    low_to_high = _db(network.s[:, 2, 0])
    high_to_high = _db(network.s[:, 2, 0])
    high_to_low = _db(network.s[:, 1, 0])
    input_rl = -_db(network.s[:, 0, 0])

    return DiplexerMetrics(
        low_band_hz=low_band,
        high_band_hz=high_band,
        low_insertion_loss_db=_max(low_to_low, low_mask),
        low_out_of_band_db=_max(low_to_high, low_mask),
        low_return_loss_db=_min(input_rl, low_mask),
        high_insertion_loss_db=_max(high_to_high, high_mask),
        high_out_of_band_db=_max(high_to_low, high_mask),
        high_return_loss_db=_min(input_rl, high_mask),
        crossover_hz=_crossover(frequencies, low_to_low, high_to_high),
    )


def evaluate_band_diplexer(
    network: SParameters, config: BandDiplexerConfig
) -> DiplexerMetrics:
    low_spec, high_spec = band_diplexer_specs(config)
    return evaluate_diplexer_bands(
        network, band_edges(low_spec), band_edges(high_spec)
    )


def _db(values: np.ndarray) -> NDArray[np.float64]:
    return np.asarray(
        20.0 * np.log10(np.maximum(np.abs(values), 1e-15)),
        dtype=np.float64,
    )


def _max(values: np.ndarray, mask: np.ndarray) -> float | None:
    if not np.any(mask):
        return None
    return float(np.max(values[mask]))


def _min(values: np.ndarray, mask: np.ndarray) -> float | None:
    if not np.any(mask):
        return None
    return float(np.min(values[mask]))


def _crossover(
    frequencies: np.ndarray, low_db: np.ndarray, high_db: np.ndarray
) -> float | None:
    difference = low_db - high_db
    indices = np.flatnonzero(np.signbit(difference[:-1]) != np.signbit(difference[1:]))
    if indices.size == 0:
        return None
    index = int(indices[0])
    f0, f1 = float(frequencies[index]), float(frequencies[index + 1])
    d0, d1 = float(difference[index]), float(difference[index + 1])
    if not math.isfinite(d0) or not math.isfinite(d1) or d1 == d0:
        return f0
    return f0 + (f1 - f0) * (-d0 / (d1 - d0))


__all__ = [
    "BandDiplexerConfig",
    "BandDiplexerDesign",
    "DiplexerConfig",
    "DiplexerDesign",
    "DiplexerError",
    "DiplexerMetrics",
    "band_diplexer_specs",
    "design_band_diplexer",
    "design_diplexer",
    "diplexer_specs",
    "make_bandpass_spec",
    "evaluate_band_diplexer",
    "evaluate_diplexer",
    "evaluate_diplexer_bands",
]
