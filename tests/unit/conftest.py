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

_EXIT_STATUS = {"code": 0}


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    del session
    _EXIT_STATUS["code"] = int(exitstatus)


def pytest_unconfigure(config: object) -> None:
    """Hard-exit after pytest's summary to avoid the Qt shutdown crash.

    Uses the original ``sys.__stdout__``/``__stderr__`` (not pytest's capture
    wrappers, which may already be torn down) and works on every platform;
    coverage data and the terminal summary are written before this hook runs.
    """
    del config
    for stream in (sys.__stdout__, sys.__stderr__):
        try:
            if stream is not None:
                stream.flush()
        except Exception:  # noqa: BLE001 - best-effort flush
            pass
    os._exit(_EXIT_STATUS["code"])
