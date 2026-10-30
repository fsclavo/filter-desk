"""Offscreen GUI smoke test."""

from __future__ import annotations

import os
from pathlib import Path

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
    assert window._spec._order.toolTip()
    assert window._spec._zl.toolTip()
    window.close()
    assert app is not None


def test_window_title_uses_neutral_default() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    window = MainWindow(session, auto_run=False)
    assert "Milestone" not in window.windowTitle()
    assert "Untitled" in window.windowTitle()
    assert "unsaved" not in window.windowTitle()
    window.close()
    assert app is not None


def test_write_project_names_from_filename(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    window = MainWindow(session, auto_run=False)
    path = tmp_path / "myfilter.filterdesk.json"
    window._write_project(path)
    assert session.title == "myfilter"
    assert "myfilter" in window.windowTitle()
    assert path.exists()
    window.close()
    assert app is not None


def test_confirm_close_save_discard_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    session.dirty = True
    window = mw.MainWindow(session, auto_run=False)
    answers = [
        mw.QMessageBox.StandardButton.Cancel,
        mw.QMessageBox.StandardButton.Discard,
        mw.QMessageBox.StandardButton.Save,
    ]
    monkeypatch.setattr(
        mw.QMessageBox, "question", lambda *args, **kwargs: answers.pop(0)
    )
    assert not window._confirm_close()
    assert window._confirm_close()

    saved: list[bool] = []
    monkeypatch.setattr(
        window, "_save_project", lambda: saved.append(True) or True
    )
    assert window._confirm_close()
    assert saved == [True]

    session.dirty = False
    assert window._confirm_close()
    window.close()
    assert app is not None


def test_open_project_is_not_dirty(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.io.native import load_project, save_project
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    source = DesignSession()
    source.synthesize_and_analyze()
    path = tmp_path / "saved.filterdesk.json"
    save_project(source.to_project(), path)

    window = MainWindow(DesignSession(), auto_run=False)
    window._session.load_project(load_project(path), path=str(path))
    window._load_session_into_ui()
    assert window._session.dirty is False
    assert "*" not in window.windowTitle()
    window.close()
    assert app is not None


def test_rename_project_updates_title(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(
        mw.QInputDialog, "getText", lambda *a, **k: ("My Filter", True)
    )
    window._rename_project()
    assert session.title == "My Filter"
    assert "My Filter" in window.windowTitle()
    window.close()
    assert app is not None


def test_export_title_falls_back_to_spec() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.title == "Untitled"
    window = MainWindow(session, auto_run=False)
    assert window._export_title().startswith("cheby1")
    session.title = "Custom"
    assert window._export_title() == "Custom"
    window.close()
    assert app is not None


def test_new_project_resets_title_and_path() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    session.title = "Old"
    session.path = "/tmp/old.filterdesk.json"
    session.dirty = False  # skip the discard confirmation
    window = MainWindow(session, auto_run=False)
    window._new_project()
    assert window._session is not session
    assert window._session.title == "Untitled"
    assert window._session.path is None
    assert "Untitled" in window.windowTitle()
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


def test_plot_auto_range_runs_without_showing_widgets() -> None:
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
    panel.auto_range()
    panel.close()
    assert app is not None


def test_extra_response_plots_populate() -> None:
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
    n = result.frequency_hz.size

    def plotted(curve: object) -> int:
        data = curve.getData()[0]  # type: ignore[attr-defined]
        return 0 if data is None else int(data.size)

    labels = [panel._tabs.tabText(i) for i in range(panel._tabs.count())]
    assert "Phase" in labels and "Impedance" in labels and "S12 / S22" in labels
    assert panel._tabs.tabToolTip(0)
    assert panel._tabs.tabToolTip(4)
    for curve in (
        panel._curve_phase21,
        panel._curve_phase11,
        panel._curve_s22,
        panel._curve_s12,
        panel._curve_zin_abs,
        panel._curve_zin_re,
        panel._curve_zin_im,
        panel._curve_zout_abs,
    ):
        assert plotted(curve) == n

    def legend_names(plot: object) -> list[str]:
        legend = plot.plotItem.legend  # type: ignore[attr-defined]
        return [label.text for _, label in legend.items]

    assert legend_names(panel._mag) == ["S21", "S11"]
    assert legend_names(panel._rev_plot) == ["S22", "S12"]

    panel.set_measured(result, "meas.s2p")
    assert plotted(panel._curve_phase21_meas) == n
    assert plotted(panel._curve_zin_abs_meas) == n
    assert plotted(panel._curve_s22_meas) == n
    assert legend_names(panel._mag) == ["S21", "S11", "S21 meas", "S11 meas"]
    assert legend_names(panel._rev_plot) == ["S22", "S12", "S22 meas", "S12 meas"]
    panel.set_measured_visible(False)
    assert plotted(panel._curve_phase21_meas) == 0
    assert plotted(panel._curve_zin_abs_meas) == 0
    assert plotted(panel._curve_s22_meas) == 0
    assert legend_names(panel._mag) == ["S21", "S11"]
    assert legend_names(panel._rev_plot) == ["S22", "S12"]
    panel.set_result(None)
    assert plotted(panel._curve_phase21) == 0
    assert plotted(panel._curve_zin_abs) == 0
    assert plotted(panel._curve_s22) == 0
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
    submenus = {a.text(): a.menu() for a in file_menu.actions() if a.menu()}
    import_menu = submenus.get("&Import")
    assert import_menu is not None
    assert any("Touchstone" in a.text() for a in import_menu.actions())

    export_menu = submenus.get("&Export")
    assert export_menu is not None
    export_labels = [a.text().replace("&", "") for a in export_menu.actions()]
    assert any("Smith" in t for t in export_labels)
    assert any("CSV" in t for t in export_labels)
    assert any("Touchstone" in t for t in export_labels)
    assert any("SPICE" in t for t in export_labels)
    assert any("LTspice" in t for t in export_labels)
    assert any("Qucs" in t for t in export_labels)
    window.close()
    assert app is not None


def test_tools_menu_holds_calculators() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    menus = {
        a.text(): a.menu() for a in window.menuBar().actions() if a.menu()
    }
    design_menu = menus.get("&Design")
    tools_menu = menus.get("&Tools")
    assert design_menu is not None and tools_menu is not None
    design_labels = [a.text().replace("&", "") for a in design_menu.actions()]
    tools_labels = [a.text().replace("&", "") for a in tools_menu.actions()]

    for calculator in (
        "Matching network",
        "Attenuator pad",
        "Coil calculator",
        "Transformer / balun",
        "Microstrip line",
        "Coaxial stub notch",
        "4-port mixed-mode",
        "Diplexer / multiplexer designer",
    ):
        assert not any(calculator in label for label in design_labels)
        assert any(calculator in label for label in tools_labels)

    for filter_action in (
        "Synthesize + Analyze",
        "Band filter wizard",
        "Snap to E-series",
        "Optimize to limits",
        "Check spec compliance",
        "Tune to VNA measurement",
    ):
        assert any(filter_action in label for label in design_labels)
    syn = next(
        action for action in design_menu.actions() if "Synthesize" in action.text()
    )
    assert syn.toolTip()
    assert syn.statusTip()

    window.close()
    assert app is not None


def test_help_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    window = mw.MainWindow(DesignSession(), auto_run=False)
    menus = {a.text(): a.menu() for a in window.menuBar().actions() if a.menu()}
    help_menu = menus.get("&Help")
    assert help_menu is not None
    labels = [a.text() for a in help_menu.actions()]
    assert any("About FilterDesk" in t for t in labels)
    assert any("GitHub" in t for t in labels)

    calls: dict[str, object] = {}
    opened: list[str] = []

    class _FakeMessageBox:
        @staticmethod
        def about(*args: object, **kwargs: object) -> None:
            calls["about"] = True

        @staticmethod
        def aboutQt(*args: object, **kwargs: object) -> None:
            calls["aboutQt"] = True

    class _FakeDesktop:
        @staticmethod
        def openUrl(url: object) -> None:
            opened.append(url.toString())  # type: ignore[attr-defined]

    monkeypatch.setattr(mw, "QMessageBox", _FakeMessageBox)
    monkeypatch.setattr(mw, "QDesktopServices", _FakeDesktop)
    window._show_about()
    window._show_about_qt()
    window._open_github()
    window._open_docs()
    assert calls.get("about") and calls.get("aboutQt")
    assert any("github.com/fsclavo/filter-desk" in u for u in opened)
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


def test_monte_carlo_overlay_toggles() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.panels.plot_panel import PlotPanel
    from filterdesk.montecarlo import MonteCarloConfig, run_monte_carlo
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None and session.sweep is not None
    result = run_monte_carlo(
        session.circuit,
        session.sweep,
        MonteCarloConfig(n_trials=8, tolerance_pct=3.0, seed=1),
    )
    panel = PlotPanel()
    panel.set_monte_carlo(result)
    assert panel.has_monte_carlo()
    n = result.frequency_hz.size
    assert panel._curve_mc_min.getData()[0].size == n
    panel.set_monte_carlo_visible(False)
    assert panel._curve_mc_min.getData()[0] is None
    panel.set_monte_carlo_visible(True)
    assert panel._curve_mc_max.getData()[0].size == n
    panel.set_monte_carlo(None)
    assert app is not None


def test_monte_carlo_readout_bits() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.panels.plot_panel import PlotPanel
    from filterdesk.montecarlo import MonteCarloConfig, run_monte_carlo
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None and session.sweep is not None
    result = run_monte_carlo(
        session.circuit,
        session.sweep,
        MonteCarloConfig(n_trials=8, tolerance_pct=3.0, seed=1),
    )
    panel = PlotPanel()
    panel.set_monte_carlo(result)
    f0 = float(result.frequency_hz[0])
    bits = panel._mc_readout_bits(f0)
    assert "MC S21" in bits and "spread" in bits
    panel.set_monte_carlo_visible(False)
    assert panel._mc_readout_bits(f0) == ""
    panel.set_monte_carlo(None)
    assert app is not None


def test_monte_carlo_dialog_builds_config() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import MonteCarloDialog
    from filterdesk.montecarlo import ToleranceDistribution

    app = QApplication.instance() or QApplication([])
    dialog = MonteCarloDialog()
    dialog._trials.setValue(250)
    dialog._tol.setText("2.5")
    dialog._seed.setText("7")
    dialog._dist.setCurrentIndex(list(ToleranceDistribution).index(
        ToleranceDistribution.NORMAL
    ))
    config = dialog.to_config()
    assert config.n_trials == 250
    assert config.tolerance_pct == 2.5
    assert config.seed == 7
    assert config.distribution == ToleranceDistribution.NORMAL
    assert app is not None


def test_main_window_monte_carlo_action(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.montecarlo import (
        MonteCarloConfig,
        ToleranceDistribution,
        run_monte_carlo,
    )
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)

    class _FakeThread:
        def start(self) -> None:
            pass

        def isRunning(self) -> bool:  # noqa: N802
            return False

        def quit(self) -> None:
            pass

        def wait(self, *_args: object) -> bool:
            return True

    class _FakeSignal:
        def connect(self, *_args: object) -> None:
            pass

    class _FakeWorker:
        progress = _FakeSignal()

    def _fake_start(
        circuit: object,
        sweep: object,
        config: MonteCarloConfig,
        limits: object,
        on_finished: object,
        on_failed: object,
    ) -> tuple[object, object]:
        on_finished(  # type: ignore[operator]
            run_monte_carlo(circuit, sweep, config, limits=limits)  # type: ignore[arg-type]
        )
        return _FakeThread(), _FakeWorker()

    class _FakeDialog:
        @staticmethod
        def ask(*args: object, **kwargs: object) -> MonteCarloConfig:
            return MonteCarloConfig(
                n_trials=10,
                tolerance_pct=2.0,
                distribution=ToleranceDistribution.UNIFORM,
                seed=1,
            )

    monkeypatch.setattr(mw, "MonteCarloDialog", _FakeDialog)
    monkeypatch.setattr(mw, "start_monte_carlo_thread", _fake_start)
    window._run_monte_carlo()

    assert "Monte-Carlo" in window._status.text()
    assert window._plots.has_monte_carlo()
    window.close()
    assert app is not None


def test_main_window_scale_response_action(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    before = session.spec.cutoff_hz
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(mw.QInputDialog, "getText", lambda *a, **k: ("2.0", True))
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    window._run_scale_response()

    assert session.spec.cutoff_hz == pytest.approx(before * 2.0)
    assert "Scaled response" in window._status.text()
    window.close()
    assert app is not None


def test_optimize_dialog_builds_config() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import OptimizeDialog
    from filterdesk.optimization import OptimizeMethod

    app = QApplication.instance() or QApplication([])
    dialog = OptimizeDialog()
    dialog._method.setCurrentIndex(
        list(OptimizeMethod).index(OptimizeMethod.NELDER_MEAD)
    )
    dialog._bound.setText("0.35")
    dialog._max_iter.setValue(123)
    config = dialog.to_config()
    assert config.method == OptimizeMethod.NELDER_MEAD
    assert config.bound_pct == pytest.approx(0.35)
    assert config.max_iter == 123
    assert app is not None


def test_main_window_optimize_action(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.overlays import LimitMetric, LimitRegion
    from filterdesk.gui import main_window as mw
    from filterdesk.optimization import (
        OptimizationConfig,
        OptimizeMethod,
        optimize_circuit,
    )
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    session.limits = [
        LimitRegion(
            id="pb",
            metric=LimitMetric.S21_DB,
            f_low_hz=200e6,
            f_high_hz=500e6,
            y_min=-3.0,
        )
    ]
    window = mw.MainWindow(session, auto_run=False)

    class _FakeThread:
        def start(self) -> None:
            pass

        def isRunning(self) -> bool:  # noqa: N802
            return False

        def quit(self) -> None:
            pass

        def wait(self, *_args: object) -> bool:
            return True

    def _fake_start(
        circuit: object,
        sweep: object,
        limits: object,
        config: OptimizationConfig,
        on_finished: object,
        on_failed: object,
    ) -> tuple[object, object]:
        on_finished(  # type: ignore[operator]
            optimize_circuit(circuit, sweep, limits, config)  # type: ignore[arg-type]
        )
        return _FakeThread(), None

    class _FakeDialog:
        @staticmethod
        def ask(*args: object, **kwargs: object) -> OptimizationConfig:
            return OptimizationConfig(
                method=OptimizeMethod.NELDER_MEAD, bound_pct=0.5, max_iter=50
            )

    monkeypatch.setattr(mw, "OptimizeDialog", _FakeDialog)
    monkeypatch.setattr(mw, "start_optimize_thread", _fake_start)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    window._run_optimize()

    assert "Optimized" in window._status.text()
    window.close()
    assert app is not None


def test_limits_panel_add_preset() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.overlays import LimitMetric
    from filterdesk.gui.panels import limits_panel as lp

    app = QApplication.instance() or QApplication([])
    panel = lp.LimitsPanel()
    recorded: list[object] = []
    panel.limits_changed.connect(recorded.append)

    panel._add_preset(lp._PRESETS[0])  # passband |S21| min
    panel._add_preset(lp._PRESETS[1])  # stopband |S21| max
    limits = panel.limits()
    assert len(limits) == 2
    assert limits[0].metric == LimitMetric.S21_DB
    assert limits[0].y_min == pytest.approx(-0.5)
    assert limits[1].y_max == pytest.approx(-40.0)
    assert limits[0].id != limits[1].id
    assert panel._table.currentRow() == 1
    assert recorded
    assert app is not None


def test_main_window_tune_nudge(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    l_id = next(el.id for el in session.circuit.elements if el.id.startswith("L"))
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(window, "_after_circuit_change", lambda: None)
    window._selected_element = l_id
    base = session.lookup_element_value(l_id)

    window._tune_selected_increase()

    assert session.lookup_element_value(l_id) == pytest.approx(
        base * (1.0 + session.DEFAULT_TUNE_STEP)
    )
    assert "Tuned" in window._status.text()
    window._tune_selected_decrease()
    step = session.DEFAULT_TUNE_STEP
    assert session.lookup_element_value(l_id) == pytest.approx(
        base * (1.0 + step) * (1.0 - step)
    )
    window.close()
    assert app is not None


def test_main_window_export_csv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    window = mw.MainWindow(session, auto_run=False)
    out = tmp_path / "export.csv"
    monkeypatch.setattr(
        mw.QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), "")
    )
    window._export_csv()
    assert out.is_file()
    assert "Wrote" in window._status.text()
    window.close()
    assert app is not None


def test_main_window_insert_resistor_arm(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.circuit import IdealResistor
    from filterdesk.domain.enums import ElementRole
    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    first_id = session.circuit.elements[0].id
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(mw.QInputDialog, "getText", lambda *a, **k: ("10", True))
    monkeypatch.setattr(window, "_after_circuit_change", lambda: None)
    window._insert_arm(first_id, ElementRole.SERIES, "R", True)

    assert session.circuit is not None
    assert any(isinstance(el, IdealResistor) for el in session.circuit.elements)
    window.close()
    assert app is not None


def test_band_filter_dialog_selection() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import BandFilterWizardDialog
    from filterdesk.services.bands import BandKind

    app = QApplication.instance() or QApplication([])
    dialog = BandFilterWizardDialog()
    band, kind = dialog.selection()
    assert band.name == "40 m"
    assert kind == BandKind.LPF
    dialog._kind.setCurrentIndex(2)  # LPF,HPF,BPF -> band-pass
    _, kind = dialog.selection()
    assert kind == BandKind.BPF
    # Rejection preset: pick the AM broadcast band + band-stop.
    am_index = dialog._band.findText("AM broadcast")
    assert am_index >= 0
    dialog._band.setCurrentIndex(am_index)
    assert dialog._kind.count() == 1
    band, kind = dialog.selection()
    assert band.name == "AM broadcast"
    assert kind == BandKind.BSF
    assert app is not None


def test_matching_dialog_live_summary() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import MatchingDialog

    app = QApplication.instance() or QApplication([])
    dialog = MatchingDialog()
    dialog._recompute()
    assert "Zin=50" in dialog._summary.text()
    assert app is not None


def test_diplexer_dialog_designs_and_exports(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import DiplexerDialog
    from filterdesk.io.touchstone import read_sparameters

    app = QApplication.instance() or QApplication([])
    dialog = DiplexerDialog()
    dialog._points.setValue(201)
    assert dialog.design()
    design = dialog.current_design()
    assert design is not None
    assert design.network.n_ports == 3
    assert dialog._metrics.rowCount() == 9
    assert dialog._samples.rowCount() == 21
    assert dialog._export_network_button.isEnabled()
    assert dialog._curve_low.getData()[0].size > 0
    assert dialog._curve_high.getData()[0].size > 0
    assert dialog._curve_input.getData()[0].size > 0
    assert dialog._curve_isolation.getData()[0].size > 0
    mid_data = dialog._curve_mid.getData()[0]
    assert mid_data is None or mid_data.size == 0

    network_path = tmp_path / "diplexer.s3p"
    assert dialog.export_network(network_path)
    assert read_sparameters(network_path).n_ports == 3
    low_path = tmp_path / "low.s2p"
    assert dialog.export_branch("low", low_path)
    assert read_sparameters(low_path).n_ports == 2
    dialog.close()
    assert app is not None


def test_diplexer_dialog_designs_bpf_pair(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import DiplexerDialog
    from filterdesk.io.touchstone import read_sparameters

    app = QApplication.instance() or QApplication([])
    dialog = DiplexerDialog()
    dialog._mode.setCurrentIndex(1)
    dialog._low_center.setText("14M")
    dialog._low_bw.setText("300k")
    dialog._high_center.setText("21M")
    dialog._high_bw.setText("500k")
    dialog._f_start.setText("5M")
    dialog._f_stop.setText("40M")
    dialog._points.setValue(401)
    assert dialog.design()
    design = dialog.current_design()
    assert design is not None
    assert design.network.n_ports == 3
    assert design.low_spec.response.value == "band_pass"
    assert design.high_spec.response.value == "band_pass"
    assert "Cruce" not in dialog._metrics.item(8, 1).text()
    network_path = tmp_path / "band_diplexer.s3p"
    assert dialog.export_network(network_path)
    assert read_sparameters(network_path).n_ports == 3
    dialog.close()
    assert app is not None


def test_duplexer_dialog_designs_and_exports(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import DiplexerDialog
    from filterdesk.io.touchstone import read_sparameters
    from filterdesk.services.duplexer import DuplexerDesign

    app = QApplication.instance() or QApplication([])
    dialog = DiplexerDialog()
    dialog._mode.setCurrentIndex(2)
    dialog._tx_center.setText("145M")
    dialog._tx_bw.setText("1M")
    dialog._rx_center.setText("147M")
    dialog._rx_bw.setText("1M")
    dialog._min_isolation.setText("60")
    dialog._max_order.setValue(6)
    dialog._f_start.setText("140M")
    dialog._f_stop.setText("152M")
    dialog._points.setValue(401)
    assert dialog.design()
    design = dialog.current_design()
    assert isinstance(design, DuplexerDesign)
    assert design.network.n_ports == 3
    assert design.selected_order == 6
    assert design.metrics.meets_target
    assert dialog._metrics.rowCount() == 10
    assert dialog._samples.rowCount() == 21
    assert dialog._samples.horizontalHeaderItem(1).text() == "TX out S21 (dB)"
    assert dialog._curve_low.getData()[0].size > 0
    assert dialog._curve_high.getData()[0].size > 0
    assert dialog._curve_isolation.getData()[0].size > 0
    network_path = tmp_path / "duplexer.s3p"
    assert dialog.export_network(network_path)
    assert read_sparameters(network_path).n_ports == 3
    tx_path = tmp_path / "tx.s2p"
    rx_path = tmp_path / "rx.s2p"
    assert dialog.export_branch("tx", tx_path)
    assert dialog.export_branch("rx", rx_path)
    assert read_sparameters(tx_path).n_ports == 2
    assert read_sparameters(rx_path).n_ports == 2
    dialog.close()
    assert app is not None


def test_triplexer_dialog_designs_and_exports(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import DiplexerDialog
    from filterdesk.io.touchstone import read_sparameters
    from filterdesk.services.multiplexer import MultiplexerDesign

    app = QApplication.instance() or QApplication([])
    dialog = DiplexerDialog()
    dialog._mode.setCurrentIndex(3)
    dialog._tri_low_center.setText("14M")
    dialog._tri_low_bw.setText("300k")
    dialog._tri_mid_center.setText("21M")
    dialog._tri_mid_bw.setText("500k")
    dialog._tri_high_center.setText("28M")
    dialog._tri_high_bw.setText("500k")
    dialog._f_start.setText("5M")
    dialog._f_stop.setText("40M")
    dialog._points.setValue(401)
    assert dialog.design()
    design = dialog.current_design()
    assert isinstance(design, MultiplexerDesign)
    assert design.network.n_ports == 4
    assert dialog._metrics.rowCount() == 14
    assert dialog._samples.columnCount() == 5
    assert dialog._samples.rowCount() == 21
    assert dialog._export_mid_button.isEnabled()
    assert dialog._curve_low.getData()[0].size > 0
    assert dialog._curve_mid.getData()[0].size > 0
    assert dialog._curve_high.getData()[0].size > 0
    assert dialog._curve_isolation.getData()[0].size > 0
    network_path = tmp_path / "triplexer.s4p"
    assert dialog.export_network(network_path)
    assert read_sparameters(network_path).n_ports == 4
    for label in ("low", "mid", "high"):
        branch_path = tmp_path / f"{label}.s2p"
        assert dialog.export_branch(label, branch_path)
        assert read_sparameters(branch_path).n_ports == 2
    dialog.close()
    assert app is not None


def test_diplexer_dialog_mode_rows_and_plot_tabs() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import DiplexerDialog

    app = QApplication.instance() or QApplication([])
    dialog = DiplexerDialog()
    assert dialog._form.isRowVisible(dialog._low_cutoff)
    assert not dialog._form.isRowVisible(dialog._low_center)
    assert dialog._export_mid_button.isHidden()
    assert dialog._results_tabs.count() == 2
    assert dialog._results_tabs.tabText(0) == "Metrics"
    assert dialog._results_tabs.tabText(1) == "Magnitude"

    dialog._mode.setCurrentIndex(1)
    assert dialog._form.isRowVisible(dialog._low_center)
    assert not dialog._form.isRowVisible(dialog._low_cutoff)
    assert dialog._export_mid_button.isHidden()

    dialog._mode.setCurrentIndex(2)
    assert dialog._form.isRowVisible(dialog._tx_center)
    assert dialog._form.isRowVisible(dialog._auto_order)
    assert dialog._export_mid_button.isHidden()

    dialog._mode.setCurrentIndex(3)
    assert dialog._form.isRowVisible(dialog._tri_mid_center)
    assert not dialog._form.isRowVisible(dialog._tx_center)
    assert not dialog._export_mid_button.isHidden()
    dialog.close()
    assert app is not None


def test_diplexer_dialog_reports_invalid_input() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import DiplexerDialog

    app = QApplication.instance() or QApplication([])
    dialog = DiplexerDialog()
    dialog._low_cutoff.setText("50M")
    dialog._high_cutoff.setText("40M")
    assert not dialog.design()
    assert "above" in dialog._status.text()
    assert not dialog._export_network_button.isEnabled()
    dialog.close()
    assert app is not None


def test_main_window_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.components_std import MatchingTopology, design_matching
    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    n = len(session.circuit.elements)
    window = mw.MainWindow(session, auto_run=False)
    design = design_matching(50.0, 25.0, -10.0, 140e6, MatchingTopology.L)

    class _FakeDialog:
        @staticmethod
        def ask(*args: object, **kwargs: object) -> object:
            return design, False, True

    monkeypatch.setattr(mw, "MatchingDialog", _FakeDialog)
    monkeypatch.setattr(window, "_after_circuit_change", lambda: None)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    window._run_matching()

    assert session.circuit is not None
    assert len(session.circuit.elements) == n + len(design.elements)
    assert "match" in window._status.text()
    window._undo.undo()
    assert len(session.circuit.elements) == n
    window.close()
    assert app is not None


def test_attenuator_dialog_live_values() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import AttenuatorDialog

    app = QApplication.instance() or QApplication([])
    dialog = AttenuatorDialog()
    dialog._recompute()
    assert "16" in dialog._series.text()  # 6 dB T-pad series ≈ 16.6 Ω
    assert "66" in dialog._shunt.text()  # ≈ 66.9 Ω
    assert app is not None


def test_main_window_attenuator(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.components_std import AttenuatorKind, design_attenuator
    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    n = len(session.circuit.elements)
    window = mw.MainWindow(session, auto_run=False)
    design = design_attenuator(6.0, 50.0, AttenuatorKind.TEE)

    class _FakeDialog:
        @staticmethod
        def ask(*args: object, **kwargs: object) -> object:
            return design

    monkeypatch.setattr(mw, "AttenuatorDialog", _FakeDialog)
    monkeypatch.setattr(window, "_after_circuit_change", lambda: None)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    window._run_attenuator()

    assert session.circuit is not None
    assert len(session.circuit.elements) == n + 3
    assert "Inserted T pad" in window._status.text()
    window._undo.undo()
    assert len(session.circuit.elements) == n
    window.close()
    assert app is not None


def test_main_window_harmonics() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    window = mw.MainWindow(session, auto_run=False)

    window._refresh_harmonics()
    table = window._harmonics_panel._table
    assert table.rowCount() >= 2  # f0 row + at least one harmonic
    assert len(window._plots._harmonic_lines) >= 1

    window._on_harmonics_f0(50e6)
    assert session.harmonics_f0_hz == pytest.approx(50e6)

    window._act_harmonics.setChecked(False)
    assert window._plots._harmonic_lines == []
    window.close()
    assert app is not None


def test_auto_sweep_toggle_and_custom_range(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.analysis.types import SweepConfig, SweepSpacing
    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession, suggested_sweep_for_spec

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    assert window._auto_sweep.isChecked()
    assert not window._f_start.isEnabled()

    window._auto_sweep.setChecked(False)
    assert window._f_start.isEnabled()
    window._f_start.setText("100M")
    window._f_stop.setText("200M")
    window._run_synthesize_and_analyze()
    assert session.sweep is not None
    assert session.sweep.f_start_hz == pytest.approx(100e6)
    assert session.sweep.f_stop_hz == pytest.approx(200e6)

    window._auto_sweep.setChecked(True)
    assert not window._f_start.isEnabled()
    assert session.sweep == suggested_sweep_for_spec(session.spec)

    custom = SweepConfig(90e6, 210e6, 1024, SweepSpacing.LOGARITHMIC)
    session.sweep = custom
    window._load_session_into_ui()
    assert not window._auto_sweep.isChecked()
    assert window._f_start.isEnabled()
    window.close()
    assert app is not None


def test_main_window_band_wizard(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication, QDialog

    from filterdesk.domain.enums import FilterResponse
    from filterdesk.gui import main_window as mw
    from filterdesk.services.bands import BandKind, band_preset_spec, find_band
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    band = find_band("40m")

    class _FakeDialog:
        def __init__(self, parent: object = None) -> None:
            self.parent = parent

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def result_spec(self):
            return band_preset_spec(band, BandKind.LPF)

        def result_band(self):
            return band

        def result_kind(self):
            return BandKind.LPF

        def snap_enabled(self) -> bool:
            return False

        def snap_series(self):
            from filterdesk.components_std import ESeries

            return ESeries.E24

    monkeypatch.setattr(mw, "BandFilterWizardDialog", _FakeDialog)
    window._run_band_wizard()

    assert session.spec.response == FilterResponse.LOW_PASS
    assert session.spec.cutoff_hz == pytest.approx(band.high_hz * 1.1)
    assert "Applied 40 m LPF" in window._status.text()

    window._undo.undo()
    assert session.spec.response == FilterResponse.HIGH_PASS
    window.close()
    assert app is not None


def test_main_window_band_wizard_updates_sweep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QApplication, QDialog

    from filterdesk.gui import main_window as mw
    from filterdesk.services.bands import (
        BandKind,
        band_preset_spec,
        band_sweep,
        find_band,
    )
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    old_start = window._f_start.text()
    old_stop = window._f_stop.text()
    band = find_band("AM broadcast")

    class _FakeDialog:
        def __init__(self, parent: object = None) -> None:
            self.parent = parent

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def result_spec(self):
            return band_preset_spec(band, BandKind.BSF)

        def result_band(self):
            return band

        def result_kind(self):
            return BandKind.BSF

        def snap_enabled(self) -> bool:
            return False

        def snap_series(self):
            from filterdesk.components_std import ESeries

            return ESeries.E24

    monkeypatch.setattr(mw, "BandFilterWizardDialog", _FakeDialog)
    window._run_band_wizard()

    sweep = band_sweep(band)
    assert window._f_start.text() == window._eng_freq(sweep.f_start_hz)
    assert window._f_stop.text() == window._eng_freq(sweep.f_stop_hz)
    assert session.sweep == sweep

    window._undo.undo()
    assert window._f_start.text() == old_start
    assert window._f_stop.text() == old_stop
    window.close()
    assert app is not None


def test_main_window_band_wizard_warns_on_bad_snap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QApplication, QDialog

    from filterdesk.components_std import ESeries
    from filterdesk.gui import main_window as mw
    from filterdesk.services.bands import BandKind, find_band
    from filterdesk.services.hf_band import (
        BandFilterRequest,
        design_band_filter,
    )
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    band = find_band("2 m")
    request = BandFilterRequest(band, BandKind.BPF)
    design = design_band_filter(request)
    assert design.selected is not None
    spec = design.selected.spec
    warnings: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        mw.QMessageBox, "warning", lambda *args, **kwargs: warnings.append(args)
    )

    class _FakeDialog:
        def __init__(self, parent: object = None) -> None:
            self.parent = parent

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def result_spec(self):
            return spec

        def result_band(self):
            return band

        def result_kind(self):
            return BandKind.BPF

        def result_request(self):
            return request

        def snap_enabled(self) -> bool:
            return True

        def snap_series(self):
            return ESeries.E24

    monkeypatch.setattr(mw, "BandFilterWizardDialog", _FakeDialog)
    window._run_band_wizard()

    assert warnings
    assert any("Snap changed the response" in str(arg) for arg in warnings[0])
    window.close()
    assert app is not None


def test_auto_fit_runs_after_harmonics_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import math

    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.bands import (
        BandKind,
        band_preset_spec,
        band_sweep,
        find_band,
    )
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.set_spec(band_preset_spec(find_band("80 m"), BandKind.LPF))
    session.sweep = band_sweep(find_band("80 m"))
    first = session.synthesize_and_analyze()
    window = mw.MainWindow(session, auto_run=False)
    window._plots.set_result(first)
    window._refresh_harmonics()
    old_lines = tuple(line.value() for line in window._plots._harmonic_lines)
    assert old_lines

    next_band = find_band("70 cm")
    session.set_spec(band_preset_spec(next_band, BandKind.BSF))
    session.sweep = band_sweep(next_band)
    second = session.synthesize_and_analyze()
    for cursor in window._plots._cursors:
        cursor.setPos(math.log10(50e6))
        cursor.setVisible(True)
    window._plots._cursor_freq_hz = 50e6
    seen: list[float] = []
    cursor_visibility: list[bool] = []

    def _capture_auto_range() -> None:
        seen.extend(line.value() for line in window._plots._harmonic_lines)
        cursor_visibility.extend(
            cursor.isVisible() for cursor in window._plots._cursors
        )

    monkeypatch.setattr(window._plots, "auto_range", _capture_auto_range)
    window._fit_plots_after_analysis = True
    window._on_analyze_finished(second)

    assert seen
    assert all(value > math.log10(second.frequency_hz[0]) for value in seen)
    assert all(value not in seen for value in old_lines)
    assert cursor_visibility and not any(cursor_visibility)
    assert window._plots.cursor_frequency_hz() is None
    window.close()
    assert app is not None


def test_main_window_fits_plots_after_synthesis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.analysis.types import SweepConfig, SweepSpacing
    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    result = session.synthesize_and_analyze()
    window = mw.MainWindow(session, auto_run=False)
    window._plots.set_result(result)
    calls: list[bool] = []
    monkeypatch.setattr(window._plots, "auto_range", lambda: calls.append(True))

    window._fit_plots_after_analysis = True
    window._on_analyze_finished(result)
    assert calls == [True]
    assert not window._fit_plots_after_analysis

    calls.clear()
    session.sweep = SweepConfig(1e6, 100e6, 512, SweepSpacing.LOGARITHMIC)
    changed = session.analyze()
    window._fit_plots_after_analysis = False
    window._on_analyze_finished(changed)
    assert calls == [True]

    calls.clear()
    window._on_analyze_finished(session.analyze())
    assert calls == []
    window.close()
    assert app is not None


def test_main_window_power_stress() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)

    assert window._stress_label.text() == ""
    window._power.setValue(100.0)  # triggers _on_power_changed -> _refresh_table

    table = window._table._table
    refs = {
        table.item(r, 0).text(): (table.item(r, 6).text(), table.item(r, 7).text())
        for r in range(table.rowCount())
    }
    assert any(v and i for v, i in refs.values())  # Vpk/Ipk populated for L/C
    assert "Peak" in window._stress_label.text()

    window._power.setValue(0.0)
    assert window._stress_label.text() == ""
    table2 = window._table._table
    assert all(
        table2.item(r, 6).text() == "" for r in range(table2.rowCount())
    )
    window.close()
    assert app is not None


def test_main_window_export_qucs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)
    out = tmp_path / "design.sch"
    monkeypatch.setattr(
        mw.QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), "")
    )
    window._export_qucs()
    assert out.is_file()
    assert out.read_text(encoding="utf-8").startswith("<Qucs Schematic")
    assert "Wrote" in window._status.text()
    window.close()
    assert app is not None


def test_main_window_export_asc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)
    out = tmp_path / "design.asc"
    monkeypatch.setattr(
        mw.QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), "")
    )
    window._export_asc()
    assert out.is_file()
    assert out.read_text(encoding="utf-8").startswith("Version 4")
    assert "Wrote" in window._status.text()
    window.close()
    assert app is not None


def test_main_window_export_touchstone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    window = mw.MainWindow(session, auto_run=False)
    out = tmp_path / "design.s2p"
    monkeypatch.setattr(
        mw.QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), "")
    )
    window._export_touchstone()
    assert out.is_file()
    assert "# HZ S RI R 50" in out.read_text(encoding="utf-8")
    assert "Wrote" in window._status.text()
    window.close()
    assert app is not None


def test_main_window_export_spice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)
    out = tmp_path / "filter.net"
    monkeypatch.setattr(
        mw.QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), "")
    )
    window._export_spice()
    assert out.is_file()
    assert "Wrote" in window._status.text()
    window.close()
    assert app is not None


