"""Shared GUI widgets."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from filterdesk.analysis.common_mode import CommonModeError, common_mode_sweep
from filterdesk.analysis.four_port import (
    FourPortError,
    FourPortMixedMode,
    mixed_mode_4port,
)
from filterdesk.analysis.mixed_mode import MixedModeError, mixed_mode_balun
from filterdesk.analysis.sensitivity import SensitivityReport
from filterdesk.analysis.types import AnalysisResult, SweepConfig, SweepSpacing
from filterdesk.components_std import (
    COAX_CABLES,
    AirCoilError,
    AttenuatorDesign,
    AttenuatorError,
    AttenuatorKind,
    BalunDesign,
    BalunError,
    BalunKind,
    CoaxCable,
    CoaxStubDesign,
    CoaxStubError,
    CoaxStubKind,
    CoaxStubResponse,
    ESeries,
    MatchingDesign,
    MatchingError,
    MatchingTopology,
    SnapStrategy,
    coax_stub_response,
    design_air_coil,
    design_attenuator,
    design_balun_options,
    design_coax_stub,
    design_matching,
    design_microstrip,
    design_toroid,
    inductor_resistance_ohm_from_q,
    list_cores,
    list_substrates,
)
from filterdesk.components_std.air_coil import AirCoilDesign, awg_for_diameter_mm
from filterdesk.components_std.microstrip import (
    MicrostripError,
    MicrostripLine,
    Substrate,
)
from filterdesk.components_std.toroid import (
    ToroidCore,
    ToroidDesign,
    ToroidError,
    awg_diameter_mm,
)
from filterdesk.components_std.transformer import (
    TransformerTopology,
)
from filterdesk.confidence import ITEMS, ConfidenceItem, confidence_for
from filterdesk.domain.circuit import (
    BalunSpec,
    Circuit,
    IdealInductor,
    MicrostripLineElement,
    NonIdealInductor,
)
from filterdesk.domain.enums import FilterResponse
from filterdesk.domain.specs import FilterSpec
from filterdesk.domain.units import format_engineering, parse_si
from filterdesk.gui.i18n import tr
from filterdesk.gui.plot_axes import freq_plot
from filterdesk.io.coax_export import coax_notch_csv
from filterdesk.io.mixed_mode_export import mixed_mode_csv, mixed_mode_json
from filterdesk.io.spice import write_tlt_spice_netlist
from filterdesk.io.touchstone import TouchstoneError, read_touchstone
from filterdesk.montecarlo import MonteCarloConfig, ToleranceDistribution
from filterdesk.optimization import OptimizationConfig, OptimizeMethod
from filterdesk.services.bands import (
    ALL_PRESETS,
    REJECTION_PRESETS,
    Band,
    BandKind,
    band_preset_spec,
)
from filterdesk.services.compare import CompareError, compare_results
from filterdesk.services.design_sweep import DesignSweepRow, SweepAxis
from filterdesk.services.hf_band import (
    BandFilterDesign,
    BandFilterDesignError,
    BandFilterRequest,
    design_band_filter,
)
from filterdesk.services.inductor_realization import (
    InductorRealizationError,
    realize_from_air_design,
    realize_from_toroid_design,
)
from filterdesk.services.measurements import MeasurementRecord
from filterdesk.services.vna_tuning import (
    VnaBoundMode,
    VnaTuningConfig,
    VnaTuningError,
    VnaTuningResult,
    fit_circuit_to_measurement,
)
from filterdesk.synthesis.distributed import (
    DistributedDesign,
    DistributedSynthesisError,
    design_distributed_lowpass,
)


class EngineeringLineEdit(QLineEdit):
    """Line edit for values like ``140M``, ``4.7p``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(tr("e.g. 140M, 50, 10n"))


_CONFIDENCE_COLORS: dict[str, str] = {
    "ideal": "#546e7a",
    "validated": "#1b5e20",
    "cross-checked": "#0d47a1",
    "estimated": "#8a4b00",
    "experimental": "#8e1b1b",
    "not evaluated": "#555555",
}


class ConfidenceBadge(QLabel):
    """Small, consistent model-confidence label with an explanatory tooltip."""

    def __init__(
        self, key: str, parent: QWidget | None = None, *, prefix: str = ""
    ) -> None:
        super().__init__(parent)
        self._item: ConfidenceItem | None = None
        self._prefix = prefix
        self.set_key(key)

    @property
    def item(self) -> ConfidenceItem | None:
        return self._item

    def set_key(self, key: str, *, prefix: str | None = None) -> None:
        if prefix is not None:
            self._prefix = prefix
        self.set_item(confidence_for(key))

    def set_item(self, item: ConfidenceItem, *, prefix: str | None = None) -> None:
        if prefix is not None:
            self._prefix = prefix
        self._item = item
        color = _CONFIDENCE_COLORS[item.level.value]
        label = f"{self._prefix}: " if self._prefix else "Model: "
        self.setText(f"{label}{item.level.value}")
        self.setStyleSheet(
            f"QLabel {{ color: white; background: {color}; padding: 2px 7px; "
            "border-radius: 4px; }"
        )
        self.setToolTip(
            f"{item.area}\nEvidence: {item.evidence}\nLimits: {item.limits}"
        )


class ConfidenceStrip(QWidget):
    """Compact, contextual filter-result status strip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 2, 4, 2)
        self._layout.addWidget(QLabel("Model status:"))
        self._layout.addStretch(1)
        self._items: tuple[ConfidenceItem, ...] = ()

    @property
    def items(self) -> tuple[ConfidenceItem, ...]:
        return self._items

    def set_items(self, items: tuple[ConfidenceItem, ...]) -> None:
        self._items = items
        while self._layout.count() > 2:
            layout_item = self._layout.takeAt(2)
            if layout_item is not None:
                widget = layout_item.widget()
                if widget is not None:
                    widget.deleteLater()
        for confidence_item in items:
            badge = ConfidenceBadge(confidence_item.key, prefix=confidence_item.area)
            badge.set_item(confidence_item)
            self._layout.addWidget(badge)


class ConfidenceDialog(QDialog):
    """Read-only inventory of what is validated, estimated or experimental."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Model confidence")
        self.resize(820, 460)
        table = QTableWidget(len(ITEMS), 4)
        table.setHorizontalHeaderLabels(["Area", "Status", "Evidence", "Limits"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setWordWrap(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row, item in enumerate(ITEMS):
            table.setItem(row, 0, QTableWidgetItem(item.area))
            table.setItem(row, 1, QTableWidgetItem(item.level.value))
            table.setItem(row, 2, QTableWidgetItem(item.evidence))
            table.setItem(row, 3, QTableWidgetItem(item.limits))
        table.resizeRowsToContents()
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Model status is explicit: validated / cross-checked / estimated / "
                "experimental / not evaluated. Estimates are not guarantees."
            )
        )
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


_STRATEGY_LABELS: dict[SnapStrategy, str] = {
    SnapStrategy.INDEPENDENT: "Independent (all L and C)",
    SnapStrategy.L_ONLY: "L only",
    SnapStrategy.C_ONLY: "C only",
    SnapStrategy.PRESERVE_LC_RESONANCES: "Preserve LC resonances",
}


class SnapDialog(QDialog):
    """Choose an E-series and a snap strategy."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        series: ESeries | str = ESeries.E24,
        strategy: SnapStrategy | str = SnapStrategy.INDEPENDENT,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Snap to E-series"))
        self._series = QComboBox()
        for es in ESeries:
            self._series.addItem(es.value, es)
        self._series.setCurrentIndex(list(ESeries).index(ESeries(series)))
        self._strategy = QComboBox()
        for st in SnapStrategy:
            self._strategy.addItem(tr(_STRATEGY_LABELS[st]), st)
        self._strategy.setCurrentIndex(list(SnapStrategy).index(SnapStrategy(strategy)))
        form = QFormLayout(self)
        form.addRow(tr("Series"), self._series)
        form.addRow(tr("Strategy"), self._strategy)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @property
    def series(self) -> ESeries:
        return ESeries(self._series.currentData())

    @property
    def strategy(self) -> SnapStrategy:
        return SnapStrategy(self._strategy.currentData())

    @classmethod
    def ask(
        cls,
        parent: QWidget | None = None,
        *,
        series: ESeries | str = ESeries.E24,
        strategy: SnapStrategy | str = SnapStrategy.INDEPENDENT,
    ) -> tuple[ESeries, SnapStrategy] | None:
        dialog = cls(parent, series=series, strategy=strategy)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.series, dialog.strategy
        return None


class NonIdealDialog(QDialog):
    """Enter finite-Q / ESR / parasitic values for the whole circuit."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Apply parasitics / finite Q"))
        self._ind_q = EngineeringLineEdit()
        self._ind_q.setPlaceholderText(tr("e.g. 100 (blank = ideal)"))
        self._q_freq = EngineeringLineEdit()
        self._q_freq.setPlaceholderText(tr("e.g. 100M (required for Q)"))
        self._ind_dcr = EngineeringLineEdit()
        self._ind_dcr.setPlaceholderText(tr("e.g. 0.5 (ohm, optional)"))
        self._ind_cpar = EngineeringLineEdit()
        self._ind_cpar.setPlaceholderText(tr("e.g. 0.2p (F, optional)"))
        self._cap_esr = EngineeringLineEdit()
        self._cap_esr.setPlaceholderText(tr("e.g. 0.05 (ohm, optional)"))
        self._cap_esl = EngineeringLineEdit()
        self._cap_esl.setPlaceholderText(tr("e.g. 0.5n (H, optional)"))
        form = QFormLayout(self)
        form.addRow(tr("Inductor Q"), self._ind_q)
        form.addRow(tr("Q reference freq"), self._q_freq)
        form.addRow(tr("Inductor DCR"), self._ind_dcr)
        form.addRow(tr("Inductor Cpar"), self._ind_cpar)
        form.addRow(tr("Capacitor ESR"), self._cap_esr)
        form.addRow(tr("Capacitor ESL"), self._cap_esl)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def kwargs(self) -> dict[str, float]:
        kwargs: dict[str, float] = {}
        q_text = self._ind_q.text().strip()
        if q_text:
            kwargs["inductor_q"] = float(q_text)
            freq_text = self._q_freq.text().strip()
            if not freq_text:
                raise ValueError(tr("Q reference frequency is required when Q is set"))
            kwargs["q_frequency_hz"] = parse_si(freq_text)
        for key, field in (
            ("inductor_dcr_ohm", self._ind_dcr),
            ("inductor_parallel_capacitance_f", self._ind_cpar),
            ("capacitor_esr_ohm", self._cap_esr),
            ("capacitor_esl_h", self._cap_esl),
        ):
            text = field.text().strip()
            if text:
                kwargs[key] = parse_si(text)
        return kwargs

    @classmethod
    def ask(cls, parent: QWidget | None = None) -> dict[str, float] | None:
        dialog = cls(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.kwargs()
        return None


class ParasiticDialog(QDialog):
    """Edit the parasitics of a single inductor or capacitor arm."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        kind: str,
        value: float = 0.0,
        series_resistance_ohm: float = 0.0,
        parallel_capacitance_f: float = 0.0,
        esr_ohm: float = 0.0,
        esl_h: float = 0.0,
    ) -> None:
        super().__init__(parent)
        self._kind = kind
        self._value = value
        form = QFormLayout(self)
        if kind == "inductor":
            self.setWindowTitle(tr("Inductor parasitics"))
            self._r = EngineeringLineEdit()
            self._r.setText(format_engineering(series_resistance_ohm, "Ohm", digits=6))
            self._cp = EngineeringLineEdit()
            self._cp.setText(format_engineering(parallel_capacitance_f, "F", digits=6))
            self._q = EngineeringLineEdit()
            self._q.setPlaceholderText(tr("optional; overrides DCR"))
            self._q_freq = EngineeringLineEdit()
            self._q_freq.setPlaceholderText(tr("e.g. 100M"))
            form.addRow(tr("Series R (DCR)"), self._r)
            form.addRow(tr("Parallel C (Cp)"), self._cp)
            form.addRow(tr("Q"), self._q)
            form.addRow(tr("Q reference freq"), self._q_freq)
        else:
            self.setWindowTitle(tr("Capacitor parasitics"))
            self._esr = EngineeringLineEdit()
            self._esr.setText(format_engineering(esr_ohm, "Ohm", digits=6))
            self._esl = EngineeringLineEdit()
            self._esl.setText(format_engineering(esl_h, "H", digits=6))
            form.addRow(tr("ESR"), self._esr)
            form.addRow(tr("ESL"), self._esl)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def kwargs(self) -> dict[str, float]:
        if self._kind == "inductor":
            kwargs = {
                "parallel_capacitance_f": parse_si(self._cp.text().strip() or "0"),
            }
            q_text = self._q.text().strip()
            if q_text:
                freq_text = self._q_freq.text().strip()
                if not freq_text:
                    raise ValueError(
                        tr("Q reference frequency is required when Q is set")
                    )
                kwargs["series_resistance_ohm"] = inductor_resistance_ohm_from_q(
                    self._value, float(q_text), parse_si(freq_text)
                )
            else:
                kwargs["series_resistance_ohm"] = parse_si(
                    self._r.text().strip() or "0"
                )
            return kwargs
        return {
            "esr_ohm": parse_si(self._esr.text().strip() or "0"),
            "esl_h": parse_si(self._esl.text().strip() or "0"),
        }

    @classmethod
    def ask(
        cls, parent: QWidget | None = None, **kwargs: object
    ) -> dict[str, float] | None:
        dialog = cls(parent, **kwargs)  # type: ignore[arg-type]
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.kwargs()
        return None


class MonteCarloDialog(QDialog):
    """Configure a Monte-Carlo tolerance run."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        initial: MonteCarloConfig | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Monte-Carlo tolerances"))
        base = initial or MonteCarloConfig()
        self._trials = QSpinBox()
        self._trials.setRange(1, 100_000)
        self._trials.setValue(base.n_trials)
        self._tol = EngineeringLineEdit()
        self._tol.setText(f"{base.tolerance_pct:g}")
        self._dist = QComboBox()
        for dist in ToleranceDistribution:
            self._dist.addItem(dist.value, dist)
        self._dist.setCurrentIndex(list(ToleranceDistribution).index(base.distribution))
        self._seed = QLineEdit()
        self._seed.setPlaceholderText(tr("optional integer"))
        if base.seed is not None:
            self._seed.setText(str(base.seed))
        form = QFormLayout(self)
        form.addRow(tr("Trials"), self._trials)
        form.addRow(tr("Tolerance ± (%)"), self._tol)
        form.addRow(tr("Distribution"), self._dist)
        form.addRow(tr("Seed"), self._seed)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def to_config(self) -> MonteCarloConfig:
        seed_text = self._seed.text().strip()
        return MonteCarloConfig(
            n_trials=int(self._trials.value()),
            tolerance_pct=parse_si(self._tol.text().strip() or "0"),
            distribution=ToleranceDistribution(self._dist.currentData()),
            seed=int(seed_text) if seed_text else None,
        )

    @classmethod
    def ask(
        cls,
        parent: QWidget | None = None,
        *,
        initial: MonteCarloConfig | None = None,
    ) -> MonteCarloConfig | None:
        dialog = cls(parent, initial=initial)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.to_config()
        return None


