"""Shared GUI widgets."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from filterdesk.analysis.sensitivity import SensitivityReport
from filterdesk.components_std import (
    AirCoilError,
    AttenuatorDesign,
    AttenuatorError,
    AttenuatorKind,
    ESeries,
    MatchingDesign,
    MatchingError,
    MatchingTopology,
    SnapStrategy,
    design_air_coil,
    design_attenuator,
    design_matching,
    design_microstrip,
    design_toroid,
    design_transformer,
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
    TransformerDesign,
    TransformerError,
    TransformerKind,
)
from filterdesk.domain.circuit import IdealInductor, NonIdealInductor
from filterdesk.domain.specs import FilterSpec
from filterdesk.domain.units import format_engineering, parse_si
from filterdesk.gui.i18n import tr
from filterdesk.montecarlo import MonteCarloConfig, ToleranceDistribution
from filterdesk.optimization import OptimizationConfig, OptimizeMethod
from filterdesk.services.bands import ALL_PRESETS, Band, BandKind
from filterdesk.services.design_sweep import DesignSweepRow, SweepAxis
from filterdesk.services.inductor_realization import (
    InductorRealizationError,
    realize_from_air_design,
    realize_from_toroid_design,
)


class EngineeringLineEdit(QLineEdit):
    """Line edit for values like ``140M``, ``4.7p``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(tr("e.g. 140M, 50, 10n"))


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
        self._strategy.setCurrentIndex(
            list(SnapStrategy).index(SnapStrategy(strategy))
        )
        form = QFormLayout(self)
        form.addRow(tr("Series"), self._series)
        form.addRow(tr("Strategy"), self._strategy)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
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
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
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
                raise ValueError(
                        tr(
                            "Q reference frequency is required when Q is set"
                        )
                    )
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
            self._cp.setText(
                format_engineering(parallel_capacitance_f, "F", digits=6)
            )
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
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
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
                        tr(
                            "Q reference frequency is required when Q is set"
                        )
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
        self._dist.setCurrentIndex(
            list(ToleranceDistribution).index(base.distribution)
        )
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
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
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
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
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