def test_component_table_shows_tolerance_column() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.circuit import Circuit, IdealInductor, Port
    from filterdesk.domain.enums import ElementRole
    from filterdesk.gui.panels.component_table import ComponentTablePanel

    app = QApplication.instance() or QApplication([])
    circuit = Circuit(
        elements=[
            IdealInductor(
                id="L1",
                value_h=1e-7,
                node_a="in",
                node_b="out",
                role=ElementRole.SERIES,
            )
        ],
        port_in=Port(name="in", node="in", impedance_ohm=50.0),
        port_out=Port(name="out", node="out", impedance_ohm=50.0),
    )
    panel = ComponentTablePanel()
    panel.set_circuit(circuit, {"L1": 2.0})
    assert panel._table.item(0, 5).text() == "2%"
    panel.set_circuit(circuit)
    assert panel._table.item(0, 5).text() == ""
    assert app is not None


def test_main_window_set_tolerance(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    assert session.circuit is not None
    l_id = next(el.id for el in session.circuit.elements if el.id.startswith("L"))
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(mw.QInputDialog, "getText", lambda *a, **k: ("5", True))
    window._set_element_tolerance(l_id)

    tol = session.element_tolerance(l_id)
    assert tol is not None and tol.tolerance_pct == pytest.approx(5.0)
    table = window._table._table
    refs = {
        table.item(r, 0).text(): table.item(r, 5).text()
        for r in range(table.rowCount())
    }
    assert refs[l_id] == "5%"
    window.close()
    assert app is not None


def test_save_as_suggests_spec_name(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.naming import default_filename
    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)
    captured: dict[str, str] = {}

    def _fake_save(*args: object) -> tuple[str, str]:
        captured["default"] = str(args[2])
        return "", ""

    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName", _fake_save)
    window._save_project_as()
    assert captured["default"] == default_filename(session.spec)
    window.close()
    assert app is not None


def test_tune_actions_toolbar_and_component_menu() -> None:
    from PySide6.QtWidgets import QApplication, QToolBar

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)

    # Toolbar keeps the generic Tune actions (with the shortcuts).
    toolbar = window.findChild(QToolBar, "MainToolBar")
    assert toolbar is not None
    tb_labels = [a.text() for a in toolbar.actions()]
    assert "Tune +" in tb_labels and "Tune −" in tb_labels
    assert window._act_tune_up.shortcut().toString() == "Ctrl+]"
    assert window._act_tune_dn.shortcut().toString() == "Ctrl+["

    # The Design menu no longer duplicates them.
    design_menu = next(
        a.menu() for a in window.menuBar().actions() if "&Design" in a.text()
    )
    design_labels = [a.text() for a in design_menu.actions()]
    assert not any(
        t.startswith("Tune +") or t.startswith("Tune −") for t in design_labels
    )

    # The Component submenu shows the step and the shortcut hint.
    assert session.circuit is not None
    window._selected_element = session.circuit.elements[0].id
    window._populate_component_menu()
    comp_labels = [a.text() for a in window._component_menu.actions()]
    assert any("Tune +" in t and "Ctrl+]" in t for t in comp_labels)
    assert any("Tune −" in t and "Ctrl+[" in t for t in comp_labels)

    window.close()
    assert app is not None


