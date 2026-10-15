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

