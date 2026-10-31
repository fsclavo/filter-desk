"""Snap system branches to E-series and rebuild the combined response."""

from __future__ import annotations

from dataclasses import dataclass

from filterdesk.components_std import ESeries, SnapReport, SnapStrategy, snap_circuit
from filterdesk.services.diplexer import BandDiplexerDesign, DiplexerDesign
from filterdesk.services.duplexer import DuplexerDesign
from filterdesk.services.multiplexer import MultiplexerDesign
from filterdesk.services.system_rebuild import SystemDesign, rebuild_system_design


@dataclass(frozen=True, slots=True)
class SystemSnapResult:
    design: (
        DiplexerDesign | BandDiplexerDesign | DuplexerDesign | MultiplexerDesign
    )
    reports: tuple[SnapReport, ...]
    series: ESeries
    strategy: SnapStrategy

    @property
    def max_delta_pct(self) -> float:
        return max((report.max_delta_pct for report in self.reports), default=0.0)

    @property
    def changed(self) -> bool:
        return any(report.entries for report in self.reports)


def snap_system_design(
    design: SystemDesign,
    series: ESeries | str,
    strategy: SnapStrategy | str = SnapStrategy.PRESERVE_LC_RESONANCES,
) -> SystemSnapResult:
    """Snap every branch and recompute the combined metrics on the same sweep."""
    series_enum = ESeries(series)
    strategy_enum = SnapStrategy(strategy)
    if isinstance(design, MultiplexerDesign):
        circuits = tuple(
            snap_circuit(circuit, series_enum, strategy_enum)[0]
            for circuit in design.circuits
        )
        reports = tuple(
            snap_circuit(circuit, series_enum, strategy_enum)[1]
            for circuit in design.circuits
        )
    elif isinstance(design, DuplexerDesign):
        tx_snapped, tx_report = snap_circuit(
            design.tx_circuit, series_enum, strategy_enum
        )
        rx_snapped, rx_report = snap_circuit(
            design.rx_circuit, series_enum, strategy_enum
        )
        circuits = (tx_snapped, rx_snapped)
        reports = (tx_report, rx_report)
    else:
        low_snapped, low_report = snap_circuit(
            design.low_circuit, series_enum, strategy_enum
        )
        high_snapped, high_report = snap_circuit(
            design.high_circuit, series_enum, strategy_enum
        )
        circuits = (low_snapped, high_snapped)
        reports = (low_report, high_report)
    return SystemSnapResult(
        design=rebuild_system_design(design, circuits),
        reports=reports,
        series=series_enum,
        strategy=strategy_enum,
    )


__all__ = ["SystemSnapResult", "snap_system_design"]
