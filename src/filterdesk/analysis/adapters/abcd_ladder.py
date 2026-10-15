"""ABCD cascade analysis for series/shunt ladders."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.types import AnalysisResult, SweepConfig
from filterdesk.domain.circuit import (
    Circuit,
    Element,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealResistor,
    IdealSeriesLC,
    NonIdealCapacitor,
    NonIdealInductor,
)
from filterdesk.domain.enums import ElementRole


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


def _z_nonideal_inductor(
    omega: NDArray[np.floating],
    l_h: float,
    r_ohm: float,
    c_parallel_f: float,
) -> NDArray[np.complexfloating]:
    z_series = r_ohm + 1j * omega * l_h
    if c_parallel_f <= 0.0:
        return z_series
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
        z = _z_nonideal_inductor(
            omega, el.value_h, el.series_resistance_ohm, el.parallel_capacitance_f
        )
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
    raise AnalysisError(f"unsupported element type: {type(el)!r}")


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
        if not circuit.elements:
            raise AnalysisError("circuit has no elements")
        freq = sweep.frequencies_hz()
        omega = 2.0 * np.pi * freq
        sections = [_element_abcd(el, omega) for el in circuit.elements]
        abcd = cascade_abcd(sections)
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