def test_main_window_export_build_sheet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    session.power_w = 10.0
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(mw.BuildSheetDialog, "ask", lambda *a, **k: (None, False))

    out = tmp_path / "design_bom.md"
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (str(out), "Build sheet (*.md)"),
    )
    window._export_build_sheet()
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "## Bill of materials" in text
    assert "Forward power | 10 W" in text
    assert "Wrote" in window._status.text()
    window.close()
    assert app is not None


def test_main_window_export_build_sheet_appends_csv_suffix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(mw.BuildSheetDialog, "ask", lambda *a, **k: (None, False))

    chosen = tmp_path / "design_bom"
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (str(chosen), "BOM CSV (*.csv)"),
    )
    window._export_build_sheet()
    assert (tmp_path / "design_bom.csv").is_file()
    window.close()
    assert app is not None


def test_build_sheet_path_aligns_extension() -> None:
    from filterdesk.gui import main_window as mw

    assert mw._build_sheet_path("x.md", "HTML (*.html)") == Path("x.html")
    assert mw._build_sheet_path("x.md", "BOM CSV (*.csv)") == Path("x.csv")
    assert mw._build_sheet_path("x", "BOM CSV (*.csv)") == Path("x.csv")
    assert mw._build_sheet_path("x.markdown", "Build sheet (*.md)") == Path(
        "x.markdown"
    )
    assert mw._build_sheet_path("x.csv", "All files (*)") == Path("x.csv")
    assert mw._build_sheet_path("x.txt", "All files (*)") == Path("x.txt")


