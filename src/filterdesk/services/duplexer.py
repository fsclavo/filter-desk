"""LC TX/RX duplexer with a common antenna port and isolation metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.multiport import SParameters
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import AnalysisResult, SweepConfig
from filterdesk.domain.circuit import Circuit
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.domain.specs import FilterSpec, SpecValidationError
from filterdesk.services.diplexer import DiplexerError, make_bandpass_spec
from filterdesk.synthesis import synthesize


class DuplexerError(ValueError):
    """Raised when a TX/RX duplexer cannot be designed."""


@dataclass(frozen=True, slots=True)
class DuplexerConfig:
    """TX and RX band requirements plus the isolation target."""

    tx_center_hz: float
    tx_bandwidth_hz: float
    rx_center_hz: float
    rx_bandwidth_hz: float
    order: int | None = None
    min_order: int = 3
    max_order: int = 9
    family: ApproximationFamily = ApproximationFamily.CHEBYSHEV_TYPE_I
    ripple_db: float | None = None
    stopband_attenuation_db: float | None = None
    z0_ohm: float = 50.0
    min_isolation_db: float = 60.0
    max_insertion_loss_db: float = 3.0

    def __post_init__(self) -> None:
        for name, value in (
            ("tx_center_hz", self.tx_center_hz),
            ("tx_bandwidth_hz", self.tx_bandwidth_hz),
            ("rx_center_hz", self.rx_center_hz),
            ("rx_bandwidth_hz", self.rx_bandwidth_hz),
            ("min_isolation_db", self.min_isolation_db),
            ("max_insertion_loss_db", self.max_insertion_loss_db),
        ):
            if value <= 0.0:
                raise DuplexerError(f"{name} must be > 0")
        if self.z0_ohm <= 0.0:
            raise DuplexerError("z0_ohm must be > 0")
        if self.min_order < 1:
            raise DuplexerError("min_order must be >= 1")
        if self.max_order < self.min_order:
            raise DuplexerError("max_order must be >= min_order")
        if self.order is not None and self.order < 1:
            raise DuplexerError("order must be >= 1")


@dataclass(frozen=True, slots=True)
class DuplexerMetrics:
    tx_band_hz: tuple[float, float]
    rx_band_hz: tuple[float, float]
    tx_insertion_loss_db: float | None
    rx_insertion_loss_db: float | None
    tx_return_loss_db: float | None
    rx_return_loss_db: float | None
    tx_band_isolation_db: float | None
    rx_band_isolation_db: float | None
    worst_isolation_db: float | None
    target_isolation_db: float
    max_insertion_loss_db: float
    meets_target: bool

    def summary(self) -> str:
        def value(number: float | None, unit: str = "dB") -> str:
            return "n/a" if number is None else f"{number:.2f} {unit}"

        status = "met" if self.meets_target else "NOT met"
        return (
            f"TX: IL {value(self.tx_insertion_loss_db)}, "
            f"RL {value(self.tx_return_loss_db)}, "
            f"isolation {value(self.tx_band_isolation_db)}; "
            f"RX: IL {value(self.rx_insertion_loss_db)}, "
            f"RL {value(self.rx_return_loss_db)}, "
            f"isolation {value(self.rx_band_isolation_db)}; "
            f"worst isolation {value(self.worst_isolation_db)} "
            f"(target {self.target_isolation_db:.1f} dB, {status})"
        )


@dataclass(frozen=True, slots=True)
class DuplexerDesign:
    config: DuplexerConfig
    tx_spec: FilterSpec
    rx_spec: FilterSpec
    tx_circuit: Circuit
    rx_circuit: Circuit
    tx_analysis: AnalysisResult
    rx_analysis: AnalysisResult
    network: SParameters
    metrics: DuplexerMetrics
    attempted_orders: tuple[int, ...]

    @property
    def selected_order(self) -> int:
        return self.tx_spec.order

    def summary(self) -> str:
        return (
            f"LC duplexer, order {self.selected_order}, "
            f"TX {self.config.tx_center_hz / 1e6:.6g} MHz / "
            f"RX {self.config.rx_center_hz / 1e6:.6g} MHz; "
            f"{self.metrics.summary()}"
        )


def design_duplexer(
    config: DuplexerConfig,
    sweep: SweepConfig,
    *,
    backend: str = "abcd",
) -> DuplexerDesign:
    """Design the TX/RX branches and search for the isolation target."""
    tx_band = _passband_edges(config.tx_center_hz, config.tx_bandwidth_hz)
    rx_band = _passband_edges(config.rx_center_hz, config.rx_bandwidth_hz)
    _validate_bands(tx_band, rx_band, sweep)
    orders = (
        (config.order,)
        if config.order is not None
        else tuple(range(config.min_order, config.max_order + 1))
    )
    best: DuplexerDesign | None = None
    attempted: list[int] = []
    for order in orders:
        attempted.append(order)
        try:
            design = _design_at_order(
                config, sweep, int(order), tx_band, rx_band, backend
            )
        except DuplexerError:
            if config.order is not None:
                raise
            continue
        if design.metrics.meets_target:
            return replace(design, attempted_orders=tuple(attempted))
        if best is None or _is_better(design, best):
            best = design
    if best is None:
        raise DuplexerError("no supported order could be synthesized")
    return replace(best, attempted_orders=tuple(attempted))


def _design_at_order(
    config: DuplexerConfig,
    sweep: SweepConfig,
    order: int,
    tx_band: tuple[float, float],
    rx_band: tuple[float, float],
    backend: str,
) -> DuplexerDesign:
    try:
        tx_spec = make_bandpass_spec(
            family=config.family,
            order=order,
            center_hz=config.tx_center_hz,
            bandwidth_hz=config.tx_bandwidth_hz,
            z0_ohm=config.z0_ohm,
            ripple_db=config.ripple_db,
            stopband_attenuation_db=config.stopband_attenuation_db,
        )
        rx_spec = make_bandpass_spec(
            family=config.family,
            order=order,
            center_hz=config.rx_center_hz,
            bandwidth_hz=config.rx_bandwidth_hz,
            z0_ohm=config.z0_ohm,
            ripple_db=config.ripple_db,
            stopband_attenuation_db=config.stopband_attenuation_db,
        )
        tx_synthesis = synthesize(tx_spec)
        rx_synthesis = synthesize(rx_spec)
        tx_analysis = analyze_circuit(
            tx_synthesis.circuit, sweep, backend=backend
        )
        rx_analysis = analyze_circuit(
            rx_synthesis.circuit, sweep, backend=backend
        )
    except (DiplexerError, SpecValidationError, ValueError) as exc:
        raise DuplexerError(str(exc)) from exc
    # Port 1 = antenna, port 2 = TX, port 3 = RX (independent of frequency).
    network = SParameters.parallel_branches(
        (
            SParameters.from_analysis(tx_analysis),
            SParameters.from_analysis(rx_analysis),
        )
    )
    metrics = evaluate_duplexer(
        network,
        tx_band,
        rx_band,
        target_isolation_db=config.min_isolation_db,
        max_insertion_loss_db=config.max_insertion_loss_db,
    )
    return DuplexerDesign(
        config=config,
        tx_spec=tx_spec,
        rx_spec=rx_spec,
        tx_circuit=tx_synthesis.circuit,
        rx_circuit=rx_synthesis.circuit,
        tx_analysis=tx_analysis,
        rx_analysis=rx_analysis,
        network=network,
        metrics=metrics,
        attempted_orders=(order,),
    )


def evaluate_duplexer(
    network: SParameters,
    tx_band: tuple[float, float],
    rx_band: tuple[float, float],
    *,
    target_isolation_db: float,
    max_insertion_loss_db: float,
) -> DuplexerMetrics:
    """Measure insertion loss, return loss and TX↔RX isolation."""
    if network.n_ports != 3:
        raise DuplexerError("duplexer evaluation needs a 3-port network")
    frequencies = network.frequency_hz
    tx_mask = (frequencies >= tx_band[0]) & (frequencies <= tx_band[1])
    rx_mask = (frequencies >= rx_band[0]) & (frequencies <= rx_band[1])
    if not np.any(tx_mask) or not np.any(rx_mask):
        raise DuplexerError("sweep does not cover both TX and RX passbands")
    s21 = _db(network.s[:, 1, 0])
    s31 = _db(network.s[:, 2, 0])
    s32 = _db(network.s[:, 2, 1])
    s11 = _db(network.s[:, 0, 0])
    tx_il = _max(s21, tx_mask)
    rx_il = _max(s31, rx_mask)
    tx_peak = _max(s32, tx_mask)
    rx_peak = _max(s32, rx_mask)
    tx_iso = None if tx_peak is None else -tx_peak
    rx_iso = None if rx_peak is None else -rx_peak
    worst_iso = (
        None
        if tx_iso is None or rx_iso is None
        else min(tx_iso, rx_iso)
    )
    meets = (
        worst_iso is not None
        and tx_il is not None
        and rx_il is not None
        and worst_iso >= target_isolation_db
        and tx_il <= max_insertion_loss_db
        and rx_il <= max_insertion_loss_db
    )
    return DuplexerMetrics(
        tx_band_hz=tx_band,
        rx_band_hz=rx_band,
        tx_insertion_loss_db=tx_il,
        rx_insertion_loss_db=rx_il,
        tx_return_loss_db=_min(-s11, tx_mask),
        rx_return_loss_db=_min(-s11, rx_mask),
        tx_band_isolation_db=tx_iso,
        rx_band_isolation_db=rx_iso,
        worst_isolation_db=worst_iso,
        target_isolation_db=target_isolation_db,
        max_insertion_loss_db=max_insertion_loss_db,
        meets_target=meets,
    )


def _is_better(candidate: DuplexerDesign, current: DuplexerDesign) -> bool:
    candidate_iso = candidate.metrics.worst_isolation_db
    current_iso = current.metrics.worst_isolation_db
    if candidate_iso is None:
        return False
    if current_iso is None:
        return True
    if candidate_iso != current_iso:
        return candidate_iso > current_iso
    return candidate.selected_order < current.selected_order


def _passband_edges(center_hz: float, bandwidth_hz: float) -> tuple[float, float]:
    high = 0.5 * (bandwidth_hz + math.sqrt(bandwidth_hz**2 + 4.0 * center_hz**2))
    return center_hz * center_hz / high, high


def _validate_bands(
    tx_band: tuple[float, float],
    rx_band: tuple[float, float],
    sweep: SweepConfig,
) -> None:
    if max(tx_band[0], rx_band[0]) <= min(tx_band[1], rx_band[1]):
        raise DuplexerError(
            "TX and RX passbands overlap: "
            f"TX {tx_band[0]:.6g}–{tx_band[1]:.6g} Hz, "
            f"RX {rx_band[0]:.6g}–{rx_band[1]:.6g} Hz"
        )
    low = min(tx_band[0], rx_band[0])
    high = max(tx_band[1], rx_band[1])
    if sweep.f_start_hz > low or sweep.f_stop_hz < high:
        raise DuplexerError(
            f"sweep must cover both passbands: {low:.6g}–{high:.6g} Hz"
        )


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


__all__ = [
    "DuplexerConfig",
    "DuplexerDesign",
    "DuplexerError",
    "DuplexerMetrics",
    "design_duplexer",
    "evaluate_duplexer",
]
