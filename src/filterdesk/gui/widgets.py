"""Shared GUI widgets."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from filterdesk.components_std import (
    AttenuatorDesign,
    AttenuatorError,
    AttenuatorKind,
    ESeries,
    SnapStrategy,
    design_attenuator,
    inductor_resistance_ohm_from_q,
)
from filterdesk.domain.units import format_engineering, parse_si
from filterdesk.montecarlo import MonteCarloConfig, ToleranceDistribution
from filterdesk.optimization import OptimizationConfig, OptimizeMethod
from filterdesk.services.bands import BANDS, Band, BandKind


class EngineeringLineEdit(QLineEdit):
    """Line edit for values like ``140M``, ``4.7p``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("e.g. 140M, 50, 10n")


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
        self.setWindowTitle("Snap to E-series")
        self._series = QComboBox()
        for es in ESeries:
            self._series.addItem(es.value, es)
        self._series.setCurrentIndex(list(ESeries).index(ESeries(series)))
        self._strategy = QComboBox()
        for st in SnapStrategy:
            self._strategy.addItem(_STRATEGY_LABELS[st], st)
        self._strategy.setCurrentIndex(
            list(SnapStrategy).index(SnapStrategy(strategy))
        )
        form = QFormLayout(self)
        form.addRow("Series", self._series)
        form.addRow("Strategy", self._strategy)
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
        self.setWindowTitle("Apply parasitics / finite Q")
        self._ind_q = EngineeringLineEdit()
        self._ind_q.setPlaceholderText("e.g. 100 (blank = ideal)")
        self._q_freq = EngineeringLineEdit()
        self._q_freq.setPlaceholderText("e.g. 100M (required for Q)")
        self._ind_dcr = EngineeringLineEdit()
        self._ind_dcr.setPlaceholderText("e.g. 0.5 (ohm, optional)")
        self._ind_cpar = EngineeringLineEdit()
        self._ind_cpar.setPlaceholderText("e.g. 0.2p (F, optional)")
        self._cap_esr = EngineeringLineEdit()
        self._cap_esr.setPlaceholderText("e.g. 0.05 (ohm, optional)")
        self._cap_esl = EngineeringLineEdit()
        self._cap_esl.setPlaceholderText("e.g. 0.5n (H, optional)")
        form = QFormLayout(self)
        form.addRow("Inductor Q", self._ind_q)
        form.addRow("Q reference freq", self._q_freq)
        form.addRow("Inductor DCR", self._ind_dcr)
        form.addRow("Inductor Cpar", self._ind_cpar)
        form.addRow("Capacitor ESR", self._cap_esr)
        form.addRow("Capacitor ESL", self._cap_esl)
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
                raise ValueError("Q reference frequency is required when Q is set")
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
            self.setWindowTitle("Inductor parasitics")
            self._r = EngineeringLineEdit()
            self._r.setText(format_engineering(series_resistance_ohm, "Ohm", digits=6))
            self._cp = EngineeringLineEdit()
            self._cp.setText(
                format_engineering(parallel_capacitance_f, "F", digits=6)
            )
            self._q = EngineeringLineEdit()
            self._q.setPlaceholderText("optional; overrides DCR")
            self._q_freq = EngineeringLineEdit()
            self._q_freq.setPlaceholderText("e.g. 100M")
            form.addRow("Series R (DCR)", self._r)
            form.addRow("Parallel C (Cp)", self._cp)
            form.addRow("Q", self._q)
            form.addRow("Q reference freq", self._q_freq)
        else:
            self.setWindowTitle("Capacitor parasitics")
            self._esr = EngineeringLineEdit()
            self._esr.setText(format_engineering(esr_ohm, "Ohm", digits=6))
            self._esl = EngineeringLineEdit()
            self._esl.setText(format_engineering(esl_h, "H", digits=6))
            form.addRow("ESR", self._esr)
            form.addRow("ESL", self._esl)
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
                    raise ValueError("Q reference frequency is required when Q is set")
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
        self.setWindowTitle("Monte-Carlo tolerances")
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
        self._seed.setPlaceholderText("optional integer")
        if base.seed is not None:
            self._seed.setText(str(base.seed))
        form = QFormLayout(self)
        form.addRow("Trials", self._trials)
        form.addRow("Tolerance ± (%)", self._tol)
        form.addRow("Distribution", self._dist)
        form.addRow("Seed", self._seed)
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
        self.setWindowTitle("Optimize to limits")
        base = initial or OptimizationConfig()
        self._method = QComboBox()
        for method in OptimizeMethod:
            self._method.addItem(self._METHOD_LABELS[method], method)
        self._method.setCurrentIndex(list(OptimizeMethod).index(base.method))
        self._bound = EngineeringLineEdit()
        self._bound.setText(f"{base.bound_pct:g}")
        self._bound.setPlaceholderText("e.g. 0.2 = ±20%")
        self._max_iter = QSpinBox()
        self._max_iter.setRange(1, 100_000)
        self._max_iter.setValue(base.max_iter)
        self._seed = QLineEdit()
        self._seed.setPlaceholderText("optional integer (global methods)")
        if base.seed is not None:
            self._seed.setText(str(base.seed))
        form = QFormLayout(self)
        form.addRow("Method", self._method)
        form.addRow("Bound (± fraction)", self._bound)
        form.addRow("Max iterations", self._max_iter)
        form.addRow("Seed", self._seed)
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
        (BandKind.LPF, "Transmit LPF"),
        (BandKind.HPF, "High-pass"),
        (BandKind.BPF, "Band-pass"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Amateur band preset")
        self._band = QComboBox()
        for band in BANDS:
            self._band.addItem(band.name)
        # Default to 40 m.
        self._band.setCurrentIndex(
            next((i for i, b in enumerate(BANDS) if b.name == "40 m"), 0)
        )
        self._kind = QComboBox()
        for _kind, label in self._KINDS:
            self._kind.addItem(label)
        form = QFormLayout(self)
        form.addRow("Band", self._band)
        form.addRow("Filter", self._kind)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def selection(self) -> tuple[Band, BandKind]:
        # Indices (not userData): PySide would coerce the StrEnum to a plain str.
        band = BANDS[self._band.currentIndex()]
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
        self.setWindowTitle("Attenuator pad")
        self._db = EngineeringLineEdit()
        self._db.setText("6")
        self._z0 = EngineeringLineEdit()
        self._z0.setText("50")
        self._kind = QComboBox()
        for _kind, label in (
            (AttenuatorKind.TEE, "T pad"),
            (AttenuatorKind.PI, "Pi pad"),
        ):
            self._kind.addItem(label)
        self._series = QLabel("—")
        self._shunt = QLabel("—")
        form = QFormLayout(self)
        form.addRow("Attenuation (dB)", self._db)
        form.addRow("System Z0 (Ohm)", self._z0)
        form.addRow("Topology", self._kind)
        form.addRow("Series R", self._series)
        form.addRow("Shunt R", self._shunt)
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
