"""Network analyzer protocol."""

from __future__ import annotations

from typing import Protocol

from filterdesk.analysis.types import AnalysisResult, SweepConfig
from filterdesk.domain.circuit import Circuit


class NetworkAnalyzer(Protocol):
    """Analyze a canonical Circuit over a frequency sweep."""

    name: str

    def analyze(self, circuit: Circuit, sweep: SweepConfig) -> AnalysisResult: ...
