"""LPF + HPF diplexer built on the N-port parallel-branch model."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

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


def evaluate_diplexer(
    network: SParameters, config: DiplexerConfig
) -> DiplexerMetrics:
    """Compute passband insertion loss, rejection, return loss and crossover."""
    if network.n_ports != 3:
        raise DiplexerError("diplexer evaluation needs a 3-port network")
    frequencies = network.frequency_hz
    low_band = (float(frequencies[0]), config.low_cutoff_hz)
    high_band = (config.high_cutoff_hz, float(frequencies[-1]))
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
    "DiplexerConfig",
    "DiplexerDesign",
    "DiplexerError",
    "DiplexerMetrics",
    "design_diplexer",
    "diplexer_specs",
    "evaluate_diplexer",
]
