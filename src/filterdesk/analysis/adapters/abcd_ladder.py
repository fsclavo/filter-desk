"""ABCD cascade analysis for series/shunt ladders."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.types import AnalysisResult, SweepConfig
from filterdesk.domain.circuit import (
    BalunSpec,
    Circuit,
    Element,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealResistor,
    IdealSeriesLC,
    MicrostripLineElement,
    MicrostripStubElement,
    NonIdealCapacitor,
    NonIdealInductor,
)
from filterdesk.domain.enums import ElementRole, MicrostripStubKind


class AnalysisError(ValueError):
    """Circuit cannot be analyzed by this backend."""


def _series_abcd(z: NDArray[np.complexfloating]) -> NDArray[np.complexfloating]:
    n = z.shape[0]
    a = np.zeros((n, 2, 2), dtype=np.complex128)
    a[:, 0, 0] = 1.0
    a[:, 0, 1] = z
    a[:, 1, 0] = 0.0
    a[:, 1, 1] = 1.0
    return a


def _shunt_abcd(y: NDArray[np.complexfloating]) -> NDArray[np.complexfloating]:
    n = y.shape[0]
    a = np.zeros((n, 2, 2), dtype=np.complex128)
    a[:, 0, 0] = 1.0
    a[:, 0, 1] = 0.0
    a[:, 1, 0] = y
    a[:, 1, 1] = 1.0
    return a


def _z_series_lc(
    omega: NDArray[np.floating], l_h: float, c_f: float
) -> NDArray[np.complexfloating]:
    return 1j * omega * l_h + 1.0 / (1j * omega * c_f)


def _y_parallel_lc(
    omega: NDArray[np.floating], l_h: float, c_f: float
) -> NDArray[np.complexfloating]:
    return 1.0 / (1j * omega * l_h) + 1j * omega * c_f


def transformer_abcd(ratio: float, n_points: int) -> NDArray[np.complexfloating]:
    """Ideal transformer ABCD, primary (ladder) : secondary (load) = ratio:1."""
    if ratio <= 0.0:
        raise AnalysisError("transformer ratio must be > 0")
    a = np.zeros((n_points, 2, 2), dtype=np.complex128)
    a[:, 0, 0] = ratio
    a[:, 0, 1] = 0.0
    a[:, 1, 0] = 0.0
    a[:, 1, 1] = 1.0 / ratio
    return a


def transmission_line_abcd(
    z0_ohm: float,
    length_m: float,
    velocity_factor: float,
    loss_db_per_m: float,
    frequency_hz: NDArray[np.floating],
) -> NDArray[np.complexfloating]:
    """ABCD of a lossy TEM line (first-order, no dispersion)."""
    if z0_ohm <= 0.0 or velocity_factor <= 0.0 or length_m < 0.0:
        raise AnalysisError("invalid transmission-line parameters")
    if loss_db_per_m < 0.0:
        raise AnalysisError("line loss must be >= 0")
    freq = np.asarray(frequency_hz, dtype=float)
    alpha = loss_db_per_m / 8.686
    beta = 2.0 * np.pi * freq / (velocity_factor * 299_792_458.0)
    gamma_l = (alpha + 1j * beta) * length_m
    cosh = np.cosh(gamma_l)
    sinh = np.sinh(gamma_l)
    a = np.zeros((freq.size, 2, 2), dtype=np.complex128)
    a[:, 0, 0] = cosh
    a[:, 0, 1] = z0_ohm * sinh
    a[:, 1, 0] = sinh / z0_ohm
    a[:, 1, 1] = cosh
    return a


def _guanella_abcd(
    balun: BalunSpec, frequency_hz: NDArray[np.floating]
) -> NDArray[np.complexfloating] | None:
    """ABCD of an N-line Guanella TLT (parallel input, series output)."""
    lines = balun.guanella_line_count
    if lines is None:
        return None
    line = transmission_line_abcd(
        balun.z0_line_ohm,
        balun.length_m,
        balun.velocity_factor,
        balun.loss_db_per_m,
        frequency_hz,
    )
    a = line[:, 0, 0]
    b = line[:, 0, 1]
    c = line[:, 1, 0]
    d = line[:, 1, 1]
    out = np.zeros_like(line)
    if balun.turns_ratio <= 1.0:
        # N lines in parallel at the low side, series at the high side.
        out[:, 0, 0] = a / lines
        out[:, 0, 1] = b
        out[:, 1, 0] = c
        out[:, 1, 1] = d * lines
    else:
        # Reverse the step-up network for a high-to-low transformation.
        out[:, 0, 0] = d * lines
        out[:, 0, 1] = -b
        out[:, 1, 0] = -c
        out[:, 1, 1] = a / lines
    return out


def _ruthroff_abcd(
    balun: BalunSpec, frequency_hz: NDArray[np.floating]
) -> NDArray[np.complexfloating] | None:
    """First-order Ruthroff 1:4 distributed network.

    Uses the equal-delay bootstrap ABCD, which reduces to a 1:2 ideal
    transformer (1:4 impedance) at zero line length. Only the 1:4/4:1 ratios are
    represented; other Ruthroff ratios keep the generic transformer + line.
    """
    if balun.kind != "ruthroff":
        return None
    ratio = balun.turns_ratio
    if abs(ratio - 0.5) > 1e-6 and abs(ratio - 2.0) > 1e-6:
        return None
    line = transmission_line_abcd(
        balun.z0_line_ohm,
        balun.length_m,
        balun.velocity_factor,
        balun.loss_db_per_m,
        frequency_hz,
    )
    cosh = line[:, 0, 0]
    z0_sinh = line[:, 0, 1]
    sinh_over_z0 = line[:, 1, 0]
    denom = 1.0 + cosh
    out = np.zeros_like(line)
    if ratio <= 1.0:
        out[:, 0, 0] = cosh / denom
        out[:, 0, 1] = z0_sinh / denom
        out[:, 1, 0] = sinh_over_z0 / denom
        out[:, 1, 1] = 2.0
    else:
        out[:, 0, 0] = 2.0
        out[:, 0, 1] = -z0_sinh / denom
        out[:, 1, 0] = -sinh_over_z0 / denom
        out[:, 1, 1] = cosh / denom
    return out


def balun_abcd(
    balun: BalunSpec, frequency_hz: NDArray[np.floating]
) -> NDArray[np.complexfloating]:
    """Behavioral/multi-line ABCD of a boundary balun/unun.

    Guanella baluns with an integer 1:N² ratio use an explicit N-line
    parallel-input/series-output network. Other kinds keep the first-order
    transformer + TEM-line model. Leakage, core loss and winding capacitance
    are applied as boundary elements.
    """
    freq = np.asarray(frequency_hz, dtype=float)
    omega = 2.0 * np.pi * freq
    if balun.kind == "ideal":
        return transformer_abcd(balun.turns_ratio, freq.size)
    sections: list[NDArray[np.complexfloating]] = []
    if balun.leakage_h > 0.0:
        sections.append(_series_abcd(1j * omega * balun.leakage_h))
    if balun.core_loss_ohm is not None and balun.core_loss_ohm > 0.0:
        sections.append(
            _shunt_abcd(np.full_like(omega, 1.0 / balun.core_loss_ohm, dtype=complex))
        )
    guanella = _guanella_abcd(balun, freq) if balun.kind == "guanella" else None
    ruthroff = _ruthroff_abcd(balun, freq) if balun.kind == "ruthroff" else None
    if guanella is not None:
        sections.append(guanella)
    elif ruthroff is not None:
        sections.append(ruthroff)
    else:
        sections.append(transformer_abcd(balun.turns_ratio, freq.size))
        if balun.length_m > 0.0:
            sections.append(
                transmission_line_abcd(
                    balun.z0_line_ohm,
                    balun.length_m,
                    balun.velocity_factor,
                    balun.loss_db_per_m,
                    freq,
                )
            )
    if balun.shunt_c_f > 0.0:
        sections.append(_shunt_abcd(1j * omega * balun.shunt_c_f))
    return cascade_abcd(sections)


def _propagation_constant(
    frequency_hz: NDArray[np.floating],
    eeff: float,
    loss_db_per_m: float,
) -> NDArray[np.complexfloating]:
    if eeff <= 0.0:
        raise AnalysisError("effective permittivity must be > 0")
    alpha = loss_db_per_m / 8.686
    beta = (
        2.0
        * np.pi
        * np.asarray(frequency_hz, dtype=float)
        / (np.sqrt(eeff) * 299_792_458.0)
    )
    return np.asarray(alpha + 1j * beta, dtype=np.complex128)


def _stub_input_impedance(
    stub: MicrostripStubElement,
    frequency_hz: NDArray[np.floating],
) -> NDArray[np.complexfloating]:
    gamma_l = (
        _propagation_constant(frequency_hz, stub.eeff, stub.loss_db_per_m)
        * stub.length_m
    )
    tanh = np.tanh(gamma_l)
    if stub.stub_kind == MicrostripStubKind.OPEN:
        if stub.length_m <= 0.0:
            return np.full_like(tanh, 1e12, dtype=np.complex128)
        z = stub.z0_ohm / np.where(np.abs(tanh) < 1e-15, 1e-15, tanh)
    else:
        z = stub.z0_ohm * tanh
    return np.asarray(z, dtype=np.complex128)


def _z_nonideal_inductor(
    omega: NDArray[np.floating],
    el: NonIdealInductor,
) -> NDArray[np.complexfloating]:
    r_ref = el.reference_resistance_ohm
    if (
        el.loss_model == "dc_skin"
        and r_ref > 0.0
        and el.q_frequency_hz is not None
        and el.q_frequency_hz > 0.0
    ):
        reference_omega = 2.0 * np.pi * el.q_frequency_hz
        ratio = np.maximum(omega / reference_omega, 1.0)
        resistance = r_ref * np.sqrt(ratio)
    else:
        resistance = np.full_like(omega, r_ref, dtype=np.float64)
    z_series = resistance + 1j * omega * el.effective_inductance_h
    c_parallel_f = el.effective_parallel_capacitance_f
    if c_parallel_f <= 0.0:
        return np.asarray(z_series, dtype=np.complex128)
    z_parallel = 1.0 / (1j * omega * c_parallel_f)
    return np.asarray(1.0 / (1.0 / z_series + 1.0 / z_parallel), dtype=np.complex128)


def _z_nonideal_capacitor(
    omega: NDArray[np.floating],
    c_f: float,
    esr_ohm: float,
    esl_h: float,
) -> NDArray[np.complexfloating]:
    return esr_ohm + 1j * omega * esl_h + 1.0 / (1j * omega * c_f)


def _element_abcd(
    el: Element, omega: NDArray[np.floating]
) -> NDArray[np.complexfloating]:
    if isinstance(el, IdealResistor):
        if el.role == ElementRole.SERIES:
            return _series_abcd(np.full_like(omega, el.value_ohm, dtype=np.complex128))
        return _shunt_abcd(np.full_like(omega, 1.0 / el.value_ohm, dtype=np.complex128))
    if isinstance(el, IdealInductor):
        z = 1j * omega * el.value_h
        if el.role == ElementRole.SERIES:
            return _series_abcd(z)
        return _shunt_abcd(1.0 / z)
    if isinstance(el, IdealCapacitor):
        z = 1.0 / (1j * omega * el.value_f)
        if el.role == ElementRole.SERIES:
            return _series_abcd(z)
        return _shunt_abcd(1.0 / z)
    if isinstance(el, NonIdealInductor):
        z = _z_nonideal_inductor(omega, el)
        if el.role == ElementRole.SERIES:
            return _series_abcd(z)
        return _shunt_abcd(1.0 / z)
    if isinstance(el, NonIdealCapacitor):
        z = _z_nonideal_capacitor(omega, el.value_f, el.esr_ohm, el.esl_h)
        if el.role == ElementRole.SERIES:
            return _series_abcd(z)
        return _shunt_abcd(1.0 / z)
    if isinstance(el, IdealSeriesLC):
        z = _z_series_lc(omega, el.value_h, el.value_f)
        if el.role == ElementRole.SERIES:
            return _series_abcd(z)
        return _shunt_abcd(1.0 / z)
    if isinstance(el, IdealParallelLC):
        y = _y_parallel_lc(omega, el.value_h, el.value_f)
        if el.role == ElementRole.SERIES:
            z = np.asarray(1.0 / y, dtype=np.complex128)
            return _series_abcd(z)
        return _shunt_abcd(y)
    if isinstance(el, IdealBruneLC):
        z_s = _z_series_lc(omega, el.series_l_h, el.series_c_f)
        y_p = _y_parallel_lc(omega, el.parallel_l_h, el.parallel_c_f)
        z = z_s + 1.0 / y_p
        if el.role == ElementRole.SERIES:
            return _series_abcd(z)
        return _shunt_abcd(1.0 / z)
    if isinstance(el, IdealDualBruneLC):
        z_s = _z_series_lc(omega, el.series_l_h, el.series_c_f)
        y_p = _y_parallel_lc(omega, el.parallel_l_h, el.parallel_c_f)
        # Parallel of series-LC branch and parallel-LC branch
        y = 1.0 / z_s + y_p
        if el.role == ElementRole.SERIES:
            return _series_abcd(np.asarray(1.0 / y, dtype=np.complex128))
        return _shunt_abcd(y)
    if isinstance(el, MicrostripLineElement):
        return transmission_line_abcd(
            el.z0_ohm,
            el.length_m,
            el.velocity_factor,
            el.loss_db_per_m,
            np.asarray(omega / (2.0 * np.pi), dtype=float),
        )
    if isinstance(el, MicrostripStubElement):
        if el.role != ElementRole.SHUNT:
            raise AnalysisError("microstrip stubs must be shunt elements")
        z = _stub_input_impedance(el, np.asarray(omega / (2.0 * np.pi), dtype=float))
        y = 1.0 / z
        return _shunt_abcd(np.asarray(y, dtype=np.complex128))
    raise AnalysisError(f"unsupported element type: {type(el)!r}")


def element_impedance_ohm(el: Element, frequency_hz: float) -> complex:
    """Return the arm impedance ``Z`` of ``el`` at ``frequency_hz`` (scalar).

    For series arms this is the series impedance; for shunt arms it is the shunt
    impedance (``1/Y``). Used by the power-stress estimate.
    """
    if isinstance(el, (MicrostripLineElement, MicrostripStubElement)):
        raise AnalysisError("distributed elements have no lumped arm impedance")
    omega = np.array([2.0 * np.pi * frequency_hz], dtype=float)
    abcd = _element_abcd(el, omega)[0]
    if el.role == ElementRole.SERIES:
        return complex(abcd[0, 1])  # B = Z
    admittance = complex(abcd[1, 0])  # C = Y
    if admittance == 0.0:
        # Open shunt arm (e.g. a parallel LC at its resonant frequency): Z -> ∞.
        return complex(math.inf)
    return 1.0 / admittance  # Z = 1/Y


def cascade_abcd(
    mats: list[NDArray[np.complexfloating]],
) -> NDArray[np.complexfloating]:
    """Left-to-right cascade: out = M1 @ M2 @ ... @ Mn per frequency."""
    if not mats:
        raise AnalysisError("no ABCD sections to cascade")
    out = mats[0]
    for m in mats[1:]:
        out = out @ m
    return out


def abcd_to_s(
    abcd: NDArray[np.complexfloating],
    z0_source: float,
    z0_load: float,
) -> tuple[
    NDArray[np.complexfloating],
    NDArray[np.complexfloating],
    NDArray[np.complexfloating],
    NDArray[np.complexfloating],
]:
    """Convert ABCD to S with possibly unequal real port impedances."""
    a = abcd[:, 0, 0]
    b = abcd[:, 0, 1]
    c = abcd[:, 1, 0]
    d = abcd[:, 1, 1]
    zs = z0_source
    zl = z0_load
    denom = a * zl + b + c * zs * zl + d * zs
    s11 = (a * zl + b - c * zs * zl - d * zs) / denom
    s21 = (2.0 * np.sqrt(zs * zl)) / denom
    s12 = (2.0 * (a * d - b * c) * np.sqrt(zs * zl)) / denom
    s22 = (-a * zl + b - c * zs * zl + d * zs) / denom
    return s11, s21, s12, s22


def abcd_zin_zout(
    abcd: NDArray[np.complexfloating],
    z_source: float,
    z_load: float,
) -> tuple[NDArray[np.complex128], NDArray[np.complex128]]:
    a = abcd[:, 0, 0]
    b = abcd[:, 0, 1]
    c = abcd[:, 1, 0]
    d = abcd[:, 1, 1]
    zin = (a * z_load + b) / (c * z_load + d)
    zout = (d * z_source + b) / (c * z_source + a)
    return (
        np.asarray(zin, dtype=np.complex128),
        np.asarray(zout, dtype=np.complex128),
    )


class LadderABCDAnalyzer:
    """Fast vectorized ABCD analyzer for series/shunt RLC ladders."""

    name = "ladder_abcd"

    def analyze(self, circuit: Circuit, sweep: SweepConfig) -> AnalysisResult:
        return self.analyze_at_frequencies(circuit, sweep.frequencies_hz())

    def analyze_at_frequencies(
        self, circuit: Circuit, frequency_hz: NDArray[np.floating] | list[float]
    ) -> AnalysisResult:
        if not circuit.elements:
            raise AnalysisError("circuit has no elements")
        freq = np.asarray(frequency_hz, dtype=float)
        if freq.ndim != 1 or freq.size < 1:
            raise AnalysisError("frequency array must be 1-D and non-empty")
        if not np.all(np.isfinite(freq)) or np.any(freq <= 0.0):
            raise AnalysisError("frequencies must be finite and > 0")
        omega = 2.0 * np.pi * freq
        sections = [_element_abcd(el, omega) for el in circuit.elements]
        abcd = cascade_abcd(sections)
        ratio = circuit.output_transformer_ratio
        if ratio != 1.0:
            abcd = abcd @ transformer_abcd(ratio, freq.size)
        if circuit.output_balun is not None:
            abcd = abcd @ balun_abcd(circuit.output_balun, freq)
        zs = circuit.port_in.impedance_ohm
        zl = circuit.port_out.impedance_ohm
        s11, s21, s12, s22 = abcd_to_s(abcd, zs, zl)
        zin, zout = abcd_zin_zout(abcd, zs, zl)
        return AnalysisResult(
            frequency_hz=freq,
            s11=s11,
            s21=s21,
            s12=s12,
            s22=s22,
            zin_ohm=zin,
            zout_ohm=zout,
            z0_source_ohm=zs,
            z0_load_ohm=zl,
            backend=self.name,
        )
