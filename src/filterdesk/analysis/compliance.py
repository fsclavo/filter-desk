"""Post-synthesis specification compliance check.

Analyzes the realized circuit over a dense grid and compares the achieved
passband ripple, stopband attenuation and band-edge loss with the requested
specification. Documented approximations (unequal terminations, modified
even-order Chebyshev, image-parameter families) are reported as notes rather
than hard failures.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import signal

from filterdesk.analysis.adapters.abcd_ladder import (
    _element_abcd,
    abcd_to_s,
    cascade_abcd,
    transformer_abcd,
)
from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.metrics import band_edges
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.circuit import Circuit
from filterdesk.domain.enums import ApproximationFamily, FilterResponse
from filterdesk.domain.specs import FilterSpec, validate_spec

_IMAGE = (ApproximationFamily.CONSTANT_K, ApproximationFamily.M_DERIVED)
_NO_TABLE = (ApproximationFamily.GAUSSIAN, ApproximationFamily.LEGENDRE)
_CLASSICAL = (
    ApproximationFamily.BUTTERWORTH,
    ApproximationFamily.CHEBYSHEV_TYPE_I,
    ApproximationFamily.CHEBYSHEV_TYPE_II,
    ApproximationFamily.ELLIPTIC,
    ApproximationFamily.BESSEL,
)


@dataclass(frozen=True, slots=True)
class ComplianceResult:
    """Achieved figures vs the requested specification."""

    ok: bool
    issues: tuple[str, ...]
    notes: tuple[str, ...]
    passband_ripple_db: float | None
    stopband_attenuation_db: float | None
    edge_loss_db: tuple[float, ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "issues": list(self.issues),
            "notes": list(self.notes),
            "passband_ripple_db": self.passband_ripple_db,
            "stopband_attenuation_db": self.stopband_attenuation_db,
            "edge_loss_db": list(self.edge_loss_db),
        }


def _s21_db_at(circuit: Circuit, frequencies: np.ndarray) -> np.ndarray:
    """Exact |S21| (dB) at arbitrary frequencies (no grid interpolation)."""
    omega = 2.0 * math.pi * np.asarray(frequencies, dtype=float)
    abcd = cascade_abcd([_element_abcd(el, omega) for el in circuit.elements])
    if circuit.output_transformer_ratio != 1.0:
        abcd = abcd @ transformer_abcd(
            circuit.output_transformer_ratio, omega.size
        )
    s21 = abcd_to_s(
        abcd,
        circuit.port_in.impedance_ohm,
        circuit.port_out.impedance_ohm,
    )[1]
    return np.asarray(20.0 * np.log10(np.abs(s21) + 1e-30), dtype=float)


def _grid(spec: FilterSpec, points: int) -> np.ndarray:
    if spec.response in (FilterResponse.LOW_PASS, FilterResponse.HIGH_PASS):
        fc = spec.cutoff_hz
        return np.logspace(math.log10(fc / 100.0), math.log10(fc * 100.0), points)
    low, high = band_edges(spec)
    return np.logspace(math.log10(low / 10.0), math.log10(high * 10.0), points)


def _reference_db(spec: FilterSpec, f: np.ndarray) -> np.ndarray | None:
    """Ideal prototype response in dB, or None when no analytic table exists."""
    family = spec.family
    if family not in _CLASSICAL:
        return None
    if family == ApproximationFamily.BUTTERWORTH:
        z, p, k = signal.buttap(spec.order)
    elif family == ApproximationFamily.CHEBYSHEV_TYPE_I:
        assert spec.passband_ripple_db is not None
        z, p, k = signal.cheb1ap(spec.order, spec.passband_ripple_db)
    elif family == ApproximationFamily.CHEBYSHEV_TYPE_II:
        assert spec.stopband_attenuation_db is not None
        z, p, k = signal.cheb2ap(spec.order, spec.stopband_attenuation_db)
    elif family == ApproximationFamily.ELLIPTIC:
        assert spec.passband_ripple_db is not None
        assert spec.stopband_attenuation_db is not None
        z, p, k = signal.ellipap(
            spec.order, spec.passband_ripple_db, spec.stopband_attenuation_db
        )
    else:  # Bessel, magnitude-normalized like the synthesizer
        z, p, k = signal.besselap(spec.order, norm="mag")

    w = 2.0 * math.pi * np.asarray(f, dtype=float)
    if spec.response == FilterResponse.LOW_PASS:
        z, p, k = signal.lp2lp_zpk(z, p, k, wo=2.0 * math.pi * spec.cutoff_hz)
    elif spec.response == FilterResponse.HIGH_PASS:
        z, p, k = signal.lp2hp_zpk(z, p, k, wo=2.0 * math.pi * spec.cutoff_hz)
    elif spec.response == FilterResponse.BAND_PASS:
        assert spec.f_center_hz is not None and spec.bandwidth_hz is not None
        z, p, k = signal.lp2bp_zpk(
            z,
            p,
            k,
            wo=2.0 * math.pi * spec.f_center_hz,
            bw=2.0 * math.pi * spec.bandwidth_hz,
        )
    else:
        assert spec.f_center_hz is not None and spec.bandwidth_hz is not None
        z, p, k = signal.lp2bs_zpk(
            z,
            p,
            k,
            wo=2.0 * math.pi * spec.f_center_hz,
            bw=2.0 * math.pi * spec.bandwidth_hz,
        )
    _, h = signal.freqs_zpk(z, p, k, worN=w)
    return np.asarray(20.0 * np.log10(np.abs(h) + 1e-30), dtype=float)


def check_spec_compliance(
    spec: FilterSpec,
    circuit: Circuit,
    *,
    points: int = 4000,
) -> ComplianceResult:
    """Analyze ``circuit`` and report whether it meets ``spec``.

    Returns achieved metrics plus human-readable issues/notes. This is a
    diagnostic: callers decide whether to warn, raise or just display it.
    """
    validate_spec(spec)
    frequency = _grid(spec, points)
    analysis = analyze_circuit(
        circuit,
        SweepConfig(
            float(frequency[0]),
            float(frequency[-1]),
            points,
            SweepSpacing.LOGARITHMIC,
        ),
    )
    s21 = np.asarray(mag_db(analysis.s21), dtype=float)
    f = np.asarray(analysis.frequency_hz, dtype=float)
    ref = _reference_db(spec, f)

    issues: list[str] = []
    notes: list[str] = []
    ripple: float | None = None
    attenuation: float | None = None

    if spec.z_source_ohm != spec.z_load_ohm:
        notes.append(
            "Unequal terminations use an ideal output transformer (ladder "
            "designed for the source impedance); the response matches the "
            "equal-termination prototype exactly."
        )
    if spec.family == ApproximationFamily.CHEBYSHEV_TYPE_I and spec.order % 2 == 0:
        notes.append(
            "Even-order Chebyshev I uses the modified equal-termination "
            "response; the stopband differs from classical tables."
        )
    if spec.family in _IMAGE:
        notes.append("Image-parameter family; strict -3 dB/ripple checks skipped.")
        return ComplianceResult(
            ok=True,
            issues=(),
            notes=tuple(notes),
            passband_ripple_db=None,
            stopband_attenuation_db=None,
            edge_loss_db=(),
        )
    if spec.family in _NO_TABLE:
        notes.append(
            "No closed-form reference table for this family; only -3 dB edge "
            "loss is checked."
        )

    # Passband / stopband masks from the ideal reference when available.
    if ref is not None:
        if spec.family in (
            ApproximationFamily.CHEBYSHEV_TYPE_I,
            ApproximationFamily.ELLIPTIC,
        ):
            assert spec.passband_ripple_db is not None
            pb_mask = ref >= -spec.passband_ripple_db - 0.05
        elif spec.family == ApproximationFamily.CHEBYSHEV_TYPE_II:
            pb_mask = ref >= -0.1
        else:
            pb_mask = ref >= -3.1
        if np.any(pb_mask):
            band = s21[pb_mask]
            if spec.family in (
                ApproximationFamily.CHEBYSHEV_TYPE_I,
                ApproximationFamily.ELLIPTIC,
            ):
                ripple = float(np.max(band) - np.min(band))
            if spec.family in (
                ApproximationFamily.CHEBYSHEV_TYPE_I,
                ApproximationFamily.ELLIPTIC,
            ):
                assert spec.passband_ripple_db is not None
                assert ripple is not None
                if ripple > spec.passband_ripple_db + 0.1:
                    issues.append(
                        f"passband ripple {ripple:.3f} dB exceeds "
                        f"{spec.passband_ripple_db:.3f} dB"
                    )
                if float(np.max(band)) > 0.2:
                    issues.append(
                        f"passband insertion loss {float(np.max(band)):.3f} dB "
                        "exceeds 0.2 dB"
                    )
            elif spec.family == ApproximationFamily.CHEBYSHEV_TYPE_II:
                if float(np.max(band)) > 0.2:
                    issues.append(
                        f"passband insertion loss {float(np.max(band)):.3f} dB "
                        "exceeds 0.2 dB"
                    )
            else:
                if float(np.max(band)) > 0.3:
                    issues.append(
                        f"passband insertion loss {float(np.max(band)):.3f} dB "
                        "exceeds 0.3 dB"
                    )

        if spec.family in (
            ApproximationFamily.CHEBYSHEV_TYPE_II,
            ApproximationFamily.ELLIPTIC,
        ):
            assert spec.stopband_attenuation_db is not None
            sb_mask = ref <= -spec.stopband_attenuation_db + 0.05
            if np.any(sb_mask):
                attenuation = float(-np.min(s21[sb_mask]))
                if attenuation < spec.stopband_attenuation_db - 0.1:
                    issues.append(
                        f"stopband attenuation {attenuation:.2f} dB is below "
                        f"{spec.stopband_attenuation_db:.2f} dB"
                    )
            else:
                issues.append("no stopband samples in the analysis grid")

    # Band-edge loss (single cutoff for LP/HP, geometric edges for BP/BS).
    if spec.response in (FilterResponse.LOW_PASS, FilterResponse.HIGH_PASS):
        edges = [spec.cutoff_hz]
    else:
        edges = list(band_edges(spec))
    edge_loss = tuple(float(x) for x in _s21_db_at(circuit, np.asarray(edges)))
    if spec.family in (
        ApproximationFamily.CHEBYSHEV_TYPE_I,
        ApproximationFamily.ELLIPTIC,
    ):
        assert spec.passband_ripple_db is not None
        expected = -spec.passband_ripple_db
        tol = 0.4
    elif spec.family == ApproximationFamily.CHEBYSHEV_TYPE_II:
        assert spec.stopband_attenuation_db is not None
        expected = -spec.stopband_attenuation_db
        tol = 0.5
    elif spec.family == ApproximationFamily.GAUSSIAN:
        expected, tol = -3.01, 2.0
    elif spec.family == ApproximationFamily.LEGENDRE:
        expected, tol = -3.01, 1.0
    else:
        expected, tol = -3.01, 0.25
    for edge, got in zip(edges, edge_loss, strict=True):
        if abs(got - expected) > tol:
            issues.append(
                f"edge {edge / 1e6:.3f} MHz is {got:.2f} dB "
                f"(expected {expected:.2f} ± {tol:.2f} dB)"
            )

    return ComplianceResult(
        ok=not issues,
        issues=tuple(issues),
        notes=tuple(notes),
        passband_ripple_db=ripple,
        stopband_attenuation_db=attenuation,
        edge_loss_db=edge_loss,
    )


__all__ = ["ComplianceResult", "check_spec_compliance"]
