"""Ideal coupled-resonator bandpass filter synthesis.

This is the narrowband J-inverter model used to size parallel-coupled lines.
It computes the even/odd impedances of each coupled section and the ideal
2-port response. It does not synthesize physical width/gap dimensions, layout,
dispersion, discontinuities or EM coupling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.multiport import SParameters
from filterdesk.analysis.types import SweepConfig
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.synthesis.families.butterworth import butterworth_g_values
from filterdesk.synthesis.families.chebyshev_i import chebyshev_type_i_g_values

_MAX_ORDER = 9
_SUPPORTED = frozenset(
    {ApproximationFamily.BUTTERWORTH, ApproximationFamily.CHEBYSHEV_TYPE_I}
)


class CoupledLineError(ValueError):
    """Raised for an invalid coupled-line filter request."""


@dataclass(frozen=True, slots=True)
class CoupledLineBpfConfig:
    center_hz: float
    bandwidth_hz: float
    order: int = 3
    family: ApproximationFamily = ApproximationFamily.CHEBYSHEV_TYPE_I
    ripple_db: float | None = 0.1
    z0_ohm: float = 50.0

    def __post_init__(self) -> None:
        if self.center_hz <= 0.0:
            raise CoupledLineError("center_hz must be > 0")
        if self.bandwidth_hz <= 0.0:
            raise CoupledLineError("bandwidth_hz must be > 0")
        if self.bandwidth_hz >= 2.0 * self.center_hz:
            raise CoupledLineError("bandwidth must be below 2*center")
        if not 1 <= self.order <= _MAX_ORDER:
            raise CoupledLineError(f"order must be in 1..{_MAX_ORDER}")
        if self.family not in _SUPPORTED:
            raise CoupledLineError(
                "coupled-line synthesis supports Butterworth and Chebyshev-I"
            )
        if self.family is ApproximationFamily.CHEBYSHEV_TYPE_I:
            if self.ripple_db is None or self.ripple_db <= 0.0:
                raise CoupledLineError("Chebyshev-I needs ripple_db > 0")
            if self.order % 2 == 0:
                raise CoupledLineError(
                    "Chebyshev-I coupled-line synthesis requires an odd order "
                    "for equal 50-ohm terminations"
                )
        if self.z0_ohm <= 0.0:
            raise CoupledLineError("z0_ohm must be > 0")


@dataclass(frozen=True, slots=True)
class CoupledLineSection:
    index: int
    j_norm: float
    z0e_ohm: float
    z0o_ohm: float
    coupling: float


@dataclass(frozen=True, slots=True)
class CoupledLineBpfDesign:
    config: CoupledLineBpfConfig
    sweep: SweepConfig
    network: SParameters
    sections: tuple[CoupledLineSection, ...]
    g_values: tuple[float, ...]
    warnings: tuple[str, ...] = ()
    meta: dict[str, object] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"Coupled-line BPF: {self.config.order} resonators, "
            f"{len(self.sections)} sections, "
            f"{self.config.center_hz / 1e6:.4g} MHz, "
            f"BW {self.config.bandwidth_hz / 1e6:.4g} MHz, "
            f"Z0 {self.config.z0_ohm:g} ohm"
        )


def _g_values(config: CoupledLineBpfConfig) -> tuple[float, ...]:
    if config.family is ApproximationFamily.BUTTERWORTH:
        return butterworth_g_values(config.order)
    assert config.ripple_db is not None
    return chebyshev_type_i_g_values(config.order, config.ripple_db)


def _inverter_values(
    g: tuple[float, ...], fbw: float
) -> tuple[float, ...]:
    n = len(g) - 2
    values = [math.sqrt(math.pi * fbw / (2.0 * g[0] * g[1]))]
    for index in range(1, n):
        values.append(
            math.pi * fbw / (2.0 * math.sqrt(g[index] * g[index + 1]))
        )
    values.append(math.sqrt(math.pi * fbw / (2.0 * g[n] * g[n + 1])))
    return tuple(values)


def _sections(
    config: CoupledLineBpfConfig, j_norm: tuple[float, ...]
) -> tuple[CoupledLineSection, ...]:
    sections: list[CoupledLineSection] = []
    for index, value in enumerate(j_norm, start=1):
        z0e = config.z0_ohm * (1.0 + value + value * value)
        z0o = config.z0_ohm * (1.0 - value + value * value)
        sections.append(
            CoupledLineSection(
                index=index,
                j_norm=value,
                z0e_ohm=z0e,
                z0o_ohm=z0o,
                coupling=(z0e - z0o) / (z0e + z0o),
            )
        )
    return tuple(sections)


def _abcd_to_s(
    abcd: NDArray[np.complex128], z0_ohm: float
) -> tuple[
    NDArray[np.complex128],
    NDArray[np.complex128],
    NDArray[np.complex128],
    NDArray[np.complex128],
]:
    a = abcd[:, 0, 0]
    b = abcd[:, 0, 1]
    c = abcd[:, 1, 0]
    d = abcd[:, 1, 1]
    denominator = a + b / z0_ohm + c * z0_ohm + d
    if np.any(np.abs(denominator) < 1e-15):
        raise CoupledLineError("coupled-line network is singular")
    s11 = (a + b / z0_ohm - c * z0_ohm - d) / denominator
    s21 = 2.0 / denominator
    s12 = 2.0 * (a * d - b * c) / denominator
    s22 = (-a + b / z0_ohm - c * z0_ohm + d) / denominator
    return s11, s21, s12, s22


def design_coupled_line_bpf(
    config: CoupledLineBpfConfig, sweep: SweepConfig
) -> CoupledLineBpfDesign:
    """Synthesize an ideal parallel-coupled half-wave-resonator BPF.

    The returned network is the narrowband J-inverter response. The section
    table gives the even/odd impedances needed for a coupled-line realization.
    """
    g = _g_values(config)
    fbw = config.bandwidth_hz / config.center_hz
    j_norm = _inverter_values(g, fbw)
    sections = _sections(config, j_norm)
    frequencies = np.asarray(sweep.frequencies_hz(), dtype=np.float64)
    omega = 2.0 * np.pi * frequencies
    y0 = 1.0 / config.z0_ohm
    slope = y0 * math.pi / 2.0
    capacitance = slope / (2.0 * math.pi * config.center_hz)
    inductance = 1.0 / ((2.0 * math.pi * config.center_hz) ** 2 * capacitance)
    response = np.zeros((frequencies.size, 2, 2), dtype=np.complex128)
    for index, frequency in enumerate(omega):
        susceptance = 1j * (
            frequency * capacitance - 1.0 / (frequency * inductance)
        )
        matrix = np.eye(2, dtype=np.complex128)
        for section_index, value in enumerate(j_norm):
            inverter = value * y0
            matrix = matrix @ np.asarray(
                [[0.0, 1j / inverter], [1j * inverter, 0.0]],
                dtype=np.complex128,
            )
            if section_index < len(j_norm) - 1:
                matrix = matrix @ np.asarray(
                    [[1.0, 0.0], [susceptance, 1.0]],
                    dtype=np.complex128,
                )
        s11, s21, s12, s22 = _abcd_to_s(matrix[None, :, :], config.z0_ohm)
        response[index, 0, 0] = s11[0]
        response[index, 1, 0] = s21[0]
        response[index, 0, 1] = s12[0]
        response[index, 1, 1] = s22[0]
    network = SParameters(
        frequency_hz=frequencies,
        s=response,
        z0_ohm=config.z0_ohm,
        source="coupled-line-model",
    )
    warnings = (
        "Ideal narrowband J-inverter model; even/odd impedances are electrical "
        "targets. Physical width/gap, dispersion, discontinuities and EM "
        "coupling are not included; verify with a field solver or VNA.",
    )
    return CoupledLineBpfDesign(
        config=config,
        sweep=sweep,
        network=network,
        sections=sections,
        g_values=g,
        warnings=warnings,
        meta={
            "fbw": fbw,
            "resonator_capacitance_f": capacitance,
            "resonator_inductance_h": inductance,
            "model": "parallel-coupled half-wave resonator J-inverter",
            "confidence": "experimental",
        },
    )


__all__ = [
    "CoupledLineBpfConfig",
    "CoupledLineBpfDesign",
    "CoupledLineError",
    "CoupledLineSection",
    "design_coupled_line_bpf",
]