class BandPresetDialog(QDialog):
    """Choose an amateur band and filter kind for a quick preset design."""

    _KINDS: tuple[tuple[BandKind, str], ...] = (
        (BandKind.LPF, tr("Transmit LPF")),
        (BandKind.HPF, tr("High-pass")),
        (BandKind.BPF, tr("Band-pass")),
        (BandKind.BSF, tr("Band-stop (notch)")),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Amateur band preset"))
        self._band = QComboBox()
        for band in ALL_PRESETS:
            self._band.addItem(band.name)
        # Default to 40 m.
        self._band.setCurrentIndex(
            next((i for i, b in enumerate(ALL_PRESETS) if b.name == "40 m"), 0)
        )
        self._kind = QComboBox()
        for _kind, label in self._KINDS:
            self._kind.addItem(label)
        form = QFormLayout(self)
        form.addRow(tr("Band"), self._band)
        form.addRow(tr("Filter"), self._kind)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def selection(self) -> tuple[Band, BandKind]:
        # Indices (not userData): PySide would coerce the StrEnum to a plain str.
        band = ALL_PRESETS[self._band.currentIndex()]
        kind = self._KINDS[self._kind.currentIndex()][0]
        return band, kind

    @classmethod
    def ask(cls, parent: QWidget | None = None) -> tuple[Band, BandKind] | None:
        dialog = cls(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selection()
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
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
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
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
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
            "  ".join(parts)
            + f"   (Zin={design.input_impedance_ohm.real:.4g}"
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
        self._l_achieved.setText(
            format_engineering(design.inductance_h, "H", digits=6)
        )
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
            self._wire_mm.setText(
                f"{awg_diameter_mm(int(self._awg.value())):.3f}"
            )
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
            wire_mm = (
                float(self._wire_mm.text().strip() or "0") if use_mm else None
            )
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
        self._l_achieved.setText(
            format_engineering(design.inductance_h, "H", digits=6)
        )
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
                f"{design.wire_diameter_mm:.3f} mm bare "
                f"(AWG {design.awg} eq.)"
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
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
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
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def selection(self) -> tuple[ESeries | None, bool]:
        data = self._series.currentData()
        series = ESeries(str(data)) if data is not None else None
        return series, self._group.isChecked()

    @classmethod
    def ask(
        cls, parent: QWidget | None = None
    ) -> tuple[ESeries | None, bool] | None:
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
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def selection(self) -> tuple[SweepAxis, str, int]:
        axis = SweepAxis(str(self._axis.currentData()))
        return axis, self._values.text().strip(), int(self._points.value())

    @classmethod
    def ask(
        cls, parent: QWidget | None = None
    ) -> tuple[SweepAxis, str, int] | None:
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
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
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
                    if metrics is None
                    or metrics.stopband_attenuation_db is None
                    else f"{metrics.stopband_attenuation_db:.1f}"
                ),
                (
                    ""
                    if metrics is None or metrics.min_return_loss_db is None
                    else f"{metrics.min_return_loss_db:.1f}"
                ),
                (
                    ""
                    if metrics is None
                    or metrics.group_delay_ripple_s is None
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
    """Transformer-type unun / balun / power transformer calculator."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Transformer / balun")
        self._cores = list_cores()
        self._design_value: TransformerDesign | None = None

        self._core = QComboBox()
        for core in self._cores:
            self._core.addItem(
                f"{core.name} - mix {core.material}, AL {core.al_nh:g} nH/N^2"
            )
        self._kind = QComboBox()
        self._kind.addItems([k.value for k in TransformerKind])
        self._z_low = EngineeringLineEdit()
        self._z_low.setText("50")
        self._z_high = EngineeringLineEdit()
        self._z_high.setText("200")
        self._frequency = EngineeringLineEdit()
        self._frequency.setText("3.5M")
        self._power = EngineeringLineEdit()
        self._power.setText("10")

        self._turns = QLabel("-")
        self._lm = QLabel("-")
        self._vi = QLabel("-")
        self._flux = QLabel("-")
        self._wire = QLabel("-")
        self._notes = QLabel("-")
        self._notes.setWordWrap(True)

        form = QFormLayout(self)
        form.addRow("Core", self._core)
        form.addRow("Kind", self._kind)
        form.addRow("Low-side Z (Ohm)", self._z_low)
        form.addRow("High-side Z (Ohm)", self._z_high)
        form.addRow("Lowest frequency", self._frequency)
        form.addRow("Power (W)", self._power)
        form.addRow("Turns", self._turns)
        form.addRow("Magnetizing L", self._lm)
        form.addRow("V / I", self._vi)
        form.addRow("Peak flux", self._flux)
        form.addRow("Wire", self._wire)
        form.addRow("Notes", self._notes)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        form.addRow(buttons)

        self._core.currentIndexChanged.connect(self._recompute)
        self._kind.currentIndexChanged.connect(self._recompute)
        for field in (self._z_low, self._z_high, self._frequency, self._power):
            field.editingFinished.connect(self._recompute)
        self._recompute()

    def selected_core(self) -> ToroidCore:
        return self._cores[self._core.currentIndex()]

    def current_design(self) -> TransformerDesign | None:
        return self._design_value

    def _recompute(self) -> None:
        try:
            design = design_transformer(
                self.selected_core(),
                z_low_ohm=parse_si(self._z_low.text().strip() or "0"),
                z_high_ohm=parse_si(self._z_high.text().strip() or "0"),
                frequency_hz=parse_si(self._frequency.text().strip() or "0"),
                power_w=float(self._power.text().strip() or "0"),
                kind=TransformerKind(self._kind.currentText()),
            )
        except (TransformerError, ValueError):
            self._design_value = None
            for label in (
                self._turns,
                self._lm,
                self._vi,
                self._flux,
                self._wire,
                self._notes,
            ):
                label.setText("-")
            return
        self._design_value = design
        self._turns.setText(
            f"{design.n_low} : {design.n_high} "
            f"(Z ratio {design.actual_impedance_ratio:.3f})"
        )
        self._lm.setText(
            format_engineering(design.magnetizing_inductance_h, "H", digits=4)
        )
        self._vi.setText(
            f"{design.v_low_rms:.3g}/{design.v_high_rms:.3g} Vrms, "
            f"{design.i_low_rms_a:.3g}/{design.i_high_rms_a:.3g} Arms"
        )
        if design.b_peak_t is None:
            self._flux.setText("-")
        else:
            text = f"{design.b_peak_t * 1000.0:.1f} mT"
            if design.bsat_margin is not None:
                text += f" (B/Bsat {design.bsat_margin:.2f})"
            self._flux.setText(text)
        self._wire.setText(
            f"low AWG {design.awg_low}, high AWG {design.awg_high}; "
            f"fit AWG {design.fit.awg}"
        )
        self._notes.setText("; ".join(design.notes) if design.notes else "-")


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

        form = QFormLayout(self)
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
                f"{line.electrical_length_deg():.1f} deg, "
                f"loss {line.loss_db():.4f} dB"
            )
        else:
            self._length_result.setText("-")
