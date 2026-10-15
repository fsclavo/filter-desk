"""Snap ideal component values to standard E-series with selectable strategies."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import StrEnum

from filterdesk.components_std.e_series import (
    ESeries,
    nearest_e_series,
)
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
)


class SnapStrategy(StrEnum):
    INDEPENDENT = "independent"
    L_ONLY = "l_only"
    C_ONLY = "c_only"
    PRESERVE_LC_RESONANCES = "preserve_lc_resonances"


@dataclass(frozen=True, slots=True)
class SnapEntry:
    element_id: str
    part: str
    original: float
    snapped: float

    @property
    def delta_pct(self) -> float:
        return 100.0 * (self.snapped - self.original) / self.original


@dataclass(frozen=True, slots=True)
class SnapReport:
    series: ESeries
    strategy: SnapStrategy
    entries: tuple[SnapEntry, ...]

    @property
    def max_delta_pct(self) -> float:
        if not self.entries:
            return 0.0
        return max(abs(e.delta_pct) for e in self.entries)

    @property
    def snapped_ids(self) -> tuple[str, ...]:
        return tuple(sorted({e.element_id for e in self.entries}))


def _snap_pair_preserve(
    l_orig: float, c_orig: float, series: ESeries
) -> tuple[float, float]:
    """Snap L to the nearest value, then pick C to hold the L·C product.

    L·C fixes the resonance (1/√(LC)), so snapping L first and choosing the
    closest C to the product-preserving ideal keeps every component within about
    half an E-series step while minimising resonance drift.
    """
    l_snap = nearest_e_series(l_orig, series)
    c_ideal = l_orig * c_orig / l_snap
    c_snap = nearest_e_series(c_ideal, series)
    return l_snap, c_snap


def snap_circuit(
    circuit: Circuit,
    series: ESeries | str = ESeries.E24,
    strategy: SnapStrategy | str = SnapStrategy.INDEPENDENT,
) -> tuple[Circuit, SnapReport]:
    """Return a copy of ``circuit`` with values snapped to ``series``.

    Resistor values are snapped except under the L/C-only strategies, where only
    the relevant reactive parts change.
    """
    series_enum = ESeries(series)
    strategy_enum = SnapStrategy(strategy)
    snap_l = strategy_enum in (
        SnapStrategy.INDEPENDENT,
        SnapStrategy.L_ONLY,
        SnapStrategy.PRESERVE_LC_RESONANCES,
    )
    snap_c = strategy_enum in (
        SnapStrategy.INDEPENDENT,
        SnapStrategy.C_ONLY,
        SnapStrategy.PRESERVE_LC_RESONANCES,
    )
    snap_r = strategy_enum in (
        SnapStrategy.INDEPENDENT,
        SnapStrategy.PRESERVE_LC_RESONANCES,
    )
    preserve = strategy_enum == SnapStrategy.PRESERVE_LC_RESONANCES
    entries: list[SnapEntry] = []

    def record(element_id: str, part: str, original: float, snapped: float) -> None:
        if snapped != original:
            entries.append(SnapEntry(element_id, part, original, snapped))

    def snap(value: float, enabled: bool) -> float:
        return nearest_e_series(value, series_enum) if enabled else value

    new_elements: list[Element] = []
    for el in circuit.elements:
        if isinstance(el, IdealCapacitor):
            c_new = snap(el.value_f, snap_c)
            record(el.id, "C", el.value_f, c_new)
            new_elements.append(dataclasses.replace(el, value_f=c_new))
        elif isinstance(el, IdealInductor):
            l_new = snap(el.value_h, snap_l)
            record(el.id, "L", el.value_h, l_new)
            new_elements.append(dataclasses.replace(el, value_h=l_new))
        elif isinstance(el, IdealResistor):
            r_new = snap(el.value_ohm, snap_r)
            record(el.id, "R", el.value_ohm, r_new)
            new_elements.append(dataclasses.replace(el, value_ohm=r_new))
        elif isinstance(el, (IdealSeriesLC, IdealParallelLC)):
            if preserve:
                l_new, c_new = _snap_pair_preserve(
                    el.value_h, el.value_f, series_enum
                )
            else:
                l_new = snap(el.value_h, snap_l)
                c_new = snap(el.value_f, snap_c)
            record(el.id, "L", el.value_h, l_new)
            record(el.id, "C", el.value_f, c_new)
            new_elements.append(
                dataclasses.replace(el, value_h=l_new, value_f=c_new)
            )
        elif isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
            if preserve:
                ls_new, cs_new = _snap_pair_preserve(
                    el.series_l_h, el.series_c_f, series_enum
                )
                lp_new, cp_new = _snap_pair_preserve(
                    el.parallel_l_h, el.parallel_c_f, series_enum
                )
            else:
                ls_new = snap(el.series_l_h, snap_l)
                cs_new = snap(el.series_c_f, snap_c)
                lp_new = snap(el.parallel_l_h, snap_l)
                cp_new = snap(el.parallel_c_f, snap_c)
            record(el.id, "Ls", el.series_l_h, ls_new)
            record(el.id, "Cs", el.series_c_f, cs_new)
            record(el.id, "Lp", el.parallel_l_h, lp_new)
            record(el.id, "Cp", el.parallel_c_f, cp_new)
            new_elements.append(
                dataclasses.replace(
                    el,
                    series_l_h=ls_new,
                    series_c_f=cs_new,
                    parallel_l_h=lp_new,
                    parallel_c_f=cp_new,
                )
            )
        else:  # pragma: no cover - exhaustive over Element
            new_elements.append(el)

    snapped_circuit = dataclasses.replace(circuit, elements=new_elements)
    report = SnapReport(
        series=series_enum,
        strategy=strategy_enum,
        entries=tuple(entries),
    )
    return snapped_circuit, report
