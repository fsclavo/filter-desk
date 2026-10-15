"""Shared GUI widgets."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from filterdesk.components_std import ESeries, SnapStrategy
from filterdesk.domain.units import parse_si


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

