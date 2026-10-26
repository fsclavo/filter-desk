"""Derive a new target specification from an analyzed circuit response.

This is deliberately a *target* update, not a re-synthesis: family, order,
topology, ripple and stopband parameters are retained. Only cutoff/center and
bandwidth are derived from the response, using the criterion implied by the
family's cutoff definition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.types import AnalysisResult
from filterdesk.domain.circuit import Circuit
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
)
from filterdesk.domain.specs import FilterSpec, validate_spec


class SpecUpdateError(ValueError):
    """Raised when the response does not contain the required crossing."""


@dataclass(frozen=True, slots=True)
class SpecUpdate:
    old_spec: FilterSpec
    new_spec: FilterSpec
    criterion: str
    threshold_db: float
    edges_hz: tuple[float, ...]
    notes: tuple[str, ...]


def _criterion(spec: FilterSpec) -> tuple[float, str]:
    if spec.family in (
        ApproximationFamily.CHEBYSHEV_TYPE_I,
        ApproximationFamily.ELLIPTIC,
    ):
        if spec.passband_ripple_db is None:
            raise SpecUpdateError("ripple-edge update needs passband ripple")
        return -float(spec.passband_ripple_db), "passband ripple edge"
    if spec.family == ApproximationFamily.CHEBYSHEV_TYPE_II:
        if spec.stopband_attenuation_db is None:
            raise SpecUpdateError("stopband-edge update needs stopband attenuation")
        return -float(spec.stopband_attenuation_db), "stopband edge"
    if spec.cutoff_definition is CutoffDefinition.STOPBAND_EDGE:
        if spec.stopband_attenuation_db is None:
            raise SpecUpdateError("stopband-edge update needs stopband attenuation")
        return -float(spec.stopband_attenuation_db), "stopband edge"
    return -3.0, "half-power (-3 dB)"


def _crossings(
    frequency_hz: NDArray[np.float64], values_db: NDArray[np.float64], threshold: float
) -> list[tuple[float, int]]:
    f = np.asarray(frequency_hz, dtype=float)
    y = np.asarray(values_db, dtype=float)
    out: list[tuple[float, int]] = []
    for index in range(f.size - 1):
        a, b = y[index], y[index + 1]
        if (a < threshold <= b) or (a >= threshold > b):
            # log-frequency interpolation; avoids bias over a wide sweep
            t = (threshold - a) / (b - a)
            if not math.isfinite(t) or t < 0.0 or t > 1.0:
                continue
            log_f = math.log(f[index]) + t * (
                math.log(f[index + 1]) - math.log(f[index])
            )
            out.append((math.exp(log_f), index))
    return out


def update_spec_from_response(
    spec: FilterSpec, circuit: Circuit, analysis: AnalysisResult
) -> SpecUpdate:
    """Return a manual target update derived from the current response."""
    threshold, criterion = _criterion(spec)
    frequency = np.asarray(analysis.frequency_hz, dtype=float)
    values = np.asarray(mag_db(analysis.s21), dtype=float)
    if frequency.size < 2:
        raise SpecUpdateError("analysis needs at least two points")
    crossings = _crossings(frequency, values, threshold)
    if len(crossings) < 2 and spec.response in (
        FilterResponse.BAND_PASS,
        FilterResponse.BAND_STOP,
    ):
        raise SpecUpdateError(
            f"fewer than two {criterion} crossings in the analysis sweep"
        )
    if not crossings:
        raise SpecUpdateError(
            f"no {criterion} crossing in the analysis sweep; widen the sweep"
        )

    edges: tuple[float, ...]
    if spec.response in (FilterResponse.LOW_PASS, FilterResponse.HIGH_PASS):
        edge = crossings[0][0]
        new_spec = replace(
            spec,
            cutoff_hz=edge,
            z_source_ohm=circuit.port_in.impedance_ohm,
            z_load_ohm=circuit.port_out.impedance_ohm,
        )
        edges = (edge,)
    else:
        low, high = crossings[0][0], crossings[-1][0]
        if high <= low:
            raise SpecUpdateError("invalid low/high response edges")
        new_spec = replace(
            spec,
            f_center_hz=math.sqrt(low * high),
            bandwidth_hz=high - low,
            z_source_ohm=circuit.port_in.impedance_ohm,
            z_load_ohm=circuit.port_out.impedance_ohm,
        )
        edges = (low, high)
    validate_spec(new_spec)
    notes = (
        f"derived from {criterion} ({threshold:g} dB)",
        "family, order, topology, ripple and stopband parameters retained",
        "circuit values were not changed; Synthesize would produce a new ideal circuit",
    )
    return SpecUpdate(
        old_spec=spec,
        new_spec=new_spec,
        criterion=criterion,
        threshold_db=threshold,
        edges_hz=edges,
        notes=notes,
    )


__all__ = ["SpecUpdate", "SpecUpdateError", "update_spec_from_response"]
