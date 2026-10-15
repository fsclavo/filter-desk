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


def test_schematic_context_menu_emits_on_right_click() -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.panels.schematic_view import SchematicPanel
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    panel = SchematicPanel()
    panel.resize(900, 300)
    panel.set_circuit(session.circuit)
    panel.show()
    app.processEvents()

    group = next(iter(panel._groups.values()))
    view_pt = panel._view.mapFromScene(group.sceneBoundingRect().center())
    received: list[str] = []
    panel.context_menu_requested.connect(lambda eid, pos: received.append(eid))
    QTest.mousePress(
        panel._view.viewport(), Qt.MouseButton.RightButton, pos=view_pt
    )
    app.processEvents()
    assert received == [group.element_id]
    panel.close()
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

    first_id = session.circuit.elements[0].id
    menu = window._build_schematic_menu(first_id)
    assert menu is not None
    labels = [a.text() for a in menu.actions()]
    assert "Edit value…" in labels
    assert "Delete element" in labels
    submenus = [a.menu() for a in menu.actions() if a.menu() is not None]
    sub_labels = [a.text() for sub in submenus for a in sub.actions()]
    assert "Series inductor" in sub_labels
    assert "Shunt capacitor" in sub_labels

    monkeypatch.setattr(
        QInputDialog, "getText", lambda *a, **k: ("10p", True)
    )
    window._insert_arm(first_id, ElementRole.SHUNT, "C", True)
    assert len(session.circuit.elements) == n + 1
    assert len(window._schematic._groups) == n + 1

    window._undo.undo()
    assert len(session.circuit.elements) == n
    assert len(window._schematic._groups) == n
    window.close()
    assert app is not None
