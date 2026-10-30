"""System-level report metadata for diplexers, duplexers and multiplexers."""

from __future__ import annotations

from dataclasses import dataclass

from filterdesk.domain.circuit import Circuit
from filterdesk.domain.units import format_engineering
from filterdesk.services.diplexer import BandDiplexerDesign, DiplexerDesign
from filterdesk.services.duplexer import DuplexerDesign
from filterdesk.services.multiplexer import MultiplexerDesign


@dataclass(frozen=True, slots=True)
class SystemBranch:
    label: str
    circuit: Circuit


@dataclass(frozen=True, slots=True)
class SystemReport:
    title: str
    branches: tuple[SystemBranch, ...]
    summary: tuple[tuple[str, str], ...]
    notes: tuple[str, ...]


def system_report(
    design: DiplexerDesign | BandDiplexerDesign | DuplexerDesign | MultiplexerDesign,
) -> SystemReport:
    """Build the common report header/branches for any supported system."""
    if isinstance(design, MultiplexerDesign):
        return _multiplexer_report(design)
    if isinstance(design, DuplexerDesign):
        return _duplexer_report(design)
    return _diplexer_report(design)


def _diplexer_report(
    design: DiplexerDesign | BandDiplexerDesign,
) -> SystemReport:
    metrics = design.metrics
    if isinstance(design, BandDiplexerDesign):
        title = "BPF + BPF diplexer"
    else:
        title = "LPF + HPF diplexer"
    summary: list[tuple[str, str]] = [
        ("Ports", "1 = common, 2 = low, 3 = high"),
        ("Order", str(design.low_spec.order)),
        ("Family", design.low_spec.family.value),
        ("Reference Z0", format_engineering(design.low_spec.z_source_ohm, "Ohm")),
        ("Low band", _band(metrics.low_band_hz)),
        ("Low insertion loss", _db(metrics.low_insertion_loss_db)),
        ("Low out-of-band", _db(metrics.low_out_of_band_db)),
        ("Low return loss", _db(metrics.low_return_loss_db)),
        ("High band", _band(metrics.high_band_hz)),
        ("High insertion loss", _db(metrics.high_insertion_loss_db)),
        ("High out-of-band", _db(metrics.high_out_of_band_db)),
        ("High return loss", _db(metrics.high_return_loss_db)),
        ("Crossover", _freq(metrics.crossover_hz)),
    ]
    return SystemReport(
        title=title,
        branches=(
            SystemBranch("Low", design.low_circuit),
            SystemBranch("High", design.high_circuit),
        ),
        summary=tuple(summary),
        notes=_common_notes("1 = common, 2 = low, 3 = high"),
    )


def _duplexer_report(design: DuplexerDesign) -> SystemReport:
    metrics = design.metrics
    summary = [
        ("Ports", "1 = antenna, 2 = TX, 3 = RX"),
        ("Order", str(design.selected_order)),
        ("Family", design.tx_spec.family.value),
        ("Reference Z0", format_engineering(design.tx_spec.z_source_ohm, "Ohm")),
        ("TX band", _band(metrics.tx_band_hz)),
        ("TX insertion loss", _db(metrics.tx_insertion_loss_db)),
        ("TX return loss", _db(metrics.tx_return_loss_db)),
        ("TX-band isolation", _db(metrics.tx_band_isolation_db)),
        ("RX band", _band(metrics.rx_band_hz)),
        ("RX insertion loss", _db(metrics.rx_insertion_loss_db)),
        ("RX return loss", _db(metrics.rx_return_loss_db)),
        ("RX-band isolation", _db(metrics.rx_band_isolation_db)),
        ("Worst isolation", _db(metrics.worst_isolation_db)),
        ("Isolation target", f"{metrics.target_isolation_db:.2f} dB"),
        ("Target met", "yes" if metrics.meets_target else "no"),
    ]
    return SystemReport(
        title="LC TX/RX duplexer",
        branches=(
            SystemBranch("TX", design.tx_circuit),
            SystemBranch("RX", design.rx_circuit),
        ),
        summary=tuple(summary),
        notes=_common_notes("1 = antenna, 2 = TX, 3 = RX")
        + ("Isolation is the combined |S32| in each band.",),
    )


def _multiplexer_report(design: MultiplexerDesign) -> SystemReport:
    metrics = design.metrics
    summary: list[tuple[str, str]] = [
        (
            "Ports",
            "1 = common, "
            + ", ".join(
                f"{index + 2} = {band.label}"
                for index, band in enumerate(design.bands)
            ),
        ),
        ("Order", str(design.config.order)),
        ("Family", design.config.family.value),
        ("Reference Z0", format_engineering(design.config.z0_ohm, "Ohm")),
    ]
    for band in metrics.bands:
        label = band.label.capitalize()
        summary.extend(
            [
                (f"{label} band", _band(band.band_hz)),
                (f"{label} insertion loss", _db(band.insertion_loss_db)),
                (f"{label} out-of-band", _db(band.out_of_band_db)),
                (f"{label} return loss", _db(band.return_loss_db)),
            ]
        )
    for index, crossover in enumerate(metrics.crossovers_hz):
        first = metrics.bands[index].label.capitalize()
        second = metrics.bands[index + 1].label.capitalize()
        summary.append((f"{first}/{second} crossover", _freq(crossover)))
    ports = "1 = common, " + ", ".join(
        f"{index + 2} = {band.label}"
        for index, band in enumerate(design.bands)
    )
    return SystemReport(
        title=f"{len(design.bands)}-band BPF multiplexer",
        branches=tuple(
            SystemBranch(band.label.capitalize(), circuit)
            for band, circuit in zip(design.bands, design.circuits, strict=True)
        ),
        summary=tuple(summary),
        notes=_common_notes(ports),
    )


def _common_notes(ports: str) -> tuple[str, ...]:
    return (
        "Ideal common-node LC model; no antenna, cavity, circulator, isolation "
        "network, EM, thermal or high-power validation.",
        f"Ports: {ports}. Metrics refer to the combined network, not each "
        "branch alone.",
    )


def _band(band: tuple[float, float]) -> str:
    return (
        f"{format_engineering(band[0], 'Hz')}–"
        f"{format_engineering(band[1], 'Hz')}"
    )


def _freq(value: float | None) -> str:
    return "n/a" if value is None else format_engineering(value, "Hz")


def _db(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f} dB"


__all__ = ["SystemBranch", "SystemReport", "system_report"]
