"""Deterministic component sensitivity for system designs."""

from __future__ import annotations

from dataclasses import dataclass, replace

from filterdesk.domain.circuit import (
    Circuit,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealResistor,
    IdealSeriesLC,
    NonIdealCapacitor,
    NonIdealInductor,
    physical_components,
)
from filterdesk.services.duplexer import DuplexerDesign
from filterdesk.services.multiplexer import MultiplexerDesign
from filterdesk.services.system_rebuild import (
    SystemDesign,
    rebuild_system_with_circuit,
)


class SystemSensitivityError(ValueError):
    """Raised when a system sensitivity analysis cannot be run."""


@dataclass(frozen=True, slots=True)
class SensitivityRow:
    branch: str
    ref: str
    kind: str
    score_db: float
    direction: str
    isolation_delta_db: float | None
    insertion_delta_db: float | None
    out_of_band_delta_db: float | None


@dataclass(frozen=True, slots=True)
class SystemSensitivityReport:
    delta_pct: float
    rows: tuple[SensitivityRow, ...]

    def summary(self) -> str:
        if not self.rows:
            return "No perturbable L/C/R components found."
        worst = self.rows[0]
        return (
            f"{len(self.rows)} components, ±{self.delta_pct:g}%; "
            f"worst: {worst.branch} {worst.ref} "
            f"({worst.score_db:.3f} dB impact)"
        )


@dataclass(frozen=True, slots=True)
class _Snapshot:
    isolation_db: float | None
    insertion_db: float | None
    out_of_band_db: float | None


def analyze_system_sensitivity(
    design: SystemDesign,
    delta_pct: float = 5.0,
) -> SystemSensitivityReport:
    """Perturb every physical L/C/R by ±delta and rank the metric impact."""
    if not 0.0 < delta_pct <= 50.0:
        raise SystemSensitivityError("delta_pct must be in (0, 50]")
    baseline = _snapshot(design)
    branches = _branches(design)
    rows: list[SensitivityRow] = []
    for index, (label, circuit) in enumerate(branches):
        for part in physical_components(circuit):
            if part.kind not in {"inductor", "capacitor", "resistor"}:
                continue
            best_row: SensitivityRow | None = None
            for factor, direction in (
                (1.0 + delta_pct / 100.0, "+"),
                (1.0 - delta_pct / 100.0, "-"),
            ):
                perturbed = _perturb_circuit(circuit, part.ref, factor)
                variant = rebuild_system_with_circuit(design, index, perturbed)
                snapshot = _snapshot(variant)
                row = _row(
                    label,
                    part.ref,
                    part.kind,
                    direction,
                    baseline,
                    snapshot,
                )
                if best_row is None or row.score_db > best_row.score_db:
                    best_row = row
            assert best_row is not None
            rows.append(best_row)
    rows.sort(key=lambda row: (-row.score_db, row.branch, row.ref))
    return SystemSensitivityReport(delta_pct=delta_pct, rows=tuple(rows))


def _branches(design: SystemDesign) -> list[tuple[str, Circuit]]:
    if isinstance(design, MultiplexerDesign):
        return [
            (band.label.capitalize(), circuit)
            for band, circuit in zip(design.bands, design.circuits, strict=True)
        ]
    if isinstance(design, DuplexerDesign):
        return [("TX", design.tx_circuit), ("RX", design.rx_circuit)]
    return [("Low", design.low_circuit), ("High", design.high_circuit)]


