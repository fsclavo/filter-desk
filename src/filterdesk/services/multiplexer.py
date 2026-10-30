"""Multi-band BPF multiplexer built on the N-port parallel-branch model."""

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
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.specs import FilterSpec, SpecValidationError
from filterdesk.services.diplexer import DiplexerError, make_bandpass_spec
from filterdesk.synthesis import synthesize


class MultiplexerError(ValueError):
    """Raised when a multiplexer cannot be designed or evaluated."""


@dataclass(frozen=True, slots=True)
class MultiplexerBand:
    label: str
    center_hz: float
    bandwidth_hz: float


@dataclass(frozen=True, slots=True)
class MultiplexerConfig:
    bands: tuple[MultiplexerBand, ...]
    order: int = 5
    family: ApproximationFamily = ApproximationFamily.CHEBYSHEV_TYPE_I
    ripple_db: float | None = None
    stopband_attenuation_db: float | None = None
    z0_ohm: float = 50.0

    def __post_init__(self) -> None:
        if len(self.bands) < 2:
            raise MultiplexerError("a multiplexer needs at least two bands")
        if self.order < 1:
            raise MultiplexerError("order must be >= 1")
        if self.z0_ohm <= 0.0:
            raise MultiplexerError("z0_ohm must be > 0")
        labels = [band.label.strip() for band in self.bands]
        if any(not label for label in labels):
            raise MultiplexerError("band labels must not be empty")
        if len(set(labels)) != len(labels):
            raise MultiplexerError("band labels must be unique")
        for band in self.bands:
            if band.center_hz <= 0.0 or band.bandwidth_hz <= 0.0:
                raise MultiplexerError(
                    f"band {band.label!r} needs positive center and bandwidth"
                )


@dataclass(frozen=True, slots=True)
class MultiplexerBandMetrics:
    label: str
    band_hz: tuple[float, float]
    insertion_loss_db: float | None
    out_of_band_db: float | None
    return_loss_db: float | None


@dataclass(frozen=True, slots=True)
class MultiplexerMetrics:
    bands: tuple[MultiplexerBandMetrics, ...]
    crossovers_hz: tuple[float | None, ...]

    def summary(self) -> str:
        parts = []
        for band in self.bands:
            parts.append(
                f"{band.label}: IL {_value(band.insertion_loss_db)}, "
                f"OOB {_value(band.out_of_band_db)}, "
                f"RL {_value(band.return_loss_db)}"
            )
        crossovers = ", ".join(
            "n/a" if value is None else f"{value / 1e6:.6g} MHz"
            for value in self.crossovers_hz
        )
        return "; ".join(parts) + f"; crossovers {crossovers}"


@dataclass(frozen=True, slots=True)
class MultiplexerDesign:
    config: MultiplexerConfig
    bands: tuple[MultiplexerBand, ...]
    specs: tuple[FilterSpec, ...]
    circuits: tuple[Circuit, ...]
    analyses: tuple[AnalysisResult, ...]
    network: SParameters
    metrics: MultiplexerMetrics

    def analysis_for(self, label: str) -> AnalysisResult | None:
        for band, analysis in zip(self.bands, self.analyses, strict=True):
            if band.label == label:
                return analysis
        return None

    def summary(self) -> str:
        labels = ", ".join(band.label for band in self.bands)
        return (
            f"LC multiplexer, order {self.config.order}, "
            f"{len(self.bands)} bands ({labels}); {self.metrics.summary()}"
        )


def multiplexer_specs(
    config: MultiplexerConfig,
) -> tuple[tuple[MultiplexerBand, ...], tuple[FilterSpec, ...]]:
    bands = tuple(sorted(config.bands, key=lambda band: band.center_hz))
    specs = tuple(
        make_bandpass_spec(
            family=config.family,
            order=config.order,
            center_hz=band.center_hz,
            bandwidth_hz=band.bandwidth_hz,
            z0_ohm=config.z0_ohm,
            ripple_db=config.ripple_db,
            stopband_attenuation_db=config.stopband_attenuation_db,
        )
        for band in bands
    )
    edges = [band_edges(spec) for spec in specs]
    for previous, current in zip(edges, edges[1:], strict=False):
        if current[0] <= previous[1]:
            raise MultiplexerError(
                "adjacent passbands overlap: "
                f"{previous[0]:.6g}–{previous[1]:.6g} Hz and "
                f"{current[0]:.6g}–{current[1]:.6g} Hz"
            )
    return bands, specs


