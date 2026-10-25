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


def test_band_preset_dialog_selection() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import BandPresetDialog
    from filterdesk.services.bands import BandKind

    app = QApplication.instance() or QApplication([])
    dialog = BandPresetDialog()
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
    dialog._kind.setCurrentIndex(3)  # ... -> band-stop
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


def test_main_window_band_preset(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.enums import FilterResponse
    from filterdesk.gui import main_window as mw
    from filterdesk.services.bands import BandKind, find_band
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)

    class _FakeDialog:
        @staticmethod
        def ask(*args: object, **kwargs: object) -> tuple[object, BandKind]:
            return find_band("40m"), BandKind.LPF

    monkeypatch.setattr(mw, "BandPresetDialog", _FakeDialog)
    window._run_band_preset()

    band = find_band("40m")
    assert session.spec.response == FilterResponse.LOW_PASS
    assert session.spec.cutoff_hz == pytest.approx(band.high_hz * 1.1)
    assert "Band preset" in window._status.text()

    window._undo.undo()
    assert session.spec.response == FilterResponse.HIGH_PASS
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


def test_toroid_dialog_live_values() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import ToroidDialog

    app = QApplication.instance() or QApplication([])
    dialog = ToroidDialog()
    names = [core.name for core in dialog._cores]
    dialog._core.setCurrentIndex(names.index("T50-2"))
    dialog._l.setText("1u")
    dialog._current.setText("1")
    dialog._recompute()

    design = dialog.current_design()
    assert design is not None
    assert design.core.name == "T50-2"
    assert design.turns == 15
    assert "AWG 16" in dialog._wire.text()
    assert "n/a (iron powder)" in dialog._sat.text()

    dialog._turns.setValue(10)
    design = dialog.current_design()
    assert design is not None and design.turns == 10
    dialog.close()
    assert app is not None
