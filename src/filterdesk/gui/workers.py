"""Background analysis worker (Qt)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import AnalysisResult, SweepConfig
from filterdesk.domain.circuit import Circuit


class AnalyzeWorker(QObject):
    finished = Signal(object)  # AnalysisResult
    failed = Signal(str)

    def __init__(
        self,
        circuit: Circuit,
        sweep: SweepConfig,
        backend: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._circuit = circuit
        self._sweep = sweep
        self._backend = backend

    def run(self) -> None:
        try:
            result = analyze_circuit(
                self._circuit, self._sweep, backend=self._backend
            )
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001 — surface to UI
            self.failed.emit(str(exc))


def start_analyze_thread(
    circuit: Circuit,
    sweep: SweepConfig,
    backend: str,
    on_finished: Callable[[object], None],
    on_failed: Callable[[str], None],
) -> tuple[QThread, AnalyzeWorker]:
    thread = QThread()
    worker = AnalyzeWorker(circuit, sweep, backend)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(on_finished)
    worker.failed.connect(on_failed)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    # Keep a reference on the thread so the worker is not GC'd early.
    thread._filterdesk_worker = worker  # type: ignore[attr-defined]
    return thread, worker


__all__ = ["AnalyzeWorker", "AnalysisResult", "start_analyze_thread"]