def design_multiplexer(
    config: MultiplexerConfig,
    sweep: SweepConfig,
    *,
    backend: str = "abcd",
) -> MultiplexerDesign:
    """Synthesize all BPF branches and combine them at a common input."""
    bands, specs = multiplexer_specs(config)
    edges = [band_edges(spec) for spec in specs]
    low = edges[0][0]
    high = edges[-1][1]
    if sweep.f_start_hz > low or sweep.f_stop_hz < high:
        raise MultiplexerError(
            f"sweep must cover all passbands: {low:.6g}–{high:.6g} Hz"
        )
    circuits: list[Circuit] = []
    analyses: list[AnalysisResult] = []
    try:
        for spec in specs:
            synthesis = synthesize(spec)
            circuits.append(synthesis.circuit)
            analyses.append(analyze_circuit(synthesis.circuit, sweep, backend=backend))
    except (DiplexerError, SpecValidationError, ValueError) as exc:
        raise MultiplexerError(str(exc)) from exc
    network = SParameters.parallel_branches(
        tuple(SParameters.from_analysis(analysis) for analysis in analyses)
    )
    metrics = evaluate_multiplexer(network, bands, edges)
    return MultiplexerDesign(
        config=config,
        bands=bands,
        specs=specs,
        circuits=tuple(circuits),
        analyses=tuple(analyses),
        network=network,
        metrics=metrics,
    )


def evaluate_multiplexer(
    network: SParameters,
    bands: tuple[MultiplexerBand, ...],
    edges: list[tuple[float, float]],
) -> MultiplexerMetrics:
    if network.n_ports != len(bands) + 1:
        raise MultiplexerError("network port count does not match the bands")
    frequencies = network.frequency_hz
    s11 = _db(network.s[:, 0, 0])
    outputs = [_db(network.s[:, index + 1, 0]) for index in range(len(bands))]
    rows: list[MultiplexerBandMetrics] = []
    for index, (band, (low, high)) in enumerate(zip(bands, edges, strict=True)):
        mask = (frequencies >= low) & (frequencies <= high)
        if not np.any(mask):
            raise MultiplexerError(
                f"sweep does not cover band {band.label!r}: {low:.6g}–{high:.6g} Hz"
            )
        other = [
            float(np.max(values[mask]))
            for other_index, values in enumerate(outputs)
            if other_index != index
        ]
        rows.append(
            MultiplexerBandMetrics(
                label=band.label,
                band_hz=(low, high),
                insertion_loss_db=_max(outputs[index], mask),
                out_of_band_db=max(other) if other else None,
                return_loss_db=_min(-s11, mask),
            )
        )
    crossovers = tuple(
        _crossover(frequencies, outputs[index], outputs[index + 1])
        for index in range(len(outputs) - 1)
    )
    return MultiplexerMetrics(bands=tuple(rows), crossovers_hz=crossovers)


def _crossover(
    frequencies: NDArray[np.float64],
    first_db: NDArray[np.float64],
    second_db: NDArray[np.float64],
) -> float | None:
    difference = first_db - second_db
    indices = np.flatnonzero(np.signbit(difference[:-1]) != np.signbit(difference[1:]))
    if indices.size == 0:
        return None
    index = int(indices[0])
    f0, f1 = float(frequencies[index]), float(frequencies[index + 1])
    d0, d1 = float(difference[index]), float(difference[index + 1])
    if not math.isfinite(d0) or not math.isfinite(d1) or d1 == d0:
        return f0
    return f0 + (f1 - f0) * (-d0 / (d1 - d0))


def _db(values: np.ndarray) -> NDArray[np.float64]:
    return np.asarray(
        20.0 * np.log10(np.maximum(np.abs(values), 1e-15)),
        dtype=np.float64,
    )


def _max(values: NDArray[np.float64], mask: NDArray[np.bool_]) -> float | None:
    if not np.any(mask):
        return None
    return float(np.max(values[mask]))


def _min(values: NDArray[np.float64], mask: NDArray[np.bool_]) -> float | None:
    if not np.any(mask):
        return None
    return float(np.min(values[mask]))


def _value(number: float | None) -> str:
    return "n/a" if number is None else f"{number:.2f} dB"


__all__ = [
    "MultiplexerBand",
    "MultiplexerBandMetrics",
    "MultiplexerConfig",
    "MultiplexerDesign",
    "MultiplexerError",
    "MultiplexerMetrics",
    "design_multiplexer",
    "evaluate_multiplexer",
    "multiplexer_specs",
]