def test_main_window_export_build_sheet_filter_overrides_suffix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(mw.BuildSheetDialog, "ask", lambda *a, **k: (None, False))

    chosen = tmp_path / "design_bom.md"
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        lambda *a, **k: (str(chosen), "HTML (*.html)"),
    )
    window._export_build_sheet()
    out = tmp_path / "design_bom.html"
    assert out.is_file()
    assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    window.close()
    assert app is not None


def test_coil_calculator_toroid_live_values() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import CoilCalculatorDialog

    app = QApplication.instance() or QApplication([])
    dialog = CoilCalculatorDialog()
    page = dialog.toroid
    names = [core.name for core in page._cores]
    page._core.setCurrentIndex(names.index("T50-2"))
    page._l.setText("1u")
    page._current.setText("1")
    page._recompute()

    design = page.current_design()
    assert design is not None
    assert design.core.name == "T50-2"
    assert design.turns == 15
    assert "AWG 16" in page._wire.text()
    assert "n/a (iron powder)" in page._sat.text()

    page._turns.setValue(10)
    design = page.current_design()
    assert design is not None and design.turns == 10
    dialog.close()
    assert app is not None


def test_coil_calculator_air_core_live_values() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import CoilCalculatorDialog

    app = QApplication.instance() or QApplication([])
    dialog = CoilCalculatorDialog()
    page = dialog.air_core
    assert page._wire_stack.currentWidget() is page._awg
    page._diameter.setText("10")
    page._awg.setValue(24)
    page._l.setText("1u")
    page._turns.setValue(0)
    page._recompute()

    design = page.current_design()
    assert design is not None
    assert design.turns == 11
    assert design.turns_below == 10
    assert design.enamel_build_mm > 0.0
    assert "mm" in page._length.text()
    assert "Ohm" in page._resistance.text()
    assert "enamelled" in page._wire_info.text()

    page._enamel.setText("0")
    page._recompute()
    design = page.current_design()
    assert design is not None and design.enamel_build_mm == 0.0
    assert "bare" in page._wire_info.text()

    page._wire_mode.setCurrentIndex(1)
    assert page._wire_stack.currentIndex() == 1
    assert page._wire_stack.currentWidget() is page._wire_mm
    page._wire_mm.setText("0.500")
    page._turns.setValue(0)
    page._l.setText("1u")
    page._recompute()
    design = page.current_design()
    assert design is not None
    assert design.wire_diameter_mm == pytest.approx(0.5)
    assert "0.500 mm" in page._wire_info.text()

    page._wire_mode.setCurrentIndex(0)
    assert page._wire_stack.currentIndex() == 0
    assert page._wire_stack.currentWidget() is page._awg

    page._turns.setValue(5)
    design = page.current_design()
    assert design is not None and design.turns == 5
    dialog.close()
    assert app is not None