def _snapshot(design: SystemDesign) -> _Snapshot:
    if isinstance(design, DuplexerDesign):
        metrics = design.metrics
        insertion = _max_optional(
            metrics.tx_insertion_loss_db, metrics.rx_insertion_loss_db
        )
        return _Snapshot(
            isolation_db=metrics.worst_isolation_db,
            insertion_db=insertion,
            out_of_band_db=None,
        )
    if isinstance(design, MultiplexerDesign):
        return _Snapshot(
            isolation_db=None,
            insertion_db=_max_optional(
                *(band.insertion_loss_db for band in design.metrics.bands)
            ),
            out_of_band_db=_max_optional(
                *(band.out_of_band_db for band in design.metrics.bands)
            ),
        )
    diplexer_metrics = design.metrics
    return _Snapshot(
        isolation_db=None,
        insertion_db=_max_optional(
            diplexer_metrics.low_insertion_loss_db,
            diplexer_metrics.high_insertion_loss_db,
        ),
        out_of_band_db=_max_optional(
            diplexer_metrics.low_out_of_band_db,
            diplexer_metrics.high_out_of_band_db,
        ),
    )


def _row(
    branch: str,
    ref: str,
    kind: str,
    direction: str,
    baseline: _Snapshot,
    variant: _Snapshot,
) -> SensitivityRow:
    isolation_delta = _delta(variant.isolation_db, baseline.isolation_db)
    insertion_delta = _delta(variant.insertion_db, baseline.insertion_db)
    out_of_band_delta = _delta(
        variant.out_of_band_db, baseline.out_of_band_db
    )
    if isolation_delta is not None:
        score = max(
            abs(isolation_delta),
            abs(insertion_delta or 0.0),
        )
    else:
        score = max(
            abs(insertion_delta or 0.0),
            abs(out_of_band_delta or 0.0),
        )
    return SensitivityRow(
        branch=branch,
        ref=ref,
        kind=kind,
        score_db=score,
        direction=direction,
        isolation_delta_db=isolation_delta,
        insertion_delta_db=insertion_delta,
        out_of_band_delta_db=out_of_band_delta,
    )


def _delta(variant: float | None, baseline: float | None) -> float | None:
    if variant is None or baseline is None:
        return None
    return variant - baseline


def _max_optional(*values: float | None) -> float | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _perturb_circuit(circuit: Circuit, ref: str, factor: float) -> Circuit:
    target = next(
        (part for part in physical_components(circuit) if part.ref == ref), None
    )
    if target is None:
        raise SystemSensitivityError(f"unknown component ref: {ref}")
    element_id = target.element_id
    suffix = ref[len(element_id) :]
    new_elements = []
    found = False
    for element in circuit.elements:
        if element.id != element_id:
            new_elements.append(element)
            continue
        found = True
        if isinstance(element, (IdealInductor, NonIdealInductor)):
            new_elements.append(replace(element, value_h=element.value_h * factor))
        elif isinstance(element, (IdealCapacitor, NonIdealCapacitor)):
            new_elements.append(replace(element, value_f=element.value_f * factor))
        elif isinstance(element, IdealResistor):
            new_elements.append(
                replace(element, value_ohm=element.value_ohm * factor)
            )
        elif isinstance(element, (IdealSeriesLC, IdealParallelLC)):
            if suffix == ".L":
                new_elements.append(
                    replace(element, value_h=element.value_h * factor)
                )
            elif suffix == ".C":
                new_elements.append(
                    replace(element, value_f=element.value_f * factor)
                )
            else:
                raise SystemSensitivityError(f"unsupported composite part: {ref}")
        elif isinstance(element, (IdealBruneLC, IdealDualBruneLC)):
            fields = {
                ".Ls": "series_l_h",
                ".Cs": "series_c_f",
                ".Lp": "parallel_l_h",
                ".Cp": "parallel_c_f",
            }
            field = fields.get(suffix)
            if field is None:
                raise SystemSensitivityError(f"unsupported composite part: {ref}")
            new_elements.append(
                replace(element, **{field: getattr(element, field) * factor})
            )
        else:
            raise SystemSensitivityError(f"unsupported component: {ref}")
    if not found:
        raise SystemSensitivityError(f"unknown element id: {element_id}")
    return replace(circuit, elements=new_elements)


__all__ = [
    "SensitivityRow",
    "SystemSensitivityError",
    "SystemSensitivityReport",
    "analyze_system_sensitivity",
]