class OptimizeDialog(QDialog):
    """Configure a component-value optimization run."""

    _METHOD_LABELS: dict[OptimizeMethod, str] = {
        OptimizeMethod.LEAST_SQUARES: "Least squares (limit residuals)",
        OptimizeMethod.NELDER_MEAD: "Nelder–Mead (bounded)",
        OptimizeMethod.DIFFERENTIAL_EVOLUTION: "Differential evolution (global)",
        OptimizeMethod.DUAL_ANNEALING: "Dual annealing (global)",
    }

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        initial: OptimizationConfig | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Optimize to limits"))
        base = initial or OptimizationConfig()
        self._method = QComboBox()
        for method in OptimizeMethod:
            self._method.addItem(tr(self._METHOD_LABELS[method]), method)
        self._method.setCurrentIndex(list(OptimizeMethod).index(base.method))
        self._bound = EngineeringLineEdit()
        self._bound.setText(f"{base.bound_pct:g}")
        self._bound.setPlaceholderText(tr("e.g. 0.2 = ±20%"))
        self._max_iter = QSpinBox()
        self._max_iter.setRange(1, 100_000)
        self._max_iter.setValue(base.max_iter)
        self._seed = QLineEdit()
        self._seed.setPlaceholderText(tr("optional integer (global methods)"))
        if base.seed is not None:
            self._seed.setText(str(base.seed))
        form = QFormLayout(self)
        form.addRow(tr("Method"), self._method)
        form.addRow(tr("Bound (± fraction)"), self._bound)
        form.addRow(tr("Max iterations"), self._max_iter)
        form.addRow(tr("Seed"), self._seed)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def to_config(self) -> OptimizationConfig:
        seed_text = self._seed.text().strip()
        return OptimizationConfig(
            method=OptimizeMethod(self._method.currentData()),
            bound_pct=float(self._bound.text().strip() or "0.2"),
            max_iter=int(self._max_iter.value()),
            seed=int(seed_text) if seed_text else None,
        )

    @classmethod
    def ask(
        cls,
        parent: QWidget | None = None,
        *,
        initial: OptimizationConfig | None = None,
    ) -> OptimizationConfig | None:
        dialog = cls(parent, initial=initial)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.to_config()
        return None


class AttenuatorDialog(QDialog):
    """Symmetric T/Pi resistive attenuator designer (live values)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Attenuator pad"))
        self._db = EngineeringLineEdit()
        self._db.setText("6")
        self._z0 = EngineeringLineEdit()
        self._z0.setText("50")
        self._kind = QComboBox()
        for _kind, label in (
            (AttenuatorKind.TEE, tr("T pad")),
            (AttenuatorKind.PI, tr("Pi pad")),
        ):
            self._kind.addItem(label)
        self._series = QLabel("—")
        self._shunt = QLabel("—")
        form = QFormLayout(self)
        form.addRow(tr("Attenuation (dB)"), self._db)
        form.addRow(tr("System Z0 (Ohm)"), self._z0)
        form.addRow(tr("Topology"), self._kind)
        form.addRow(tr("Series R"), self._series)
        form.addRow(tr("Shunt R"), self._shunt)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._db.editingFinished.connect(self._recompute)
        self._z0.editingFinished.connect(self._recompute)
        self._kind.currentIndexChanged.connect(self._recompute)
        self._recompute()

    def _kind_value(self) -> AttenuatorKind:
        return (AttenuatorKind.TEE, AttenuatorKind.PI)[self._kind.currentIndex()]

    def _design(self) -> AttenuatorDesign:
        return design_attenuator(
            float(self._db.text().strip() or "0"),
            parse_si(self._z0.text().strip() or "50"),
            self._kind_value(),
        )

    def _recompute(self) -> None:
        try:
            design = self._design()
        except (AttenuatorError, ValueError):
            self._series.setText("—")
            self._shunt.setText("—")
            return
        self._series.setText(format_engineering(design.r_series_ohm, "Ohm", digits=4))
        self._shunt.setText(format_engineering(design.r_shunt_ohm, "Ohm", digits=4))

    @classmethod
    def ask(cls, parent: QWidget | None = None) -> AttenuatorDesign | None:
        dialog = cls(parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        try:
            return dialog._design()
        except (AttenuatorError, ValueError):
            return None


class MatchingDialog(QDialog):
    """Design an L/Pi/T matching network to a complex load (live values)."""

    _TOPOS: tuple[tuple[MatchingTopology, str], ...] = (
        (MatchingTopology.L, tr("L (2 elements)")),
        (MatchingTopology.PI, tr("Pi (3 elements)")),
        (MatchingTopology.T, tr("T (3 elements)")),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Matching network"))
        self._z0 = EngineeringLineEdit()
        self._z0.setText("50")
        self._rl = EngineeringLineEdit()
        self._rl.setText("25")
        self._xl = EngineeringLineEdit()
        self._xl.setText("0")
        self._f = EngineeringLineEdit()
        self._f.setText("7.1M")
        self._topo = QComboBox()
        for _t, label in self._TOPOS:
            self._topo.addItem(label)
        self._q = EngineeringLineEdit()
        self._q.setPlaceholderText(tr("auto (Pi/T only)"))
        self._model = QCheckBox(tr("Model the load (series X) at the output"))
        self._where = QComboBox()
        self._where.addItem(tr("Input"))
        self._where.addItem(tr("Output"))
        self._summary = QLabel("—")
        self._summary.setWordWrap(True)

        form = QFormLayout(self)
        form.addRow(tr("Source Z0 (Ohm)"), self._z0)
        form.addRow(tr("Load R (Ohm)"), self._rl)
        form.addRow(tr("Load X (Ohm, +ind/-cap)"), self._xl)
        form.addRow(tr("Frequency"), self._f)
        form.addRow(tr("Topology"), self._topo)
        form.addRow(tr("Loaded Q"), self._q)
        form.addRow(tr("Insert at"), self._where)
        form.addRow(self._model)
        form.addRow(tr("Elements"), self._summary)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        for field in (self._z0, self._rl, self._xl, self._f, self._q):
            field.editingFinished.connect(self._recompute)
        self._topo.currentIndexChanged.connect(self._recompute)
        self._recompute()

    def _topology(self) -> MatchingTopology:
        return self._TOPOS[self._topo.currentIndex()][0]

    def _design(self) -> MatchingDesign:
        q_text = self._q.text().strip()
        return design_matching(
            parse_si(self._z0.text().strip() or "50"),
            parse_si(self._rl.text().strip() or "1"),
            parse_si(self._xl.text().strip() or "0"),
            parse_si(self._f.text().strip() or "1M"),
            self._topology(),
            float(q_text) if q_text else None,
        )

    def _recompute(self) -> None:
        try:
            design = self._design()
        except (MatchingError, ValueError) as exc:
            self._summary.setText(f"— ({exc})")
            return
        parts = []
        for el in design.elements:
            unit = "H" if el.kind == "L" else "F"
            value_text = format_engineering(el.value, unit, digits=4)
            parts.append(f"{el.role.value} {el.kind}={value_text}")
        self._summary.setText(
            "  ".join(parts) + f"   (Zin={design.input_impedance_ohm.real:.4g}"
            f"{design.input_impedance_ohm.imag:+g}j)"
        )

    def result_tuple(self) -> tuple[MatchingDesign, bool, bool]:
        return (
            self._design(),
            self._model.isChecked(),
            self._where.currentIndex() == 0,
        )

    @classmethod
    def ask(
        cls, parent: QWidget | None = None
    ) -> tuple[MatchingDesign, bool, bool] | None:
        dialog = cls(parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        try:
            return dialog.result_tuple()
        except (MatchingError, ValueError):
            return None


class _ToroidPage(QWidget):
    """Toroid turn / wire / saturation calculator (live results)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cores: tuple[ToroidCore, ...] = list_cores()
        self._design_value: ToroidDesign | None = None

        self._core = QComboBox()
        for core in self._cores:
            self._core.addItem(
                f"{core.name} - mix {core.material} "
                f"({core.kind.replace('_', ' ')}, {core.color}), "
                f"AL {core.al_nh:g} nH/N^2"
            )
        self._l = EngineeringLineEdit()
        self._l.setText("1u")
        self._turns = QSpinBox()
        self._turns.setRange(0, 999)
        self._turns.setSpecialValueText(tr("auto (from L)"))
        self._current = EngineeringLineEdit()
        self._current.setText("0")
        self._turns_exact = QLabel("-")
        self._turns_used = QLabel("-")
        self._l_achieved = QLabel("-")
        self._wire = QLabel("-")
        self._length = QLabel("-")
        self._flux = QLabel("-")
        self._sat = QLabel("-")

        form = QFormLayout(self)
        form.addRow(tr("Core"), self._core)
        form.addRow(tr("Target L"), self._l)
        form.addRow(tr("Turns (0 = auto)"), self._turns)
        form.addRow(tr("Peak current (A)"), self._current)
        form.addRow(tr("Exact turns"), self._turns_exact)
        form.addRow(tr("Use turns"), self._turns_used)
        form.addRow(tr("Achieved L"), self._l_achieved)
        form.addRow(tr("Wire"), self._wire)
        form.addRow(tr("Wire length"), self._length)
        form.addRow(tr("Peak flux"), self._flux)
        form.addRow(tr("Saturation"), self._sat)

        self._core.currentIndexChanged.connect(self._recompute)
        self._l.editingFinished.connect(self._recompute)
        self._turns.valueChanged.connect(self._recompute)
        self._current.editingFinished.connect(self._recompute)
        self._recompute()

    def selected_core(self) -> ToroidCore:
        return self._cores[self._core.currentIndex()]

    def current_design(self) -> ToroidDesign | None:
        return self._design_value

    def set_target_inductance(self, value_h: float) -> None:
        self._l.setText(format_engineering(value_h, "H", digits=6))
        self._recompute()

    def current_a(self) -> float:
        try:
            return float(self._current.text().strip() or "0")
        except ValueError:
            return 0.0

    def _recompute(self) -> None:
        core = self.selected_core()
        turns = int(self._turns.value())
        try:
            current = float(self._current.text().strip() or "0")
            if turns > 0:
                design = design_toroid(core, turns=turns, current_a=current)
            else:
                target = parse_si(self._l.text().strip() or "0")
                design = design_toroid(core, inductance_h=target, current_a=current)
        except (ToroidError, ValueError):
            self._design_value = None
            for label in (
                self._turns_exact,
                self._turns_used,
                self._l_achieved,
                self._wire,
                self._length,
                self._flux,
                self._sat,
            ):
                label.setText("-")
            return

        self._design_value = design
        self._turns_exact.setText(f"{design.turns_exact:.2f}")
        self._turns_used.setText(str(design.turns))
        self._l_achieved.setText(format_engineering(design.inductance_h, "H", digits=6))
        if design.wire.fits:
            self._wire.setText(
                f"AWG {design.wire.awg} ({design.wire.diameter_mm:.3f} mm), "
                f"max {design.wire.max_diameter_mm:.3f} mm"
            )
        else:
            self._wire.setText(
                f"does not fit (max {design.wire.max_diameter_mm:.3f} mm)"
            )
        self._length.setText(f"{design.wire_length_m:.3f} m")
        if design.flux_density_t is None:
            self._flux.setText("-")
            self._sat.setText("-")
        else:
            self._flux.setText(f"{design.flux_density_t * 1000.0:.1f} mT")
            if design.saturation_ratio is None:
                self._sat.setText(tr("n/a (iron powder)"))
            else:
                flag = "  SATURATED" if design.saturated else ""
                self._sat.setText(f"B/Bsat = {design.saturation_ratio:.2f}{flag}")


