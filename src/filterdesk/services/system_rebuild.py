"""Reanalyze a system design after changing its branch circuits."""

from __future__ import annotations

from dataclasses import replace

from filterdesk.analysis.metrics import band_edges
from filterdesk.analysis.multiport import SParameters
from filterdesk.analysis.service import analyze_circuit
from filterdesk.domain.circuit import Circuit
from filterdesk.services.diplexer import (
    BandDiplexerDesign,
    DiplexerDesign,
    evaluate_band_diplexer,
    evaluate_diplexer,
)
from filterdesk.services.duplexer import DuplexerDesign, evaluate_duplexer
from filterdesk.services.multiplexer import (
    MultiplexerDesign,
    evaluate_multiplexer,
)

SystemDesign = DiplexerDesign | BandDiplexerDesign | DuplexerDesign | MultiplexerDesign


def rebuild_system_design(
    design: SystemDesign, circuits: tuple[Circuit, ...]
) -> SystemDesign:
    """Reanalyze ``circuits`` on the stored sweep and rebuild the N-port."""
    if isinstance(design, MultiplexerDesign):
        if len(circuits) != len(design.circuits):
            raise ValueError("multiplexer branch count changed")
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
        return replace(
            design,
            circuits=circuits,
            analyses=analyses,
            network=network,
            metrics=multiplexer_metrics,
        )
    if isinstance(design, DuplexerDesign):
        if len(circuits) != 2:
            raise ValueError("duplexer needs TX and RX circuits")
        tx_analysis = analyze_circuit(
            circuits[0], design.sweep, backend=_backend(design.tx_analysis)
        )
        rx_analysis = analyze_circuit(
            circuits[1], design.sweep, backend=_backend(design.rx_analysis)
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
        return replace(
            design,
            tx_circuit=circuits[0],
            rx_circuit=circuits[1],
            tx_analysis=tx_analysis,
            rx_analysis=rx_analysis,
            network=network,
            metrics=duplexer_metrics,
        )
    if len(circuits) != 2:
        raise ValueError("diplexer needs low and high circuits")
    low_analysis = analyze_circuit(
        circuits[0], design.sweep, backend=_backend(design.low_analysis)
    )
    high_analysis = analyze_circuit(
        circuits[1], design.sweep, backend=_backend(design.high_analysis)
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
    return replace(
        design,
        low_circuit=circuits[0],
        high_circuit=circuits[1],
        low_analysis=low_analysis,
        high_analysis=high_analysis,
        network=network,
        metrics=diplexer_metrics,
    )


def _backend(analysis: object) -> str:
    return str(getattr(analysis, "backend", "") or "abcd")


__all__ = ["SystemDesign", "rebuild_system_design"]
