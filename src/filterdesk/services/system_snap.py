"""Snap system branches to E-series and rebuild the combined response."""

from __future__ import annotations

from dataclasses import dataclass, replace

from filterdesk.analysis.metrics import band_edges
from filterdesk.analysis.multiport import SParameters
from filterdesk.analysis.service import analyze_circuit
from filterdesk.components_std import ESeries, SnapReport, SnapStrategy, snap_circuit
from filterdesk.services.diplexer import (
    BandDiplexerDesign,
    DiplexerDesign,
    evaluate_band_diplexer,
    evaluate_diplexer,
)
from filterdesk.services.duplexer import (
    DuplexerDesign,
    evaluate_duplexer,
)
from filterdesk.services.multiplexer import (
    MultiplexerDesign,
    evaluate_multiplexer,
)


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
    design: DiplexerDesign | BandDiplexerDesign | DuplexerDesign | MultiplexerDesign,
    series: ESeries | str,
    strategy: SnapStrategy | str = SnapStrategy.PRESERVE_LC_RESONANCES,
) -> SystemSnapResult:
    """Snap every branch and recompute the combined metrics on the same sweep."""
    series_enum = ESeries(series)
    strategy_enum = SnapStrategy(strategy)
    if isinstance(design, MultiplexerDesign):
        snapped = tuple(
            snap_circuit(circuit, series_enum, strategy_enum)
            for circuit in design.circuits
        )
        circuits = tuple(item[0] for item in snapped)
        reports = tuple(item[1] for item in snapped)
        analyses = tuple(
            analyze_circuit(circuit, design.sweep, backend=_backend(analysis))
            for circuit, analysis in zip(circuits, design.analyses, strict=True)
        )
        network = SParameters.parallel_branches(
            tuple(SParameters.from_analysis(analysis) for analysis in analyses)
        )
        multiplexer_metrics = evaluate_multiplexer(
            network,
            design.bands,
            [band_edges(spec) for spec in design.specs],
        )
        return SystemSnapResult(
            design=replace(
                design,
                circuits=circuits,
                analyses=analyses,
                network=network,
                metrics=multiplexer_metrics,
            ),
            reports=reports,
            series=series_enum,
            strategy=strategy_enum,
        )
    if isinstance(design, DuplexerDesign):
        tx_snapped, tx_report = snap_circuit(
            design.tx_circuit, series_enum, strategy_enum
        )
        rx_snapped, rx_report = snap_circuit(
            design.rx_circuit, series_enum, strategy_enum
        )
        tx_analysis = analyze_circuit(
            tx_snapped, design.sweep, backend=_backend(design.tx_analysis)
        )
        rx_analysis = analyze_circuit(
            rx_snapped, design.sweep, backend=_backend(design.rx_analysis)
        )
        network = SParameters.parallel_branches(
            (
                SParameters.from_analysis(tx_analysis),
                SParameters.from_analysis(rx_analysis),
            )
        )
        duplexer_metrics = evaluate_duplexer(
            network,
            design.metrics.tx_band_hz,
            design.metrics.rx_band_hz,
            target_isolation_db=design.config.min_isolation_db,
            max_insertion_loss_db=design.config.max_insertion_loss_db,
        )
        return SystemSnapResult(
            design=replace(
                design,
                tx_circuit=tx_snapped,
                rx_circuit=rx_snapped,
                tx_analysis=tx_analysis,
                rx_analysis=rx_analysis,
                network=network,
                metrics=duplexer_metrics,
            ),
            reports=(tx_report, rx_report),
            series=series_enum,
            strategy=strategy_enum,
        )
    low_snapped, low_report = snap_circuit(
        design.low_circuit, series_enum, strategy_enum
    )
    high_snapped, high_report = snap_circuit(
        design.high_circuit, series_enum, strategy_enum
    )
    low_analysis = analyze_circuit(
        low_snapped, design.sweep, backend=_backend(design.low_analysis)
    )
    high_analysis = analyze_circuit(
        high_snapped, design.sweep, backend=_backend(design.high_analysis)
    )
    network = SParameters.parallel_branches(
        (
            SParameters.from_analysis(low_analysis),
            SParameters.from_analysis(high_analysis),
        )
    )
    diplexer_metrics = (
        evaluate_band_diplexer(network, design.config)
        if isinstance(design, BandDiplexerDesign)
        else evaluate_diplexer(network, design.config)
    )
    return SystemSnapResult(
        design=replace(
            design,
            low_circuit=low_snapped,
            high_circuit=high_snapped,
            low_analysis=low_analysis,
            high_analysis=high_analysis,
            network=network,
            metrics=diplexer_metrics,
        ),
        reports=(low_report, high_report),
        series=series_enum,
        strategy=strategy_enum,
    )


def _backend(analysis: object) -> str:
    return str(getattr(analysis, "backend", "") or "abcd")


__all__ = ["SystemSnapResult", "snap_system_design"]
