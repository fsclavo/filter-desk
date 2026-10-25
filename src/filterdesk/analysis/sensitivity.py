"""Per-component sensitivity of a filter response (read-only analysis).

For every tunable component value we estimate how much |S21| (dB) moves per +1 %
change, using a central finite difference and the fast ladder analyzer. When
limit regions and/or optimizer objectives are supplied we also report which
direction reduces the worst residual (tuning guidance).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import AnalysisResult, SweepConfig
from filterdesk.domain.circuit import Circuit
from filterdesk.domain.overlays import LimitRegion
from filterdesk.optimization.objectives import (
    Objective,
    combined_residuals,
    residual_norm,
)
from filterdesk.optimization.variables import apply_values, tunable_params

Band = tuple[float, float]

_UNIT_BY_FIELD = {
    "value_h": "H",
    "value_f": "F",
    "value_ohm": "Ohm",
    "series_l_h": "H",
    "parallel_l_h": "H",
    "series_c_f": "F",
    "parallel_c_f": "F",
}


class SensitivityError(ValueError):
    """Raised when a sensitivity run cannot start."""


@dataclass(frozen=True, slots=True)
class ParamSensitivity:
    """Sensitivity of one tunable component value."""

    ref: str
    element_id: str
    field: str
    value: float
    unit: str
    max_abs_db_per_pct: float
    rms_db_per_pct: float
    worst_frequency_hz: float
    limit_margin_delta: float | None
    direction: int  # +1 increase, -1 decrease, 0 no guidance


@dataclass(frozen=True, slots=True)
class SensitivityReport:
    """Ranked sensitivities (largest impact first)."""

    rows: tuple[ParamSensitivity, ...]
    relative_step_pct: float
    backend: str
    band: Band | None
    frequency_hz: NDArray[np.float64]
    nominal_s21_db: NDArray[np.float64]


def _residual_norm(
    result: AnalysisResult,
    limits: Sequence[LimitRegion],
    objectives: Sequence[Objective],
) -> float | None:
    if not limits and not objectives:
        return None
    return residual_norm(combined_residuals(result, list(limits), list(objectives)))


def sensitivity(
    circuit: Circuit,
    sweep: SweepConfig,
    *,
    limits: Sequence[LimitRegion] = (),
    objectives: Sequence[Objective] = (),
    relative_step_pct: float = 1.0,
    backend: str = "abcd",
    band: Band | None = None,
) -> SensitivityReport:
    """Rank component values by their effect on |S21| (and limit margins).

    ``relative_step_pct`` is the finite-difference step in percent; the emitted
    slopes are normalised to *per +1 %* so they compare across L/C/R units.
    ``band`` restricts the worst-point/RMS statistics to a frequency interval.
    """
    if relative_step_pct <= 0.0:
        raise SensitivityError("relative_step_pct must be > 0")
    params = tunable_params(circuit)
    if not params:
        raise SensitivityError("circuit has no tunable components")

    frequencies = np.asarray(sweep.frequencies_hz(), dtype=float)
    if band is not None:
        low, high = float(band[0]), float(band[1])
        if low <= 0.0 or high <= low:
            raise SensitivityError("band needs 0 < low < high (Hz)")
        mask = (frequencies >= low) & (frequencies <= high)
        if not np.any(mask):
            raise SensitivityError("band has no sweep samples")
    else:
        mask = np.ones(frequencies.shape, dtype=bool)
    band_freq = frequencies[mask]

    nominal = analyze_circuit(circuit, sweep, backend=backend)
    nominal_db = np.asarray(mag_db(nominal.s21), dtype=float)
    nominal_norm = _residual_norm(nominal, limits, objectives)

    values = np.asarray([p.value for p in params], dtype=float)
    frac = relative_step_pct / 100.0
    rows: list[ParamSensitivity] = []
    for index, param in enumerate(params):
        delta = abs(param.value) * frac
        if delta == 0.0:
            delta = frac  # zero-valued parameter: use an absolute step
        up_values = values.copy()
        up_values[index] = param.value + delta
        down_values = values.copy()
        down_value = param.value - delta
        down_valid = down_value > 0.0
        if down_valid:
            down_values[index] = down_value

        up = analyze_circuit(
            apply_values(circuit, params, up_values), sweep, backend=backend
        )
        up_db = np.asarray(mag_db(up.s21), dtype=float)
        down: AnalysisResult | None = None
        if down_valid:
            down = analyze_circuit(
                apply_values(circuit, params, down_values), sweep, backend=backend
            )
            down_db = np.asarray(mag_db(down.s21), dtype=float)
            slope = (up_db - down_db) / (2.0 * relative_step_pct)
        else:
            slope = (up_db - nominal_db) / relative_step_pct

        band_slope = slope[mask]
        magnitudes = np.abs(band_slope)
        worst = int(np.argmax(magnitudes))
        direction = 0
        margin_delta: float | None = None
        if nominal_norm is not None:
            up_norm = _residual_norm(up, limits, objectives)
            assert up_norm is not None
            down_norm = (
                _residual_norm(down, limits, objectives)
                if down is not None
                else nominal_norm
            )
            assert down_norm is not None
            if up_norm < down_norm - 1e-15:
                direction = 1
            elif down_norm < up_norm - 1e-15:
                direction = -1
            margin_delta = float(nominal_norm - min(up_norm, down_norm))

        rows.append(
            ParamSensitivity(
                ref=param.ref,
                element_id=param.element_id,
                field=param.field,
                value=param.value,
                unit=_UNIT_BY_FIELD.get(param.field, ""),
                max_abs_db_per_pct=float(magnitudes[worst]),
                rms_db_per_pct=float(np.sqrt(np.mean(band_slope * band_slope))),
                worst_frequency_hz=float(band_freq[worst]),
                limit_margin_delta=margin_delta,
                direction=direction,
            )
        )

    rows.sort(key=lambda row: row.max_abs_db_per_pct, reverse=True)
    return SensitivityReport(
        rows=tuple(rows),
        relative_step_pct=relative_step_pct,
        backend=backend,
        band=band,
        frequency_hz=frequencies,
        nominal_s21_db=nominal_db,
    )


__all__ = [
    "Band",
    "ParamSensitivity",
    "SensitivityError",
    "SensitivityReport",
    "sensitivity",
]
