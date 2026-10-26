"""scikit-rf analysis adapter (not part of the domain model)."""

from __future__ import annotations

import numpy as np
import skrf as rf
from numpy.typing import NDArray

from filterdesk.analysis.adapters.abcd_ladder import (
    AnalysisError,
    _element_abcd,
    abcd_to_s,
    transformer_abcd,
)
from filterdesk.analysis.types import AnalysisResult, SweepConfig
from filterdesk.domain.circuit import Circuit


class ScikitRFAnalyzer:
    """Build a cascade of scikit-rf Networks at a common z0, then renormalize.

    Elements are cascaded at a single reference impedance (geometric mean of the
    two port impedances); the resulting two-port is renormalized to
    ``[z_source_ohm, z_load_ohm]`` so unequal terminations are supported.
    """

    name = "scikit_rf"

    def analyze(self, circuit: Circuit, sweep: SweepConfig) -> AnalysisResult:
        return self.analyze_at_frequencies(circuit, sweep.frequencies_hz())

    def analyze_at_frequencies(
        self, circuit: Circuit, frequency_hz: NDArray[np.floating] | list[float]
    ) -> AnalysisResult:
        if not circuit.elements:
            raise AnalysisError("circuit has no elements")
        freq_hz = np.asarray(frequency_hz, dtype=float)
        if freq_hz.ndim != 1 or freq_hz.size < 1:
            raise AnalysisError("frequency array must be 1-D and non-empty")
        if not np.all(np.isfinite(freq_hz)) or np.any(freq_hz <= 0.0):
            raise AnalysisError("frequencies must be finite and > 0")
        zs = circuit.port_in.impedance_ohm
        zl = circuit.port_out.impedance_ohm
        z0_ref = float(np.sqrt(zs * zl))
        frequency = rf.Frequency.from_f(np.asarray(freq_hz, dtype=float), unit="Hz")
        omega = 2.0 * np.pi * np.asarray(freq_hz, dtype=float)

        networks: list[rf.Network] = []
        for el in circuit.elements:
            abcd = _element_abcd(el, omega)
            s11, s21, s12, s22 = abcd_to_s(abcd, z0_ref, z0_ref)
            s = np.zeros((len(freq_hz), 2, 2), dtype=np.complex128)
            s[:, 0, 0] = s11
            s[:, 1, 0] = s21
            s[:, 0, 1] = s12
            s[:, 1, 1] = s22
            networks.append(
                rf.Network(frequency=frequency, s=s, z0=z0_ref, name=el.id)
            )

        ratio = circuit.output_transformer_ratio
        if ratio != 1.0:
            t_abcd = transformer_abcd(ratio, len(freq_hz))
            s11, s21, s12, s22 = abcd_to_s(t_abcd, z0_ref, z0_ref)
            s_t = np.zeros((len(freq_hz), 2, 2), dtype=np.complex128)
            s_t[:, 0, 0] = s11
            s_t[:, 1, 0] = s21
            s_t[:, 0, 1] = s12
            s_t[:, 1, 1] = s22
            networks.append(
                rf.Network(frequency=frequency, s=s_t, z0=z0_ref, name="T1")
            )

        ntw = networks[0]
        for n in networks[1:]:
            ntw = ntw ** n

        if abs(zs - zl) > 1e-12 * max(zs, zl):
            ntw.renormalize([zs, zl])

        s = ntw.s
        s11 = s[:, 0, 0]
        s21 = s[:, 1, 0]
        s12 = s[:, 0, 1]
        s22 = s[:, 1, 1]

        gamma_in = s11
        zin = zs * (1.0 + gamma_in) / (1.0 - gamma_in)
        gamma_out = s22
        zout = zl * (1.0 + gamma_out) / (1.0 - gamma_out)

        return AnalysisResult(
            frequency_hz=np.asarray(freq_hz, dtype=float),
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
