"""Monte-Carlo tolerance / yield analysis for system designs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from filterdesk.domain.circuit import Circuit
from filterdesk.montecarlo import (
    ElementTolerance,
    MonteCarloConfig,
    ToleranceDistribution,
    perturb_circuit,
)
from filterdesk.services.duplexer import DuplexerDesign
from filterdesk.services.multiplexer import MultiplexerDesign
from filterdesk.services.system_rebuild import SystemDesign, rebuild_system_design


class SystemMonteCarloError(ValueError):
    """Raised when a system Monte-Carlo run cannot be completed."""


@dataclass(frozen=True, slots=True)
class SystemMonteCarloConfig:
    n_trials: int = 200
    tolerance_pct: float = 2.0
    distribution: ToleranceDistribution = ToleranceDistribution.UNIFORM
    seed: int | None = None
    max_insertion_loss_db: float = 3.0
    max_out_of_band_db: float = -15.0
    min_isolation_db: float | None = None
    overrides: dict[str, ElementTolerance] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.n_trials < 1:
            raise ValueError("n_trials must be >= 1")
        if self.tolerance_pct < 0.0:
            raise ValueError("tolerance_pct must be >= 0")
        if self.min_isolation_db is not None and self.min_isolation_db <= 0.0:
            raise ValueError("min_isolation_db must be > 0")


@dataclass(frozen=True, slots=True)
class SystemMonteCarloResult:
    config: SystemMonteCarloConfig
    n_trials: int
    passes: int
    yield_fraction: float
    isolation_min_db: float | None
    isolation_p05_db: float | None
    isolation_p50_db: float | None
    isolation_p95_db: float | None
    insertion_max_db: float | None
    insertion_p95_db: float | None
    out_of_band_max_db: float | None
    out_of_band_p95_db: float | None
    isolation_failures: int
    insertion_failures: int
    out_of_band_failures: int
    isolation_target_db: float | None
    insertion_target_db: float
    out_of_band_target_db: float | None

    def summary(self) -> str:
        parts = [
            f"{self.n_trials} trials, yield {self.yield_fraction * 100:.1f}% "
            f"({self.passes}/{self.n_trials})"
        ]
        if self.isolation_p50_db is not None:
            parts.append(
                f"isolation min/p05/p50 = "
                f"{self.isolation_min_db:.2f}/"
                f"{self.isolation_p05_db:.2f}/"
                f"{self.isolation_p50_db:.2f} dB"
            )
        if self.insertion_max_db is not None:
            parts.append(
                f"max IL = {self.insertion_max_db:.2f} dB "
                f"(p95 {self.insertion_p95_db:.2f})"
            )
        if self.out_of_band_max_db is not None:
            parts.append(
                f"worst OOB = {self.out_of_band_max_db:.2f} dB "
                f"(p95 {self.out_of_band_p95_db:.2f})"
            )
        return "; ".join(parts)


def analyze_system_montecarlo(
    design: SystemDesign,
    config: SystemMonteCarloConfig,
) -> SystemMonteCarloResult:
    """Run tolerance trials and estimate yield for the configured criteria."""
    branches = _branches(design)
    isolation_target = _isolation_target(design, config)
    oob_target = (
        None if isinstance(design, DuplexerDesign) else config.max_out_of_band_db
    )
    rng = np.random.default_rng(config.seed)
    isolation_values: list[float] = []
    insertion_values: list[float] = []
    oob_values: list[float] = []
    passes = 0
    isolation_failures = 0
    insertion_failures = 0
    oob_failures = 0
    for _ in range(config.n_trials):
        perturbed: list[Circuit] = []
        for label, circuit in branches:
            branch_config = MonteCarloConfig(
                n_trials=1,
                tolerance_pct=config.tolerance_pct,
                distribution=config.distribution,
                seed=config.seed,
                overrides=_branch_overrides(config.overrides, label),
            )
            perturbed.append(perturb_circuit(circuit, rng, branch_config))
        variant = rebuild_system_design(design, tuple(perturbed))
        snapshot = _snapshot(variant)
        if snapshot.isolation_db is not None:
            isolation_values.append(snapshot.isolation_db)
        if snapshot.insertion_db is not None:
            insertion_values.append(snapshot.insertion_db)
        if snapshot.out_of_band_db is not None:
            oob_values.append(snapshot.out_of_band_db)
        isolation_ok = (
            isolation_target is None
            or (
                snapshot.isolation_db is not None
                and snapshot.isolation_db >= isolation_target
            )
        )
        insertion_ok = (
            snapshot.insertion_db is not None
            and snapshot.insertion_db <= config.max_insertion_loss_db
        )
        oob_ok = (
            oob_target is None
            or (
                snapshot.out_of_band_db is not None
                and snapshot.out_of_band_db <= oob_target
            )
        )
        if not isolation_ok:
            isolation_failures += 1
        if not insertion_ok:
            insertion_failures += 1
        if not oob_ok:
            oob_failures += 1
        if isolation_ok and insertion_ok and oob_ok:
            passes += 1
    return SystemMonteCarloResult(
        config=config,
        n_trials=config.n_trials,
        passes=passes,
        yield_fraction=passes / config.n_trials,
        isolation_min_db=_stat(isolation_values, np.min),
        isolation_p05_db=_percentile(isolation_values, 5),
        isolation_p50_db=_percentile(isolation_values, 50),
        isolation_p95_db=_percentile(isolation_values, 95),
        insertion_max_db=_stat(insertion_values, np.max),
        insertion_p95_db=_percentile(insertion_values, 95),
        out_of_band_max_db=_stat(oob_values, np.max),
        out_of_band_p95_db=_percentile(oob_values, 95),
        isolation_failures=isolation_failures,
        insertion_failures=insertion_failures,
        out_of_band_failures=oob_failures,
        isolation_target_db=isolation_target,
        insertion_target_db=config.max_insertion_loss_db,
        out_of_band_target_db=oob_target,
    )


def _branches(design: SystemDesign) -> list[tuple[str, Circuit]]:
    if isinstance(design, MultiplexerDesign):
        return [
            (band.label.capitalize(), circuit)
            for band, circuit in zip(design.bands, design.circuits, strict=True)
        ]
    if isinstance(design, DuplexerDesign):
        return [("TX", design.tx_circuit), ("RX", design.rx_circuit)]
    return [("Low", design.low_circuit), ("High", design.high_circuit)]


def _isolation_target(
    design: SystemDesign, config: SystemMonteCarloConfig
) -> float | None:
    if config.min_isolation_db is not None:
        return config.min_isolation_db
    if isinstance(design, DuplexerDesign):
        return design.config.min_isolation_db
    return None


def _branch_overrides(
    overrides: dict[str, ElementTolerance], label: str
) -> dict[str, ElementTolerance]:
    prefix = f"{label}:"
    return {
        key[len(prefix) :]: value
        for key, value in overrides.items()
        if key.startswith(prefix)
    }


@dataclass(frozen=True, slots=True)
class _Snapshot:
    isolation_db: float | None
    insertion_db: float | None
    out_of_band_db: float | None


def _snapshot(design: SystemDesign) -> _Snapshot:
    if isinstance(design, DuplexerDesign):
        metrics = design.metrics
        return _Snapshot(
            isolation_db=metrics.worst_isolation_db,
            insertion_db=_max_optional(
                metrics.tx_insertion_loss_db, metrics.rx_insertion_loss_db
            ),
            out_of_band_db=None,
        )
    if isinstance(design, MultiplexerDesign):
        return _Snapshot(
            isolation_db=None,
            insertion_db=_max_optional(
                *(band.insertion_loss_db for band in design.metrics.bands)
            ),
            out_of_band_db=_max_optional(
                *(band.out_of_band_db for band in design.metrics.bands)
            ),
        )
    diplexer_metrics = design.metrics
    return _Snapshot(
        isolation_db=None,
        insertion_db=_max_optional(
            diplexer_metrics.low_insertion_loss_db,
            diplexer_metrics.high_insertion_loss_db,
        ),
        out_of_band_db=_max_optional(
            diplexer_metrics.low_out_of_band_db,
            diplexer_metrics.high_out_of_band_db,
        ),
    )


def _max_optional(*values: float | None) -> float | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _stat(
    values: list[float], function: Callable[[np.ndarray], float]
) -> float | None:
    if not values:
        return None
    return float(function(np.asarray(values, dtype=float)))


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=float), q))


__all__ = [
    "SystemMonteCarloConfig",
    "SystemMonteCarloError",
    "SystemMonteCarloResult",
    "analyze_system_montecarlo",
]
