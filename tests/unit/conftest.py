"""Shared pytest configuration.

The GUI tests build real PySide6 widgets offscreen. Repeatedly closing/iterating
every top-level widget after each test corrupts Qt's internal widget registry
(segfault inside ``QApplication.topLevelWidgets``) on some Python/PySide6
combinations, so cleanup is left to the tests themselves (``window.close()`` /
``qtbot``). ``pytest_unconfigure`` hard-exits after the summary to skip the
nondeterministic PySide6/pyqtgraph shutdown crash (exit 139/134/1).
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

_EXIT_STATUS = {"code": 0}


@pytest.fixture(scope="session", autouse=True)
def _qt_app() -> object:
    """Keep a single QApplication alive (and GC disabled) for the whole session.

    Tests use ``QApplication.instance() or QApplication([])``; if that per-test
    wrapper is garbage-collected it can destroy the Qt application mid-suite,
    corrupting Qt's widget registry (segfault/abort in later tests). A session
    reference keeps it alive. Cyclic GC is also disabled: collecting leaked
    pyqtgraph items while new widgets are being built aborts inside C++. The
    hard-exit skips both the final GC and Qt teardown.
    """
    import gc

    from PySide6.QtWidgets import QApplication

    gc.disable()
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _isolate_settings() -> object:
    """Give every test a fresh in-memory settings store (never real QSettings)."""
    from filterdesk.gui.settings import InMemorySettingsStore, set_settings_store

    store = InMemorySettingsStore()
    set_settings_store(store)
    yield store
    set_settings_store(None)


@pytest.fixture(autouse=True)
def _dismiss_close_prompt(monkeypatch: pytest.MonkeyPatch) -> object:
    """Discard unsaved changes automatically when tests close a dirty window."""
    from PySide6.QtWidgets import QMessageBox

    original = QMessageBox.question

    def _question(parent, title, text, *args, **kwargs):  # type: ignore[no-untyped-def]
        if title == "Unsaved changes":
            return QMessageBox.StandardButton.Discard
        return original(parent, title, text, *args, **kwargs)

    monkeypatch.setattr(QMessageBox, "question", _question)
    yield None


@pytest.fixture(autouse=True)
def _reset_language() -> object:
    """Always run tests in English so translation state cannot leak between them."""
    from filterdesk.gui.i18n import Language, set_language

    set_language(Language.EN)
    yield None
    set_language(Language.EN)



def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    del session
    _EXIT_STATUS["code"] = int(exitstatus)


def _hard_exit(code: int) -> None:
    """Terminate the process without running Python/C++ destructors.

    On Windows ``os._exit`` itself raises an access violation after the Qt
    shutdown sequence, so terminate via the kernel instead.
    """
    if sys.platform == "win32":  # pragma: no cover - exercised only on Windows CI
        import ctypes

        k32 = getattr(ctypes, "WinDLL")("kernel32")  # noqa: B009
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        k32.TerminateProcess.restype = ctypes.c_int
        handle = k32.GetCurrentProcess()
        k32.TerminateProcess(handle, code)
    os._exit(code)


def pytest_unconfigure(config: object) -> None:
    """Hard-exit after pytest's summary to avoid the Qt shutdown crash.

    Uses the original ``sys.__stdout__``/``__stderr__`` (not pytest's capture
    wrappers, which may already be torn down). Coverage data and the terminal
    summary are written before this hook runs.
    """
    del config
    for stream in (sys.__stdout__, sys.__stderr__):
        try:
            if stream is not None:
                stream.flush()
        except Exception:  # noqa: BLE001 - best-effort flush
            pass
    _hard_exit(_EXIT_STATUS["code"])