def test_sensitivity_dialog_rows() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import SensitivityDialog
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.circuit is not None and session.sweep is not None
    report = session.sensitivity()
    dialog = SensitivityDialog(report)
    assert dialog._table.rowCount() == len(report.rows)
    assert dialog.take_action() is None
    dialog.close()
    assert app is not None


def test_build_sheet_dialog_selection() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.components_std import ESeries
    from filterdesk.gui.widgets import BuildSheetDialog

    app = QApplication.instance() or QApplication([])
    dialog = BuildSheetDialog()
    series, group = dialog.selection()
    assert series is None and group is False

    dialog._series.setCurrentIndex(dialog._series.findText("E24"))
    dialog._group.setChecked(True)
    series, group = dialog.selection()
    assert series is ESeries.E24 and group is True
    dialog.close()
    assert app is not None


def test_design_sweep_dialogs() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import DesignSweepDialog, DesignSweepResultDialog
    from filterdesk.services.design_sweep import (
        DesignSweepConfig,
        SweepAxis,
        run_design_sweep,
    )
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    dialog = DesignSweepDialog()
    axis, values, points = dialog.selection()
    assert axis is SweepAxis.ORDER and values == "" and points == 512
    dialog._values.setText("3,5")
    assert dialog.selection()[1] == "3,5"
    dialog.close()

    session = DesignSession()
    session.synthesize()
    rows = run_design_sweep(
        DesignSweepConfig(session.spec, SweepAxis.ORDER, (3, 5, 7), points=64)
    )
    result = DesignSweepResultDialog(list(rows))
    assert result._table.rowCount() == 3
    assert result.take_spec() is None
    result._table.selectRow(1)
    result._on_apply()
    spec = result.take_spec()
    assert spec is not None and spec.order == 5
    result.close()
    assert app is not None


