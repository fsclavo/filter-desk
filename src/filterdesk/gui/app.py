"""GUI application entry."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from filterdesk.gui.main_window import MainWindow
from filterdesk.services.session import DesignSession


def _app_icon() -> QIcon:
    """Load the bundled application/window icon (empty if unavailable)."""
    candidates = [Path(__file__).resolve().parent.parent / "assets" / "logo.png"]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        candidates.append(Path(str(meipass)) / "filterdesk" / "assets" / "logo.png")
    for path in candidates:
        if path.is_file():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                return QIcon(pixmap)
    return QIcon()


def _hide_owned_console() -> None:
    """On Windows, hide the console created for a double-clicked launch.

    The frozen exe is a console build so the CLI still works from a terminal.
    When started by double-click Windows attaches a dedicated console; detect it
    via ``GetConsoleProcessList`` (count == 1) and hide it. A console shared with
    a shell (cmd.exe + process) is left untouched.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return
        buf = (ctypes.c_uint * 8)()
        count = kernel32.GetConsoleProcessList(buf, len(buf))
        if count <= 1:
            user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:  # noqa: BLE001 — best-effort cosmetic
        return


def run_gui(argv: list[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    _hide_owned_console()
    # PyQtGraph SVG export + Qt6 (context-menu Export) — apply before plots load.
    from filterdesk.gui.pyqtgraph_patches import apply_pyqtgraph_svg_exporter_qt6_patch

    apply_pyqtgraph_svg_exporter_qt6_patch()

    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication(args)
    assert app is not None
    QCoreApplication.setOrganizationName("FilterDesk")
    QCoreApplication.setApplicationName("FilterDesk")
    icon = _app_icon()
    if not icon.isNull() and isinstance(app, QApplication):
        app.setWindowIcon(icon)
    session = DesignSession()
    window = MainWindow(session)
    window.show()
    if owns_app:
        return int(app.exec())
    return 0
