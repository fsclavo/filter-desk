"""Apply finite-Q / parasitic models to every branch of a system design."""

from __future__ import annotations

from dataclasses import dataclass

from filterdesk.components_std import nonidealize_circuit
from filterdesk.domain.circuit import Circuit
from filterdesk.domain.specs import FilterSpec
from filterdesk.services.duplexer import DuplexerDesign
from filterdesk.services.multiplexer import MultiplexerDesign
from filterdesk.services.system_rebuild import SystemDesign, rebuild_system_design


@dataclass(frozen=True, slots=True)
class SystemParasiticsConfig:
    """Global per-branch parasitic assumptions (simple first-order model)."""

    inductor_q: float | None = None
    inductor_dcr_ohm: float = 0.0
    inductor_parallel_capacitance_f: float = 0.0
    inductor_srf_hz: float | None = None
    capacitor_esr_ohm: float = 0.0
    capacitor_esl_h: float = 0.0
    inductor_loss_model: str = "constant"

    def __post_init__(self) -> None:
        if self.inductor_q is not None and self.inductor_q <= 0.0:
            raise ValueError("inductor_q must be > 0")
        for name, value in (
            ("inductor_dcr_ohm", self.inductor_dcr_ohm),
            ("inductor_parallel_capacitance_f", self.inductor_parallel_capacitance_f),
            ("capacitor_esr_ohm", self.capacitor_esr_ohm),
            ("capacitor_esl_h", self.capacitor_esl_h),
        ):
            if value < 0.0:
                raise ValueError(f"{name} must be >= 0")
        if self.inductor_srf_hz is not None and self.inductor_srf_hz <= 0.0:
            raise ValueError("inductor_srf_hz must be > 0")

    @property
    def is_identity(self) -> bool:
        return (
            self.inductor_q is None
            and self.inductor_dcr_ohm == 0.0
            and self.inductor_parallel_capacitance_f == 0.0
            and self.inductor_srf_hz is None
            and self.capacitor_esr_ohm == 0.0
            and self.capacitor_esl_h == 0.0
            and self.inductor_loss_model == "constant"
        )


@dataclass(frozen=True, slots=True)
class SystemParasiticsResult:
    design: SystemDesign
    config: SystemParasiticsConfig


def apply_system_parasitics(
    design: SystemDesign,
    config: SystemParasiticsConfig,
) -> SystemParasiticsResult:
    """Apply the same parasitic assumptions to every branch and reanalyze."""
    if config.is_identity:
        return SystemParasiticsResult(design=design, config=config)
    if isinstance(design, MultiplexerDesign):
        circuits = tuple(
            _parasitic_circuit(circuit, spec, config)
            for circuit, spec in zip(design.circuits, design.specs, strict=True)
        )
    elif isinstance(design, DuplexerDesign):
        circuits = (
            _parasitic_circuit(design.tx_circuit, design.tx_spec, config),
            _parasitic_circuit(design.rx_circuit, design.rx_spec, config),
        )
    else:
        circuits = (
            _parasitic_circuit(design.low_circuit, design.low_spec, config),
            _parasitic_circuit(design.high_circuit, design.high_spec, config),
        )
    return SystemParasiticsResult(
        design=rebuild_system_design(design, circuits),
        config=config,
    )


def _parasitic_circuit(
    circuit: Circuit,
    spec: FilterSpec,
    config: SystemParasiticsConfig,
) -> Circuit:
    reference_hz = spec.f_center_hz or spec.cutoff_hz
    return nonidealize_circuit(
        circuit,
        inductor_q=config.inductor_q,
        q_frequency_hz=reference_hz if config.inductor_q is not None else None,
        inductor_dcr_ohm=config.inductor_dcr_ohm,
        inductor_parallel_capacitance_f=config.inductor_parallel_capacitance_f,
        capacitor_esr_ohm=config.capacitor_esr_ohm,
        capacitor_esl_h=config.capacitor_esl_h,
        inductor_srf_hz=config.inductor_srf_hz,
        inductor_loss_model=config.inductor_loss_model,
    )


__all__ = [
    "SystemParasiticsConfig",
    "SystemParasiticsResult",
    "apply_system_parasitics",
]