def test_coil_calculator_apply_realizes_inductor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from filterdesk.domain.circuit import IdealInductor
    from filterdesk.domain.enums import ElementRole
    from filterdesk.gui.widgets import CoilCalculatorDialog

    app = QApplication.instance() or QApplication([])
    element = IdealInductor("L1", 1e-6, "in", "out", ElementRole.SERIES)
    dialog = CoilCalculatorDialog(element=element)
    assert dialog.toroid.current_design() is not None
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *a, **k: QMessageBox.StandardButton.Ok,
    )
    dialog._on_apply()
    realized = dialog.realized_element()
    assert realized is not None
    assert realized.winding is not None
    assert realized.winding.kind == "toroid"
    dialog.close()
    assert app is not None


def test_theme_menu_persists_and_applies() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.gui.settings import THEME_KEY, get_settings_store
    from filterdesk.gui.theme import LIGHT, ThemeMode
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    window._apply_theme(ThemeMode.LIGHT)
    assert get_settings_store().get_str(THEME_KEY) == "light"
    assert window._theme_mode is ThemeMode.LIGHT
    assert (
        window._plots._mag.backgroundBrush().color().name()
        == LIGHT.plot_background
    )
    window._apply_theme(ThemeMode.SYSTEM)
    assert get_settings_store().get_str(THEME_KEY) == "system"
    window.close()
    assert app is not None


