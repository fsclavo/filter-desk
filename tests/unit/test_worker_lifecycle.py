"""Real QThread lifecycle tests for the GUI workers.

Success and failure paths, plus the close-time termination fallback. These guard
the crash class we have hit before (a QThread destroyed while still running).
Events are pumped manually instead of using pytest-qt timers, which avoids a
capture/timer race with worker threads.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEventLoop  # noqa: E402

from filterdesk.analysis.types import SweepConfig, SweepSpacing  # noqa: E402
from filterdesk.domain.overlays import LimitRegion  # noqa: E402
from filterdesk.gui.workers import (  # noqa: E402
    start_analyze_thread,
    start_import_thread,
    start_monte_carlo_thread,
    start_optimize_thread,
)
from filterdesk.montecarlo import MonteCarloConfig  # noqa: E402
from filterdesk.optimization import OptimizationConfig  # noqa: E402
from filterdesk.services.session import DesignSession  # noqa: E402

SMALL_SWEEP = SweepConfig(10e6, 1e9, 24, SweepSpacing.LOGARITHMIC)


def _session() -> DesignSession:
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    return session


def _spin_until(predicate, timeout_s: float = 20.0) -> None:
    app = QCoreApplication.instance()
    deadline = time.monotonic() + timeout_s
    while not predicate() and time.monotonic() < deadline:
        if app is not None:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        time.sleep(0.005)


def _run(thread, done: list[object], errors: list[str]) -> None:
    thread.start()
    _spin_until(lambda: bool(done) or bool(errors))
    thread.quit()
    assert thread.wait(5000)
    assert not thread.isRunning()


def test_analyze_worker_finishes() -> None:
    session = _session()
    results: list[object] = []
    errors: list[str] = []
    thread, _worker = start_analyze_thread(
        session.circuit, SMALL_SWEEP, "abcd", results.append, errors.append
    )
    _run(thread, results, errors)
    assert results and not errors


def test_analyze_worker_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from filterdesk.gui import workers

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("analyze boom")

    monkeypatch.setattr(workers, "analyze_circuit", _boom)
    session = _session()
    results: list[object] = []
    errors: list[str] = []
    thread, _worker = start_analyze_thread(
        session.circuit, SMALL_SWEEP, "abcd", results.append, errors.append
    )
    _run(thread, results, errors)
    assert errors == ["analyze boom"]


def test_monte_carlo_worker_finishes() -> None:
    session = _session()
    config = MonteCarloConfig(n_trials=5, tolerance_pct=2.0, seed=1)
    results: list[object] = []
    errors: list[str] = []
    thread, _worker = start_monte_carlo_thread(
        session.circuit, SMALL_SWEEP, config, [], results.append, errors.append
    )
    _run(thread, results, errors)
    assert results and not errors


def test_optimize_worker_finishes() -> None:
    session = _session()
    limits = [LimitRegion("pb", "s21_db", 140e6, 1e9, y_min=-3.0)]
    config = OptimizationConfig(max_iter=3)
    results: list[object] = []
    errors: list[str] = []
    thread, _worker = start_optimize_thread(
        session.circuit,
        SMALL_SWEEP,
        limits,
        config,
        results.append,
        errors.append,
    )
    _run(thread, results, errors)
    assert results and not errors


def test_import_worker_success_and_failure(tmp_path: Path) -> None:
    path = tmp_path / "thru.s2p"
    path.write_text(
        "! test\n# Hz S RI R 50\n"
        "1000000 1 0 0 0 0 0 1 0\n"
        "2000000 1 0 0 0 0 0 1 0\n",
        encoding="utf-8",
    )
    results: list[object] = []
    errors: list[str] = []
    thread, _worker = start_import_thread(path, results.append, errors.append)
    _run(thread, results, errors)
    assert results and not errors

    missing = tmp_path / "missing.s2p"
    results2: list[object] = []
    errors2: list[str] = []
    thread2, _worker2 = start_import_thread(
        missing, results2.append, errors2.append
    )
    _run(thread2, results2, errors2)
    assert errors2 and not results2


def test_close_event_terminates_stuck_thread() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow

    class FakeThread:
        def __init__(self) -> None:
            self.running = True
            self.interrupted = False
            self.quit_called = False
            self.terminated = False
            self.wait_calls = 0

        def isRunning(self) -> bool:
            return self.running

        def requestInterruption(self) -> None:
            self.interrupted = True

        def quit(self) -> None:
            self.quit_called = True

        def wait(self, _ms: int) -> bool:
            self.wait_calls += 1
            return False

        def terminate(self) -> None:
            self.terminated = True
            self.running = False

    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    fake = FakeThread()
    window._mc_thread = fake  # type: ignore[assignment]
    window.close()
    assert fake.interrupted and fake.quit_called and fake.terminated
    assert fake.wait_calls >= 2
    assert app is not None
