"""Compare 2-port VNA captures against a system's S-parameter paths."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from filterdesk.analysis.multiport import SParameters
from filterdesk.analysis.types import AnalysisResult
from filterdesk.services.compare import CompareResult, compare_results
from filterdesk.services.diplexer import BandDiplexerDesign, DiplexerDesign
from filterdesk.services.duplexer import DuplexerDesign
from filterdesk.services.multiplexer import MultiplexerDesign
from filterdesk.services.system_rebuild import SystemDesign


class SystemCompareError(ValueError):
    """Raised when a system path comparison cannot be performed."""


@dataclass(frozen=True, slots=True)
class MeasurementPath:
    label: str
    from_port: int
    to_port: int


@dataclass(frozen=True, slots=True)
class PathComparison:
    path: MeasurementPath
    compare: CompareResult


def default_measurement_paths(design: SystemDesign) -> tuple[MeasurementPath, ...]:
    """Return the useful 2-port paths for the current system."""
    if isinstance(design, MultiplexerDesign):
        paths = [
            MeasurementPath(
                f"Common → {band.label.capitalize()}", 0, index + 1
            )
            for index, band in enumerate(design.bands)
        ]
        paths += [
            MeasurementPath(
                f"{design.bands[index].label.capitalize()} ↔ "
                f"{design.bands[index + 1].label.capitalize()}",
                index + 1,
                index + 2,
            )
            for index in range(len(design.bands) - 1)
        ]
        return tuple(paths)
    if isinstance(design, DuplexerDesign):
        return (
            MeasurementPath("Common → TX", 0, 1),
            MeasurementPath("Common → RX", 0, 2),
            MeasurementPath("TX ↔ RX", 1, 2),
        )
    if isinstance(design, BandDiplexerDesign):
        return (
            MeasurementPath("Common → Low", 0, 1),
            MeasurementPath("Common → High", 0, 2),
            MeasurementPath("Low ↔ High", 1, 2),
        )
    if isinstance(design, DiplexerDesign):
        return (
            MeasurementPath("Common → Low", 0, 1),
            MeasurementPath("Common → High", 0, 2),
            MeasurementPath("Low ↔ High", 1, 2),
        )
    raise SystemCompareError("unsupported system design")


def compare_system_paths(
    design: SystemDesign,
    measurements: Mapping[str, AnalysisResult],
) -> tuple[PathComparison, ...]:
    """Compare each supplied measured path against the simulated network.

    Keys are path labels from :func:`default_measurement_paths`. Every measured
    file is a 2-port capture with all other system ports terminated in 50 Ω.
    """
    results: list[PathComparison] = []
    for path in default_measurement_paths(design):
        measured = measurements.get(path.label)
        if measured is None:
            continue
        simulated = _simulated_path(design.network, path)
        try:
            comparison = compare_results(simulated, measured)
        except Exception as exc:  # CompareError is a ValueError
            raise SystemCompareError(f"{path.label}: {exc}") from exc
        results.append(PathComparison(path=path, compare=comparison))
    if not results:
        raise SystemCompareError("no measured paths were supplied")
    return tuple(results)


def _simulated_path(
    network: SParameters, path: MeasurementPath
) -> AnalysisResult:
    if not 0 <= path.from_port < network.n_ports:
        raise SystemCompareError(f"invalid from port: {path.from_port}")
    if not 0 <= path.to_port < network.n_ports:
        raise SystemCompareError(f"invalid to port: {path.to_port}")
    if path.from_port == path.to_port:
        raise SystemCompareError("from and to ports must differ")
    s11 = network.s[:, path.from_port, path.from_port]
    s21 = network.s[:, path.to_port, path.from_port]
    s12 = network.s[:, path.from_port, path.to_port]
    s22 = network.s[:, path.to_port, path.to_port]
    z0 = network.z0_ohm
    zeros = np.zeros_like(network.frequency_hz, dtype=np.complex128)
    return AnalysisResult(
        frequency_hz=network.frequency_hz,
        s11=s11,
        s21=s21,
        s12=s12,
        s22=s22,
        zin_ohm=zeros + z0,
        zout_ohm=zeros + z0,
        z0_source_ohm=z0,
        z0_load_ohm=z0,
        backend="simulated",
    )


__all__ = [
    "MeasurementPath",
    "PathComparison",
    "SystemCompareError",
    "compare_system_paths",
    "default_measurement_paths",
]
