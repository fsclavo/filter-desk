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


def test_consecutive_shunt_arms_render_separately() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.enums import ElementRole
    from filterdesk.gui.panels.schematic_view import SchematicPanel
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    # Deleting a middle series arm leaves two shunt arms sharing one node.
    session.delete_arm("C3")
    assert session.circuit is not None
    shunt_ids = [
        el.id for el in session.circuit.elements if el.role == ElementRole.SHUNT
    ]
    assert len(shunt_ids) >= 2

    panel = SchematicPanel()
    panel.resize(1200, 300)
    panel.set_circuit(session.circuit)
    centers = [
        round(panel._groups[eid].sceneBoundingRect().center().x()) for eid in shunt_ids
    ]
    assert len(set(centers)) == len(centers)
    panel.close()
    assert app is not None


def test_component_menu_reflects_selection() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    window = MainWindow(session, auto_run=False)

    window._selected_element = None
    window._populate_component_menu()
    actions = window._component_menu.actions()
    assert [a.text() for a in actions] == ["(select a component first)"]
    assert not actions[0].isEnabled()

    first = session.circuit.elements[0]
    window._selected_element = first.id
    window._populate_component_menu()
    labels = [a.text() for a in window._component_menu.actions()]
    assert "Edit value…" in labels
    assert "Delete element" in labels
    assert "Convert to Inductor" in labels  # HP ladder starts with series C
    sub_labels = [
        a.text()
        for action in window._component_menu.actions()
        if action.menu() is not None
        for a in action.menu().actions()
    ]
    assert "Shunt capacitor" in sub_labels
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


def test_measured_overlay_toggles() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.panels.plot_panel import PlotPanel
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    result = session.analysis
    assert result is not None
    panel = PlotPanel()
    panel.set_result(result)
    panel.set_measured(result, "meas.s2p")
    assert panel.has_measured()
    n = result.frequency_hz.size

    def plotted(curve: object) -> int:
        data = curve.getData()[0]  # type: ignore[attr-defined]
        return 0 if data is None else int(data.size)

    assert plotted(panel._curve_s21_meas) == n
    panel.set_measured_visible(False)
    assert plotted(panel._curve_s21_meas) == 0
    panel.set_measured_visible(True)
    assert plotted(panel._curve_s21_meas) == n
    assert app is not None


def test_file_menu_has_import_touchstone() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    menus = {
        a.text(): a.menu() for a in window.menuBar().actions() if a.menu()
    }
    file_menu = menus.get("&File")
    assert file_menu is not None
    assert any("Import Touchstone" in a.text() for a in file_menu.actions())
    window.close()
    assert app is not None


def test_snap_command_apply_and_undo() -> None:
    from PySide6.QtGui import QUndoStack
    from PySide6.QtWidgets import QApplication

    from filterdesk.components_std import ESeries, SnapStrategy, nearest_e_series
    from filterdesk.domain.circuit import IdealCapacitor, IdealInductor
    from filterdesk.gui.commands import SnapCommand
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    before = [
        (el.id, el.value_h if isinstance(el, IdealInductor) else el.value_f)
        for el in session.circuit.elements
        if isinstance(el, (IdealInductor, IdealCapacitor))
    ]

    stack = QUndoStack()
    stack.push(SnapCommand(session, ESeries.E24, SnapStrategy.INDEPENDENT))
    assert session.circuit is not None
    for el in session.circuit.elements:
        if isinstance(el, IdealInductor):
            assert el.value_h == nearest_e_series(el.value_h, ESeries.E24)
        elif isinstance(el, IdealCapacitor):
            assert el.value_f == nearest_e_series(el.value_f, ESeries.E24)

    stack.undo()
    assert session.circuit is not None
    after = [
        (el.id, el.value_h if isinstance(el, IdealInductor) else el.value_f)
        for el in session.circuit.elements
        if isinstance(el, (IdealInductor, IdealCapacitor))
    ]
    assert after == before
    assert app is not None


