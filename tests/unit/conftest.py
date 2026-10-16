"""Shared pytest configuration.

Keeps the offscreen Qt environment deterministic and tears down top-level widgets
after every test so async QThreads (analyze/optimize/Monte-Carlo workers) are
stopped before interpreter shutdown — otherwise PySide6 can abort/segfault at
exit with the mangled exit code 139/134.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

_EXIT_STATUS = {"code": 0}


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    del session
    _EXIT_STATUS["code"] = int(exitstatus)


def pytest_unconfigure(config: object) -> None:
    """Hard-exit after pytest's summary to avoid a nondeterministic PySide6 /
    pyqtgraph shutdown crash (SIGSEGV/abort at interpreter exit) that would fail an
    otherwise-green CI run with code 139/134."""
    del config
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os._exit(_EXIT_STATUS["code"])


@pytest.fixture(autouse=True)
def _qt_teardown() -> object:
    yield
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:  # pragma: no cover - PySide6 always present in this suite
        return
    app = QApplication.instance()
    if app is None:
        return
    for widget in list(app.topLevelWidgets()):
        debounce = getattr(widget, "_debounce", None)
        if debounce is not None:
            try:
                debounce.stop()
            except Exception:  # noqa: BLE001
                pass
        for attr in (
            "_analyze_thread",
            "_mc_thread",
            "_optimize_thread",
            "_import_thread",
        ):
            thread = getattr(widget, attr, None)
            if thread is not None and getattr(thread, "isRunning", lambda: False)():
                try:
                    thread.quit()
                    thread.wait(2000)
                except Exception:  # noqa: BLE001
                    pass
        try:
            widget.close()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
    app.processEvents()
