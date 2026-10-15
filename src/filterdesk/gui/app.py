"""GUI application entry."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from filterdesk.gui.main_window import MainWindow
from filterdesk.services.session import DesignSession


def run_gui(argv: list[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    # PyQtGraph SVG export + Qt6 (context-menu Export) — apply before plots load.
    from filterdesk.gui.pyqtgraph_patches import apply_pyqtgraph_svg_exporter_qt6_patch

    apply_pyqtgraph_svg_exporter_qt6_patch()

    app = QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QApplication(args)
    assert app is not None
    session = DesignSession()
    window = MainWindow(session)
    window.show()
    if owns_app:
        return int(app.exec())
    return 0