def test_main_window_snap_action(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.components_std import ESeries, SnapStrategy, nearest_e_series
    from filterdesk.domain.circuit import IdealCapacitor, IdealInductor
    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)

    class _FakeSnapDialog:
        @staticmethod
        def ask(*args: object, **kwargs: object) -> tuple[ESeries, SnapStrategy]:
            return (ESeries.E24, SnapStrategy.INDEPENDENT)

    monkeypatch.setattr(mw, "SnapDialog", _FakeSnapDialog)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    window._run_snap()

    assert "Snapped to E24" in window._status.text()
    assert session.circuit is not None
    for el in session.circuit.elements:
        if isinstance(el, IdealInductor):
            assert el.value_h == nearest_e_series(el.value_h, ESeries.E24)
        elif isinstance(el, IdealCapacitor):
            assert el.value_f == nearest_e_series(el.value_f, ESeries.E24)
    window.close()
    assert app is not None


def test_nonideal_command_apply_and_undo() -> None:
    from PySide6.QtGui import QUndoStack
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.circuit import (
        IdealCapacitor,
        IdealInductor,
        NonIdealCapacitor,
        NonIdealInductor,
    )
    from filterdesk.gui.commands import NonIdealCommand
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    assert all(
        isinstance(el, (IdealInductor, IdealCapacitor))
        for el in session.circuit.elements
    )

    stack = QUndoStack()
    stack.push(
        NonIdealCommand(
            session,
            {"inductor_q": 100.0, "q_frequency_hz": 100e6, "capacitor_esr_ohm": 0.5},
        )
    )
    assert session.circuit is not None
    assert any(isinstance(el, NonIdealInductor) for el in session.circuit.elements)
    assert any(isinstance(el, NonIdealCapacitor) for el in session.circuit.elements)

    stack.undo()
    assert session.circuit is not None
    assert not any(
        isinstance(el, (NonIdealInductor, NonIdealCapacitor))
        for el in session.circuit.elements
    )
    assert app is not None


def test_main_window_nonideal_action(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.circuit import NonIdealCapacitor
    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)

    class _FakeDialog:
        @staticmethod
        def ask(*args: object, **kwargs: object) -> dict[str, float]:
            return {"capacitor_esr_ohm": 0.5}

    monkeypatch.setattr(mw, "NonIdealDialog", _FakeDialog)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    window._run_nonideal()

    assert "Applied parasitics" in window._status.text()
    assert session.circuit is not None
    assert any(isinstance(el, NonIdealCapacitor) for el in session.circuit.elements)
    window.close()
    assert app is not None


def test_component_table_shows_parasitics() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.circuit import Circuit, NonIdealInductor, Port
    from filterdesk.domain.enums import ElementRole
    from filterdesk.gui.panels.component_table import ComponentTablePanel

    app = QApplication.instance() or QApplication([])
    el = NonIdealInductor(
        id="L1",
        value_h=1e-6,
        node_a="in",
        node_b="out",
        role=ElementRole.SERIES,
        series_resistance_ohm=1.0,
        parallel_capacitance_f=1e-12,
    )
    circuit = Circuit(
        elements=[el],
        port_in=Port(name="in", node="in", impedance_ohm=50.0),
        port_out=Port(name="out", node="out", impedance_ohm=50.0),
    )
    panel = ComponentTablePanel()
    panel.set_circuit(circuit)
    text = panel._table.item(0, 4).text()
    assert "R=" in text and "Cp=" in text
    assert app is not None


def test_main_window_edit_parasitics(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.circuit import IdealInductor, NonIdealInductor
    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    l_id = next(
        el.id for el in session.circuit.elements if isinstance(el, IdealInductor)
    )
    window = mw.MainWindow(session, auto_run=False)

    class _FakeParasiticDialog:
        @staticmethod
        def ask(*args: object, **kwargs: object) -> dict[str, float]:
            return {"series_resistance_ohm": 1.0}

    monkeypatch.setattr(mw, "ParasiticDialog", _FakeParasiticDialog)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    window._edit_element_parasitics(l_id)

    assert "Updated parasitics" in window._status.text()
    assert session.circuit is not None
    target = next(el for el in session.circuit.elements if el.id == l_id)
    assert isinstance(target, NonIdealInductor)
    assert target.series_resistance_ohm == 1.0
    window.close()
    assert app is not None