def test_window_state_persisted_on_close() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.gui.settings import (
        GEOMETRY_KEY,
        STATE_KEY,
        get_settings_store,
    )
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    window.close()
    assert get_settings_store().get_bytes(GEOMETRY_KEY)
    assert get_settings_store().get_bytes(STATE_KEY)
    assert app is not None


def test_spanish_language_applies() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.i18n import Language, current_language
    from filterdesk.gui.main_window import MainWindow
    from filterdesk.gui.settings import (
        LANGUAGE_KEY,
        InMemorySettingsStore,
        set_settings_store,
    )
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    set_settings_store(InMemorySettingsStore({LANGUAGE_KEY: "es"}))
    window = MainWindow(DesignSession(), auto_run=False)
    assert current_language() is Language.ES
    assert window.menuBar().actions()[0].text() == "&Archivo"
    assert window._spec._response.itemText(0) == "Paso bajo"
    assert window._docks[0].windowTitle() == "Especificación"
    window.close()
    assert app is not None


def test_language_selection_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from filterdesk.gui.i18n import Language
    from filterdesk.gui.main_window import MainWindow
    from filterdesk.gui.settings import LANGUAGE_KEY, get_settings_store
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    shown: list[object] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *a, **k: shown.append(a) or QMessageBox.StandardButton.Ok,
    )
    window._request_language(Language.ES)
    assert get_settings_store().get_str(LANGUAGE_KEY) == "es"
    assert shown
    # The running UI stays in English until the app is restarted.
    assert window.menuBar().actions()[0].text() == "&File"
    window.close()
    assert app is not None


def test_app_icon_loads() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.app import _app_icon

    app = QApplication.instance() or QApplication([])
    icon = _app_icon()
    assert not icon.isNull()
    assert not icon.pixmap(32, 32).isNull()
    assert app is not None
