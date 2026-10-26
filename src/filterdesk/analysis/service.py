"""High-level analyze helper."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from filterdesk.analysis.adapters import LadderABCDAnalyzer, ScikitRFAnalyzer
from filterdesk.analysis.adapters.abcd_ladder import AnalysisError
from filterdesk.analysis.types import AnalysisResult, SweepConfig
from filterdesk.domain.circuit import Circuit


def get_analyzer(name: str = "abcd") -> LadderABCDAnalyzer | ScikitRFAnalyzer:
    key = name.lower().replace("-", "_")
    if key in {"abcd", "ladder_abcd", "ladder"}:
        return LadderABCDAnalyzer()
    if key in {"skrf", "scikit_rf", "scikit-rf"}:
        return ScikitRFAnalyzer()
    raise AnalysisError(f"unknown analyzer: {name!r}")


def analyze_circuit(
    circuit: Circuit,
    sweep: SweepConfig,
    *,
    backend: str = "abcd",
) -> AnalysisResult:
    return get_analyzer(backend).analyze(circuit, sweep)


def analyze_at_frequencies(
    circuit: Circuit,
    frequency_hz: Sequence[float] | NDArray[np.floating],
    *,
    backend: str = "abcd",
) -> AnalysisResult:
    return get_analyzer(backend).analyze_at_frequencies(
        circuit, np.asarray(frequency_hz, dtype=float)
    )
