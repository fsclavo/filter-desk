"""Background analysis worker (Qt)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import AnalysisResult, SweepConfig
from filterdesk.domain.circuit import Circuit
from filterdesk.domain.overlays import LimitRegion
from filterdesk.io.touchstone import TouchstoneData, read_touchstone
from filterdesk.montecarlo import MonteCarloConfig, run_monte_carlo
from filterdesk.optimization import OptimizationConfig, optimize_circuit


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


class MonteCarloWorker(QObject):
    finished = Signal(object)  # MonteCarloResult
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(
        self,
        circuit: Circuit,
        sweep: SweepConfig,
        config: MonteCarloConfig,
        limits: list[LimitRegion],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._circuit = circuit
        self._sweep = sweep
        self._config = config
        self._limits = limits

    def run(self) -> None:
        try:
            result = run_monte_carlo(
                self._circuit,
                self._sweep,
                self._config,
                limits=self._limits,
                progress=self.progress.emit,
            )
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001 — surface to UI
            self.failed.emit(str(exc))


def start_monte_carlo_thread(
    circuit: Circuit,
    sweep: SweepConfig,
    config: MonteCarloConfig,
    limits: list[LimitRegion],
    on_finished: Callable[[object], None],
    on_failed: Callable[[str], None],
) -> tuple[QThread, MonteCarloWorker]:
    thread = QThread()
    worker = MonteCarloWorker(circuit, sweep, config, limits)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(on_finished)
    worker.failed.connect(on_failed)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread._filterdesk_worker = worker  # type: ignore[attr-defined]
    return thread, worker


class OptimizeWorker(QObject):
    finished = Signal(object)  # OptimizationResult
    failed = Signal(str)

    def __init__(
        self,
        circuit: Circuit,
        sweep: SweepConfig,
        limits: list[LimitRegion],
        config: OptimizationConfig,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._circuit = circuit
        self._sweep = sweep
        self._limits = limits
        self._config = config

    def run(self) -> None:
        try:
            result = optimize_circuit(
                self._circuit, self._sweep, self._limits, self._config
            )
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001 — surface to UI
            self.failed.emit(str(exc))


def start_optimize_thread(
    circuit: Circuit,
    sweep: SweepConfig,
    limits: list[LimitRegion],
    config: OptimizationConfig,
    on_finished: Callable[[object], None],
    on_failed: Callable[[str], None],
) -> tuple[QThread, OptimizeWorker]:
    thread = QThread()
    worker = OptimizeWorker(circuit, sweep, limits, config)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(on_finished)
    worker.failed.connect(on_failed)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread._filterdesk_worker = worker  # type: ignore[attr-defined]
    return thread, worker


class ImportTouchstoneWorker(QObject):
    """Load a Touchstone file off the UI thread."""

    finished = Signal(object)  # TouchstoneData
    failed = Signal(str)

    def __init__(self, path: Path | str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._path = Path(path)

    def run(self) -> None:
        try:
            data = read_touchstone(self._path)
            self.finished.emit(data)
        except Exception as exc:  # noqa: BLE001 — surface to UI
            self.failed.emit(str(exc))


def start_import_thread(
    path: Path | str,
    on_finished: Callable[[object], None],
    on_failed: Callable[[str], None],
) -> tuple[QThread, ImportTouchstoneWorker]:
    thread = QThread()
    worker = ImportTouchstoneWorker(path)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(on_finished)
    worker.failed.connect(on_failed)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread._filterdesk_worker = worker  # type: ignore[attr-defined]
    return thread, worker


__all__ = [
    "AnalyzeWorker",
    "AnalysisResult",
    "ImportTouchstoneWorker",
    "MonteCarloWorker",
    "OptimizeWorker",
    "TouchstoneData",
    "start_analyze_thread",
    "start_import_thread",
    "start_monte_carlo_thread",
    "start_optimize_thread",
]
