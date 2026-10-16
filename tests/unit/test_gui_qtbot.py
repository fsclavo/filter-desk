"""Real GUI interaction tests using pytest-qt (offscreen)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QToolBar  # noqa: E402

from filterdesk.gui.main_window import MainWindow  # noqa: E402
from filterdesk.services.session import DesignSession  # noqa: E402


def test_qtbot_ctrl_bracket_tunes_selected(qtbot) -> None:  # type: ignore[no-untyped-def]
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    window = MainWindow(session, auto_run=False)
    qtbot.addWidget(window)
    # Avoid kicking off the async re-analysis thread during the interaction.
    window._after_circuit_change = lambda: None  # type: ignore[method-assign]
    l_id = next(el.id for el in session.circuit.elements if el.id.startswith("L"))
    window._selected_element = l_id
    before = session.lookup_element_value(l_id)

    window.show()
    qtbot.waitExposed(window)

    toolbar = window.findChild(QToolBar, "MainToolBar")
    assert toolbar is not None
    button = toolbar.widgetForAction(window._act_tune_up)
    assert button is not None
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert session.lookup_element_value(l_id) > before
