"""Main application window."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QThread, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QKeySequence,
    QUndoCommand,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSpinBox,
    QStatusBar,
    QToolBar,
    QWidget,
)

from filterdesk import __version__
from filterdesk.analysis.limits_eval import evaluate_limits
from filterdesk.analysis.types import AnalysisResult, SweepConfig, SweepSpacing
from filterdesk.components_std import set_element_parasitics
from filterdesk.domain import circuit_edit
from filterdesk.domain.circuit import (
    Circuit,
    Element,
    IdealCapacitor,
    IdealInductor,
    IdealResistor,
    NonIdealCapacitor,
    NonIdealInductor,
)
from filterdesk.domain.enums import ElementRole
from filterdesk.domain.naming import default_filename
from filterdesk.domain.overlays import Marker
from filterdesk.domain.specs import FilterSpec
from filterdesk.domain.units import format_engineering, parse_si
from filterdesk.gui.commands import (
    EditCircuitCommand,
    NonIdealCommand,
    RetuneMarkerCommand,
    SetElementValueCommand,
    SetLimitsCommand,
    SetMarkersCommand,
    SnapCommand,
    SynthesizeCommand,
)
from filterdesk.gui.panels.component_table import ComponentTablePanel
from filterdesk.gui.panels.limits_panel import LimitsPanel
from filterdesk.gui.panels.markers_panel import MarkersPanel
from filterdesk.gui.panels.plot_panel import PlotPanel
from filterdesk.gui.panels.schematic_view import SchematicPanel
from filterdesk.gui.panels.spec_panel import SpecPanel
from filterdesk.gui.widgets import (
    EngineeringLineEdit,
    MonteCarloDialog,
    NonIdealDialog,
    OptimizeDialog,
    ParasiticDialog,
    SnapDialog,
)
from filterdesk.gui.workers import (
    start_analyze_thread,
    start_import_thread,
    start_monte_carlo_thread,
    start_optimize_thread,
)
from filterdesk.io.csv_export import export_csv
from filterdesk.io.native import load_project, save_project
from filterdesk.io.qucs import write_qucs_schematic
from filterdesk.io.spice import write_ltspice_asc, write_spice_netlist
from filterdesk.io.touchstone import (
    TouchstoneData,
    TouchstoneError,
    write_touchstone_s2p,
)
from filterdesk.montecarlo import MonteCarloResult
from filterdesk.optimization import OptimizationResult
from filterdesk.plotting import get_plot_backend
from filterdesk.services.compare import CompareError, compare_results
from filterdesk.services.retune import RetuneRequest, retune_spec, scale_response
from filterdesk.services.session import DesignSession


def _exc_text(exc: BaseException) -> str:
    """Format exceptions for dialogs (AssertionError often has empty str())."""
    text = str(exc).strip()
    if text:
        return f"{type(exc).__name__}: {text}"
    return f"{type(exc).__name__} (no message)"


_REPO_URL = "https://github.com/fsclavo/filter-desk"
_DOCS_URL = f"{_REPO_URL}/blob/main/docs/user-manual.md"

_INSERT_CHOICES: tuple[tuple[str, ElementRole, str], ...] = (
    ("Series inductor", ElementRole.SERIES, "L"),
    ("Series capacitor", ElementRole.SERIES, "C"),
    ("Series resistor", ElementRole.SERIES, "R"),
    ("Shunt inductor", ElementRole.SHUNT, "L"),
    ("Shunt capacitor", ElementRole.SHUNT, "C"),
    ("Shunt resistor", ElementRole.SHUNT, "R"),
)


class MainWindow(QMainWindow):
    def __init__(
        self,
        session: DesignSession | None = None,
        *,
        auto_run: bool = True,
    ) -> None:
        super().__init__()
        self.setWindowTitle("FilterDesk")
        self.resize(1280, 800)
        self._session = session or DesignSession()
        self._undo = QUndoStack(self)
        self._selected_element: str | None = None
        self._analyze_thread: QThread | None = None
        self._import_thread: QThread | None = None
        self._mc_thread: QThread | None = None
        self._optimize_thread: QThread | None = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(80)
        self._debounce.timeout.connect(self._run_analyze)

        self._spec = SpecPanel()
        self._table = ComponentTablePanel()
        self._schematic = SchematicPanel()
        self._plots = PlotPanel()
        self._markers_panel = MarkersPanel()
        self._limits_panel = LimitsPanel()
        self._docks: list[QDockWidget] = []
        self.setCentralWidget(self._plots)

        self._add_dock(
            "Specification", self._spec, Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self._add_dock(
            "Schematic", self._schematic, Qt.DockWidgetArea.TopDockWidgetArea
        )
        self._add_dock(
            "Components", self._table, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._add_dock(
            "Markers", self._markers_panel, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._add_dock(
            "Limits", self._limits_panel, Qt.DockWidgetArea.RightDockWidgetArea
        )

        self._f_start = EngineeringLineEdit()
        self._f_stop = EngineeringLineEdit()
        self._points = QSpinBox()
        self._points.setRange(64, 8192)
        self._points.setValue(1024)
        self._status = QLabel("Ready")
        self._build_toolbar()
        self.setStatusBar(QStatusBar())
        self.statusBar().addPermanentWidget(self._status)

        self._spec.spec_changed.connect(self._mark_dirty)
        self._table.value_edited.connect(self._on_value_edited)
        self._schematic.element_selected.connect(self._on_schematic_element_selected)
        self._schematic.context_menu_requested.connect(
            self._on_schematic_context_menu
        )
        self._table.element_selected.connect(self._on_table_element_selected)
        self._markers_panel.markers_changed.connect(self._on_markers_edited)
        self._markers_panel.add_at_cursor_requested.connect(self._add_marker_at_cursor)
        self._plots.markers_changed.connect(self._on_markers_dragged)
        self._limits_panel.limits_changed.connect(self._on_limits_edited)
        self._build_menus()
        self._load_session_into_ui()
        if auto_run:
            self._run_synthesize_and_analyze()

    def _add_dock(
        self, title: str, widget: QWidget, area: Qt.DockWidgetArea
    ) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(title)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        self._docks.append(dock)
        return dock

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setObjectName("MainToolBar")
        self.addToolBar(tb)
        act_syn = QAction("Synthesize", self)
        act_syn.triggered.connect(self._run_synthesize_and_analyze)
        tb.addAction(act_syn)
        act_an = QAction("Analyze", self)
        act_an.triggered.connect(self._run_analyze)
        tb.addAction(act_an)
        tb.addSeparator()
        self._act_tune_up = QAction("Tune +", self)
        self._act_tune_up.setShortcut("Ctrl+]")
        self._act_tune_up.setToolTip(
            "Tune the selected component up one step (Ctrl+])"
        )
        self._act_tune_up.triggered.connect(self._tune_selected_increase)
        tb.addAction(self._act_tune_up)
        self._act_tune_dn = QAction("Tune −", self)
        self._act_tune_dn.setShortcut("Ctrl+[")
        self._act_tune_dn.setToolTip(
            "Tune the selected component down one step (Ctrl+[)"
        )
        self._act_tune_dn.triggered.connect(self._tune_selected_decrease)
        tb.addAction(self._act_tune_dn)
        tb.addSeparator()
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.addWidget(QLabel("Start Frequency"))
        lay.addWidget(self._f_start)
        lay.addWidget(QLabel("Stop Frequency"))
        lay.addWidget(self._f_stop)
        lay.addWidget(QLabel("N"))
        lay.addWidget(self._points)
        self._f_start.setMaximumWidth(90)
        self._f_stop.setMaximumWidth(90)
        self._f_start.setToolTip("Sweep start frequency, e.g. 10M or 1G")
        self._f_stop.setToolTip("Sweep stop frequency, e.g. 1G")
        tb.addWidget(wrap)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        act_open = QAction("&Open…", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._open_project)
        act_save = QAction("&Save", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._save_project)
        act_save_as = QAction("Save &As…", self)
        act_save_as.triggered.connect(self._save_project_as)
        act_import_ts = QAction("&Import Touchstone…", self)
        act_import_ts.triggered.connect(self._import_touchstone)
        act_export_smith = QAction("Export &Smith chart…", self)
        act_export_smith.triggered.connect(self._export_smith_chart)
        act_export_csv = QAction("Export C&SV…", self)
        act_export_csv.triggered.connect(self._export_csv)
        act_export_spice = QAction("Export SPICE &netlist…", self)
        act_export_spice.triggered.connect(self._export_spice)
        act_export_s2p = QAction("Export &Touchstone (.s2p)…", self)
        act_export_s2p.triggered.connect(self._export_touchstone)
        act_export_asc = QAction("Export LTspice (.&asc)…", self)
        act_export_asc.triggered.connect(self._export_asc)
        act_export_qucs = QAction("Export &Qucs (.sch)…", self)
        act_export_qucs.triggered.connect(self._export_qucs)
        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_open)
        file_menu.addAction(act_save)
        file_menu.addAction(act_save_as)
        file_menu.addSeparator()
        import_menu = file_menu.addMenu("&Import")
        import_menu.addAction(act_import_ts)
        export_menu = file_menu.addMenu("&Export")
        export_menu.addAction(act_export_smith)
        export_menu.addAction(act_export_csv)
        export_menu.addAction(act_export_s2p)
        export_menu.addAction(act_export_spice)
        export_menu.addAction(act_export_asc)
        export_menu.addAction(act_export_qucs)
        file_menu.addSeparator()
        file_menu.addAction(act_quit)

        edit_menu = self.menuBar().addMenu("&Edit")
        act_undo = self._undo.createUndoAction(self, "&Undo")
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_redo = self._undo.createRedoAction(self, "&Redo")
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(act_undo)
        edit_menu.addAction(act_redo)
        edit_menu.addSeparator()
        act_add_m = QAction("Add &marker at cursor", self)
        act_add_m.setShortcut("Ctrl+M")
        act_add_m.triggered.connect(self._add_marker_at_cursor)
        edit_menu.addAction(act_add_m)

        view_menu = self.menuBar().addMenu("&View")
        for dock in self._docks:
            view_menu.addAction(dock.toggleViewAction())
        view_menu.addSeparator()
        self._act_measured = QAction("Show &measured overlay", self)
        self._act_measured.setCheckable(True)
        self._act_measured.setChecked(True)
        self._act_measured.toggled.connect(self._plots.set_measured_visible)
        view_menu.addAction(self._act_measured)
        self._act_mc = QAction("Show Monte-Carlo &envelope", self)
        self._act_mc.setCheckable(True)
        self._act_mc.setChecked(True)
        self._act_mc.toggled.connect(self._plots.set_monte_carlo_visible)
        view_menu.addAction(self._act_mc)

        design_menu = self.menuBar().addMenu("&Design")
        act_syn = QAction("&Synthesize + Analyze", self)
        act_syn.setShortcut("Ctrl+Return")
        act_syn.triggered.connect(self._run_synthesize_and_analyze)
        design_menu.addAction(act_syn)
        act_snap = QAction("Sna&p to E-series…", self)
        act_snap.triggered.connect(self._run_snap)
        design_menu.addAction(act_snap)
        act_nonideal = QAction("Apply &parasitics / Q…", self)
        act_nonideal.triggered.connect(self._run_nonideal)
        design_menu.addAction(act_nonideal)
        act_mc = QAction("&Monte-Carlo tolerances…", self)
        act_mc.triggered.connect(self._run_monte_carlo)
        design_menu.addAction(act_mc)
        act_scale = QAction("Scale &response…", self)
        act_scale.triggered.connect(self._run_scale_response)
        design_menu.addAction(act_scale)
        act_opt = QAction("&Optimize to limits…", self)
        act_opt.triggered.connect(self._run_optimize)
        design_menu.addAction(act_opt)
        design_menu.addSeparator()
        self._component_menu = design_menu.addMenu("&Component")
        self._component_menu.aboutToShow.connect(self._populate_component_menu)

        help_menu = self.menuBar().addMenu("&Help")
        act_about = QAction("&About FilterDesk", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)
        act_about_qt = QAction("About &Qt", self)
        act_about_qt.triggered.connect(self._show_about_qt)
        help_menu.addAction(act_about_qt)
        help_menu.addSeparator()
        act_github = QAction("&GitHub repository", self)
        act_github.triggered.connect(self._open_github)
        help_menu.addAction(act_github)
        act_docs = QAction("&User manual", self)
        act_docs.triggered.connect(self._open_docs)
        help_menu.addAction(act_docs)

    def _load_session_into_ui(self) -> None:
        self._selected_element = None
        self._spec.set_spec(self._session.spec)
        assert self._session.sweep is not None
        self._f_start.setText(self._eng_freq(self._session.sweep.f_start_hz))
        self._f_stop.setText(self._eng_freq(self._session.sweep.f_stop_hz))
        self._points.setValue(self._session.sweep.n_points)
        self._table.set_circuit(self._session.circuit, self._tolerance_map())
        self._schematic.set_circuit(self._session.circuit)
        self._plots.set_result(self._session.analysis)
        self._plots.set_monte_carlo(None)
        self._plots.set_measured(
            self._session.measured, self._session.measured_name or ""
        )
        self._markers_panel.set_markers(self._session.markers)
        self._limits_panel.set_limits(self._session.limits)
        self._plots.set_markers(self._session.markers)
        self._plots.set_limits(self._session.limits)
        self._refresh_limit_status()
        self._update_title()

    @staticmethod
    def _eng_freq(hz: float) -> str:
        if hz >= 1e9:
            return f"{hz / 1e9:g}G"
        if hz >= 1e6:
            return f"{hz / 1e6:g}M"
        if hz >= 1e3:
            return f"{hz / 1e3:g}k"
        return f"{hz:g}"

    def _mark_dirty(self) -> None:
        self._session.dirty = True
        self._update_title()

    def _update_title(self) -> None:
        dirty = "*" if self._session.dirty else ""
        path = self._session.path or "unsaved"
        self.setWindowTitle(f"FilterDesk — {self._session.title}{dirty} — {path}")

    def _apply_spec_and_sweep_from_ui(self) -> None:
        spec = self._spec.build_spec()
        self._session.set_spec(spec)
        self._session.sweep = SweepConfig(
            f_start_hz=parse_si(self._f_start.text()),
            f_stop_hz=parse_si(self._f_stop.text()),
            n_points=int(self._points.value()),
            spacing=SweepSpacing.LOGARITHMIC,
        )

    def _tolerance_map(self) -> dict[str, float]:
        return {
            ref: tol.tolerance_pct
            for ref, tol in self._session.element_tolerances.items()
        }

    def _after_circuit_change(self) -> None:
        self._table.set_circuit(self._session.circuit, self._tolerance_map())
        self._schematic.set_circuit(self._session.circuit)
        self._spec.set_spec(self._session.spec)
        if self._selected_element_obj() is None:
            self._selected_element = None
        self._plots.set_monte_carlo(None)
        self._update_title()
        self._debounce.start()

    def _run_synthesize_and_analyze(self) -> None:
        try:
            new_spec = self._spec.build_spec()
            self._session.sweep = SweepConfig(
                f_start_hz=parse_si(self._f_start.text()),
                f_stop_hz=parse_si(self._f_stop.text()),
                n_points=int(self._points.value()),
                spacing=SweepSpacing.LOGARITHMIC,
            )
            cmd = SynthesizeCommand(
                self._session, new_spec, on_applied=self._after_circuit_change
            )
            self._undo.push(cmd)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Synthesize failed", _exc_text(exc))
            return
        self._status.setText("Synthesized — analyzing…")
        self._run_analyze()

    def _run_snap(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, "Snap to E-series", "Synthesize a circuit first."
            )
            return
        choice = SnapDialog.ask(self)
        if choice is None:
            return
        series, strategy = choice
        cmd = SnapCommand(
            self._session, series, strategy, on_applied=self._after_circuit_change
        )
        self._undo.push(cmd)
        report = cmd.report
        if report is None or not report.entries:
            self._status.setText(
                f"Snap to {series.value}: values already on the grid"
            )
        else:
            self._status.setText(
                f"Snapped to {series.value} ({strategy.value}) — "
                f"max change {report.max_delta_pct:.2f}%"
            )
        self._run_analyze()

    def _run_nonideal(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, "Apply parasitics", "Synthesize a circuit first."
            )
            return
        try:
            kwargs = NonIdealDialog.ask(self)
        except ValueError as exc:
            QMessageBox.warning(self, "Apply parasitics", _exc_text(exc))
            return
        if not kwargs:
            return
        cmd = NonIdealCommand(
            self._session, kwargs, on_applied=self._after_circuit_change
        )
        self._undo.push(cmd)
        self._status.setText(f"Applied parasitics ({len(kwargs)} term(s))")
        self._run_analyze()

    def _run_monte_carlo(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, "Monte-Carlo", "Synthesize a circuit first."
            )
            return
        try:
            self._apply_spec_and_sweep_from_ui()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Invalid specification", _exc_text(exc))
            return
        config = MonteCarloDialog.ask(self)
        if config is None:
            return
        assert self._session.sweep is not None
        assert self._session.circuit is not None
        self._status.setText(f"Monte-Carlo: {config.n_trials} trials…")
        if self._mc_thread is not None and self._mc_thread.isRunning():
            self._mc_thread.quit()
            self._mc_thread.wait(100)
        thread, worker = start_monte_carlo_thread(
            self._session.circuit,
            self._session.sweep,
            config,
            self._session.limits,
            self._on_mc_finished,
            self._on_mc_failed,
        )
        worker.progress.connect(self._on_mc_progress)
        self._mc_thread = thread
        thread.start()

    def _on_mc_progress(self, done: int, total: int) -> None:
        self._status.setText(f"Monte-Carlo: {done}/{total} trials…")

    def _on_mc_finished(self, result: object) -> None:
        assert isinstance(result, MonteCarloResult)
        self._plots.set_monte_carlo(result)
        if not self._act_mc.isChecked():
            self._act_mc.setChecked(True)
        msg = (
            f"Monte-Carlo: {result.n_trials} trials, worst-case spread "
            f"{result.max_spread_db:.2f} dB"
        )
        if result.yield_fraction is not None:
            msg += f" — yield {100.0 * result.yield_fraction:.1f}%"
        self._status.setText(msg)

    def _on_mc_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Monte-Carlo failed", message)
        self._status.setText("Monte-Carlo failed")

    def _run_scale_response(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, "Scale response", "Synthesize a circuit first."
            )
            return
        text, ok = QInputDialog.getText(
            self,
            "Scale response",
            "Scale factor (e.g. 0.5 halves, 2 doubles):",
            text="1.0",
        )
        if not ok or not text.strip():
            return
        try:
            factor = float(text)
            new_spec = scale_response(self._session.spec, factor)
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Scale response", _exc_text(exc))
            return
        cmd = SynthesizeCommand(
            self._session, new_spec, on_applied=self._after_circuit_change
        )
        self._undo.push(cmd)
        self._status.setText(f"Scaled response ×{factor:g}")
        self._run_analyze()

    def _run_optimize(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(self, "Optimize", "Synthesize a circuit first.")
            return
        if not [lim for lim in self._session.limits if lim.enabled]:
            QMessageBox.information(
                self, "Optimize", "Add at least one enabled limit region first."
            )
            return
        try:
            self._apply_spec_and_sweep_from_ui()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Invalid specification", _exc_text(exc))
            return
        config = OptimizeDialog.ask(self)
        if config is None:
            return
        assert self._session.circuit is not None
        assert self._session.sweep is not None
        self._status.setText("Optimizing…")
        if self._optimize_thread is not None and self._optimize_thread.isRunning():
            self._optimize_thread.quit()
            self._optimize_thread.wait(100)
        thread, _worker = start_optimize_thread(
            self._session.circuit,
            self._session.sweep,
            self._session.limits,
            config,
            self._on_optimize_finished,
            self._on_optimize_failed,
        )
        self._optimize_thread = thread
        thread.start()

    def _on_optimize_finished(self, result: object) -> None:
        assert isinstance(result, OptimizationResult)
        cmd = EditCircuitCommand(
            self._session,
            result.circuit,
            text="Optimize",
            on_applied=self._after_circuit_change,
        )
        self._undo.push(cmd)
        self._status.setText(
            f"Optimized ({result.method.value}): cost "
            f"{result.initial_cost:.4f} → {result.final_cost:.4f}"
        )
        self._run_analyze()

    def _on_optimize_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Optimize failed", message)
        self._status.setText("Optimize failed")

    def _run_analyze(self) -> None:
        if self._session.circuit is None:
            self._run_synthesize_and_analyze()
            return
        try:
            self._apply_spec_and_sweep_from_ui()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Invalid specification", _exc_text(exc))
            return
        assert self._session.sweep is not None
        self._status.setText("Analyzing…")
        if self._analyze_thread is not None and self._analyze_thread.isRunning():
            self._analyze_thread.quit()
            self._analyze_thread.wait(100)
        thread, _worker = start_analyze_thread(
            self._session.circuit,
            self._session.sweep,
            self._session.backend,
            self._on_analyze_finished,
            self._on_analyze_failed,
        )
        self._analyze_thread = thread
        thread.start()

    def _on_analyze_finished(self, result: object) -> None:
        assert isinstance(result, AnalysisResult)
        self._session.analysis = result
        self._plots.set_result(result)
        self._plots.set_markers(self._session.markers)
        self._plots.set_limits(self._session.limits)
        self._refresh_limit_status()
        metrics = self._session.summary_metrics()
        self._status.setText(
            f"Done ({result.backend}, {result.frequency_hz.shape[0]} pts)  "
            f"S21 [{metrics['s21_db_min']:.2f} … {metrics['s21_db_max']:.2f}] dB"
        )
        self._update_title()

    def _refresh_limit_status(self) -> None:
        if self._session.analysis is None or not self._session.limits:
            self._limits_panel.set_pass_fail_text("")
            return
        results = evaluate_limits(self._session.analysis, self._session.limits)
        parts: list[str] = []
        for lim in self._session.limits:
            status = results.get(lim.id)
            if status is True:
                parts.append(f"{lim.id}:PASS")
            elif status is False:
                parts.append(f"{lim.id}:FAIL")
            else:
                parts.append(f"{lim.id}:—")
        self._limits_panel.set_pass_fail_text("  ".join(parts))

    def _on_analyze_failed(self, message: str) -> None:
        self._status.setText("Analysis failed")
        text = message.strip() or "Unknown analysis error"
        QMessageBox.critical(self, "Analysis failed", text)

    def _on_value_edited(self, element_id: str, value: float) -> None:
        try:
            old = self._session.lookup_element_value(element_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Invalid value", _exc_text(exc))
            self._table.set_circuit(self._session.circuit, self._tolerance_map())
            return
        if abs(old - value) < 1e-30 * max(1.0, abs(old)):
            return
        cmd = SetElementValueCommand(
            self._session,
            element_id,
            old,
            value,
            on_applied=self._after_circuit_change,
        )
        self._undo.push(cmd)

    def _on_markers_edited(self, markers: object) -> None:
        assert isinstance(markers, list)
        cmd = SetMarkersCommand(
            self._session,
            markers,
            on_applied=self._after_overlays_change,
            text="Edit markers",
        )
        self._undo.push(cmd)

    def _on_markers_dragged(self, markers: object) -> None:
        assert isinstance(markers, list)
        new_spec = self._retune_from_markers(markers)
        cmd: QUndoCommand
        if new_spec is not None:
            cmd = RetuneMarkerCommand(
                self._session,
                markers,
                new_spec,
                on_applied=self._after_retune,
            )
        else:
            cmd = SetMarkersCommand(
                self._session,
                markers,
                on_applied=self._after_overlays_change,
                text="Move marker",
            )
        self._undo.push(cmd)

    def _retune_from_markers(self, markers: list[Marker]) -> FilterSpec | None:
        """Return a retuned spec if a dragged marker is bound to a landmark."""
        old = {m.id: m for m in self._session.markers}
        request: RetuneRequest | None = None
        for marker in markers:
            previous = old.get(marker.id)
            if previous is None or marker.frequency_hz == previous.frequency_hz:
                continue
            landmark = marker.landmark
            freq = marker.frequency_hz
            if landmark == "cutoff":
                request = RetuneRequest(cutoff_hz=freq)
            elif landmark == "f_center":
                request = RetuneRequest(f_center_hz=freq)
            elif landmark == "bandwidth":
                center = self._session.spec.f_center_hz
                if center:
                    request = RetuneRequest(bandwidth_hz=2.0 * abs(freq - center))
        if request is None:
            return None
        try:
            return retune_spec(self._session.spec, request)
        except ValueError:
            return None

    def _after_retune(self) -> None:
        self._after_circuit_change()
        self._after_overlays_change()

    def _on_limits_edited(self, limits: object) -> None:
        assert isinstance(limits, list)
        cmd = SetLimitsCommand(
            self._session,
            limits,
            on_applied=self._after_overlays_change,
            text="Edit limits",
        )
        self._undo.push(cmd)

    def _after_overlays_change(self) -> None:
        self._markers_panel.set_markers(self._session.markers)
        self._limits_panel.set_limits(self._session.limits)
        self._plots.set_markers(self._session.markers)
        self._plots.set_limits(self._session.limits)
        self._refresh_limit_status()
        self._update_title()

    def _add_marker_at_cursor(self) -> None:
        freq = self._plots.cursor_frequency_hz()
        if freq is None or freq <= 0.0:
            QMessageBox.information(
                self,
                "Add marker",
                "Move the mouse over a plot first to set the cursor frequency.",
            )
            return
        if not self._markers_panel.can_add():
            QMessageBox.warning(
                self, "Add marker", "Maximum number of markers reached."
            )
            return
        markers = list(self._session.markers)
        markers.append(
            Marker(id=self._markers_panel.next_id(), frequency_hz=freq, label="")
        )
        cmd = SetMarkersCommand(
            self._session,
            markers,
            on_applied=self._after_overlays_change,
            text="Add marker",
        )
        self._undo.push(cmd)

    def _on_schematic_element_selected(self, element_id: str) -> None:
        self._selected_element = element_id
        self._table.select_element(element_id)

    def _on_table_element_selected(self, element_id: str) -> None:
        self._selected_element = element_id
        self._schematic.set_highlighted(element_id)

    def _selected_element_obj(self) -> Element | None:
        circuit = self._session.circuit
        if circuit is None or self._selected_element is None:
            return None
        target = self._selected_element
        return next((e for e in circuit.elements if e.id == target), None)

    @staticmethod
    def _is_tunable(el: Element) -> bool:
        return isinstance(
            el,
            (
                IdealCapacitor,
                IdealInductor,
                IdealResistor,
                NonIdealCapacitor,
                NonIdealInductor,
            ),
        )

    def _add_tune_actions(
        self, menu: QMenu, el: Element, element_id: str
    ) -> None:
        if not self._is_tunable(el):
            return
        pct = self._session.step_fraction(element_id) * 100.0
        act_up = menu.addAction(f"Tune +{pct:g}%  (Ctrl+])")
        act_up.triggered.connect(
            lambda *_: self._nudge_element(element_id, 1)
        )
        act_dn = menu.addAction(f"Tune −{pct:g}%  (Ctrl+[)")
        act_dn.triggered.connect(
            lambda *_: self._nudge_element(element_id, -1)
        )
        act_step = menu.addAction("Set tune &step…")
        act_step.triggered.connect(
            lambda *_: self._set_element_step(element_id)
        )
        act_tol = menu.addAction("Set &tolerance…")
        act_tol.triggered.connect(
            lambda *_: self._set_element_tolerance(element_id)
        )

    def _tune_selected_increase(self) -> None:
        if self._selected_element is not None:
            self._nudge_element(self._selected_element, 1)

    def _tune_selected_decrease(self) -> None:
        if self._selected_element is not None:
            self._nudge_element(self._selected_element, -1)

    def _nudge_element(self, element_id: str, direction: int) -> None:
        if self._session.circuit is None:
            return
        try:
            new_value = self._session.nudged_value(element_id, direction)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Tune", _exc_text(exc))
            return
        self._on_value_edited(element_id, new_value)
        self._status.setText(f"Tuned {element_id} → {new_value:.6g}")

    def _set_element_tolerance(self, element_id: str) -> None:
        current = self._session.element_tolerance(element_id)
        text = f"{current.tolerance_pct:g}" if current is not None else ""
        text, ok = QInputDialog.getText(
            self,
            "Component tolerance",
            f"Tolerance ±% for {element_id} (blank to clear):",
            text=text,
        )
        if not ok:
            return
        if not text.strip():
            self._session.clear_element_tolerance(element_id)
            self._status.setText(f"Cleared tolerance for {element_id}")
            self._table.set_circuit(self._session.circuit, self._tolerance_map())
            return
        try:
            pct = float(text)
            self._session.set_element_tolerance(element_id, pct)
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Component tolerance", _exc_text(exc))
            return
        self._status.setText(f"Tolerance for {element_id}: ±{pct:g}%")
        self._table.set_circuit(self._session.circuit, self._tolerance_map())

    def _set_element_step(self, element_id: str) -> None:
        current = self._session.step_fraction(element_id)
        text, ok = QInputDialog.getText(
            self,
            "Tune step",
            f"Relative step per nudge for {element_id} (0.02 = 2%):",
            text=f"{current:g}",
        )
        if not ok or not text.strip():
            return
        try:
            fraction = float(text)
            self._session.set_element_step(element_id, fraction)
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Tune step", _exc_text(exc))
            return
        self._status.setText(f"Tune step for {element_id}: {fraction * 100:g}%")

    def _populate_component_menu(self) -> None:
        """Rebuild the Design → Component menu for the selected element."""
        menu = self._component_menu
        menu.clear()
        el = self._selected_element_obj()
        if el is None:
            placeholder = menu.addAction("(select a component first)")
            placeholder.setEnabled(False)
            return
        element_id = el.id
        act_edit = menu.addAction("Edit value…")
        act_edit.triggered.connect(lambda *_: self._edit_element_value(element_id))
        self._add_tune_actions(menu, el, element_id)
        if isinstance(
            el, (IdealCapacitor, IdealInductor, NonIdealCapacitor, NonIdealInductor)
        ):
            act_par = menu.addAction("Edit parasitics…")
            act_par.triggered.connect(
                lambda *_: self._edit_element_parasitics(element_id)
            )
        if isinstance(el, (IdealCapacitor, IdealInductor)):
            name = "Inductor" if isinstance(el, IdealCapacitor) else "Capacitor"
            act_conv = menu.addAction(f"Convert to {name}")
            act_conv.triggered.connect(lambda *_: self._convert_arm(element_id))
        menu.addSeparator()
        before_menu = menu.addMenu("Insert before")
        after_menu = menu.addMenu("Insert after")
        for label, role, kind in _INSERT_CHOICES:
            act_b = before_menu.addAction(label)
            act_b.triggered.connect(
                lambda *_, r=role, k=kind: self._insert_arm(element_id, r, k, True)
            )
            act_a = after_menu.addAction(label)
            act_a.triggered.connect(
                lambda *_, r=role, k=kind: self._insert_arm(element_id, r, k, False)
            )
        menu.addSeparator()
        circuit = self._session.circuit
        act_del = menu.addAction("Delete element")
        act_del.triggered.connect(lambda *_: self._delete_arm(element_id))
        if circuit is not None and len(circuit.elements) <= 1:
            act_del.setEnabled(False)

    def _push_circuit_edit(self, new_circuit: Circuit, text: str) -> None:
        cmd = EditCircuitCommand(
            self._session,
            new_circuit,
            text=text,
            on_applied=self._after_circuit_change,
        )
        self._undo.push(cmd)

    def _on_schematic_context_menu(
        self, element_id: str, global_pos: QPoint
    ) -> None:
        menu = self._build_schematic_menu(element_id)
        if menu is not None:
            menu.exec(global_pos)

    def _build_schematic_menu(self, element_id: str) -> QMenu | None:
        circuit = self._session.circuit
        if circuit is None:
            return None
        el = next((e for e in circuit.elements if e.id == element_id), None)
        if el is None:
            return None
        menu = QMenu(self)
        act_edit = menu.addAction("Edit value…")
        act_edit.triggered.connect(
            lambda *_: self._edit_element_value(element_id)
        )
        self._add_tune_actions(menu, el, element_id)
        if isinstance(
            el, (IdealCapacitor, IdealInductor, NonIdealCapacitor, NonIdealInductor)
        ):
            act_par = menu.addAction("Edit parasitics…")
            act_par.triggered.connect(
                lambda *_: self._edit_element_parasitics(element_id)
            )
        if isinstance(el, (IdealCapacitor, IdealInductor)):
            name = "Inductor" if isinstance(el, IdealCapacitor) else "Capacitor"
            act_conv = menu.addAction(f"Convert to {name}")
            act_conv.triggered.connect(lambda *_: self._convert_arm(element_id))
        menu.addSeparator()
        before_menu = menu.addMenu("Insert before")
        after_menu = menu.addMenu("Insert after")
        for label, role, kind in _INSERT_CHOICES:
            act_b = before_menu.addAction(label)
            act_b.triggered.connect(
                lambda *_, r=role, k=kind: self._insert_arm(element_id, r, k, True)
            )
            act_a = after_menu.addAction(label)
            act_a.triggered.connect(
                lambda *_, r=role, k=kind: self._insert_arm(element_id, r, k, False)
            )
        menu.addSeparator()
        act_del = menu.addAction("Delete element")
        act_del.triggered.connect(lambda *_: self._delete_arm(element_id))
        return menu

    def _edit_element_value(self, element_id: str) -> None:
        circuit = self._session.circuit
        if circuit is None:
            return
        el = next((e for e in circuit.elements if e.id == element_id), None)
        if isinstance(el, (IdealCapacitor, NonIdealCapacitor)):
            current, unit = el.value_f, "F"
        elif isinstance(el, (IdealInductor, NonIdealInductor)):
            current, unit = el.value_h, "H"
        elif isinstance(el, IdealResistor):
            current, unit = el.value_ohm, "Ohm"
        else:
            QMessageBox.information(
                self, "Edit element", "Only ideal L/C/R arms can be edited here."
            )
            return
        text, ok = QInputDialog.getText(
            self,
            "Edit element",
            f"{element_id} value:",
            text=format_engineering(current, unit, digits=6),
        )
        if not ok or not text.strip():
            return
        try:
            value = parse_si(text)
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Edit element", _exc_text(exc))
            return
        self._on_value_edited(element_id, value)

    def _edit_element_parasitics(self, element_id: str) -> None:
        circuit = self._session.circuit
        if circuit is None:
            return
        el = next((e for e in circuit.elements if e.id == element_id), None)
        if isinstance(el, (IdealInductor, NonIdealInductor)):
            kind = "inductor"
            dialog_kwargs: dict[str, float | str] = {
                "kind": kind,
                "value": el.value_h,
                "series_resistance_ohm": (
                    el.series_resistance_ohm
                    if isinstance(el, NonIdealInductor)
                    else 0.0
                ),
                "parallel_capacitance_f": (
                    el.parallel_capacitance_f
                    if isinstance(el, NonIdealInductor)
                    else 0.0
                ),
            }
        elif isinstance(el, (IdealCapacitor, NonIdealCapacitor)):
            kind = "capacitor"
            dialog_kwargs = {
                "kind": kind,
                "value": el.value_f,
                "esr_ohm": (
                    el.esr_ohm if isinstance(el, NonIdealCapacitor) else 0.0
                ),
                "esl_h": el.esl_h if isinstance(el, NonIdealCapacitor) else 0.0,
            }
        else:
            QMessageBox.information(
                self, "Edit parasitics", "Only L/C arms have parasitics."
            )
            return
        try:
            kwargs = ParasiticDialog.ask(self, **dialog_kwargs)
            if not kwargs:
                return
            new_circuit = set_element_parasitics(circuit, element_id, **kwargs)
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Edit parasitics", _exc_text(exc))
            return
        self._push_circuit_edit(new_circuit, f"Edit {element_id} parasitics")
        self._status.setText(f"Updated parasitics on {element_id}")
        self._run_analyze()

    def _insert_arm(
        self, element_id: str, role: ElementRole, kind: str, before: bool
    ) -> None:
        circuit = self._session.circuit
        if circuit is None:
            return
        text, ok = QInputDialog.getText(
            self,
            "Insert element",
            f"New {kind} value:",
            text=self._default_arm_text(kind),
        )
        if not ok or not text.strip():
            return
        try:
            value = parse_si(text)
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Insert element", _exc_text(exc))
            return
        elements = list(circuit.elements)
        ids = [el.id for el in elements]
        if element_id not in ids:
            return
        idx = ids.index(element_id)
        if before:
            before_id: str | None = element_id
        else:
            before_id = elements[idx + 1].id if idx + 1 < len(elements) else None
        try:
            new_circuit = circuit_edit.insert_simple_arm(
                circuit, role=role, kind=kind, value_si=value, before_id=before_id
            )
        except circuit_edit.CircuitEditError as exc:
            QMessageBox.warning(self, "Insert element", _exc_text(exc))
            return
        self._push_circuit_edit(new_circuit, f"Insert {kind} arm")

    def _convert_arm(self, element_id: str) -> None:
        circuit = self._session.circuit
        if circuit is None:
            return
        el = next((e for e in circuit.elements if e.id == element_id), None)
        if not isinstance(el, (IdealCapacitor, IdealInductor)):
            return
        target = "L" if isinstance(el, IdealCapacitor) else "C"
        reference_hz = circuit_edit.reference_frequency_hz(circuit)
        if reference_hz is None:
            QMessageBox.warning(
                self, "Convert element", "No reference frequency available."
            )
            return
        try:
            new_circuit = circuit_edit.convert_simple_arm(
                circuit, element_id, target, reference_hz
            )
        except circuit_edit.CircuitEditError as exc:
            QMessageBox.warning(self, "Convert element", _exc_text(exc))
            return
        self._push_circuit_edit(new_circuit, f"Convert {element_id}")

    def _delete_arm(self, element_id: str) -> None:
        circuit = self._session.circuit
        if circuit is None:
            return
        try:
            new_circuit = circuit_edit.delete_arm(circuit, element_id)
        except circuit_edit.CircuitEditError as exc:
            QMessageBox.warning(self, "Delete element", _exc_text(exc))
            return
        self._push_circuit_edit(new_circuit, f"Delete {element_id}")

    def _default_arm_text(self, kind: str) -> str:
        circuit = self._session.circuit
        if kind == "R":
            if circuit is None:
                return "50"
            return format_engineering(circuit.port_in.impedance_ohm, "Ohm", digits=4)
        if circuit is None:
            return "1n" if kind == "L" else "1p"
        z0 = circuit.port_in.impedance_ohm
        freq = circuit_edit.reference_frequency_hz(circuit)
        if freq is None or z0 <= 0.0:
            return "1n" if kind == "L" else "1p"
        omega = 2.0 * math.pi * freq
        if kind == "L":
            return format_engineering(z0 / omega, "H", digits=4)
        return format_engineering(1.0 / (omega * z0), "F", digits=4)

    def _open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open FilterDesk project",
            "",
            "FilterDesk (*.filterdesk.json *.fdsk.json);;JSON (*.json)",
        )
        if not path:
            return
        try:
            project = load_project(path)
            self._session.load_project(project, path=path)
            self._undo.clear()
            self._load_session_into_ui()
            self._run_analyze()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open failed", _exc_text(exc))

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About FilterDesk",
            f"<b>FilterDesk</b> {__version__}<br><br>"
            "Passive lumped-element RF filter synthesis and analysis.<br>"
            "Licensed under the Apache License 2.0.<br>"
            "Uses Qt via PySide6 (LGPL-3.0).<br><br>"
            f'<a href="{_REPO_URL}">{_REPO_URL}</a>',
        )

    def _show_about_qt(self) -> None:
        QMessageBox.aboutQt(self, "About Qt")

    def _open_github(self) -> None:
        QDesktopServices.openUrl(QUrl(_REPO_URL))

    def _open_docs(self) -> None:
        QDesktopServices.openUrl(QUrl(_DOCS_URL))

    def _save_project(self) -> None:
        if self._session.path:
            self._write_project(Path(self._session.path))
        else:
            self._save_project_as()

    def _save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save FilterDesk project",
            default_filename(self._session.spec),
            "FilterDesk (*.filterdesk.json)",
        )
        if not path:
            return
        if not path.endswith(".json"):
            path += ".filterdesk.json"
        self._write_project(Path(path))

    def _write_project(self, path: Path) -> None:
        try:
            self._apply_spec_and_sweep_from_ui()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Invalid specification", _exc_text(exc))
            return
        try:
            save_project(self._session.to_project(), path)
            self._session.path = str(path)
            self._session.dirty = False
            self._update_title()
            self._status.setText(f"Saved {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", _exc_text(exc))

    def _import_touchstone(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Touchstone",
            "",
            "Touchstone (*.s1p *.s2p *.s3p *.snp *.ts);;All files (*)",
        )
        if not path:
            return
        if self._import_thread is not None and self._import_thread.isRunning():
            self._import_thread.quit()
            self._import_thread.wait(100)
        thread, _worker = start_import_thread(
            path, self._on_touchstone_loaded, self._on_touchstone_failed
        )
        self._import_thread = thread
        thread.start()
        self._status.setText("Importing measured data…")

    def _on_touchstone_loaded(self, data: object) -> None:
        assert isinstance(data, TouchstoneData)
        name = Path(data.source).name if data.source else "measured"
        try:
            result = data.to_analysis_result()
        except TouchstoneError as exc:
            QMessageBox.information(
                self,
                "Import Touchstone",
                f"Loaded {name}\n{data.summary()}\n\n"
                f"Compare/overlay currently supports 2-port data only ({exc}).",
            )
            return
        self._session.set_measured(result, name)
        self._plots.set_measured(result, name)
        self._act_measured.setChecked(True)
        detail = f"Imported measured data from {name}\n{data.summary()}"
        if self._session.analysis is not None:
            try:
                cmp = compare_results(self._session.analysis, result)
            except CompareError as exc:
                detail += f"\n\nCompare unavailable: {exc}"
            else:
                detail += f"\n\nCompare (overlap band):\n{cmp.summary()}"
        self._status.setText(f"Imported {name}: {data.summary()}")
        QMessageBox.information(self, "Import Touchstone", detail)

    def _on_touchstone_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Import Touchstone", message)

    def _export_smith_chart(self) -> None:
        result = self._session.analysis
        if result is None:
            QMessageBox.information(
                self,
                "Export Smith chart",
                "Analyze a design first (Design → Synthesize + Analyze).",
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Smith chart",
            default_filename(self._session.spec, suffix=".png"),
            "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)",
        )
        if not path:
            return
        if Path(path).suffix.lower() not in {
            ".png",
            ".svg",
            ".pdf",
            ".jpg",
            ".jpeg",
            ".tif",
            ".tiff",
        }:
            path += ".png"
        try:
            get_plot_backend().save_smith_chart(
                result,
                path,
                markers=self._session.markers,
                title="Smith chart — S11 / S22",
            )
            self._status.setText(f"Wrote {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", _exc_text(exc))

    def _export_csv(self) -> None:
        result = self._session.analysis
        if result is None:
            QMessageBox.information(
                self,
                "Export CSV",
                "Analyze a design first (Design → Synthesize + Analyze).",
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            default_filename(self._session.spec, suffix=".csv"),
            "CSV (*.csv);;All files (*)",
        )
        if not path:
            return
        spec = self._session.spec
        try:
            export_csv(
                result,
                path,
                comment=(
                    f"family={spec.family.value} order={spec.order} "
                    f"{spec.response.value} backend={result.backend}"
                ),
            )
            self._status.setText(f"Wrote {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", _exc_text(exc))

    def _export_touchstone(self) -> None:
        result = self._session.analysis
        if result is None:
            QMessageBox.information(
                self,
                "Export Touchstone",
                "Analyze a design first (Design → Synthesize + Analyze).",
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Touchstone (.s2p)",
            default_filename(self._session.spec, suffix=".s2p"),
            "Touchstone (*.s2p);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".s2p"):
            path += ".s2p"
        spec = self._session.spec
        try:
            write_touchstone_s2p(
                result,
                path,
                comment=f"family={spec.family.value} order={spec.order}",
            )
            self._status.setText(f"Wrote {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", _exc_text(exc))

    def _export_spice(self) -> None:
        circuit = self._session.circuit
        if circuit is None:
            QMessageBox.information(
                self, "Export SPICE", "Synthesize a circuit first."
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export SPICE netlist",
            default_filename(self._session.spec, suffix=".net"),
            "SPICE netlist (*.net *.cir);;All files (*)",
        )
        if not path:
            return
        try:
            write_spice_netlist(
                circuit,
                path,
                title=self._session.title,
                ac=self._session.sweep,
            )
            self._status.setText(f"Wrote {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", _exc_text(exc))

    def _export_asc(self) -> None:
        circuit = self._session.circuit
        if circuit is None:
            QMessageBox.information(
                self, "Export LTspice", "Synthesize a circuit first."
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export LTspice schematic",
            default_filename(self._session.spec, suffix=".asc"),
            "LTspice schematic (*.asc);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".asc"):
            path += ".asc"
        try:
            write_ltspice_asc(
                circuit,
                path,
                title=self._session.title,
                ac=self._session.sweep,
            )
            self._status.setText(f"Wrote {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", _exc_text(exc))

    def _export_qucs(self) -> None:
        circuit = self._session.circuit
        if circuit is None:
            QMessageBox.information(
                self, "Export Qucs", "Synthesize a circuit first."
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Qucs schematic",
            default_filename(self._session.spec, suffix=".sch"),
            "Qucs schematic (*.sch);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".sch"):
            path += ".sch"
        try:
            write_qucs_schematic(
                circuit, path, title=self._session.title
            )
            self._status.setText(f"Wrote {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", _exc_text(exc))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._analyze_thread is not None and self._analyze_thread.isRunning():
            self._analyze_thread.quit()
            self._analyze_thread.wait(500)
        if self._import_thread is not None and self._import_thread.isRunning():
            self._import_thread.quit()
            self._import_thread.wait(500)
        if self._mc_thread is not None and self._mc_thread.isRunning():
            self._mc_thread.quit()
            self._mc_thread.wait(2000)
        if self._optimize_thread is not None and self._optimize_thread.isRunning():
            self._optimize_thread.quit()
            self._optimize_thread.wait(2000)
        super().closeEvent(event)
