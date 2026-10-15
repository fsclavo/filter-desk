"""Offscreen GUI smoke test."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")


def test_main_window_constructs() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    window = MainWindow(session, auto_run=False)
    assert "FilterDesk" in window.windowTitle()
    window.close()
    assert app is not None


def test_schematic_edit_insert_and_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication, QInputDialog

    from filterdesk.domain.enums import ElementRole
    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.circuit is not None
    window = MainWindow(session, auto_run=False)
    n = len(session.circuit.elements)

    monkeypatch.setattr(
        QInputDialog, "getText", lambda *a, **k: ("10p", True)
    )
    first_id = session.circuit.elements[0].id
    window._insert_arm(first_id, ElementRole.SHUNT, "C", True)
    assert len(session.circuit.elements) == n + 1
    assert len(window._schematic._groups) == n + 1

    window._undo.undo()
    assert len(session.circuit.elements) == n
    assert len(window._schematic._groups) == n
    window.close()
    assert app is not None
