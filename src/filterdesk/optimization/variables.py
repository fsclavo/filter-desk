"""Tunable-component model for the optimizer (pure, GUI-independent)."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

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


@dataclass(frozen=True, slots=True)
class TunableParam:
    """One scalar component value the optimizer may vary."""

    ref: str
    element_id: str
    field: str
    value: float


def tunable_params(circuit: Circuit) -> list[TunableParam]:
    """Enumerate every reactive/R nominal value as an optimization variable."""
    params: list[TunableParam] = []
    for el in circuit.elements:
        if isinstance(el, IdealInductor):
            params.append(TunableParam(el.id, el.id, "value_h", el.value_h))
        elif isinstance(el, IdealCapacitor):
            params.append(TunableParam(el.id, el.id, "value_f", el.value_f))
        elif isinstance(el, IdealResistor):
            params.append(TunableParam(el.id, el.id, "value_ohm", el.value_ohm))
        elif isinstance(el, (IdealSeriesLC, IdealParallelLC)):
            params.append(
                TunableParam(f"{el.id}.L", el.id, "value_h", el.value_h)
            )
            params.append(
                TunableParam(f"{el.id}.C", el.id, "value_f", el.value_f)
            )
        elif isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
            params.extend(
                (
                    TunableParam(f"{el.id}.Ls", el.id, "series_l_h", el.series_l_h),
                    TunableParam(f"{el.id}.Cs", el.id, "series_c_f", el.series_c_f),
                    TunableParam(f"{el.id}.Lp", el.id, "parallel_l_h", el.parallel_l_h),
                    TunableParam(f"{el.id}.Cp", el.id, "parallel_c_f", el.parallel_c_f),
                )
            )
        elif isinstance(el, NonIdealInductor):
            params.append(TunableParam(el.id, el.id, "value_h", el.value_h))
        elif isinstance(el, NonIdealCapacitor):
            params.append(TunableParam(el.id, el.id, "value_f", el.value_f))
    return params


def _replace_element(el: Element, update: dict[str, float]) -> Element:
    if not update:
        return el
    if isinstance(el, IdealInductor):
        return replace(el, value_h=update.get("value_h", el.value_h))
    if isinstance(el, IdealCapacitor):
        return replace(el, value_f=update.get("value_f", el.value_f))
    if isinstance(el, IdealResistor):
        return replace(el, value_ohm=update.get("value_ohm", el.value_ohm))
    if isinstance(el, (IdealSeriesLC, IdealParallelLC)):
        return replace(
            el,
            value_h=update.get("value_h", el.value_h),
            value_f=update.get("value_f", el.value_f),
        )
    if isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
        return replace(
            el,
            series_l_h=update.get("series_l_h", el.series_l_h),
            series_c_f=update.get("series_c_f", el.series_c_f),
            parallel_l_h=update.get("parallel_l_h", el.parallel_l_h),
            parallel_c_f=update.get("parallel_c_f", el.parallel_c_f),
        )
    if isinstance(el, NonIdealInductor):
        return replace(el, value_h=update.get("value_h", el.value_h))
    if isinstance(el, NonIdealCapacitor):
        return replace(el, value_f=update.get("value_f", el.value_f))
    return el


def apply_values(
    circuit: Circuit,
    params: list[TunableParam],
    values: NDArray[np.floating] | list[float],
) -> Circuit:
    """Return a copy of ``circuit`` with each param set to its new value."""
    changes: dict[str, dict[str, float]] = {}
    for param, value in zip(params, values, strict=True):
        changes.setdefault(param.element_id, {})[param.field] = float(value)
    elements: list[Element] = [
        _replace_element(el, changes.get(el.id, {})) for el in circuit.elements
    ]
    return replace(circuit, elements=elements)
