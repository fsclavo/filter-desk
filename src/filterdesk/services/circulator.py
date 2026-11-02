"""First-order ideal circulator and isolator S-parameter models.

The model represents an ideal circulation path with independent insertion loss,
isolation and return-loss magnitudes. It is not a physical ferrite-junction
model: phase, bandwidth, power handling and magnet bias are not simulated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from filterdesk.analysis.multiport import MultiportError, SParameters
from filterdesk.analysis.types import SweepConfig


class CirculatorError(ValueError):
    """Raised for an invalid circulator/isolator request."""


@dataclass(frozen=True, slots=True)
class CirculatorConfig:
    insertion_loss_db: float = 0.5
    isolation_db: float = 30.0
    return_loss_db: float = 20.0
    z0_ohm: float = 50.0

    def __post_init__(self) -> None:
        for name, value in (
            ("insertion_loss_db", self.insertion_loss_db),
            ("isolation_db", self.isolation_db),
            ("return_loss_db", self.return_loss_db),
        ):
            if not np.isfinite(value) or value < 0.0:
                raise CirculatorError(f"{name} must be finite and >= 0")
        if self.z0_ohm <= 0.0:
            raise CirculatorError("z0_ohm must be > 0")


@dataclass(frozen=True, slots=True)
class CirculatorDesign:
    config: CirculatorConfig
    sweep: SweepConfig
    network: SParameters

    def summary(self) -> str:
        return (
            f"Circulator: IL {self.config.insertion_loss_db:.2f} dB, "
            f"isolation {self.config.isolation_db:.2f} dB, "
            f"RL {self.config.return_loss_db:.2f} dB, "
            f"Z0 {self.config.z0_ohm:g} ohm"
        )


@dataclass(frozen=True, slots=True)
class IsolatorDesign:
    config: CirculatorConfig
    sweep: SweepConfig
    network: SParameters

    def summary(self) -> str:
        return (
            f"Isolator: IL {self.config.insertion_loss_db:.2f} dB, "
            f"isolation {self.config.isolation_db:.2f} dB, "
            f"RL {self.config.return_loss_db:.2f} dB, "
            f"Z0 {self.config.z0_ohm:g} ohm"
        )


def _amplitude(db: float) -> float:
    return float(10.0 ** (-db / 20.0))


def design_circulator(
    config: CirculatorConfig, sweep: SweepConfig
) -> CirculatorDesign:
    """Build a 3-port circulating network: 1→2, 2→3, 3→1."""
    frequencies = np.asarray(sweep.frequencies_hz(), dtype=np.float64)
    through = _amplitude(config.insertion_loss_db)
    isolated = _amplitude(config.isolation_db)
    reflection = _amplitude(config.return_loss_db)
    s = np.zeros((frequencies.size, 3, 3), dtype=np.complex128)
    s[:, 1, 0] = through
    s[:, 2, 1] = through
    s[:, 0, 2] = through
    s[:, 0, 1] = isolated
    s[:, 1, 2] = isolated
    s[:, 2, 0] = isolated
    s[:, 0, 0] = reflection
    s[:, 1, 1] = reflection
    s[:, 2, 2] = reflection
    network = SParameters(
        frequency_hz=frequencies,
        s=s,
        z0_ohm=config.z0_ohm,
        source="circulator-model",
    )
    return CirculatorDesign(config=config, sweep=sweep, network=network)


def design_isolator(config: CirculatorConfig, sweep: SweepConfig) -> IsolatorDesign:
    """Terminate port 3 of the circulator model with a matched load."""
    circulator = design_circulator(config, sweep)
    try:
        network = circulator.network.terminate(
            3, z_load_ohm=complex(config.z0_ohm)
        )
    except MultiportError as exc:  # pragma: no cover - defensive
        raise CirculatorError(str(exc)) from exc
    return IsolatorDesign(config=config, sweep=sweep, network=network)


__all__ = [
    "CirculatorConfig",
    "CirculatorDesign",
    "CirculatorError",
    "IsolatorDesign",
    "design_circulator",
    "design_isolator",
]
