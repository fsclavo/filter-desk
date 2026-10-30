"""Main application window."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QByteArray, QPoint, Qt, QThread, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,
    QKeySequence,
    QUndoCommand,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDockWidget,
    QDoubleSpinBox,
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
from filterdesk.analysis.compliance import check_spec_compliance
from filterdesk.analysis.limits_eval import evaluate_limits
from filterdesk.analysis.types import AnalysisResult, SweepConfig, SweepSpacing
from filterdesk.components_std import SnapStrategy, set_element_parasitics
from filterdesk.confidence import filter_confidence_items
from filterdesk.domain import circuit_edit
from filterdesk.domain.circuit import (
    Circuit,
    Element,
    IdealCapacitor,
    IdealInductor,
    IdealResistor,
    MicrostripLineElement,
    MicrostripStubElement,
    NonIdealCapacitor,
    NonIdealInductor,
)
from filterdesk.domain.enums import ElementRole, FilterResponse
from filterdesk.domain.naming import default_filename, default_stem
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
    SetSpecCommand,
    SnapCommand,
    SynthesizeCommand,
)
from filterdesk.gui.i18n import Language, language_from_code, set_language, tr
from filterdesk.gui.panels.component_table import ComponentTablePanel
from filterdesk.gui.panels.harmonics_panel import HarmonicsPanel
from filterdesk.gui.panels.limits_panel import LimitsPanel
from filterdesk.gui.panels.markers_panel import MarkersPanel
from filterdesk.gui.panels.measurements_panel import MeasurementsPanel
from filterdesk.gui.panels.plot_panel import PlotPanel
from filterdesk.gui.panels.schematic_view import SchematicPanel
from filterdesk.gui.panels.spec_panel import SpecPanel
from filterdesk.gui.recent_files import (
    add_recent,
    clear_recent,
    load_recent,
    prune_missing,
    remove_recent,
)
from filterdesk.gui.settings import (
    GEOMETRY_KEY,
    LANGUAGE_KEY,
    STATE_KEY,
    THEME_KEY,
    get_settings_store,
)
from filterdesk.gui.theme import ThemeColors, ThemeMode, apply_theme
from filterdesk.gui.widgets import (
    AttenuatorDialog,
    BandFilterWizardDialog,
    BuildSheetDialog,
    CoaxStubDialog,
    CoilCalculatorDialog,
    ConfidenceDialog,
    DesignSweepDialog,
    DesignSweepResultDialog,
    DistributedSynthesisDialog,
    EngineeringLineEdit,
    FourPortMixedModeDialog,
    MatchingDialog,
    MeasurementDetailsDialog,
    MicrostripDialog,
    MonteCarloDialog,
    NonIdealDialog,
    OptimizeDialog,
    ParasiticDialog,
    SensitivityDialog,
    SnapDialog,
    TransformerDialog,
    VnaTuningDialog,
)
from filterdesk.gui.workers import (
    start_analyze_thread,
    start_import_thread,
    start_monte_carlo_thread,
    start_optimize_thread,
)
from filterdesk.io.build_sheet import write_build_sheet
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
from filterdesk.services.bands import band_sweep
from filterdesk.services.compare import CompareError, compare_results
from filterdesk.services.design_sweep import (
    DesignSweepConfig,
    parse_values,
    run_design_sweep,
)
from filterdesk.services.hf_band import evaluate_band_filter_response
from filterdesk.services.measurements import MeasurementRecord
from filterdesk.services.retune import RetuneRequest, retune_spec, scale_response
from filterdesk.services.session import (
    DEFAULT_TITLE,
    DesignSession,
    is_default_sweep,
    suggested_sweep_for_spec,
)
from filterdesk.services.spec_update import SpecUpdateError, update_spec_from_response
from filterdesk.services.vna_measurement import (
    VnaMeasurementMetadata,
    read_vna_metadata,
)


def _exc_text(exc: BaseException) -> str:
    """Format exceptions for dialogs (AssertionError often has empty str())."""
    text = str(exc).strip()
    if text:
        return f"{type(exc).__name__}: {text}"
    return f"{type(exc).__name__} (no message)"


_BUILD_SHEET_SUFFIXES: dict[str, tuple[str, ...]] = {
    "csv": (".csv",),
    "html": (".html", ".htm"),
    "md": (".md", ".markdown"),
}


def _build_sheet_path(path: str, selected_filter: str) -> Path:
    """Align the export extension with the filter the user picked in the dialog."""
    target = Path(path)
    suffix = target.suffix.lower()
    if selected_filter.startswith("All files"):
        if suffix in {s for group in _BUILD_SHEET_SUFFIXES.values() for s in group}:
            return target
        return target if suffix else target.with_suffix(".md")
    if "CSV" in selected_filter:
        allowed = _BUILD_SHEET_SUFFIXES["csv"]
    elif "HTML" in selected_filter:
        allowed = _BUILD_SHEET_SUFFIXES["html"]
    else:
        allowed = _BUILD_SHEET_SUFFIXES["md"]
    if suffix in allowed:
        return target
    return target.with_suffix(allowed[0])


_REPO_URL = "https://github.com/fsclavo/filter-desk"
_DOCS_URL = f"{_REPO_URL}/blob/main/docs/user-manual.md"


def _project_stem(path: str) -> str:
    """Human-readable project name from a project file path."""
    name = Path(path).name
    for suffix in (".filterdesk.json", ".fdsk.json", ".json"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


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
        self._theme_mode = self._load_theme_mode()
        self._theme_colors: ThemeColors | None = None
        self._theme_actions: dict[ThemeMode, QAction] = {}
        self._language = self._load_language()
        self._language_actions: dict[Language, QAction] = {}
        set_language(self._language)
        self._selected_element: str | None = None
        self._analyze_thread: QThread | None = None
        self._import_thread: QThread | None = None
        self._mc_thread: QThread | None = None
        self._optimize_thread: QThread | None = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(80)
        self._debounce.timeout.connect(self._run_analyze)
        self._fit_plots_after_analysis = False

        self._spec = SpecPanel()
        self._table = ComponentTablePanel()
        self._schematic = SchematicPanel()
        self._plots = PlotPanel()
        self._markers_panel = MarkersPanel()
        self._limits_panel = LimitsPanel()
        self._measurements_panel = MeasurementsPanel()
        self._harmonics_panel = HarmonicsPanel()
        self._docks: list[QDockWidget] = []
        self.setCentralWidget(self._plots)

        self._add_dock(
            "Specification", self._spec, Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self._add_dock(
            "Schematic", self._schematic, Qt.DockWidgetArea.TopDockWidgetArea
        )
        self._add_dock("Components", self._table, Qt.DockWidgetArea.RightDockWidgetArea)
        self._add_dock(
            "Markers", self._markers_panel, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._add_dock(
            "Limits", self._limits_panel, Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._add_dock(
            "Measurements",
            self._measurements_panel,
            Qt.DockWidgetArea.RightDockWidgetArea,
        )
        self._add_dock(
            "Harmonics",
            self._harmonics_panel,
            Qt.DockWidgetArea.RightDockWidgetArea,
        )
        self._harmonics_panel.f0_changed.connect(self._on_harmonics_f0)

        self._f_start = EngineeringLineEdit()
        self._f_stop = EngineeringLineEdit()
        self._points = QSpinBox()
        self._points.setRange(64, 8192)
        self._points.setValue(1024)
        self._status = QLabel(tr("Ready"))
        self._build_toolbar()
        self.setStatusBar(QStatusBar())
        self.statusBar().addPermanentWidget(self._status)
        self._stress_label = QLabel("")
        self._stress_label.setToolTip(
            "Worst-case peak voltage/current from the nodal power-stress analysis"
        )
        self.statusBar().addPermanentWidget(self._stress_label)

        self._spec.spec_changed.connect(self._mark_dirty)
        self._table.value_edited.connect(self._on_value_edited)
        self._schematic.element_selected.connect(self._on_schematic_element_selected)
        self._schematic.context_menu_requested.connect(self._on_schematic_context_menu)
        self._table.element_selected.connect(self._on_table_element_selected)
        self._markers_panel.markers_changed.connect(self._on_markers_edited)
        self._markers_panel.add_at_cursor_requested.connect(self._add_marker_at_cursor)
        self._measurements_panel.import_requested.connect(self._import_touchstone)
        self._measurements_panel.use_requested.connect(self._use_measurement)
        self._measurements_panel.details_requested.connect(
            self._show_measurement_details
        )
        self._measurements_panel.delete_requested.connect(self._delete_measurement)
        self._measurements_panel.clear_requested.connect(self._clear_measurements)
        self._plots.markers_changed.connect(self._on_markers_dragged)
        self._limits_panel.limits_changed.connect(self._on_limits_edited)
        self._build_menus()
        self._load_session_into_ui()
        self._apply_theme(self._theme_mode, persist=False)
        self._restore_window_state()
        if auto_run:
            self._run_synthesize_and_analyze()

    def _add_dock(
        self, title: str, widget: QWidget, area: Qt.DockWidgetArea
    ) -> QDockWidget:
        # objectName stays the English key so saved layouts survive a language
        # change; only the displayed title is translated.
        dock = QDockWidget(tr(title), self)
        dock.setObjectName(title)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        self._docks.append(dock)
        return dock

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setObjectName("MainToolBar")
        self.addToolBar(tb)
        act_syn = QAction(tr("Synthesize"), self)
        act_syn.triggered.connect(self._run_synthesize_and_analyze)
        tb.addAction(act_syn)
        act_an = QAction(tr("Analyze"), self)
        act_an.triggered.connect(self._run_analyze)
        tb.addAction(act_an)
        tb.addSeparator()
        self._act_tune_up = QAction(tr("Tune +"), self)
        self._act_tune_up.setShortcut("Ctrl+]")
        self._act_tune_up.setToolTip(
            tr("Tune the selected component up one step (Ctrl+])")
        )
        self._act_tune_up.triggered.connect(self._tune_selected_increase)
        tb.addAction(self._act_tune_up)
        self._act_tune_dn = QAction(tr("Tune −"), self)
        self._act_tune_dn.setShortcut("Ctrl+[")
        self._act_tune_dn.setToolTip(
            tr("Tune the selected component down one step (Ctrl+[)")
        )
        self._act_tune_dn.triggered.connect(self._tune_selected_decrease)
        tb.addAction(self._act_tune_dn)
        tb.addSeparator()
        self._power = QDoubleSpinBox()
        self._power.setRange(0.0, 1_000_000.0)
        self._power.setDecimals(1)
        self._power.setSingleStep(10.0)
        self._power.setSuffix(" W")
        self._power.setValue(0.0)
        self._power.setMaximumWidth(110)
        power_tip = tr(
            "Forward transmit power (W) used to estimate the peak voltage and "
            "current in each L/C (the Vpk / Ipk columns). 0 disables it.\n"
            "Evaluated at the passband landmark (cutoff for LP/HP, center for "
            "BP/BS) assuming a matched Z0 system — use it to pick component "
            "voltage/current ratings (e.g. capacitor voltage) for TX filters."
        )
        self._power.setToolTip(power_tip)
        self._power.valueChanged.connect(self._on_power_changed)
        pwrap = QWidget()
        play = QHBoxLayout(pwrap)
        play.setContentsMargins(4, 0, 4, 0)
        p_label = QLabel(tr("TX Power"))
        p_label.setToolTip(power_tip)
        play.addWidget(p_label)
        play.addWidget(self._power)
        tb.addWidget(pwrap)
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(4, 0, 4, 0)
        self._auto_sweep = QCheckBox(tr("Auto"))
        self._auto_sweep.setChecked(True)
        self._auto_sweep.setToolTip(
            tr("Choose a plotting range from the filter type on each synthesis")
        )
        self._auto_sweep.toggled.connect(self._on_auto_sweep_toggled)
        lay.addWidget(self._auto_sweep)
        lay.addWidget(QLabel(tr("Start Frequency")))
        lay.addWidget(self._f_start)
        lay.addWidget(QLabel(tr("Stop Frequency")))
        lay.addWidget(self._f_stop)
        lay.addWidget(QLabel("N"))
        lay.addWidget(self._points)
        self._f_start.setMaximumWidth(90)
        self._f_stop.setMaximumWidth(90)
        self._f_start.setToolTip(tr("Sweep start frequency, e.g. 10M or 1G"))
        self._f_stop.setToolTip(tr("Sweep stop frequency, e.g. 1G"))
        tb.addWidget(wrap)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu(tr("&File"))
        act_new = QAction(tr("&New"), self)
        act_new.setShortcut(QKeySequence.StandardKey.New)
        act_new.triggered.connect(self._new_project)
        act_open = QAction(tr("&Open…"), self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._open_project)
        act_save = QAction(tr("&Save"), self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._save_project)
        act_save_as = QAction(tr("Save &As…"), self)
        act_save_as.triggered.connect(self._save_project_as)
        act_rename = QAction(tr("&Rename project…"), self)
        act_rename.triggered.connect(self._rename_project)
        act_import_ts = QAction(tr("&Import Touchstone…"), self)
        act_import_ts.triggered.connect(self._import_touchstone)
        act_export_smith = QAction(tr("Export &Smith chart…"), self)
        act_export_smith.triggered.connect(self._export_smith_chart)
        act_export_csv = QAction(tr("Export C&SV…"), self)
        act_export_csv.triggered.connect(self._export_csv)
        act_export_spice = QAction(tr("Export SPICE &netlist…"), self)
        act_export_spice.triggered.connect(self._export_spice)
        act_export_s2p = QAction(tr("Export &Touchstone (.s2p)…"), self)
        act_export_s2p.triggered.connect(self._export_touchstone)
        act_export_asc = QAction(tr("Export LTspice (.&asc)…"), self)
        act_export_asc.triggered.connect(self._export_asc)
        act_export_qucs = QAction(tr("Export &Qucs (.sch)…"), self)
        act_export_qucs.triggered.connect(self._export_qucs)
        act_export_build = QAction(tr("Export build sheet / &BOM…"), self)
        act_export_build.triggered.connect(self._export_build_sheet)
        act_quit = QAction(tr("&Quit"), self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_new)
        file_menu.addAction(act_open)
        self._recent_menu = file_menu.addMenu(tr("&Recent projects"))
        self._refresh_recent_menu()
        file_menu.addSeparator()
        file_menu.addAction(act_save)
        file_menu.addAction(act_save_as)
        file_menu.addAction(act_rename)
        file_menu.addSeparator()
        import_menu = file_menu.addMenu(tr("&Import"))
        import_menu.addAction(act_import_ts)
        export_menu = file_menu.addMenu(tr("&Export"))
        export_menu.addAction(act_export_smith)
        export_menu.addAction(act_export_csv)
        export_menu.addAction(act_export_s2p)
        export_menu.addAction(act_export_spice)
        export_menu.addAction(act_export_asc)
        export_menu.addAction(act_export_qucs)
        export_menu.addAction(act_export_build)
        file_menu.addSeparator()
        file_menu.addAction(act_quit)

        edit_menu = self.menuBar().addMenu(tr("&Edit"))
        act_undo = self._undo.createUndoAction(self, tr("&Undo"))
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_redo = self._undo.createRedoAction(self, tr("&Redo"))
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(act_undo)
        edit_menu.addAction(act_redo)
        edit_menu.addSeparator()
        act_add_m = QAction(tr("Add &marker at cursor"), self)
        act_add_m.setShortcut("Ctrl+M")
        act_add_m.triggered.connect(self._add_marker_at_cursor)
        edit_menu.addAction(act_add_m)

        view_menu = self.menuBar().addMenu(tr("&View"))
        for dock in self._docks:
            view_menu.addAction(dock.toggleViewAction())
        view_menu.addSeparator()
        self._act_measured = QAction(tr("Show &measured overlay"), self)
        self._act_measured.setCheckable(True)
        self._act_measured.setChecked(True)
        self._act_measured.toggled.connect(self._plots.set_measured_visible)
        view_menu.addAction(self._act_measured)
        self._act_mc = QAction(tr("Show Monte-Carlo &envelope"), self)
        self._act_mc.setCheckable(True)
        self._act_mc.setChecked(True)
        self._act_mc.toggled.connect(self._plots.set_monte_carlo_visible)
        view_menu.addAction(self._act_mc)
        self._act_harmonics = QAction(tr("Show &harmonic markers"), self)
        self._act_harmonics.setCheckable(True)
        self._act_harmonics.setChecked(True)
        self._act_harmonics.toggled.connect(self._plots.set_harmonics_visible)
        view_menu.addAction(self._act_harmonics)
        view_menu.addSeparator()
        theme_menu = view_menu.addMenu(tr("&Theme"))
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for mode, label in (
            (ThemeMode.SYSTEM, tr("System")),
            (ThemeMode.LIGHT, tr("Light")),
            (ThemeMode.DARK, tr("Dark")),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(mode is self._theme_mode)
            action.triggered.connect(lambda checked=False, m=mode: self._apply_theme(m))
            theme_group.addAction(action)
            theme_menu.addAction(action)
            self._theme_actions[mode] = action
        language_menu = view_menu.addMenu(tr("&Language"))
        language_group = QActionGroup(self)
        language_group.setExclusive(True)
        for language, label in (
            (Language.EN, tr("English")),
            (Language.ES, tr("Español")),
        ):
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(language is self._language)
            action.triggered.connect(
                lambda checked=False, lang=language: self._request_language(lang)
            )
            language_group.addAction(action)
            language_menu.addAction(action)
            self._language_actions[language] = action

        design_menu = self.menuBar().addMenu(tr("&Design"))
        act_syn = QAction(tr("&Synthesize + Analyze"), self)
        act_syn.setShortcut("Ctrl+Return")
        act_syn.triggered.connect(self._run_synthesize_and_analyze)
        design_menu.addAction(act_syn)
        act_band_wizard = QAction(tr("&Band filter wizard…"), self)
        act_band_wizard.triggered.connect(self._run_band_wizard)
        design_menu.addAction(act_band_wizard)
        act_update_spec = QAction(tr("Update spec from &circuit…"), self)
        act_update_spec.triggered.connect(self._run_update_spec_from_circuit)
        design_menu.addAction(act_update_spec)
        act_distributed = QAction(tr("&Distributed microstrip realization…"), self)
        act_distributed.triggered.connect(self._run_distributed)
        design_menu.addAction(act_distributed)
        design_menu.addSeparator()
        act_snap = QAction(tr("Sna&p to E-series…"), self)
        act_snap.triggered.connect(self._run_snap)
        design_menu.addAction(act_snap)
        act_nonideal = QAction(tr("Apply &parasitics / Q…"), self)
        act_nonideal.triggered.connect(self._run_nonideal)
        design_menu.addAction(act_nonideal)
        design_menu.addSeparator()
        act_mc = QAction(tr("&Monte-Carlo tolerances…"), self)
        act_mc.triggered.connect(self._run_monte_carlo)
        design_menu.addAction(act_mc)
        act_scale = QAction(tr("Scale &response…"), self)
        act_scale.triggered.connect(self._run_scale_response)
        design_menu.addAction(act_scale)
        act_opt = QAction(tr("&Optimize to limits…"), self)
        act_opt.triggered.connect(self._run_optimize)
        design_menu.addAction(act_opt)
        act_sens = QAction(tr("Component &sensitivity…"), self)
        act_sens.triggered.connect(self._run_sensitivity)
        design_menu.addAction(act_sens)
        act_sweep = QAction(tr("Parameter s&weep…"), self)
        act_sweep.triggered.connect(self._run_design_sweep)
        design_menu.addAction(act_sweep)
        design_menu.addSeparator()
        act_compliance = QAction(tr("Check spec &compliance…"), self)
        act_compliance.triggered.connect(self._run_compliance_check)
        design_menu.addAction(act_compliance)
        act_vna = QAction(tr("Tune to &VNA measurement…"), self)
        act_vna.triggered.connect(self._run_vna_tuning)
        design_menu.addAction(act_vna)
        design_menu.addSeparator()
        self._component_menu = design_menu.addMenu(tr("&Component"))
        self._component_menu.aboutToShow.connect(self._populate_component_menu)

        tools_menu = self.menuBar().addMenu(tr("&Tools"))
        act_match = QAction(tr("Matching &network…"), self)
        act_match.triggered.connect(self._run_matching)
        tools_menu.addAction(act_match)
        act_atten = QAction(tr("&Attenuator pad…"), self)
        act_atten.triggered.connect(self._run_attenuator)
        tools_menu.addAction(act_atten)
        tools_menu.addSeparator()
        act_coil = QAction(tr("&Coil calculator…"), self)
        act_coil.triggered.connect(self._run_coil_calculator)
        tools_menu.addAction(act_coil)
        act_transformer = QAction(tr("Trans&former / balun / unun…"), self)
        act_transformer.triggered.connect(self._run_transformer)
        tools_menu.addAction(act_transformer)
        act_microstrip = QAction(tr("&Microstrip line…"), self)
        act_microstrip.triggered.connect(self._run_microstrip)
        tools_menu.addAction(act_microstrip)
        act_coax = QAction(tr("Coaxial &stub notch…"), self)
        act_coax.triggered.connect(self._run_coax_stub)
        tools_menu.addAction(act_coax)
        act_four_port = QAction(tr("&4-port mixed-mode…"), self)
        act_four_port.triggered.connect(self._run_four_port_mixed)
        tools_menu.addAction(act_four_port)

        help_menu = self.menuBar().addMenu(tr("&Help"))
        act_about = QAction(tr("&About FilterDesk"), self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)
        act_about_qt = QAction(tr("About &Qt"), self)
        act_about_qt.triggered.connect(self._show_about_qt)
        help_menu.addAction(act_about_qt)
        help_menu.addSeparator()
        act_github = QAction(tr("&GitHub repository"), self)
        act_github.triggered.connect(self._open_github)
        help_menu.addAction(act_github)
        act_docs = QAction(tr("&User manual"), self)
        act_docs.triggered.connect(self._open_docs)
        help_menu.addAction(act_docs)
        act_confidence = QAction(tr("Model &confidence…"), self)
        act_confidence.triggered.connect(self._show_confidence)
        help_menu.addAction(act_confidence)

        menu_tips = {
            file_menu: tr("Project files, imports and exports."),
            edit_menu: tr("Undo, redo and measurement markers."),
            view_menu: tr("Docks, overlays, theme and language."),
            design_menu: tr("Synthesis, tuning, optimization and compliance."),
            tools_menu: tr("Independent RF calculators and analysis tools."),
            help_menu: tr("Documentation, model confidence and About."),
        }
        for menu, tip in menu_tips.items():
            menu.menuAction().setToolTip(tip)
            menu.menuAction().setStatusTip(tip)

        action_tips = {
            act_new: tr("Create a new filter project."),
            act_open: tr("Open a saved FilterDesk project."),
            act_save: tr("Save the current project."),
            act_save_as: tr("Save the project under a new name."),
            act_rename: tr("Change the project title."),
            act_import_ts: tr("Import measured S11/S21 data from Touchstone."),
            act_export_build: tr("Export the BOM and build sheet."),
            act_quit: tr("Close FilterDesk."),
            act_undo: tr("Undo the last design edit."),
            act_redo: tr("Redo the last undone edit."),
            act_add_m: tr("Add a marker at the cursor frequency."),
            self._act_measured: tr("Show or hide the measured overlay."),
            self._act_mc: tr("Show or hide the Monte-Carlo envelope."),
            self._act_harmonics: tr("Show or hide harmonic marker lines."),
            act_syn: tr("Synthesize the current specification and analyze it."),
            act_band_wizard: tr(
                "Quick presets or guided band-filter design by requirements."
            ),
            act_update_spec: tr(
                "Derive center/cutoff and bandwidth from the analyzed response."
            ),
            act_distributed: tr("Realize a low-pass filter with microstrip lines."),
            act_snap: tr("Round L/C values to a standard E-series grid."),
            act_nonideal: tr("Apply finite Q, ESR/DCR and parasitic models."),
            act_mc: tr("Run a Monte-Carlo tolerance analysis."),
            act_scale: tr("Scale the filter response in frequency."),
            act_opt: tr("Optimize component values against the limits."),
            act_sens: tr("Rank components by sensitivity and tuning direction."),
            act_sweep: tr("Compare design variants along one parameter."),
            act_compliance: tr("Check the response against the specification."),
            act_vna: tr("Trim component values to a measured VNA response."),
            act_match: tr("Design an L/Pi/T matching network."),
            act_atten: tr("Design and insert a T/Pi resistive attenuator."),
            act_coil: tr("Calculate toroid and air-core coils."),
            act_transformer: tr("Design transformers, baluns, ununs and chokes."),
            act_microstrip: tr("Microstrip line, stub and quarter-wave calculators."),
            act_coax: tr("Design a shunt coax stub notch."),
            act_four_port: tr("Import an .s4p and inspect mixed-mode S data."),
            act_docs: tr("Open the user manual in a browser."),
            act_confidence: tr("Inspect model validation and confidence levels."),
            act_about: tr("Show version and license information."),
        }
        for action, tip in action_tips.items():
            action.setToolTip(tip)
            action.setStatusTip(tip)

    def _load_session_into_ui(self) -> None:
        # Populating the widgets emits ``spec_changed``; keep the session's
        # unsaved flag as-is (e.g. a freshly opened project is not dirty).
        was_dirty = self._session.dirty
        self._selected_element = None
        self._spec.set_spec(self._session.spec)
        assert self._session.sweep is not None
        self._f_start.setText(self._eng_freq(self._session.sweep.f_start_hz))
        self._f_stop.setText(self._eng_freq(self._session.sweep.f_stop_hz))
        self._points.setValue(self._session.sweep.n_points)
        auto_sweep = is_default_sweep(self._session.spec, self._session.sweep)
        self._auto_sweep.blockSignals(True)
        self._auto_sweep.setChecked(auto_sweep)
        self._auto_sweep.blockSignals(False)
        self._f_start.setEnabled(not auto_sweep)
        self._f_stop.setEnabled(not auto_sweep)
        self._refresh_table()
        self._schematic.set_circuit(self._session.circuit)
        self._plots.set_result(self._session.analysis)
        if self._session.analysis is not None:
            self._plots.auto_range()
        self._plots.set_monte_carlo(None)
        self._plots.set_measured(
            self._session.measured, self._session.measured_name or ""
        )
        self._markers_panel.set_markers(self._session.markers)
        self._limits_panel.set_limits(self._session.limits)
        self._measurements_panel.set_records(
            self._session.measurements, self._session.active_measurement
        )
        self._plots.set_markers(self._session.markers)
        self._plots.set_limits(self._session.limits)
        self._refresh_limit_status()
        self._refresh_confidence()
        self._session.dirty = was_dirty
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

    def _display_name(self) -> str:
        """Project name shown in the window title (title, else file name)."""
        title = self._session.title.strip()
        if title and title != DEFAULT_TITLE:
            return title
        if self._session.path:
            return _project_stem(self._session.path)
        return DEFAULT_TITLE

    def _update_title(self) -> None:
        dirty = "*" if self._session.dirty else ""
        self.setWindowTitle(f"FilterDesk — {self._display_name()}{dirty}")

    def _export_title(self) -> str:
        """Title for exported files: project name, else a spec-derived fallback."""
        title = self._session.title.strip()
        if title and title != DEFAULT_TITLE:
            return title
        return default_stem(self._session.spec)

    def _load_theme_mode(self) -> ThemeMode:
        raw = get_settings_store().get_str(THEME_KEY, ThemeMode.SYSTEM.value)
        try:
            return ThemeMode(raw)
        except ValueError:
            return ThemeMode.SYSTEM

    def _load_language(self) -> Language:
        raw = get_settings_store().get_str(LANGUAGE_KEY, Language.EN.value)
        return language_from_code(raw)

    def _request_language(self, language: Language) -> None:
        if language is self._language:
            return
        get_settings_store().set_str(LANGUAGE_KEY, language.value)
        QMessageBox.information(
            self,
            tr("Language"),
            tr("Language changed. Restart FilterDesk to apply."),
        )

    def _apply_theme(self, mode: ThemeMode, *, persist: bool = True) -> None:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        colors = apply_theme(app, mode)
        self._theme_mode = mode
        self._theme_colors = colors
        self._plots.set_theme(colors)
        self._schematic.refresh_theme()
        action = self._theme_actions.get(mode)
        if action is not None:
            action.setChecked(True)
        if persist:
            get_settings_store().set_str(THEME_KEY, mode.value)
            self._status.setText(tr("Theme: {mode}", mode=mode.value))

    def _restore_window_state(self) -> None:
        store = get_settings_store()
        geometry = store.get_bytes(GEOMETRY_KEY)
        if geometry:
            self.restoreGeometry(QByteArray(geometry))
        state = store.get_bytes(STATE_KEY)
        if state:
            self.restoreState(QByteArray(state))

    def _save_window_state(self) -> None:
        store = get_settings_store()
        store.set_bytes(GEOMETRY_KEY, bytes(self.saveGeometry().data()))
        store.set_bytes(STATE_KEY, bytes(self.saveState().data()))

    def _on_auto_sweep_toggled(self, checked: bool) -> None:
        self._f_start.setEnabled(not checked)
        self._f_stop.setEnabled(not checked)
        if not checked:
            return
        try:
            spec = self._spec.build_spec()
        except Exception:  # noqa: BLE001
            return
        self._session.sweep = suggested_sweep_for_spec(
            spec, n_points=int(self._points.value())
        )
        self._sync_sweep_controls()

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

    def _refresh_table(self) -> None:
        """Rebuild the component table (tolerances + power-stress columns)."""
        report = self._session.compute_stress()
        self._table.set_circuit(self._session.circuit, self._tolerance_map(), report)
        if report is None:
            self._stress_label.setText("")
            return
        self._stress_label.setText(
            f"Peak {report.max_v_peak_v:.0f} V / {report.max_i_peak_a:.2f} A"
            f" @ {self._eng_freq(report.frequency_hz)}"
        )

    def _on_power_changed(self, value: float) -> None:
        self._session.power_w = float(value)
        self._refresh_table()

    def _on_harmonics_f0(self, value: float) -> None:
        self._session.harmonics_f0_hz = value if value > 0.0 else None
        self._refresh_harmonics()

    def _refresh_harmonics(self) -> None:
        report = self._session.compute_harmonics()
        self._harmonics_panel.set_report(report)
        freqs = [h.frequency_hz for h in report.harmonics] if report is not None else []
        self._plots.set_harmonics(freqs)

    def _sync_sweep_controls(self) -> None:
        sweep = self._session.sweep
        if sweep is None:
            return
        self._f_start.setText(self._eng_freq(sweep.f_start_hz))
        self._f_stop.setText(self._eng_freq(sweep.f_stop_hz))
        self._points.setValue(sweep.n_points)

    def _after_synth_change(self) -> None:
        self._fit_plots_after_analysis = True
        self._sync_sweep_controls()
        self._after_circuit_change()

    def _after_circuit_change(self) -> None:
        self._refresh_table()
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
            if self._auto_sweep.isChecked():
                new_sweep = suggested_sweep_for_spec(
                    new_spec, n_points=int(self._points.value())
                )
            else:
                new_sweep = SweepConfig(
                    f_start_hz=parse_si(self._f_start.text()),
                    f_stop_hz=parse_si(self._f_stop.text()),
                    n_points=int(self._points.value()),
                    spacing=SweepSpacing.LOGARITHMIC,
                )
            cmd = SynthesizeCommand(
                self._session,
                new_spec,
                new_sweep=new_sweep,
                on_applied=self._after_synth_change,
            )
            self._undo.push(cmd)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Synthesize failed"), _exc_text(exc))
            return
        self._status.setText(tr("Synthesized — analyzing…"))
        self._run_analyze()

    def _run_snap(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, tr("Snap to E-series"), tr("Synthesize a circuit first.")
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
                tr("Snap to {series}: values already on the grid", series=series.value)
            )
        else:
            self._status.setText(
                tr(
                    "Snapped to {series} ({strategy}) — max change {delta:.2f}%",
                    series=series.value,
                    strategy=strategy.value,
                    delta=report.max_delta_pct,
                )
            )
        self._run_analyze()

    def _run_nonideal(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, tr("Apply parasitics"), tr("Synthesize a circuit first.")
            )
            return
        try:
            kwargs = NonIdealDialog.ask(self)
        except ValueError as exc:
            QMessageBox.warning(self, tr("Apply parasitics"), _exc_text(exc))
            return
        if not kwargs:
            return
        cmd = NonIdealCommand(
            self._session, kwargs, on_applied=self._after_circuit_change
        )
        self._undo.push(cmd)
        self._status.setText(
            tr("Applied parasitics ({count} term(s))", count=len(kwargs))
        )
        self._run_analyze()

    def _run_monte_carlo(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, tr("Monte-Carlo"), tr("Synthesize a circuit first.")
            )
            return
        try:
            self._apply_spec_and_sweep_from_ui()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Invalid specification"), _exc_text(exc))
            return
        config = MonteCarloDialog.ask(self)
        if config is None:
            return
        assert self._session.sweep is not None
        assert self._session.circuit is not None
        self._status.setText(
            tr("Monte-Carlo: {trials} trials…", trials=config.n_trials)
        )
        self._stop_thread(self._mc_thread, 2000)
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
        self._status.setText(
            tr(
                "Monte-Carlo: {done}/{total} trials…",
                done=done,
                total=total,
            )
        )

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
        QMessageBox.warning(self, tr("Monte-Carlo failed"), message)
        self._status.setText(tr("Monte-Carlo failed"))

    def _run_compliance_check(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, tr("Spec compliance"), tr("Synthesize a circuit first.")
            )
            return
        try:
            report = check_spec_compliance(self._session.spec, self._session.circuit)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Spec compliance"), _exc_text(exc))
            return
        result = "PASS" if report.ok else "FAIL"
        lines = [tr("Spec compliance: {result}", result=result)]
        if report.passband_ripple_db is not None:
            lines.append(
                tr(
                    "Passband ripple: {value} dB",
                    value=f"{report.passband_ripple_db:.3f}",
                )
            )
        if report.stopband_attenuation_db is not None:
            lines.append(
                tr(
                    "Stopband attenuation: {value} dB",
                    value=f"{report.stopband_attenuation_db:.2f}",
                )
            )
        if report.edge_loss_db:
            lines.append(
                tr(
                    "Edge loss: {values}",
                    values=", ".join(
                        f"{value:.2f} dB" for value in report.edge_loss_db
                    ),
                )
            )
        for issue in report.issues:
            lines.append(tr("Issue: {detail}", detail=issue))
        for note in report.notes:
            lines.append(tr("Note: {detail}", detail=note))
        text = "\n".join(lines)
        if report.ok:
            QMessageBox.information(self, tr("Spec compliance"), text)
        else:
            QMessageBox.warning(self, tr("Spec compliance"), text)
        self._status.setText(tr("Spec compliance: {result}", result=result))

    def _run_band_wizard(self) -> None:
        dialog = BandFilterWizardDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        spec = dialog.result_spec()
        band = dialog.result_band()
        kind = dialog.result_kind()
        if spec is None or band is None:
            return
        try:
            self._undo.push(
                SynthesizeCommand(
                    self._session,
                    spec,
                    new_sweep=band_sweep(band),
                    on_applied=self._after_synth_change,
                )
            )
            if dialog.snap_enabled():
                series = dialog.snap_series()
                self._undo.push(
                    SnapCommand(
                        self._session,
                        series,
                        SnapStrategy.PRESERVE_LC_RESONANCES,
                        on_applied=self._after_circuit_change,
                    )
                )
                assert self._session.circuit is not None
                response = evaluate_band_filter_response(
                    dialog.result_request(),
                    self._session.circuit,
                )
                if not response.ok:
                    QMessageBox.warning(
                        self,
                        tr("Snap changed the response"),
                        tr(
                            "Snapping to {series} no longer meets the passband/"
                            "stopband target. Undo with Ctrl+Z or choose a finer "
                            "series (E96 for VHF/UHF).",
                            series=series.value,
                        ),
                    )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Band filter wizard"), _exc_text(exc))
            return
        self._status.setText(
            tr(
                "Applied {band} {kind} — analyzing…",
                band=band.name,
                kind=kind.value.upper(),
            )
        )
        self._run_analyze()

    def _run_attenuator(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, tr("Attenuator"), tr("Synthesize a circuit first.")
            )
            return
        design = AttenuatorDialog.ask(self)
        if design is None:
            return
        new_circuit = circuit_edit.insert_resistive_pad(
            self._session.circuit,
            kind=design.kind.value,
            r_series_ohm=design.r_series_ohm,
            r_shunt_ohm=design.r_shunt_ohm,
            at_input=True,
        )
        self._push_circuit_edit(new_circuit, tr("Insert attenuator"))
        self._status.setText(
            f"Inserted {design.kind.value.upper()} pad "
            f"{design.attenuation_db:g} dB @ {design.z0_ohm:g} Ohm"
        )
        self._run_analyze()

    def _matching_element(self, role: ElementRole, kind: str, value: float) -> Element:
        if kind == "L":
            return IdealInductor(id="X", value_h=value, node_a="", node_b="", role=role)
        return IdealCapacitor(id="X", value_f=value, node_a="", node_b="", role=role)

    def _run_coil_calculator(self) -> None:
        element = self._selected_element_obj()
        selected = (
            element if isinstance(element, (IdealInductor, NonIdealInductor)) else None
        )
        dialog = CoilCalculatorDialog(self, element=selected)
        dialog.exec()
        realized = dialog.realized_element()
        if realized is None or self._session.circuit is None:
            return
        elements = [
            realized if el.id == realized.id else el
            for el in self._session.circuit.elements
        ]
        new_circuit = replace(self._session.circuit, elements=elements)
        self._push_circuit_edit(new_circuit, tr("Realize {ref}", ref=realized.id))
        self._status.setText(
            tr("Realized {ref} as a physical winding", ref=realized.id)
        )
        self._run_analyze()

    def _run_transformer(self) -> None:
        dialog = TransformerDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if self._session.circuit is None:
            QMessageBox.information(
                self,
                tr("Transformer / balun / unun"),
                tr("Synthesize a circuit first."),
            )
            return
        if dialog.remove_requested():
            new_circuit = replace(self._session.circuit, output_balun=None)
            self._push_circuit_edit(new_circuit, tr("Remove output balun"))
            self._run_analyze()
            self._status.setText(tr("Removed output balun"))
            return
        balun = dialog.balun_spec()
        if balun is None:
            return
        new_circuit = replace(
            self._session.circuit,
            output_balun=balun,
            output_transformer_ratio=1.0,
        )
        self._push_circuit_edit(new_circuit, tr("Apply output balun"))
        self._run_analyze()
        self._status.setText(tr("Applied output balun ({kind})", kind=balun.kind))

    def _run_coax_stub(self) -> None:
        CoaxStubDialog(self).exec()

    def _run_four_port_mixed(self) -> None:
        dialog = FourPortMixedModeDialog(self)
        dialog.exec()

    def _run_microstrip(self) -> None:
        MicrostripDialog(self).exec()

    def _run_distributed(self) -> None:
        if self._session.spec.response != FilterResponse.LOW_PASS:
            QMessageBox.information(
                self,
                tr("Distributed microstrip realization"),
                tr("Choose a low-pass specification first."),
            )
            return
        dialog = DistributedSynthesisDialog(self._session.spec, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        design = dialog.design()
        if design is None:
            return
        self._push_circuit_edit(
            design.circuit, tr("Apply distributed microstrip realization")
        )
        self._run_analyze()
        message = tr(
            "Applied distributed microstrip realization on {substrate}",
            substrate=design.substrate.name,
        )
        if design.warnings:
            message += " — " + "; ".join(design.warnings)
        self._status.setText(message)

    def _run_vna_tuning(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, tr("VNA tuning"), tr("Synthesize a circuit first.")
            )
            return
        measured = self._session.measured
        if measured is None:
            QMessageBox.information(
                self,
                tr("VNA tuning"),
                tr("Import a measured Touchstone file first (File → Import)."),
            )
            return
        dialog = VnaTuningDialog(self._session.circuit, measured, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        tuned = dialog.result_circuit()
        if tuned is None:
            return
        self._push_circuit_edit(tuned, tr("Tune to VNA measurement"))
        self._run_analyze()
        self._status.setText(tr("Applied VNA-guided tuning"))

    def _run_matching(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, tr("Matching network"), tr("Synthesize a circuit first.")
            )
            return
        result = MatchingDialog.ask(self)
        if result is None:
            return
        design, model_load, at_input = result
        elements = [
            self._matching_element(e.role, e.kind, e.value) for e in design.elements
        ]
        if model_load:
            omega = 2.0 * math.pi * design.frequency_hz
            xl = design.load_x_ohm
            if abs(xl) > 1e-12:
                if xl > 0.0:
                    load_el: Element = IdealInductor(
                        id="X",
                        value_h=xl / omega,
                        node_a="",
                        node_b="",
                        role=ElementRole.SERIES,
                    )
                else:
                    load_el = IdealCapacitor(
                        id="X",
                        value_f=-1.0 / (omega * xl),
                        node_a="",
                        node_b="",
                        role=ElementRole.SERIES,
                    )
                elements.append(load_el)
            new_circuit = circuit_edit.insert_elements(
                self._session.circuit, elements, at_input=False
            )
            new_circuit = replace(
                new_circuit,
                port_out=replace(new_circuit.port_out, impedance_ohm=design.load_r_ohm),
            )
        else:
            new_circuit = circuit_edit.insert_elements(
                self._session.circuit, elements, at_input=at_input
            )
        self._push_circuit_edit(new_circuit, tr("Insert matching network"))
        self._status.setText(
            f"Inserted {design.topology.value.upper()} match "
            f"({design.source_ohm:g} -> {design.load_r_ohm:g}"
            f"{design.load_x_ohm:+g}j Ohm)"
        )
        self._run_analyze()

    def _run_scale_response(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, tr("Scale response"), tr("Synthesize a circuit first.")
            )
            return
        text, ok = QInputDialog.getText(
            self,
            tr("Scale response"),
            "Scale factor (e.g. 0.5 halves, 2 doubles):",
            text="1.0",
        )
        if not ok or not text.strip():
            return
        try:
            factor = float(text)
            new_spec = scale_response(self._session.spec, factor)
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Scale response"), _exc_text(exc))
            return
        new_sweep = (
            suggested_sweep_for_spec(
                new_spec, n_points=int(self._points.value())
            )
            if self._auto_sweep.isChecked()
            else None
        )
        cmd = SynthesizeCommand(
            self._session,
            new_spec,
            new_sweep=new_sweep,
            on_applied=self._after_synth_change,
        )
        self._undo.push(cmd)
        self._status.setText(tr("Scaled response ×{factor:g}", factor=factor))
        self._run_analyze()

    def _run_optimize(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, tr("Optimize"), tr("Synthesize a circuit first.")
            )
            return
        if not [lim for lim in self._session.limits if lim.enabled]:
            QMessageBox.information(
                self, tr("Optimize"), tr("Add at least one enabled limit region first.")
            )
            return
        try:
            self._apply_spec_and_sweep_from_ui()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Invalid specification"), _exc_text(exc))
            return
        config = OptimizeDialog.ask(self)
        if config is None:
            return
        assert self._session.circuit is not None
        assert self._session.sweep is not None
        self._status.setText(tr("Optimizing…"))
        self._stop_thread(self._optimize_thread, 2000)
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

    def _run_sensitivity(self) -> None:
        if self._session.circuit is None or self._session.sweep is None:
            QMessageBox.information(
                self, tr("Component sensitivity"), tr("Synthesize a circuit first.")
            )
            return
        try:
            report = self._session.sensitivity()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Component sensitivity"), _exc_text(exc))
            return
        self._status.setText(
            tr("Sensitivity: {count} components analyzed", count=len(report.rows))
        )
        dialog = SensitivityDialog(report, self)
        dialog.exec()
        action = dialog.take_action()
        if action is not None:
            ref, direction = action
            self._nudge_element(ref, direction)

    def _run_design_sweep(self) -> None:
        if self._session.circuit is None:
            QMessageBox.information(
                self, tr("Parameter sweep"), tr("Synthesize a circuit first.")
            )
            return
        try:
            self._apply_spec_and_sweep_from_ui()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Invalid specification"), _exc_text(exc))
            return
        options = DesignSweepDialog.ask(self)
        if options is None:
            return
        axis, raw_values, points = options
        try:
            values = parse_values(axis, raw_values)
            rows = run_design_sweep(
                DesignSweepConfig(
                    base_spec=self._session.spec,
                    axis=axis,
                    values=values,
                    points=points,
                )
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Parameter sweep"), _exc_text(exc))
            return
        if not rows:
            QMessageBox.information(self, tr("Parameter sweep"), tr("No variants."))
            return
        self._status.setText(tr("Parameter sweep: {count} variants", count=len(rows)))
        dialog = DesignSweepResultDialog(list(rows), self)
        dialog.exec()
        spec = dialog.take_spec()
        if spec is not None:
            self._spec.set_spec(spec)
            self._run_synthesize_and_analyze()

    def _on_optimize_finished(self, result: object) -> None:
        assert isinstance(result, OptimizationResult)
        cmd = EditCircuitCommand(
            self._session,
            result.circuit,
            text=tr("Optimize"),
            on_applied=self._after_circuit_change,
        )
        self._undo.push(cmd)
        self._status.setText(
            f"Optimized ({result.method.value}): cost "
            f"{result.initial_cost:.4f} → {result.final_cost:.4f}"
        )
        self._run_analyze()

    def _on_optimize_failed(self, message: str) -> None:
        QMessageBox.warning(self, tr("Optimize failed"), message)
        self._status.setText(tr("Optimize failed"))

    def _refresh_confidence(self) -> None:
        circuit = self._session.circuit
        self._plots.set_confidence_items(
            () if circuit is None else filter_confidence_items(circuit)
        )

    def _run_update_spec_from_circuit(self) -> None:
        circuit = self._session.circuit
        analysis = self._session.analysis
        if circuit is None or analysis is None:
            QMessageBox.information(
                self,
                tr("Update spec from circuit"),
                tr("Analyze a circuit first."),
            )
            return
        try:
            update = update_spec_from_response(self._session.spec, circuit, analysis)
        except (SpecUpdateError, ValueError) as exc:
            QMessageBox.warning(self, tr("Update spec from circuit"), _exc_text(exc))
            return
        old = update.old_spec
        new = update.new_spec
        if old.response in (FilterResponse.LOW_PASS, FilterResponse.HIGH_PASS):
            change = (
                f"{tr('Cutoff')}: {format_engineering(old.cutoff_hz, 'Hz')} -> "
                f"{format_engineering(new.cutoff_hz, 'Hz')}"
            )
        else:
            old_center = format_engineering(old.f_center_hz or 0.0, "Hz")
            new_center = format_engineering(new.f_center_hz or 0.0, "Hz")
            change = (
                f"{tr('Center')}: {old_center} -> {new_center}; "
                f"{tr('Bandwidth')}: "
                f"{format_engineering(old.bandwidth_hz or 0.0, 'Hz')} -> "
                f"{format_engineering(new.bandwidth_hz or 0.0, 'Hz')}"
            )
        answer = QMessageBox.question(
            self,
            tr("Update spec from circuit"),
            tr(
                "{change}\n\nDerived from {criterion}. "
                "Family, order, topology, ripple and stopband parameters stay "
                "unchanged. The circuit is not modified; Synthesize would create "
                "a new ideal circuit.",
                change=change,
                criterion=update.criterion,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._undo.push(
            SetSpecCommand(
                self._session,
                new,
                on_applied=self._after_spec_update,
            )
        )
        self._status.setText(tr("Updated target spec from circuit response"))

    def _after_spec_update(self) -> None:
        self._spec.set_spec(self._session.spec)
        self._update_title()

    def _run_analyze(self) -> None:
        if self._session.circuit is None:
            self._run_synthesize_and_analyze()
            return
        try:
            self._apply_spec_and_sweep_from_ui()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Invalid specification"), _exc_text(exc))
            return
        assert self._session.sweep is not None
        self._status.setText(tr("Analyzing…"))
        self._stop_thread(self._analyze_thread, 500)
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
        old_range = self._plots.frequency_range()
        self._plots.set_result(result)
        new_range = self._plots.frequency_range()
        range_changed = (
            old_range is None
            or new_range is None
            or not math.isclose(old_range[0], new_range[0], rel_tol=1e-9)
            or not math.isclose(old_range[1], new_range[1], rel_tol=1e-9)
        )
        self._plots.set_markers(self._session.markers)
        self._plots.set_limits(self._session.limits)
        self._refresh_limit_status()
        self._refresh_harmonics()
        self._refresh_confidence()
        if self._fit_plots_after_analysis or (
            self._auto_sweep.isChecked() and range_changed
        ):
            self._plots.auto_range()
            self._fit_plots_after_analysis = False
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
        self._fit_plots_after_analysis = False
        self._status.setText(tr("Analysis failed"))
        text = message.strip() or "Unknown analysis error"
        QMessageBox.critical(self, tr("Analysis failed"), text)

    def _on_value_edited(self, element_id: str, value: float) -> None:
        try:
            old = self._session.lookup_element_value(element_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Invalid value"), _exc_text(exc))
            self._refresh_table()
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
            text=tr("Edit markers"),
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
                text=tr("Move marker"),
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
            text=tr("Edit limits"),
        )
        self._undo.push(cmd)

    def _after_overlays_change(self) -> None:
        self._markers_panel.set_markers(self._session.markers)
        self._limits_panel.set_limits(self._session.limits)
        self._measurements_panel.set_records(
            self._session.measurements, self._session.active_measurement
        )
        self._plots.set_markers(self._session.markers)
        self._plots.set_limits(self._session.limits)
        self._refresh_limit_status()
        self._update_title()

    def _add_marker_at_cursor(self) -> None:
        freq = self._plots.cursor_frequency_hz()
        if freq is None or freq <= 0.0:
            QMessageBox.information(
                self,
                tr("Add marker"),
                tr("Move the mouse over a plot first to set the cursor frequency."),
            )
            return
        if not self._markers_panel.can_add():
            QMessageBox.warning(
                self, tr("Add marker"), tr("Maximum number of markers reached.")
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
            text=tr("Add marker"),
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

    def _add_tune_actions(self, menu: QMenu, el: Element, element_id: str) -> None:
        if not self._is_tunable(el):
            return
        pct = self._session.step_fraction(element_id) * 100.0
        act_up = menu.addAction(f"Tune +{pct:g}%  (Ctrl+])")
        act_up.triggered.connect(lambda *_: self._nudge_element(element_id, 1))
        act_dn = menu.addAction(f"Tune −{pct:g}%  (Ctrl+[)")
        act_dn.triggered.connect(lambda *_: self._nudge_element(element_id, -1))
        act_step = menu.addAction(tr("Set tune &step…"))
        act_step.triggered.connect(lambda *_: self._set_element_step(element_id))
        act_tol = menu.addAction(tr("Set &tolerance…"))
        act_tol.triggered.connect(lambda *_: self._set_element_tolerance(element_id))

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
            QMessageBox.warning(self, tr("Tune"), _exc_text(exc))
            return
        self._on_value_edited(element_id, new_value)
        self._status.setText(
            tr("Tuned {ref} → {value:.6g}", ref=element_id, value=new_value)
        )

    def _set_element_tolerance(self, element_id: str) -> None:
        current = self._session.element_tolerance(element_id)
        text = f"{current.tolerance_pct:g}" if current is not None else ""
        text, ok = QInputDialog.getText(
            self,
            tr("Component tolerance"),
            f"Tolerance ±% for {element_id} (blank to clear):",
            text=text,
        )
        if not ok:
            return
        if not text.strip():
            self._session.clear_element_tolerance(element_id)
            self._status.setText(tr("Cleared tolerance for {ref}", ref=element_id))
            self._refresh_table()
            return
        try:
            pct = float(text)
            self._session.set_element_tolerance(element_id, pct)
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Component tolerance"), _exc_text(exc))
            return
        self._status.setText(
            tr("Tolerance for {ref}: ±{pct:g}%", ref=element_id, pct=pct)
        )
        self._refresh_table()

    def _set_element_step(self, element_id: str) -> None:
        current = self._session.step_fraction(element_id)
        text, ok = QInputDialog.getText(
            self,
            tr("Tune step"),
            f"Relative step per nudge for {element_id} (0.02 = 2%):",
            text=f"{current:g}",
        )
        if not ok or not text.strip():
            return
        try:
            fraction = float(text)
            self._session.set_element_step(element_id, fraction)
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Tune step"), _exc_text(exc))
            return
        self._status.setText(
            tr(
                "Tune step for {ref}: {pct:g}%",
                ref=element_id,
                pct=fraction * 100,
            )
        )

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
        act_del = menu.addAction(tr("Delete element"))
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

    def _on_schematic_context_menu(self, element_id: str, global_pos: QPoint) -> None:
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
        distributed = isinstance(el, (MicrostripLineElement, MicrostripStubElement))
        act_edit = menu.addAction("Edit value…")
        act_edit.triggered.connect(lambda *_: self._edit_element_value(element_id))
        act_edit.setEnabled(not distributed)
        if not distributed:
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
        act_del = menu.addAction(tr("Delete element"))
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
                self,
                tr("Edit element"),
                tr("Only ideal L/C/R arms can be edited here."),
            )
            return
        text, ok = QInputDialog.getText(
            self,
            tr("Edit element"),
            f"{element_id} value:",
            text=format_engineering(current, unit, digits=6),
        )
        if not ok or not text.strip():
            return
        try:
            value = parse_si(text)
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Edit element"), _exc_text(exc))
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
                "esr_ohm": (el.esr_ohm if isinstance(el, NonIdealCapacitor) else 0.0),
                "esl_h": el.esl_h if isinstance(el, NonIdealCapacitor) else 0.0,
            }
        else:
            QMessageBox.information(
                self, tr("Edit parasitics"), tr("Only L/C arms have parasitics.")
            )
            return
        try:
            kwargs = ParasiticDialog.ask(self, **dialog_kwargs)
            if not kwargs:
                return
            new_circuit = set_element_parasitics(
                circuit,
                element_id,
                series_resistance_ohm=kwargs.get("series_resistance_ohm"),
                parallel_capacitance_f=kwargs.get("parallel_capacitance_f"),
                esr_ohm=kwargs.get("esr_ohm"),
                esl_h=kwargs.get("esl_h"),
            )
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Edit parasitics"), _exc_text(exc))
            return
        self._push_circuit_edit(
            new_circuit, tr("Edit {ref} parasitics", ref=element_id)
        )
        self._status.setText(tr("Updated parasitics on {ref}", ref=element_id))
        self._run_analyze()

    def _insert_arm(
        self, element_id: str, role: ElementRole, kind: str, before: bool
    ) -> None:
        circuit = self._session.circuit
        if circuit is None:
            return
        text, ok = QInputDialog.getText(
            self,
            tr("Insert element"),
            f"New {kind} value:",
            text=self._default_arm_text(kind),
        )
        if not ok or not text.strip():
            return
        try:
            value = parse_si(text)
        except ValueError as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Insert element"), _exc_text(exc))
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
            QMessageBox.warning(self, tr("Insert element"), _exc_text(exc))
            return
        self._push_circuit_edit(new_circuit, tr("Insert {kind} arm", kind=kind))

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
                self, tr("Convert element"), tr("No reference frequency available.")
            )
            return
        try:
            new_circuit = circuit_edit.convert_simple_arm(
                circuit, element_id, target, reference_hz
            )
        except circuit_edit.CircuitEditError as exc:
            QMessageBox.warning(self, tr("Convert element"), _exc_text(exc))
            return
        self._push_circuit_edit(new_circuit, tr("Convert {ref}", ref=element_id))

    def _delete_arm(self, element_id: str) -> None:
        circuit = self._session.circuit
        if circuit is None:
            return
        try:
            new_circuit = circuit_edit.delete_arm(circuit, element_id)
        except circuit_edit.CircuitEditError as exc:
            QMessageBox.warning(self, tr("Delete element"), _exc_text(exc))
            return
        self._push_circuit_edit(new_circuit, tr("Delete {ref}", ref=element_id))

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
            tr("Open FilterDesk project"),
            "",
            "FilterDesk (*.filterdesk.json *.fdsk.json);;JSON (*.json)",
        )
        if not path:
            return
        self._open_project_path(Path(path))

    def _open_project_path(self, path: Path) -> None:
        if not path.is_file():
            remove_recent(path)
            self._refresh_recent_menu()
            QMessageBox.warning(
                self,
                tr("Missing recent project"),
                tr("The file no longer exists:\n{path}", path=path),
            )
            return
        try:
            project = load_project(path)
            self._session.load_project(project, path=str(path))
            self._undo.clear()
            self._load_session_into_ui()
            self._run_analyze()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, tr("Open failed"), _exc_text(exc))
            return
        add_recent(path)
        self._refresh_recent_menu()

    def _open_recent_project(self, path: str) -> None:
        self._open_project_path(Path(path))

    def _clear_recent_projects(self) -> None:
        clear_recent()
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        menu = getattr(self, "_recent_menu", None)
        if menu is None:
            return
        menu.clear()
        existing, _missing = prune_missing(load_recent())
        if not existing:
            empty = menu.addAction(tr("No recent projects"))
            empty.setEnabled(False)
            return
        for index, path in enumerate(existing, start=1):
            label = f"{index}. {Path(path).name}".replace("&", "&&")
            action = menu.addAction(label)
            action.setToolTip(path)
            action.triggered.connect(
                lambda _checked=False, item=path: self._open_recent_project(item)
            )
        menu.addSeparator()
        clear_action = menu.addAction(tr("Clear recent projects"))
        clear_action.triggered.connect(self._clear_recent_projects)

    def _new_project(self) -> None:
        if self._session.dirty:
            answer = QMessageBox.question(
                self,
                tr("New project"),
                tr("Discard the current unsaved changes?"),
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                return
        self._session = DesignSession()
        self._undo.clear()
        self._session.synthesize_and_analyze()
        self._load_session_into_ui()

    def _rename_project(self) -> None:
        current = self._session.title.strip()
        if not current or current == DEFAULT_TITLE:
            current = default_stem(self._session.spec)
        text, ok = QInputDialog.getText(
            self, tr("Rename project"), tr("Project name:"), text=current
        )
        if not ok:
            return
        text = text.strip()
        if not text:
            return
        self._session.title = text
        self._session.dirty = True
        self._update_title()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            tr("About FilterDesk"),
            f"<b>FilterDesk</b> {__version__}<br><br>"
            "Passive lumped-element RF filter synthesis and analysis.<br>"
            "Licensed under the Apache License 2.0.<br>"
            "Uses Qt via PySide6 (LGPL-3.0).<br><br>"
            f'<a href="{_REPO_URL}">{_REPO_URL}</a>',
        )

    def _show_about_qt(self) -> None:
        QMessageBox.aboutQt(self, tr("About Qt"))

    def _open_github(self) -> None:
        QDesktopServices.openUrl(QUrl(_REPO_URL))

    def _open_docs(self) -> None:
        QDesktopServices.openUrl(QUrl(_DOCS_URL))

    def _show_confidence(self) -> None:
        ConfidenceDialog(self).exec()

    def _save_project(self) -> bool:
        if self._session.path:
            return self._write_project(Path(self._session.path))
        return self._save_project_as()

    def _save_project_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save FilterDesk project"),
            default_filename(self._session.spec),
            "FilterDesk (*.filterdesk.json)",
        )
        if not path:
            return False
        if not path.endswith(".json"):
            path += ".filterdesk.json"
        return self._write_project(Path(path))

    def _write_project(self, path: Path) -> bool:
        try:
            self._apply_spec_and_sweep_from_ui()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Invalid specification"), _exc_text(exc))
            return False
        try:
            if self._session.title.strip() in ("", DEFAULT_TITLE):
                self._session.title = _project_stem(str(path))
            save_project(self._session.to_project(), path)
            self._session.path = str(path)
            self._session.dirty = False
            self._update_title()
            self._status.setText(tr("Saved {path}", path=path))
            add_recent(path)
            self._refresh_recent_menu()
            return True
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, tr("Save failed"), _exc_text(exc))
            return False

    def _import_touchstone(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Import Touchstone"),
            "",
            "Touchstone (*.s1p *.s2p *.s3p *.snp *.ts);;All files (*)",
        )
        if not path:
            return
        self._stop_thread(self._import_thread, 500)
        thread, _worker = start_import_thread(
            path, self._on_touchstone_loaded, self._on_touchstone_failed
        )
        self._import_thread = thread
        thread.start()
        self._status.setText(tr("Importing measured data…"))

    def _on_touchstone_loaded(self, data: object) -> None:
        assert isinstance(data, TouchstoneData)
        name = Path(data.source).name if data.source else "measured"
        try:
            result = data.to_analysis_result()
        except TouchstoneError as exc:
            QMessageBox.information(
                self,
                tr("Import Touchstone"),
                f"Loaded {name}\n{data.summary()}\n\n"
                f"Compare/overlay currently supports 2-port data only ({exc}).",
            )
            return
        metadata = VnaMeasurementMetadata()
        if data.source:
            try:
                metadata = read_vna_metadata(data.source)
            except (OSError, ValueError):
                pass
        record = MeasurementRecord.from_arrays(
            name=name,
            source=data.source or "",
            z0_ohm=data.z0_ohm,
            frequency_hz=data.frequency_hz,
            s11=data.s[:, 0, 0],
            s21=data.s[:, 1, 0],
            s12=data.s[:, 0, 1],
            s22=data.s[:, 1, 1],
            metadata=metadata,
        )
        self._session.add_measurement(record)
        self._measurements_panel.set_records(
            self._session.measurements, self._session.active_measurement
        )
        self._plots.set_measured(
            self._session.measured, self._session.measured_name or ""
        )
        self._act_measured.setChecked(True)
        detail = f"Imported measured data from {name}\n{data.summary()}"
        if metadata.summary():
            detail += f"\n{metadata.summary()}"
        if self._session.analysis is not None:
            try:
                cmp = compare_results(self._session.analysis, result)
            except CompareError as exc:
                detail += f"\n\nCompare unavailable: {exc}"
            else:
                detail += f"\n\nCompare (overlap band):\n{cmp.summary()}"
        self._status.setText(f"Imported {name}: {data.summary()}")
        QMessageBox.information(self, tr("Import Touchstone"), detail)

    def _use_measurement(self, index: int) -> None:
        try:
            self._session.activate_measurement(index)
        except IndexError:
            return
        self._measurements_panel.set_records(
            self._session.measurements, self._session.active_measurement
        )
        self._plots.set_measured(
            self._session.measured, self._session.measured_name or ""
        )
        self._act_measured.setChecked(True)
        self._status.setText(
            tr(
                "Active measurement: {name}",
                name=self._session.measured_name or "",
            )
        )

    def _show_measurement_details(self, index: int) -> None:
        if not 0 <= index < len(self._session.measurements):
            return
        dialog = MeasurementDetailsDialog(
            self._session.measurements[index],
            self._session.analysis,
            self,
        )
        dialog.exec()

    def _delete_measurement(self, index: int) -> None:
        try:
            self._session.remove_measurement(index)
        except IndexError:
            return
        self._measurements_panel.set_records(
            self._session.measurements, self._session.active_measurement
        )
        self._plots.set_measured(
            self._session.measured, self._session.measured_name or ""
        )

    def _clear_measurements(self) -> None:
        if not self._session.measurements:
            return
        answer = QMessageBox.question(
            self,
            tr("Clear measurements"),
            tr("Delete all stored measurements from this project?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._session.clear_measurements()
        self._measurements_panel.set_records([], None)
        self._plots.set_measured(None, "")
        self._act_measured.setChecked(False)

    def _on_touchstone_failed(self, message: str) -> None:
        QMessageBox.critical(self, tr("Import Touchstone"), message)

    def _export_smith_chart(self) -> None:
        result = self._session.analysis
        if result is None:
            QMessageBox.information(
                self,
                tr("Export Smith chart"),
                tr("Analyze a design first (Design → Synthesize + Analyze)."),
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Export Smith chart"),
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
            self._status.setText(tr("Wrote {path}", path=path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, tr("Export failed"), _exc_text(exc))

    def _export_csv(self) -> None:
        result = self._session.analysis
        if result is None:
            QMessageBox.information(
                self,
                tr("Export CSV"),
                tr("Analyze a design first (Design → Synthesize + Analyze)."),
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Export CSV"),
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
            self._status.setText(tr("Wrote {path}", path=path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, tr("Export failed"), _exc_text(exc))

    def _export_touchstone(self) -> None:
        result = self._session.analysis
        if result is None:
            QMessageBox.information(
                self,
                tr("Export Touchstone"),
                tr("Analyze a design first (Design → Synthesize + Analyze)."),
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Export Touchstone (.s2p)"),
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
            self._status.setText(tr("Wrote {path}", path=path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, tr("Export failed"), _exc_text(exc))

    def _export_spice(self) -> None:
        circuit = self._session.circuit
        if circuit is None:
            QMessageBox.information(
                self, tr("Export SPICE"), tr("Synthesize a circuit first.")
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Export SPICE netlist"),
            default_filename(self._session.spec, suffix=".net"),
            "SPICE netlist (*.net *.cir);;All files (*)",
        )
        if not path:
            return
        try:
            write_spice_netlist(
                circuit,
                path,
                title=self._export_title(),
                ac=self._session.sweep,
            )
            self._status.setText(tr("Wrote {path}", path=path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, tr("Export failed"), _exc_text(exc))

    def _export_asc(self) -> None:
        circuit = self._session.circuit
        if circuit is None:
            QMessageBox.information(
                self, tr("Export LTspice"), tr("Synthesize a circuit first.")
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Export LTspice schematic"),
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
                title=self._export_title(),
                ac=self._session.sweep,
            )
            self._status.setText(tr("Wrote {path}", path=path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, tr("Export failed"), _exc_text(exc))

    def _export_qucs(self) -> None:
        circuit = self._session.circuit
        if circuit is None:
            QMessageBox.information(
                self, tr("Export Qucs"), tr("Synthesize a circuit first.")
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Export Qucs schematic"),
            default_filename(self._session.spec, suffix=".sch"),
            "Qucs schematic (*.sch);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".sch"):
            path += ".sch"
        try:
            write_qucs_schematic(circuit, path, title=self._export_title())
            self._status.setText(tr("Wrote {path}", path=path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, tr("Export failed"), _exc_text(exc))

    def _export_build_sheet(self) -> None:
        circuit = self._session.circuit
        if circuit is None:
            QMessageBox.information(
                self, tr("Export build sheet"), tr("Synthesize a circuit first.")
            )
            return
        options = BuildSheetDialog.ask(self)
        if options is None:
            return
        series, group = options
        path, selected = QFileDialog.getSaveFileName(
            self,
            tr("Export build sheet / BOM"),
            default_filename(self._session.spec, suffix="_bom.md"),
            "Build sheet (*.md);;BOM CSV (*.csv);;HTML (*.html);;All files (*)",
        )
        if not path:
            return
        target = _build_sheet_path(path, selected)
        tolerances = {
            ref: tol.tolerance_pct
            for ref, tol in self._session.element_tolerances.items()
        }
        try:
            write_build_sheet(
                circuit,
                target,
                spec=self._session.spec,
                tolerances=tolerances,
                stress=self._session.compute_stress(),
                power_w=self._session.power_w,
                title=self._export_title(),
                series=series,
                group=group,
            )
            self._status.setText(tr("Wrote {path}", path=target))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, tr("Export failed"), _exc_text(exc))

    @staticmethod
    def _stop_thread(thread: QThread | None, timeout_ms: int) -> None:
        """Ask a worker thread to stop, terminating it as a last resort.

        ``quit()`` only ends the thread's event loop; a long Monte-Carlo or
        solver loop cannot always observe it. A QThread destroyed while still
        running aborts Qt, so on timeout we terminate it before the window goes
        away (the app hard-exits on shutdown anyway).
        """
        if thread is None:
            return
        try:
            if not thread.isRunning():
                return
            thread.requestInterruption()
            thread.quit()
            if thread.wait(timeout_ms):
                return
            thread.terminate()
            thread.wait(1000)
        except RuntimeError:
            # The C++ QThread was already deleted; nothing left to stop.
            return

    def _confirm_close(self) -> bool:
        if not self._session.dirty:
            return True
        answer = QMessageBox.question(
            self,
            tr("Unsaved changes"),
            tr("Save changes before closing? Unsaved work will be lost."),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self._save_project()
        return True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._confirm_close():
            event.ignore()
            return
        self._save_window_state()
        self._stop_thread(self._analyze_thread, 500)
        self._stop_thread(self._import_thread, 500)
        self._stop_thread(self._mc_thread, 2000)
        self._stop_thread(self._optimize_thread, 2000)
        self._plots.set_monte_carlo(None)
        super().closeEvent(event)