class _AirCoilPage(QWidget):
    """Single-layer close-wound air-core solenoid (Wheeler)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._design_value: AirCoilDesign | None = None

        self._l = EngineeringLineEdit()
        self._l.setText("1u")
        self._diameter = EngineeringLineEdit()
        self._diameter.setText("10")
        self._wire_mode = QComboBox()
        self._wire_mode.addItems([tr("Wire AWG"), tr("Wire diameter (mm)")])
        self._awg = QSpinBox()
        self._awg.setRange(8, 40)
        self._awg.setValue(24)
        self._wire_mm = EngineeringLineEdit()
        self._wire_mm.setText(f"{awg_diameter_mm(24):.3f}")
        self._wire_stack = QStackedWidget()
        self._wire_stack.addWidget(self._awg)
        self._wire_stack.addWidget(self._wire_mm)
        self._enamel = EngineeringLineEdit()
        self._enamel.setPlaceholderText(tr("auto (grade 1); 0 = bare"))
        self._turns = QSpinBox()
        self._turns.setRange(0, 9999)
        self._turns.setSpecialValueText(tr("auto (from L)"))

        self._turns_exact = QLabel("-")
        self._turns_used = QLabel("-")
        self._below = QLabel("-")
        self._l_achieved = QLabel("-")
        self._length = QLabel("-")
        self._ratio = QLabel("-")
        self._wire_info = QLabel("-")
        self._wire = QLabel("-")
        self._resistance = QLabel("-")

        note = QLabel(
            "Perfect close winding, single layer. Wire defaults to typical "
            "grade-1 enamel (blank build) — use 0 for bare copper. Enamel "
            "lengthens the coil and lowers L. Self-capacitance / SRF and Q are "
            "not modelled; verify at the operating frequency."
        )
        note.setWordWrap(True)

        form = QFormLayout(self)
        form.addRow(tr("Target L"), self._l)
        form.addRow(tr("Diameter (mm)"), self._diameter)
        form.addRow(tr("Wire"), self._wire_mode)
        form.addRow("", self._wire_stack)
        form.addRow(tr("Enamel build (mm)"), self._enamel)
        form.addRow(tr("Turns (0 = auto)"), self._turns)
        form.addRow(tr("Exact turns"), self._turns_exact)
        form.addRow(tr("Use turns"), self._turns_used)
        form.addRow(tr("Closest below"), self._below)
        form.addRow(tr("Achieved L"), self._l_achieved)
        form.addRow(tr("Coil length"), self._length)
        form.addRow(tr("Length / diameter"), self._ratio)
        form.addRow(tr("Wire size"), self._wire_info)
        form.addRow(tr("Wire length"), self._wire)
        form.addRow(tr("DC resistance"), self._resistance)
        form.addRow(note)

        self._l.editingFinished.connect(self._recompute)
        self._diameter.editingFinished.connect(self._recompute)
        self._wire_mode.currentIndexChanged.connect(self._on_wire_mode)
        self._awg.valueChanged.connect(self._recompute)
        self._wire_mm.editingFinished.connect(self._recompute)
        self._enamel.editingFinished.connect(self._recompute)
        self._turns.valueChanged.connect(self._recompute)
        self._recompute()

    def current_design(self) -> AirCoilDesign | None:
        return self._design_value

    def set_target_inductance(self, value_h: float) -> None:
        self._l.setText(format_engineering(value_h, "H", digits=6))
        self._recompute()

    def _on_wire_mode(self, index: int) -> None:
        self._wire_stack.setCurrentIndex(index)
        if index == 1:
            self._wire_mm.setText(f"{awg_diameter_mm(int(self._awg.value())):.3f}")
        else:
            try:
                diameter = float(self._wire_mm.text().strip())
            except ValueError:
                diameter = 0.0
            if diameter > 0.0:
                self._awg.setValue(awg_for_diameter_mm(diameter))
        self._recompute()

    def _recompute(self) -> None:
        turns = int(self._turns.value())
        use_mm = self._wire_mode.currentIndex() == 1
        try:
            diameter = float(self._diameter.text().strip() or "0")
            awg = None if use_mm else int(self._awg.value())
            wire_mm = float(self._wire_mm.text().strip() or "0") if use_mm else None
            enamel_text = self._enamel.text().strip()
            enamel = float(enamel_text) if enamel_text else None
            if turns > 0:
                design = design_air_coil(
                    diameter_mm=diameter,
                    awg=awg,
                    wire_diameter_mm=wire_mm,
                    enamel_build_mm=enamel,
                    turns=turns,
                )
            else:
                target = parse_si(self._l.text().strip() or "0")
                design = design_air_coil(
                    diameter_mm=diameter,
                    awg=awg,
                    wire_diameter_mm=wire_mm,
                    enamel_build_mm=enamel,
                    inductance_h=target,
                )
        except (AirCoilError, ValueError):
            self._design_value = None
            for label in (
                self._turns_exact,
                self._turns_used,
                self._below,
                self._l_achieved,
                self._length,
                self._ratio,
                self._wire_info,
                self._wire,
                self._resistance,
            ):
                label.setText("-")
            return

        self._design_value = design
        self._turns_exact.setText(f"{design.turns_exact:.2f}")
        self._turns_used.setText(str(design.turns))
        if design.turns_below < design.turns:
            self._below.setText(
                f"{design.turns_below} -> "
                f"{format_engineering(design.inductance_below_h, 'H', digits=6)}"
            )
        else:
            self._below.setText("-")
        self._l_achieved.setText(format_engineering(design.inductance_h, "H", digits=6))
        self._length.setText(f"{design.length_mm:.2f} mm")
        short = " (short coil)" if design.short_coil else ""
        self._ratio.setText(f"{design.length_to_diameter:.2f}{short}")
        if design.enamel_build_mm > 0.0:
            self._wire_info.setText(
                f"{design.wire_diameter_mm:.3f} mm bare / "
                f"{design.overall_diameter_mm:.3f} mm enamelled "
                f"(AWG {design.awg} eq.)"
            )
        else:
            self._wire_info.setText(
                f"{design.wire_diameter_mm:.3f} mm bare (AWG {design.awg} eq.)"
            )
        self._wire.setText(f"{design.wire_length_m:.3f} m")
        self._resistance.setText(f"{design.resistance_ohm:.3f} Ohm")


class CoilCalculatorDialog(QDialog):
    """Coil calculators: toroid (AL) and single-layer air-core (Wheeler)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        element: IdealInductor | NonIdealInductor | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Coil calculator"))
        self.toroid = _ToroidPage(self)
        self.air_core = _AirCoilPage(self)
        self._element = element
        self._realized: NonIdealInductor | None = None
        if element is not None:
            self.toroid.set_target_inductance(element.value_h)
            self.air_core.set_target_inductance(element.value_h)
        self._tabs = QTabWidget(self)
        self._tabs.addTab(self.toroid, tr("Toroid"))
        self._tabs.addTab(self.air_core, tr("Air-core"))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        if element is not None:
            apply = buttons.addButton(
                tr("Apply to selected inductor"),
                QDialogButtonBox.ButtonRole.ActionRole,
            )
            apply.clicked.connect(self._on_apply)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(buttons)

    def _on_apply(self) -> None:
        element = self._element
        if element is None:
            return
        if self._tabs.currentIndex() == 0:
            toroid = self.toroid.current_design()
            if toroid is None:
                return
            try:
                realization = realize_from_toroid_design(
                    element, toroid, current_a=self.toroid.current_a()
                )
            except (InductorRealizationError, ValueError) as exc:
                QMessageBox.warning(self, tr("Realize inductor"), str(exc))
                return
        else:
            air = self.air_core.current_design()
            if air is None:
                return
            try:
                realization = realize_from_air_design(element, air)
            except (InductorRealizationError, ValueError) as exc:
                QMessageBox.warning(self, tr("Realize inductor"), str(exc))
                return
        self._realized = realization.element
        if realization.notes:
            QMessageBox.information(
                self, tr("Winding notes"), "\n".join(realization.notes)
            )
        self.accept()

    def realized_element(self) -> NonIdealInductor | None:
        """The realized inductor, when the user applied a winding."""
        return self._realized


