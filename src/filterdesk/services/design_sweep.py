"""Design-parameter sweeps (order/family/frequency/ripple trade-off tables).

Each value is applied to a base specification, validated, synthesized and
analyzed over a common sweep so the rows can be compared. Invalid combinations
(for example even-order elliptic) are reported per row instead of aborting the
whole sweep. Band metrics come from :mod:`filterdesk.analysis.metrics`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from filterdesk.analysis.metrics import (
    Band,
    BandMetrics,
    band_edges,
    band_metrics,
    default_bands,
)
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import (
    ApproximationFamily,
    FilterResponse,
)
from filterdesk.domain.specs import (
    FilterSpec,
    default_cutoff_definition,
    validate_spec,
)
from filterdesk.domain.units import parse_si
from filterdesk.synthesis import synthesis_note, synthesize


class SweepAxis(StrEnum):
    ORDER = "order"
    FAMILY = "family"
    CUTOFF = "cutoff"
    CENTER = "center"
    BANDWIDTH = "bandwidth"
    RIPPLE = "ripple"
    STOPBAND_ATT = "stopband_att"
    M_FACTOR = "m_factor"


class DesignSweepError(ValueError):
    """Raised when a sweep cannot start."""


@dataclass(frozen=True, slots=True)
class DesignSweepConfig:
    """Base specification plus the values to sweep along one axis."""

    base_spec: FilterSpec
    axis: SweepAxis
    values: tuple[float | str, ...]
    points: int = 512
    passband: Band | None = None
    stopband: Band | None = None


@dataclass(frozen=True, slots=True)
class DesignSweepRow:
    value: float | str
    ok: bool
    error: str | None
    n_components: int
    metrics: BandMetrics | None
    note: str | None
    spec: FilterSpec | None


def parse_values(axis: SweepAxis, raw: str) -> tuple[float | str, ...]:
    """Parse a comma-separated value list for ``axis`` (SI units for Hz axes)."""
    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    if not tokens:
        raise DesignSweepError("no values given")
    if axis == SweepAxis.FAMILY:
        return tuple(tokens)
    if axis == SweepAxis.ORDER:
        return tuple(int(token) for token in tokens)
    if axis in (SweepAxis.CUTOFF, SweepAxis.CENTER, SweepAxis.BANDWIDTH):
        return tuple(parse_si(token) for token in tokens)
    return tuple(float(token) for token in tokens)


def default_sweep(spec: FilterSpec, points: int) -> SweepConfig:
    """Frequency sweep covering the base spec band (and its stopband)."""
    low_edge, high_edge = band_edges(spec)
    if spec.response in (FilterResponse.LOW_PASS, FilterResponse.HIGH_PASS):
        return SweepConfig(
            low_edge / 20.0, low_edge * 20.0, points, SweepSpacing.LOGARITHMIC
        )
    return SweepConfig(
        low_edge / 5.0, high_edge * 5.0, points, SweepSpacing.LOGARITHMIC
    )


def _normalize_family(spec: FilterSpec, family: ApproximationFamily) -> FilterSpec:
    """Adapt family-specific fields so a family comparison stays valid."""
    ripple = spec.passband_ripple_db
    stop_att = spec.stopband_attenuation_db
    m_parameter = spec.m_parameter
    if family == ApproximationFamily.CHEBYSHEV_TYPE_I:
        ripple = ripple if ripple and ripple > 0.0 else 0.1
        stop_att = None
        m_parameter = None
    elif family == ApproximationFamily.CHEBYSHEV_TYPE_II:
        stop_att = stop_att if stop_att and stop_att > 0.0 else 40.0
        ripple = None
        m_parameter = None
    elif family == ApproximationFamily.ELLIPTIC:
        ripple = ripple if ripple and ripple > 0.0 else 0.1
        stop_att = stop_att if stop_att and stop_att > 0.0 else 40.0
        if stop_att <= ripple:
            stop_att = ripple * 10.0
        m_parameter = None
    elif family == ApproximationFamily.M_DERIVED:
        m_parameter = (
            m_parameter if m_parameter and 0.0 < m_parameter < 1.0 else 0.6
        )
        ripple = None
        stop_att = None
    else:
        ripple = None
        stop_att = None
        m_parameter = None
    return replace(
        spec,
        family=family,
        cutoff_definition=default_cutoff_definition(family),
        passband_ripple_db=ripple,
        stopband_attenuation_db=stop_att,
        m_parameter=m_parameter,
    )


def _apply_axis(
    spec: FilterSpec, axis: SweepAxis, value: float | str
) -> FilterSpec:
    if axis == SweepAxis.ORDER:
        return replace(spec, order=int(value))
    if axis == SweepAxis.FAMILY:
        return _normalize_family(spec, ApproximationFamily(str(value)))
    if axis == SweepAxis.CUTOFF:
        return replace(spec, cutoff_hz=float(value))
    if axis == SweepAxis.CENTER:
        return replace(spec, f_center_hz=float(value))
    if axis == SweepAxis.BANDWIDTH:
        return replace(spec, bandwidth_hz=float(value))
    if axis == SweepAxis.RIPPLE:
        return replace(spec, passband_ripple_db=float(value))
    if axis == SweepAxis.STOPBAND_ATT:
        return replace(spec, stopband_attenuation_db=float(value))
    if axis == SweepAxis.M_FACTOR:
        return replace(spec, m_parameter=float(value))
    raise DesignSweepError(f"unsupported axis: {axis!r}")


def run_design_sweep(
    config: DesignSweepConfig,
) -> list[DesignSweepRow]:
    """Synthesize/analyze one variant per value; invalid variants are flagged."""
    if not config.values:
        raise DesignSweepError("no values to sweep")
    if config.points < 2:
        raise DesignSweepError("points must be >= 2")
    sweep = default_sweep(config.base_spec, config.points)
    passband, stopband = default_bands(config.base_spec)
    if config.passband is not None:
        passband = config.passband
    if config.stopband is not None:
        stopband = config.stopband

    rows: list[DesignSweepRow] = []
    for value in config.values:
        try:
            spec = _apply_axis(config.base_spec, config.axis, value)
            validate_spec(spec)
            synth = synthesize(spec)
            analysis = analyze_circuit(synth.circuit, sweep)
            metrics = band_metrics(
                analysis, passband=passband, stopband=stopband
            )
        except ValueError as exc:
            rows.append(
                DesignSweepRow(
                    value=value,
                    ok=False,
                    error=str(exc),
                    n_components=0,
                    metrics=None,
                    note=None,
                    spec=None,
                )
            )
            continue
        rows.append(
            DesignSweepRow(
                value=value,
                ok=True,
                error=None,
                n_components=len(synth.circuit.elements),
                metrics=metrics,
                note=synthesis_note(spec),
                spec=spec,
            )
        )
    return rows


__all__ = [
    "Band",
    "DesignSweepConfig",
    "DesignSweepError",
    "DesignSweepRow",
    "SweepAxis",
    "default_bands",
    "default_sweep",
    "parse_values",
    "run_design_sweep",
]