class SensitivityDialog(QDialog):
    """Show ranked component sensitivities and optionally tune the selection."""

    def __init__(
        self, report: SensitivityReport, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Component sensitivity"))
        self._rows = report.rows
        self._action: tuple[str, int] | None = None

        self._table = QTableWidget(len(self._rows), 6, self)
        self._table.setHorizontalHeaderLabels(
            [
                tr("Ref"),
                tr("Value"),
                tr("d|S21| dB/%"),
                tr("RMS dB/%"),
                tr("Worst f"),
                tr("Suggestion"),
            ]
        )
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        for index, row in enumerate(self._rows):
            value = (
                format_engineering(row.value, row.unit, digits=6)
                if row.unit
                else f"{row.value:.6g}"
            )
            worst = format_engineering(row.worst_frequency_hz, "Hz", digits=6)
            suggestion = (
                tr("increase")
                if row.direction > 0
                else tr("decrease")
                if row.direction < 0
                else "—"
            )
            cells = [
                row.ref,
                value,
                f"{row.max_abs_db_per_pct:.4f}",
                f"{row.rms_db_per_pct:.4f}",
                worst,
                suggestion,
            ]
            for column, text in enumerate(cells):
                self._table.setItem(index, column, QTableWidgetItem(text))
        if self._rows:
            self._table.selectRow(0)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        tune = buttons.addButton(
            "Tune selected", QDialogButtonBox.ButtonRole.ActionRole
        )
        tune.clicked.connect(self._on_tune)
        buttons.rejected.connect(self.reject)

        note = QLabel(
            tr(
                "{count} components · step {step:g}% · backend {backend}. "
                "A tuning suggestion requires limits/objectives.",
                count=len(self._rows),
                step=report.relative_step_pct,
                backend=report.backend,
            )
        )
        note.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def _on_tune(self) -> None:
        index = self._table.currentRow()
        if 0 <= index < len(self._rows):
            row = self._rows[index]
            self._action = (row.ref, row.direction if row.direction else 1)
            self.accept()

    def take_action(self) -> tuple[str, int] | None:
        """Element ref + direction to nudge, when the user chose to tune."""
        return self._action


class BuildSheetDialog(QDialog):
    """Options for a BOM / build-sheet export."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Build sheet options"))
        self._series = QComboBox()
        self._series.addItem(tr("No E-series snap"), None)
        for series in ESeries:
            self._series.addItem(series.value, series)
        self._group = QCheckBox(tr("Group identical parts (combine refs and quantity)"))
        form = QFormLayout(self)
        form.addRow(tr("E-series"), self._series)
        form.addRow(self._group)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def selection(self) -> tuple[ESeries | None, bool]:
        data = self._series.currentData()
        series = ESeries(str(data)) if data is not None else None
        return series, self._group.isChecked()

    @classmethod
    def ask(cls, parent: QWidget | None = None) -> tuple[ESeries | None, bool] | None:
        dialog = cls(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selection()
        return None


class DesignSweepDialog(QDialog):
    """Configure a design parameter sweep."""

    _AXIS_LABELS: dict[SweepAxis, str] = {
        SweepAxis.ORDER: "Order",
        SweepAxis.FAMILY: "Family",
        SweepAxis.CUTOFF: "Cutoff (Hz)",
        SweepAxis.CENTER: "Center (Hz)",
        SweepAxis.BANDWIDTH: "Bandwidth (Hz)",
        SweepAxis.RIPPLE: "Passband ripple (dB)",
        SweepAxis.STOPBAND_ATT: "Stopband attenuation (dB)",
        SweepAxis.M_FACTOR: "m parameter",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Parameter sweep"))
        self._axis = QComboBox()
        for axis in SweepAxis:
            self._axis.addItem(tr(self._AXIS_LABELS.get(axis, axis.value)), axis.value)
        self._values = QLineEdit()
        self._values.setPlaceholderText(tr("e.g. 3,5,7,9"))
        self._points = QSpinBox()
        self._points.setRange(64, 8192)
        self._points.setValue(512)
        form = QFormLayout(self)
        form.addRow(tr("Axis"), self._axis)
        form.addRow(tr("Values"), self._values)
        form.addRow(tr("Points"), self._points)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def selection(self) -> tuple[SweepAxis, str, int]:
        axis = SweepAxis(str(self._axis.currentData()))
        return axis, self._values.text().strip(), int(self._points.value())

    @classmethod
    def ask(cls, parent: QWidget | None = None) -> tuple[SweepAxis, str, int] | None:
        dialog = cls(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selection()
        return None


class DesignSweepResultDialog(QDialog):
    """Show sweep rows and let the user load one into the design."""

    def __init__(
        self, rows: list[DesignSweepRow], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Design sweep"))
        self._rows = tuple(rows)
        self._spec: FilterSpec | None = None

        headers = [
            tr("Value"),
            "OK",
            "N",
            tr("Ripple dB"),
            tr("Stop dB"),
            tr("RL dB"),
            tr("GD ps"),
            tr("Note / error"),
        ]
        self._table = QTableWidget(len(self._rows), len(headers), self)
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        first_ok = -1
        for index, row in enumerate(self._rows):
            metrics = row.metrics
            if row.ok and first_ok < 0:
                first_ok = index
            cells = [
                str(row.value),
                tr("yes") if row.ok else tr("no"),
                str(row.n_components) if row.ok else "",
                (
                    ""
                    if metrics is None or metrics.passband_ripple_db is None
                    else f"{metrics.passband_ripple_db:.3f}"
                ),
                (
                    ""
                    if metrics is None or metrics.stopband_attenuation_db is None
                    else f"{metrics.stopband_attenuation_db:.1f}"
                ),
                (
                    ""
                    if metrics is None or metrics.min_return_loss_db is None
                    else f"{metrics.min_return_loss_db:.1f}"
                ),
                (
                    ""
                    if metrics is None or metrics.group_delay_ripple_s is None
                    else f"{metrics.group_delay_ripple_s * 1e12:.1f}"
                ),
                row.note or row.error or "",
            ]
            for column, text in enumerate(cells):
                self._table.setItem(index, column, QTableWidgetItem(text))
        if first_ok >= 0:
            self._table.selectRow(first_ok)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        apply = buttons.addButton(
            tr("Apply selected"), QDialogButtonBox.ButtonRole.ActionRole
        )
        apply.clicked.connect(self._on_apply)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addWidget(buttons)

    def _on_apply(self) -> None:
        index = self._table.currentRow()
        if 0 <= index < len(self._rows):
            row = self._rows[index]
            if row.ok and row.spec is not None:
                self._spec = row.spec
                self.accept()

    def take_spec(self) -> FilterSpec | None:
        """Specification of the applied row, if the user chose one."""
        return self._spec


class TransformerDialog(QDialog):
    """Unified transformer / balun / unun designer and boundary inserter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transformer / balun / unun")
        self.setMinimumWidth(820)
        self._cores = list_cores()
        self._design_value: BalunDesign | None = None
        self._options: list[BalunDesign] = []
        self._remove_requested = False

        self._core = QComboBox()
        for core in self._cores:
            self._core.addItem(
                f"{core.name} - mix {core.material}, AL {core.al_nh:g} nH/N^2"
            )
        for index, core in enumerate(self._cores):
            if core.name == "FT140-43":
                self._core.setCurrentIndex(index)
                break
        self._kind = QComboBox()
        self._kind.addItems([k.value for k in BalunKind])
        self._kind.setCurrentText(BalunKind.UNUN.value)
        self._topology = QComboBox()
        self._topology.addItems([t.value for t in TransformerTopology])
        self._z_low = EngineeringLineEdit()
        self._z_low.setText("50")
        self._z_high = EngineeringLineEdit()
        self._z_high.setText("200")
        self._frequency = EngineeringLineEdit()
        self._frequency.setText("3.5M")
        self._frequency_max = EngineeringLineEdit()
        self._frequency_max.setText("30M")
        self._power = EngineeringLineEdit()
        self._power.setText("10")

        self._options_table = QTableWidget(0, 9)
        self._options_table.setHorizontalHeaderLabels(
            [
                "Option",
                "Total",
                "Lm",
                "Lk",
                "X/Z",
                "Bsat/B",
                "DCR low/high",
                "Fit",
                "Flags",
            ]
        )
        self._options_table.verticalHeader().setVisible(False)
        self._options_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._options_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._options_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        options_header = self._options_table.horizontalHeader()
        for column in range(8):
            options_header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        options_header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self._options_table.setColumnWidth(8, 300)
        self._options_table.setWordWrap(True)
        self._options_table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._options_table.setMaximumHeight(180)
        self._flags_legend = QLabel(
            "LF = magnetizing reactance below target; SAT = Bsat/B below 3; "
            "FIT = no single-layer fit; HF = many turns / leakage at high HF; "
            "THERMAL = estimated hot temperature above 100 °C (or above Tc)."
        )
        self._flags_legend.setWordWrap(True)

        self._turns = QLabel("-")
        self._inductances = QLabel("-")
        self._model = QLabel("-")
        self._vi = QLabel("-")
        self._flux = QLabel("-")
        self._wire = QLabel("-")
        self._notes = QLabel("-")
        self._notes.setWordWrap(True)

        self._coupling = EngineeringLineEdit()
        self._coupling.setText("98")
        self._tan_delta = EngineeringLineEdit()
        self._tan_delta.setText("2")
        self._winding_c = EngineeringLineEdit()
        self._winding_c.setText("0")
        self._line_z0 = EngineeringLineEdit()
        self._line_z0.setText("")
        self._line_length = EngineeringLineEdit()
        self._line_length.setText("")
        self._vf = EngineeringLineEdit()
        self._vf.setText("0.7")
        self._line_loss = EngineeringLineEdit()
        self._line_loss.setText("0")

        design_tab = QWidget()
        design_form = QFormLayout(design_tab)
        design_form.addRow("Core", self._core)
        design_form.addRow("Kind", self._kind)
        design_form.addRow("Topology", self._topology)
        design_form.addRow("Low-side Z (Ohm)", self._z_low)
        design_form.addRow("High-side Z (Ohm)", self._z_high)
        design_form.addRow("Lowest frequency", self._frequency)
        design_form.addRow("Highest frequency", self._frequency_max)
        design_form.addRow("Power (W)", self._power)
        design_form.addRow("Winding options", self._options_table)
        design_form.addRow("Flags legend", self._flags_legend)
        design_form.addRow("Turns", self._turns)
        design_form.addRow("Inductances", self._inductances)
        design_form.addRow("V / I", self._vi)
        design_form.addRow("Peak flux", self._flux)
        design_form.addRow("Wire", self._wire)

        model_tab = QWidget()
        model_form = QFormLayout(model_tab)
        model_form.addRow("Model", self._model)
        model_form.addRow("Coupling (%)", self._coupling)
        model_form.addRow("Core tan delta (%)", self._tan_delta)
        model_form.addRow("Winding C (pF)", self._winding_c)
        model_form.addRow("TLT line Z0 (Ohm)", self._line_z0)
        model_form.addRow("TLT length (m, blank=auto)", self._line_length)
        model_form.addRow("TLT velocity factor", self._vf)
        model_form.addRow("TLT loss (dB/m)", self._line_loss)
        self._cm_table = QTableWidget(0, 3)
        self._cm_table.setHorizontalHeaderLabels(
            [tr("Frequency"), "|Zcm| (Ohm)", tr("Attenuation (dB)")]
        )
        self._cm_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._cm_table.setMaximumHeight(130)
        self._cm_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._mm_table = QTableWidget(0, 3)
        self._mm_table.setHorizontalHeaderLabels(
            [tr("Frequency"), "Sdd21 (dB)", "|Scc|"]
        )
        self._mm_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._mm_table.setMaximumHeight(130)
        self._mm_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._confidence = ConfidenceBadge("thermal")
        model_form.addRow("Mixed-mode (3-port)", self._mm_table)
        model_form.addRow("Common-mode sweep", self._cm_table)
        model_form.addRow("Confidence", self._confidence)
        model_form.addRow("Notes", self._notes)

        tabs = QTabWidget()
        tabs.addTab(design_tab, "Design")
        tabs.addTab(model_tab, "Model")
        self._tabs = tabs

        buttons = QDialogButtonBox()
        self._apply_button = buttons.addButton(
            "Apply as output balun", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._remove_button = buttons.addButton(
            "Remove", QDialogButtonBox.ButtonRole.ActionRole
        )
        self._export_tlt_button = buttons.addButton(
            tr("Export TLT SPICE…"), QDialogButtonBox.ButtonRole.ActionRole
        )
        close = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        self._apply_button.clicked.connect(self.accept)
        self._remove_button.clicked.connect(self._remove)
        self._export_tlt_button.clicked.connect(self._export_tlt_spice)
        close.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

        self._core.currentIndexChanged.connect(self._recompute)
        self._kind.currentIndexChanged.connect(self._recompute)
        self._topology.currentIndexChanged.connect(self._recompute)
        for field in (
            self._z_low,
            self._z_high,
            self._frequency,
            self._frequency_max,
            self._power,
            self._coupling,
            self._tan_delta,
            self._winding_c,
            self._line_z0,
            self._line_length,
            self._vf,
            self._line_loss,
        ):
            field.editingFinished.connect(self._recompute)
        self._options_table.itemSelectionChanged.connect(self._on_option_selected)
        self._recompute()

    def selected_core(self) -> ToroidCore:
        return self._cores[self._core.currentIndex()]

    def current_design(self) -> BalunDesign | None:
        return self._design_value

    def balun_spec(self) -> BalunSpec | None:
        return None if self._design_value is None else self._design_value.to_spec()

    def remove_requested(self) -> bool:
        return self._remove_requested

    def _remove(self) -> None:
        self._remove_requested = True
        self.accept()

    def _export_tlt_spice(self) -> None:
        balun = self.balun_spec()
        if balun is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Export TLT SPICE"),
            "",
            tr("SPICE netlist (*.cir *.net);;All files (*)"),
        )
        if not path:
            return
        try:
            f_min = parse_si(self._frequency.text().strip() or "0")
            f_max = parse_si(self._frequency_max.text().strip() or "0")
            if f_min <= 0.0 or f_max <= f_min:
                f_max = f_min * 1.1
            write_tlt_spice_netlist(
                balun,
                path,
                ac=SweepConfig(
                    f_start_hz=f_min,
                    f_stop_hz=f_max,
                    n_points=101,
                    spacing=SweepSpacing.LOGARITHMIC,
                ),
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr("Export TLT SPICE"), str(exc))

    def _recompute(self) -> None:
        try:
            options = design_balun_options(
                self.selected_core(),
                kind=BalunKind(self._kind.currentText()),
                z_unbalanced_ohm=parse_si(self._z_low.text().strip() or "0"),
                z_balanced_ohm=parse_si(self._z_high.text().strip() or "0"),
                f_min_hz=parse_si(self._frequency.text().strip() or "0"),
                f_max_hz=parse_si(self._frequency_max.text().strip() or "0"),
                power_w=float(self._power.text().strip() or "0"),
                topology=TransformerTopology(self._topology.currentText()),
                coupling=float(self._coupling.text().strip() or "0") / 100.0,
                tan_delta=float(self._tan_delta.text().strip() or "0") / 100.0,
                winding_capacitance_f=parse_si(self._winding_c.text().strip() or "0")
                * 1e-12,
                line_z0_ohm=(
                    parse_si(self._line_z0.text().strip())
                    if self._line_z0.text().strip()
                    else None
                ),
                line_length_m=(
                    parse_si(self._line_length.text().strip())
                    if self._line_length.text().strip()
                    else None
                ),
                velocity_factor=float(self._vf.text().strip() or "0"),
                line_loss_db_per_m=float(self._line_loss.text().strip() or "0"),
            )
        except (BalunError, ValueError):
            self._options = []
            self._design_value = None
            self._options_table.setRowCount(0)
            self._export_tlt_button.setEnabled(False)
            for label in (
                self._turns,
                self._inductances,
                self._model,
                self._vi,
                self._flux,
                self._wire,
                self._notes,
            ):
                label.setText("-")
            return
        self._options = options
        self._populate_options()
        recommended = next(
            (
                index
                for index, design in enumerate(options)
                if design.reactance_ratio >= 4.0
            ),
            len(options) // 2,
        )
        self._options_table.blockSignals(True)
        self._options_table.selectRow(recommended)
        self._options_table.blockSignals(False)
        self._show_design(options[recommended])

    def _populate_options(self) -> None:
        self._options_table.setRowCount(len(self._options))
        for row, design in enumerate(self._options):
            dcr = (
                "-"
                if design.dcr_primary_ohm is None or design.dcr_secondary_ohm is None
                else f"{design.dcr_primary_ohm:.3g}/{design.dcr_secondary_ohm:.3g}"
            )
            values = (
                f"{design.n_primary}:{design.n_secondary}",
                str(design.total_turns),
                format_engineering(design.magnetizing_inductance_h, "H", digits=3),
                format_engineering(design.leakage_inductance_h, "H", digits=3),
                f"{design.reactance_ratio:.2f}",
                (
                    "-"
                    if design.bsat_margin is None
                    else f"{(design.bsat_margin_hot or design.bsat_margin):.1f}"
                ),
                dcr,
                str(design.fit.awg) if design.fit.awg is not None else "n/f",
                design.status_text,
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(f"{design.status_text}\n" + "; ".join(design.notes))
                self._options_table.setItem(row, col, item)
        self._options_table.resizeRowsToContents()

    def _on_option_selected(self) -> None:
        rows = self._options_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if 0 <= row < len(self._options):
            self._show_design(self._options[row])

    def _show_design(self, design: BalunDesign) -> None:
        self._design_value = design
        spec = design.to_spec()
        self._turns.setText(
            f"{spec.ratio_text} "
            f"(total {design.total_turns}, X/Z {design.reactance_ratio:.2f})"
        )
        lm = format_engineering(design.magnetizing_inductance_h, "H", digits=4)
        lk = format_engineering(design.leakage_inductance_h, "H", digits=4)
        dcr = ""
        if design.dcr_primary_ohm is not None and design.dcr_secondary_ohm is not None:
            dcr = (
                f"; DCR low/high {design.dcr_primary_ohm:.3g}/"
                f"{design.dcr_secondary_ohm:.3g} Ohm"
            )
        self._inductances.setText(f"Lm {lm}, Lk {lk}{dcr}")
        model = f"{design.kind.value}, Zline {design.z0_line_ohm:.3g} Ohm"
        line_count = spec.guanella_line_count
        if line_count is not None:
            model += f", {line_count}-line Guanella"
        if design.kind.value == "ruthroff" and (
            abs(spec.turns_ratio - 0.5) <= 1e-6 or abs(spec.turns_ratio - 2.0) <= 1e-6
        ):
            model += ", Ruthroff 1:4 distributed"
        if design.length_m:
            model += f", l {design.length_m * 1000.0:.1f} mm"
        if design.common_mode_impedance_ohm > 0.0:
            model += f", Zcm(fmin) {design.common_mode_impedance_ohm:.3g} Ohm"
            cm_db = design.common_mode_attenuation_db
            if cm_db is not None:
                model += f", CM atten {cm_db:.1f} dB"
        if design.total_loss_w is not None:
            model += f", loss {design.total_loss_w:.2f} W, hot {design.thermal_text}"
        self._model.setText(model)
        self._vi.setText(
            f"{design.v_unbalanced_rms:.3g}/{design.v_balanced_rms:.3g} Vrms, "
            f"{design.i_unbalanced_rms_a:.3g}/{design.i_balanced_rms_a:.3g} Arms"
        )
        if design.b_peak_t is None:
            self._flux.setText("-")
        else:
            text = f"{design.b_peak_t * 1000.0:.1f} mT"
            margin = design.bsat_margin_hot or design.bsat_margin
            if margin is not None:
                text += f" (Bsat/B {margin:.2f} hot)"
            self._flux.setText(text)
        self._wire.setText(
            f"primary AWG {design.awg_primary}, secondary AWG "
            f"{design.awg_secondary}; fit AWG {design.fit.awg}"
        )
        self._notes.setText("; ".join(design.notes) if design.notes else "-")
        tlt_export = False
        if spec.guanella_line_count is not None:
            tlt_export = True
        elif design.kind.value == "ruthroff" and abs(spec.turns_ratio - 0.5) <= 1e-6:
            tlt_export = True
        self._export_tlt_button.setEnabled(tlt_export)
        self._show_common_mode(design)
        self._show_mixed_mode(design)

    def _show_mixed_mode(self, design: BalunDesign) -> None:
        self._mm_table.setRowCount(0)
        try:
            f_min = parse_si(self._frequency.text().strip() or "0")
            f_max = parse_si(self._frequency_max.text().strip() or "0")
            if f_min <= 0.0 or f_max <= f_min:
                return
            freqs = [f_min * (f_max / f_min) ** (index / 4.0) for index in range(5)]
            report = mixed_mode_balun(design.to_spec(), freqs)
        except (MixedModeError, ValueError):
            return
        for index, freq in enumerate(report.frequency_hz):
            row = self._mm_table.rowCount()
            self._mm_table.insertRow(row)
            self._mm_table.setItem(
                row,
                0,
                QTableWidgetItem(format_engineering(float(freq), "Hz", digits=5)),
            )
            sdd21 = report.sdd[index, 1, 0]
            self._mm_table.setItem(
                row,
                1,
                QTableWidgetItem(f"{20.0 * math.log10(max(abs(sdd21), 1e-15)):.2f}"),
            )
            self._mm_table.setItem(
                row, 2, QTableWidgetItem(f"{abs(report.scc[index]):.4f}")
            )

    def _show_common_mode(self, design: BalunDesign) -> None:
        self._cm_table.setRowCount(0)
        if design.kind.value != "choke":
            return
        try:
            f_min = parse_si(self._frequency.text().strip() or "0")
            f_max = parse_si(self._frequency_max.text().strip() or "0")
            if f_min <= 0.0 or f_max <= f_min:
                return
            freqs = [f_min * (f_max / f_min) ** (index / 4.0) for index in range(5)]
            report = common_mode_sweep(
                design.to_spec(), freqs, z0_ohm=design.z_unbalanced_ohm
            )
        except (CommonModeError, ValueError):
            return
        for point in report.points:
            row = self._cm_table.rowCount()
            self._cm_table.insertRow(row)
            self._cm_table.setItem(
                row,
                0,
                QTableWidgetItem(
                    format_engineering(point.frequency_hz, "Hz", digits=5)
                ),
            )
            self._cm_table.setItem(
                row, 1, QTableWidgetItem(f"{abs(point.impedance_ohm):.4g}")
            )
            self._cm_table.setItem(
                row, 2, QTableWidgetItem(f"{point.attenuation_db:.2f}")
            )


class MicrostripDialog(QDialog):
    """Microstrip line calculator (Hammerstad-Jensen, first-order losses)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Microstrip line")
        self._substrates = list_substrates()
        self._line_value: MicrostripLine | None = None

        self._substrate = QComboBox()
        for substrate in self._substrates:
            self._substrate.addItem(
                f"{substrate.name} - er {substrate.er:g}, "
                f"h {substrate.h_mm:g} mm, tanD {substrate.tan_delta:g}"
            )
        self._z0 = EngineeringLineEdit()
        self._z0.setText("50")
        self._frequency = EngineeringLineEdit()
        self._frequency.setText("1G")
        self._length = EngineeringLineEdit()
        self._length.setText("0")

        self._width = QLabel("-")
        self._eeff = QLabel("-")
        self._lambda = QLabel("-")
        self._loss = QLabel("-")
        self._length_result = QLabel("-")
        self._confidence = ConfidenceBadge("microstrip")

        form = QFormLayout(self)
        form.addRow("Confidence", self._confidence)
        form.addRow("Substrate", self._substrate)
        form.addRow("Z0 (Ohm)", self._z0)
        form.addRow("Frequency", self._frequency)
        form.addRow("Length (m, optional)", self._length)
        form.addRow("Width", self._width)
        form.addRow("Effective er", self._eeff)
        form.addRow("Wavelength", self._lambda)
        form.addRow("Loss", self._loss)
        form.addRow("Length result", self._length_result)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        form.addRow(buttons)

        self._substrate.currentIndexChanged.connect(self._recompute)
        for field in (self._z0, self._frequency, self._length):
            field.editingFinished.connect(self._recompute)
        self._recompute()

    def selected_substrate(self) -> Substrate:
        return self._substrates[self._substrate.currentIndex()]

    def current_line(self) -> MicrostripLine | None:
        return self._line_value

    def _recompute(self) -> None:
        try:
            line = design_microstrip(
                parse_si(self._z0.text().strip() or "0"),
                self.selected_substrate(),
                parse_si(self._frequency.text().strip() or "0"),
                length_m=parse_si(self._length.text().strip() or "0"),
            )
        except (MicrostripError, ValueError):
            self._line_value = None
            for label in (
                self._width,
                self._eeff,
                self._lambda,
                self._loss,
                self._length_result,
            ):
                label.setText("-")
            return
        self._line_value = line
        self._width.setText(f"{line.width_mm:.3f} mm")
        self._eeff.setText(f"{line.eeff:.4f}")
        self._lambda.setText(
            f"{line.wavelength_m * 1000.0:.2f} mm "
            f"(lambda/4 {line.quarter_wave_m * 1000.0:.2f} mm)"
        )
        self._loss.setText(
            f"{line.loss_db_per_m:.3f} dB/m "
            f"(cond {line.conductor_loss_db_per_m:.3f}, "
            f"diel {line.dielectric_loss_db_per_m:.3f})"
        )
        if line.length_m:
            self._length_result.setText(
                f"{line.electrical_length_deg():.1f} deg, loss {line.loss_db():.4f} dB"
            )
        else:
            self._length_result.setText("-")


class CoaxStubDialog(QDialog):
    """Shunt coaxial stub notch calculator (lambda/4 open or lambda/2 short)."""

    _KINDS: tuple[tuple[CoaxStubKind, str], ...] = (
        (CoaxStubKind.OPEN_QUARTER, tr("Open λ/4")),
        (CoaxStubKind.SHORT_HALF, tr("Shorted λ/2")),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Coaxial stub notch"))
        self._design: CoaxStubDesign | None = None
        self._cables: tuple[CoaxCable | None, ...] = (None, *COAX_CABLES)
        self._cable = QComboBox()
        self._cable.addItem(tr("Custom"))
        for cable in COAX_CABLES:
            self._cable.addItem(cable.name)
        self._z0 = EngineeringLineEdit()
        self._z0.setText("50")
        self._frequency = EngineeringLineEdit()
        self._frequency.setText("146M")
        self._vf = EngineeringLineEdit()
        self._vf.setText("0.66")
        self._kind = QComboBox()
        for _kind, label in self._KINDS:
            self._kind.addItem(label)
        self._loss = EngineeringLineEdit()
        self._loss.setText("0")
        self._line_z0 = EngineeringLineEdit()
        self._line_z0.setText("50")
        self._length = QLabel("-")
        self._wavelength = QLabel("-")
        self._loss_result = QLabel("-")
        self._depth = QLabel("-")
        self._bandwidth = QLabel("-")
        self._loaded_q = QLabel("-")
        self._response: CoaxStubResponse | None = None
        self._plot = freq_plot(tr("Notch response"))
        self._plot.setLogMode(x=True, y=False)
        self._plot.setLabel("left", tr("Magnitude"), units="dB")
        self._plot.addLegend()
        self._plot.setMinimumHeight(260)
        self._curve_s21 = self._plot.plot(
            pen=pg.mkPen("#1f77b4", width=2), name="S21"
        )
        self._curve_s11 = self._plot.plot(
            pen=pg.mkPen("#d62728", width=2), name="S11"
        )
        self._export_status = QLabel("")
        self._note = QLabel(
            tr(
                "Shunt stub across the feedline. Ideal narrowband notch; "
                "verify connectors, cable loss and the real velocity factor."
            )
        )
        self._note.setWordWrap(True)
        form = QFormLayout(self)
        form.addRow(tr("Cable preset"), self._cable)
        form.addRow(tr("Cable Z0 (Ohm)"), self._z0)
        form.addRow(tr("Notch frequency"), self._frequency)
        form.addRow(tr("Velocity factor"), self._vf)
        form.addRow(tr("Stub type"), self._kind)
        form.addRow(tr("Cable loss (dB/m)"), self._loss)
        form.addRow(tr("Through-line Z0 (Ohm)"), self._line_z0)
        form.addRow(tr("Physical length"), self._length)
        form.addRow(tr("Guided wavelength"), self._wavelength)
        form.addRow(tr("Estimated loss"), self._loss_result)
        form.addRow(tr("Notch depth"), self._depth)
        form.addRow(tr("−3 dB bandwidth"), self._bandwidth)
        form.addRow(tr("Loaded Q"), self._loaded_q)
        form.addRow(self._note)
        form.addRow(self._plot)
        form.addRow(self._export_status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._export_button = buttons.addButton(
            tr("Export coax CSV…"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(self._export_csv)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        form.addRow(buttons)
        for field in (self._z0, self._frequency, self._vf, self._loss, self._line_z0):
            field.editingFinished.connect(self._recompute)
        self._kind.currentIndexChanged.connect(self._recompute)
        self._cable.currentIndexChanged.connect(self._on_cable_changed)
        self._on_cable_changed()
        self._recompute()

    def current_design(self) -> CoaxStubDesign | None:
        return self._design

    def _export_csv(self) -> None:
        if self._design is None or self._response is None:
            return
        path, _selected = QFileDialog.getSaveFileName(
            self,
            tr("Export coax notch CSV"),
            "coax_notch.csv",
            "CSV (*.csv);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            Path(path).write_text(
                coax_notch_csv(self._design, self._response), encoding="utf-8"
            )
        except OSError as exc:
            QMessageBox.critical(self, tr("Export failed"), str(exc))
            return
        self._export_status.setText(tr("Wrote {path}", path=path))

    def _selected_cable(self) -> CoaxCable | None:
        return self._cables[self._cable.currentIndex()]

    def _on_cable_changed(self) -> None:
        cable = self._selected_cable()
        custom = cable is None
        for field in (self._z0, self._vf, self._loss):
            field.setEnabled(custom)
        if cable is not None:
            self._z0.setText(f"{cable.z0_ohm:g}")
            self._vf.setText(f"{cable.velocity_factor:g}")
        self._recompute()

    def _recompute(self) -> None:
        cable = self._selected_cable()
        try:
            frequency = parse_si(self._frequency.text().strip() or "0")
            if cable is not None:
                self._loss.setText(f"{cable.loss_db_per_m(frequency):.4g}")
            design = design_coax_stub(
                parse_si(self._z0.text().strip() or "0"),
                frequency,
                float(self._vf.text().strip() or "0"),
                kind=self._KINDS[self._kind.currentIndex()][0],
                loss_db_per_m=float(self._loss.text().strip() or "0"),
                cable=cable,
            )
            response = coax_stub_response(
                design,
                line_z0_ohm=parse_si(self._line_z0.text().strip() or "0"),
            )
        except (CoaxStubError, ValueError):
            self._design = None
            self._response = None
            empty = np.array([], dtype=float)
            self._curve_s21.setData(empty, empty)
            self._curve_s11.setData(empty, empty)
            self._export_button.setEnabled(False)
            for label in (
                self._length,
                self._wavelength,
                self._loss_result,
                self._depth,
                self._bandwidth,
                self._loaded_q,
            ):
                label.setText("-")
            return
        self._design = design
        self._response = response
        self._length.setText(f"{design.length_m * 1000.0:.2f} mm")
        self._wavelength.setText(f"{design.wavelength_m * 1000.0:.2f} mm")
        self._loss_result.setText(f"{design.loss_db:.4f} dB")
        self._depth.setText(
            "≥120 dB"
            if response.notch_depth_db >= 120.0
            else f"{response.notch_depth_db:.1f} dB"
        )
        self._bandwidth.setText(
            "-"
            if response.bandwidth_3db_hz is None
            else format_engineering(response.bandwidth_3db_hz, "Hz")
        )
        self._loaded_q.setText(
            "-" if response.loaded_q is None else f"{response.loaded_q:.2f}"
        )
        self._curve_s21.setData(response.frequency_hz, response.s21_db)
        self._curve_s11.setData(response.frequency_hz, response.s11_db)
        self._plot.autoRange()
        self._export_button.setEnabled(True)


class DistributedSynthesisDialog(QDialog):
    """Convert the current low-pass spec into microstrip line sections."""

    def __init__(self, spec: FilterSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Distributed microstrip realization"))
        self._spec = spec
        self._substrates = list_substrates()
        self._design: DistributedDesign | None = None

        self._substrate = QComboBox()
        for substrate in self._substrates:
            self._substrate.addItem(
                f"{substrate.name} - er {substrate.er:g}, "
                f"h {substrate.h_mm:g} mm, tanD {substrate.tan_delta:g}"
            )
        self._angle = EngineeringLineEdit()
        self._angle.setText("30")
        self._z_min = EngineeringLineEdit()
        self._z_min.setText("10")
        self._z_max = EngineeringLineEdit()
        self._z_max.setText("250")
        self._confidence = ConfidenceBadge("distributed")
        self._preview = QLabel()
        self._preview.setWordWrap(True)
        self._preview.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        form = QFormLayout(self)
        form.addRow(tr("Confidence"), self._confidence)
        form.addRow(tr("Substrate"), self._substrate)
        form.addRow(tr("Electrical length (deg)"), self._angle)
        form.addRow(tr("Minimum Z0 (Ohm)"), self._z_min)
        form.addRow(tr("Maximum Z0 (Ohm)"), self._z_max)
        form.addRow(tr("Preview"), self._preview)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._buttons = buttons

        self._substrate.currentIndexChanged.connect(self._recompute)
        for field in (self._angle, self._z_min, self._z_max):
            field.editingFinished.connect(self._recompute)
        self._recompute()

    def selected_substrate(self) -> Substrate:
        return self._substrates[self._substrate.currentIndex()]

    def design(self) -> DistributedDesign | None:
        return self._design

    def accept(self) -> None:
        if self._design is None:
            return
        super().accept()

    def _recompute(self) -> None:
        try:
            design = design_distributed_lowpass(
                self._spec,
                self.selected_substrate(),
                electrical_length_deg=float(self._angle.text().strip() or "0"),
                z0_min_ohm=float(self._z_min.text().strip() or "0"),
                z0_max_ohm=float(self._z_max.text().strip() or "0"),
            )
        except (DistributedSynthesisError, ValueError) as exc:
            self._design = None
            self._preview.setText(str(exc))
            self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        self._design = design
        rows = [
            f"{el.id}: Z0={el.z0_ohm:.4g} Ω, W={el.width_mm:.3g} mm, "
            f"L={el.length_m * 1e3:.4g} mm, θ={el.angle_deg:.3g}°"
            for el in design.circuit.elements
            if isinstance(el, MicrostripLineElement)
        ]
        if design.warnings:
            rows.append("")
            rows.extend(f"Warning: {warning}" for warning in design.warnings)
        self._preview.setText("\n".join(rows))
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)


class VnaTuningDialog(QDialog):
    """Trim circuit values to a measured VNA magnitude response."""

    def __init__(
        self,
        circuit: Circuit,
        measured: AnalysisResult,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tune to VNA measurement")
        self._circuit = circuit
        self._measured = measured
        self._result: VnaTuningResult | None = None

        freq = measured.frequency_hz
        self._f_min = EngineeringLineEdit()
        self._f_min.setText(f"{float(freq.min()):.6g}")
        self._f_max = EngineeringLineEdit()
        self._f_max.setText(f"{float(freq.max()):.6g}")
        self._bound = EngineeringLineEdit()
        self._bound.setText("20")
        self._max_points = QSpinBox()
        self._max_points.setRange(2, max(2, measured.frequency_hz.size))
        self._max_points.setValue(min(401, measured.frequency_hz.size))
        self._bound_mode = QComboBox()
        self._bound_mode.addItems([mode.value for mode in VnaBoundMode])
        self._fit_s11 = QCheckBox("Fit S11")
        self._fit_s11.setChecked(True)
        self._fit_s21 = QCheckBox("Fit S21")
        self._fit_s21.setChecked(True)
        self._fit_phase = QCheckBox("Fit phase / auto delay")
        self._fit_phase.setChecked(False)

        self._summary = QLabel("-")
        self._summary.setWordWrap(True)
        self._details = QLabel("-")
        self._details.setWordWrap(True)
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Component", "Initial", "Final"])
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        form = QFormLayout(self)
        form.addRow("Measured", QLabel(measured.backend or "VNA"))
        form.addRow("Fit from", self._f_min)
        form.addRow("Fit to", self._f_max)
        form.addRow("Bound (%)", self._bound)
        form.addRow("Search", self._bound_mode)
        form.addRow("Max points", self._max_points)
        form.addRow(self._fit_s11, self._fit_s21)
        form.addRow(self._fit_phase)
        form.addRow("Result", self._summary)
        form.addRow("Details", self._details)
        form.addRow(self._table)

        buttons = QDialogButtonBox()
        self._run_button = buttons.addButton(
            "Run fit", QDialogButtonBox.ButtonRole.ActionRole
        )
        self._apply_button = buttons.addButton(
            "Apply", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._apply_button.setEnabled(False)
        close = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        self._run_button.clicked.connect(self._run_fit)
        self._apply_button.clicked.connect(self.accept)
        close.clicked.connect(self.reject)
        form.addRow(buttons)

    def current_result(self) -> VnaTuningResult | None:
        return self._result

    def result_circuit(self) -> Circuit | None:
        return None if self._result is None else self._result.circuit

    def _run_fit(self) -> None:
        try:
            bound = float(self._bound.text().strip() or "0") / 100.0
            cfg = VnaTuningConfig(
                bound_pct=bound,
                bound_mode=VnaBoundMode(self._bound_mode.currentText()),
                max_points=self._max_points.value(),
                fit_s11=self._fit_s11.isChecked(),
                fit_s21=self._fit_s21.isChecked(),
                fit_phase=self._fit_phase.isChecked(),
                f_min_hz=parse_si(self._f_min.text().strip() or "0"),
                f_max_hz=parse_si(self._f_max.text().strip() or "0"),
            )
        except (VnaTuningError, ValueError) as exc:
            QMessageBox.warning(self, "VNA tuning", str(exc))
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = fit_circuit_to_measurement(self._circuit, self._measured, cfg)
        except (VnaTuningError, ValueError) as exc:
            self._result = None
            self._apply_button.setEnabled(False)
            QMessageBox.warning(self, "VNA tuning", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._result = result
        self._summary.setText(
            f"{result.initial_rms_db:.3f} -> {result.final_rms_db:.3f} dB RMS "
            f"({result.improvement_db:+.3f} dB, {result.n_evaluations} evaluations)"
        )
        details = (
            f"S21 {result.initial_rms_s21_db:.3f} -> "
            f"{result.final_rms_s21_db:.3f} dB RMS; "
            f"S11 {result.initial_rms_s11_db:.3f} -> "
            f"{result.final_rms_s11_db:.3f} dB RMS; "
            f"{result.frequency_hz.size} points"
        )
        if result.delay_s is not None:
            details += (
                f"; delay {result.delay_s * 1e9:.2f} ns"
                f"; phase S21 {result.phase_s21_deg or 0.0:+.2f} deg"
                f", S11 {result.phase_s11_deg or 0.0:+.2f} deg"
            )
        if result.quality_notes:
            details += "; quality: " + "; ".join(result.quality_notes)
        self._details.setText(details)
        self._table.setRowCount(len(result.refs))
        for row, (ref, initial, final) in enumerate(
            zip(result.refs, result.initial_values, result.final_values, strict=True)
        ):
            self._table.setItem(row, 0, QTableWidgetItem(ref))
            self._table.setItem(row, 1, QTableWidgetItem(f"{initial:.6g}"))
            self._table.setItem(row, 2, QTableWidgetItem(f"{final:.6g}"))
        self._apply_button.setEnabled(True)


class BandFilterWizardDialog(QDialog):
    """Quick or guided Chebyshev-I design for any amateur/broadcast band."""

    _KINDS: tuple[tuple[BandKind, str], ...] = (
        (BandKind.LPF, tr("Transmit LPF")),
        (BandKind.HPF, tr("High-pass")),
        (BandKind.BPF, tr("Band-pass")),
        (BandKind.BSF, tr("Band-stop (notch)")),
    )
    _MODES: tuple[str, ...] = (tr("Quick preset"), tr("Guided design"))

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Band filter wizard"))
        self.setMinimumWidth(820)
        self._design_value: BandFilterDesign | None = None

        self._mode = QComboBox()
        for label in self._MODES:
            self._mode.addItem(label)
        self._band = QComboBox()
        for band in ALL_PRESETS:
            self._band.addItem(band.name)
        self._band.setCurrentIndex(
            next((i for i, b in enumerate(ALL_PRESETS) if b.name == "40 m"), 0)
        )
        self._kind = QComboBox()
        self._kind_choices = self._KINDS
        self._rejection_mode: bool | None = None
        self._last_amateur_kind = BandKind.LPF
        for _kind, label in self._KINDS:
            self._kind.addItem(label)

        self._quick_summary = QLabel("-")
        self._quick_summary.setWordWrap(True)
        quick = QWidget()
        quick_layout = QFormLayout(quick)
        quick_layout.addRow(self._quick_summary)

        self._z_in = EngineeringLineEdit()
        self._z_in.setText("50")
        self._z_out = EngineeringLineEdit()
        self._z_out.setText("50")
        self._ripple = EngineeringLineEdit()
        self._ripple.setText("0.1")
        self._max_il = EngineeringLineEdit()
        self._max_il.setText("0.5")
        self._min_stop = EngineeringLineEdit()
        self._min_stop.setText("30")
        self._pass_edge = EngineeringLineEdit()
        self._stop_edge = EngineeringLineEdit()
        self._guard = EngineeringLineEdit()
        self._guard.setText("50")
        self._max_order = QSpinBox()
        self._max_order.setRange(2, 12)
        self._max_order.setValue(12)
        self._snap = QCheckBox(tr("Snap after apply"))
        self._snap.setChecked(False)
        self._snap_series = QComboBox()
        for series in (ESeries.E24, ESeries.E48, ESeries.E96):
            self._snap_series.addItem(series.value)
        self._snap_series.setEnabled(False)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            [
                tr("Order"),
                tr("Passband"),
                tr("Stop low"),
                tr("Stop high"),
                tr("2f/3f"),
                tr("Status"),
            ]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._result = QLabel("-")
        self._result.setWordWrap(True)
        self._notes = QLabel("-")
        self._notes.setWordWrap(True)
        self._confidence = ConfidenceBadge("filter_synthesis")

        guided = QWidget()
        guided_layout = QFormLayout(guided)
        guided_layout.addRow(tr("Source Z (Ohm)"), self._z_in)
        guided_layout.addRow(tr("Load Z (Ohm)"), self._z_out)
        guided_layout.addRow(tr("Passband ripple (dB)"), self._ripple)
        guided_layout.addRow(tr("Max insertion loss (dB)"), self._max_il)
        guided_layout.addRow(tr("Min stopband attenuation (dB)"), self._min_stop)
        guided_layout.addRow(tr("Pass edge (Hz)"), self._pass_edge)
        guided_layout.addRow(tr("Stop edge (Hz)"), self._stop_edge)
        guided_layout.addRow(tr("Stopband guard (% of band span)"), self._guard)
        guided_layout.addRow(tr("Max order"), self._max_order)
        guided_layout.addRow(self._snap)
        guided_layout.addRow(tr("Series"), self._snap_series)
        guided_layout.addRow(tr("Candidates"), self._table)
        guided_layout.addRow(self._confidence)
        guided_layout.addRow(tr("Result"), self._result)
        guided_layout.addRow(tr("Notes"), self._notes)

        self._stack = QStackedWidget()
        self._stack.addWidget(quick)
        self._stack.addWidget(guided)

        form = QFormLayout(self)
        form.addRow(tr("Mode"), self._mode)
        form.addRow(tr("Band"), self._band)
        form.addRow(tr("Filter"), self._kind)
        form.addRow(self._stack)

        self._design_button = QPushButton(tr("Design"))
        self._apply_button = QPushButton(tr("Apply to project"))
        self._apply_button.setEnabled(False)
        buttons = QDialogButtonBox()
        buttons.addButton(self._design_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(self._apply_button, QDialogButtonBox.ButtonRole.AcceptRole)
        close = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        self._design_button.clicked.connect(self._run_design)
        self._apply_button.clicked.connect(self.accept)
        close.clicked.connect(self.reject)
        form.addRow(buttons)

        self._band.currentIndexChanged.connect(self._on_selection_changed)
        self._band.currentIndexChanged.connect(self._sync_snap_series)
        self._kind.currentIndexChanged.connect(self._on_selection_changed)
        self._mode.currentIndexChanged.connect(self._sync_mode)
        self._snap.toggled.connect(self._snap_series.setEnabled)
        self._sync_kind_choices()
        self._sync_snap_series()
        self._sync_edges()
        self._sync_mode()

    def selection(self) -> tuple[Band, BandKind]:
        return ALL_PRESETS[self._band.currentIndex()], self.result_kind()

    def current_design(self) -> BandFilterDesign | None:
        return self._design_value

    def result_spec(self) -> FilterSpec | None:
        if self._mode.currentIndex() == 0:
            return self._quick_spec()
        if self._design_value is None or self._design_value.selected is None:
            return None
        return self._design_value.selected.spec

    def result_band(self) -> Band:
        return ALL_PRESETS[self._band.currentIndex()]

    def result_kind(self) -> BandKind:
        return self._kind_choices[self._kind.currentIndex()][0]

    def snap_enabled(self) -> bool:
        return self._snap.isChecked()

    def snap_series(self) -> ESeries:
        return ESeries(self._snap_series.currentText())

    def result_request(self) -> BandFilterRequest:
        if self._mode.currentIndex() == 1 and self._design_value is not None:
            return self._design_value.request
        return BandFilterRequest(self.result_band(), self.result_kind())

    def _quick_spec(self) -> FilterSpec | None:
        try:
            return band_preset_spec(self.result_band(), self.result_kind())
        except (KeyError, ValueError):
            return None

    def _kind_label(self) -> str:
        return self._kind_choices[self._kind.currentIndex()][1]

    def _sync_kind_choices(self) -> None:
        rejection = self.result_band() in REJECTION_PRESETS
        if rejection == self._rejection_mode:
            return
        if self._rejection_mode is False:
            self._last_amateur_kind = self.result_kind()
        self._rejection_mode = rejection
        choices = (
            (self._KINDS[-1],)
            if rejection
            else self._KINDS
        )
        preferred = BandKind.BSF if rejection else self._last_amateur_kind
        self._kind.blockSignals(True)
        self._kind.clear()
        for _kind, label in choices:
            self._kind.addItem(label)
        self._kind_choices = choices
        index = next(
            (i for i, (kind, _label) in enumerate(choices) if kind is preferred),
            0,
        )
        self._kind.setCurrentIndex(index)
        self._kind.blockSignals(False)

    def _describe_spec(self, spec: FilterSpec) -> str:
        if spec.response in (FilterResponse.LOW_PASS, FilterResponse.HIGH_PASS):
            return tr(
                "Order {order} Chebyshev-I {kind}; cutoff {cutoff}.",
                order=spec.order,
                kind=self._kind_label(),
                cutoff=format_engineering(spec.cutoff_hz, "Hz"),
            )
        return tr(
            "Order {order} Chebyshev-I {kind}; center {center}; bandwidth {bandwidth}.",
            order=spec.order,
            kind=self._kind_label(),
            center=format_engineering(spec.f_center_hz or 0.0, "Hz"),
            bandwidth=format_engineering(spec.bandwidth_hz or 0.0, "Hz"),
        )

    def _sync_snap_series(self) -> None:
        recommended = (
            ESeries.E96 if self.result_band().low_hz >= 100e6 else ESeries.E24
        )
        index = self._snap_series.findText(recommended.value)
        if index >= 0:
            self._snap_series.setCurrentIndex(index)

    def _sync_edges(self) -> None:
        band, kind = self.selection()
        edges = kind in (BandKind.LPF, BandKind.HPF)
        if kind is BandKind.LPF:
            pass_edge, stop_edge = band.high_hz, band.high_hz * 1.5
        elif kind is BandKind.HPF:
            pass_edge, stop_edge = band.low_hz, band.low_hz / 1.5
        else:
            pass_edge, stop_edge = band.low_hz, band.high_hz
        self._pass_edge.setText(format_engineering(pass_edge, "Hz"))
        self._stop_edge.setText(format_engineering(stop_edge, "Hz"))
        self._pass_edge.setEnabled(edges)
        self._stop_edge.setEnabled(edges)
        self._guard.setEnabled(not edges)

    def _sync_mode(self) -> None:
        guided = self._mode.currentIndex() == 1
        self._stack.setCurrentIndex(1 if guided else 0)
        self._design_button.setVisible(guided)
        if guided:
            self._run_design()
        else:
            self._update_quick()

    def _on_selection_changed(self) -> None:
        self._sync_kind_choices()
        self._sync_edges()
        if self._mode.currentIndex() == 1:
            self._run_design()
        else:
            self._update_quick()

    def _update_quick(self) -> None:
        self._design_value = None
        spec = self._quick_spec()
        if spec is None:
            self._quick_summary.setText(tr("Invalid band preset."))
            self._apply_button.setEnabled(False)
            return
        self._quick_summary.setText(self._describe_spec(spec))
        self._apply_button.setEnabled(True)

    def _run_design(self) -> None:
        if self._mode.currentIndex() != 1:
            return
        band, kind = self.selection()
        try:
            request = BandFilterRequest(
                band=band,
                kind=kind,
                z_source_ohm=parse_si(self._z_in.text().strip() or "0"),
                z_load_ohm=parse_si(self._z_out.text().strip() or "0"),
                passband_ripple_db=float(self._ripple.text().strip() or "0"),
                max_insertion_loss_db=float(self._max_il.text().strip() or "0"),
                min_stopband_attenuation_db=float(self._min_stop.text().strip() or "0"),
                stopband_guard=float(self._guard.text().strip() or "0") / 100.0,
                max_order=self._max_order.value(),
                pass_edge_hz=(
                    parse_si(self._pass_edge.text().strip() or "0")
                    if kind in (BandKind.LPF, BandKind.HPF)
                    else None
                ),
                stop_edge_hz=(
                    parse_si(self._stop_edge.text().strip() or "0")
                    if kind in (BandKind.LPF, BandKind.HPF)
                    else None
                ),
            )
            design = design_band_filter(request)
        except (BandFilterDesignError, ValueError) as exc:
            self._design_value = None
            self._table.setRowCount(0)
            self._result.setText(str(exc))
            self._notes.setText("-")
            self._apply_button.setEnabled(False)
            return
        self._design_value = design
        self._table.setRowCount(len(design.candidates))
        for row, candidate in enumerate(design.candidates):
            harmonics = "—"
            if (
                candidate.harmonic_2f_db is not None
                and candidate.harmonic_3f_db is not None
            ):
                harmonics = (
                    f"{-candidate.harmonic_2f_db:.0f}/"
                    f"{-candidate.harmonic_3f_db:.0f} dB"
                )
            values = (
                str(candidate.order),
                f"{candidate.passband_min_db:.2f} dB",
                "—"
                if candidate.stopband_low_db is None
                else f"{candidate.stopband_low_db:.1f} dB",
                "—"
                if candidate.stopband_high_db is None
                else f"{candidate.stopband_high_db:.1f} dB",
                harmonics,
                tr("OK") if candidate.ok else tr("No"),
            )
            for col, value in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(value))
        self._table.resizeRowsToContents()
        if design.selected is None:
            self._result.setText(tr("No order met the requirements"))
            self._notes.setText("; ".join(design.notes))
            self._apply_button.setEnabled(False)
            return
        spec = design.selected.spec
        self._result.setText(self._describe_spec(spec))
        self._notes.setText("; ".join(design.notes))
        self._apply_button.setEnabled(True)


class MeasurementDetailsDialog(QDialog):
    """Read-only provenance and comparison for one stored measurement."""

    def __init__(
        self,
        record: MeasurementRecord,
        analysis: AnalysisResult | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Measurement details"))
        self.setMinimumWidth(620)
        metadata = record.metadata
        form = QFormLayout(self)
        form.addRow(tr("Name"), QLabel(record.name))
        form.addRow(tr("Source"), QLabel(record.source or "—"))
        form.addRow(tr("VNA model"), QLabel(metadata.vna_model or "—"))
        form.addRow(tr("Calibration"), QLabel(metadata.calibration or "—"))
        form.addRow(tr("Reference plane"), QLabel(metadata.reference_plane or "—"))
        form.addRow(tr("Cables"), QLabel(metadata.cables or "—"))
        form.addRow(tr("Connectors"), QLabel(metadata.connectors or "—"))
        form.addRow(tr("Terminations"), QLabel(metadata.terminations or "—"))
        form.addRow(tr("Fixture"), QLabel(metadata.fixture or "—"))
        temperature = (
            "—"
            if metadata.temperature_c is None
            else f"{metadata.temperature_c:g}"
        )
        form.addRow(tr("Temperature (C)"), QLabel(temperature))
        form.addRow(tr("Measured at"), QLabel(metadata.measured_at or "—"))
        form.addRow(tr("Operator"), QLabel(metadata.operator or "—"))
        form.addRow(tr("Notes"), QLabel(metadata.notes or "—"))
        if analysis is None:
            comparison = tr("Analyze a design to compare against this measurement.")
        else:
            try:
                comparison = compare_results(
                    analysis, record.to_analysis_result()
                ).summary()
            except CompareError as exc:
                comparison = str(exc)
        compare_label = QLabel(comparison)
        compare_label.setWordWrap(True)
        form.addRow(tr("Comparison"), compare_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        form.addRow(buttons)


class FourPortMixedModeDialog(QDialog):
    """Import a 4-port Touchstone file and show its mixed-mode S blocks."""

    _MAX_ROWS = 2000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("4-port mixed-mode"))
        self.setMinimumWidth(820)
        self._path = QLabel("-")
        self._path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._open_button = QPushButton(tr("Open .s4p…"))
        self._open_button.clicked.connect(self._choose_file)
        self._report: FourPortMixedMode | None = None
        self._source: str | None = None
        self._export_csv_button = QPushButton(tr("Export CSV…"))
        self._export_json_button = QPushButton(tr("Export JSON…"))
        self._export_csv_button.setEnabled(False)
        self._export_json_button.setEnabled(False)
        self._export_csv_button.clicked.connect(self._export_csv)
        self._export_json_button.clicked.connect(self._export_json)
        self._summary = QLabel(tr("Open a 4-port Touchstone file to analyze."))
        self._summary.setWordWrap(True)
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            [
                tr("Frequency"),
                tr("Sdd21 (dB)"),
                tr("Sdc21 (dB)"),
                tr("Scd21 (dB)"),
                tr("Scc21 (dB)"),
            ]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._plot = pg.PlotWidget(title=tr("Mixed-mode S (dB)"))
        self._plot.setLogMode(x=True, y=False)
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.setLabel("bottom", tr("Frequency"), units="Hz")
        self._plot.setLabel("left", tr("Magnitude"), units="dB")
        self._plot.addLegend()
        self._plot.setMinimumHeight(280)
        self._curve_sdd = self._plot.plot(
            pen=pg.mkPen("#1f77b4", width=2), name="Sdd21"
        )
        self._curve_sdc = self._plot.plot(
            pen=pg.mkPen("#ff7f0e", width=2), name="Sdc21"
        )
        self._curve_scd = self._plot.plot(
            pen=pg.mkPen("#2ca02c", width=2), name="Scd21"
        )
        self._curve_scc = self._plot.plot(
            pen=pg.mkPen("#d62728", width=2), name="Scc21"
        )
        self._view_tabs = QTabWidget()
        self._view_tabs.addTab(self._table, tr("Table"))
        self._view_tabs.addTab(self._plot, tr("Plot"))

        top = QHBoxLayout()
        top.addWidget(self._open_button)
        top.addWidget(self._path, 1)
        top.addWidget(self._export_csv_button)
        top.addWidget(self._export_json_button)
        self._export_status = QLabel("")
        form = QFormLayout(self)
        form.addRow(top)
        form.addRow(self._summary)
        form.addRow(self._export_status)
        form.addRow(self._view_tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        form.addRow(buttons)

    @staticmethod
    def _db(value: complex) -> float:
        return 20.0 * math.log10(max(abs(value), 1e-15))

    def _default_export_name(self, suffix: str) -> str:
        stem = Path(self._source).stem if self._source else "mixed_mode"
        return f"{stem}{suffix}"

    def _export_csv(self) -> None:
        if self._report is None:
            return
        path, _selected = QFileDialog.getSaveFileName(
            self,
            tr("Export mixed-mode CSV"),
            self._default_export_name(".csv"),
            "CSV (*.csv);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            Path(path).write_text(
                mixed_mode_csv(self._report), encoding="utf-8"
            )
        except OSError as exc:
            QMessageBox.critical(self, tr("Export failed"), str(exc))
            return
        self._export_status.setText(tr("Wrote {path}", path=path))

    def _export_json(self) -> None:
        if self._report is None:
            return
        path, _selected = QFileDialog.getSaveFileName(
            self,
            tr("Export mixed-mode JSON"),
            self._default_export_name(".json"),
            "JSON (*.json);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            Path(path).write_text(
                mixed_mode_json(self._report, source=self._source),
                encoding="utf-8",
            )
        except OSError as exc:
            QMessageBox.critical(self, tr("Export failed"), str(exc))
            return
        self._export_status.setText(tr("Wrote {path}", path=path))

    def _choose_file(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            tr("Open 4-port Touchstone"),
            "",
            "Touchstone 4-port (*.s4p *.S4P);;All files (*)",
        )
        if path:
            self.load_path(path)

    def load_path(self, path: str | Path) -> bool:
        try:
            data = read_touchstone(path)
            if data.n_ports != 4:
                raise FourPortError(
                    tr(
                        "Mixed-mode requires a 4-port file (got {ports}).",
                        ports=data.n_ports,
                    )
                )
            report = mixed_mode_4port(
                data.s, data.frequency_hz, z0_ohm=data.z0_ohm
            )
        except (TouchstoneError, FourPortError, OSError, ValueError) as exc:
            self._table.setRowCount(0)
            empty = np.array([], dtype=float)
            for curve in (
                self._curve_sdd,
                self._curve_sdc,
                self._curve_scd,
                self._curve_scc,
            ):
                curve.setData(empty, empty)
            self._report = None
            self._source = None
            self._export_csv_button.setEnabled(False)
            self._export_json_button.setEnabled(False)
            self._export_status.setText("")
            self._summary.setText(str(exc))
            self._path.setText(str(path))
            return False

        self._path.setText(str(path))
        self._report = report
        self._source = data.source
        self._export_csv_button.setEnabled(True)
        self._export_json_button.setEnabled(True)
        self._export_status.setText("")
        shown = min(report.frequency_hz.size, self._MAX_ROWS)
        suffix = (
            f" — showing {shown} of {report.frequency_hz.size} points"
            if shown < report.frequency_hz.size
            else ""
        )
        self._summary.setText(
            tr(
                "4-port, {points} points, {fmin}–{fmax}; "
                "Zd={zd} Ω, Zc={zc} Ω{suffix}",
                points=report.frequency_hz.size,
                fmin=format_engineering(float(report.frequency_hz[0]), "Hz"),
                fmax=format_engineering(float(report.frequency_hz[-1]), "Hz"),
                zd=format_engineering(report.z0_diff_ohm, "Ohm", digits=4),
                zc=format_engineering(report.z0_common_ohm, "Ohm", digits=4),
                suffix=suffix,
            )
        )
        indices = np.linspace(
            0, report.frequency_hz.size - 1, shown, dtype=int
        )
        self._table.setUpdatesEnabled(False)
        try:
            self._table.setRowCount(indices.size)
            for row, index in enumerate(indices):
                values = (
                    report.frequency_hz[index],
                    self._db(complex(report.sdd[index, 1, 0])),
                    self._db(complex(report.sdc[index, 1, 0])),
                    self._db(complex(report.scd[index, 1, 0])),
                    self._db(complex(report.scc[index, 1, 0])),
                )
                cells = (
                    format_engineering(float(values[0]), "Hz", digits=5),
                    f"{values[1]:.2f}",
                    f"{values[2]:.2f}",
                    f"{values[3]:.2f}",
                    f"{values[4]:.2f}",
                )
                for column, text in enumerate(cells):
                    self._table.setItem(row, column, QTableWidgetItem(text))
        finally:
            self._table.setUpdatesEnabled(True)
        self._table.resizeRowsToContents()

        freq = report.frequency_hz
        curves = (
            (self._curve_sdd, report.sdd[:, 1, 0]),
            (self._curve_sdc, report.sdc[:, 1, 0]),
            (self._curve_scd, report.scd[:, 1, 0]),
            (self._curve_scc, report.scc[:, 1, 0]),
        )
        for curve, series in curves:
            curve.setData(freq, np.asarray([self._db(complex(v)) for v in series]))
        self._plot.autoRange()
        return True
