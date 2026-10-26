"""Specification editor panel."""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from filterdesk.domain.enums import (
    ApproximationFamily,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import (
    FilterSpec,
    SpecValidationError,
    default_cutoff_definition,
    default_topology,
)
from filterdesk.domain.units import format_engineering, parse_si
from filterdesk.gui.i18n import (
    family_label,
    response_label,
    topology_label,
    tr,
)
from filterdesk.gui.widgets import EngineeringLineEdit
from filterdesk.synthesis.order_estimate import (
    OrderEstimateError,
    estimate_minimum_order,
    supports_order_estimation,
)

E = TypeVar("E", bound=Enum)


def _enum_from_combo(combo: QComboBox, enum_cls: type[E]) -> E:
    """Read combo userData; PySide6 stores StrEnum values as plain str."""
    data = combo.currentData()
    if data is None:
        raise SpecValidationError(f"no selection in {enum_cls.__name__}")
    if isinstance(data, enum_cls):
        return data
    return enum_cls(str(data))


def _fmt_hz(hz: float) -> str:
    if hz >= 1e9:
        return f"{hz / 1e9:g}G"
    if hz >= 1e6:
        return f"{hz / 1e6:g}M"
    if hz >= 1e3:
        return f"{hz / 1e3:g}k"
    return f"{hz:g}"


class SpecPanel(QWidget):
    spec_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._family = QComboBox()
        for fam in (
            ApproximationFamily.BUTTERWORTH,
            ApproximationFamily.CHEBYSHEV_TYPE_I,
            ApproximationFamily.CHEBYSHEV_TYPE_II,
            ApproximationFamily.ELLIPTIC,
            ApproximationFamily.BESSEL,
            ApproximationFamily.GAUSSIAN,
            ApproximationFamily.LEGENDRE,
            ApproximationFamily.CONSTANT_K,
            ApproximationFamily.M_DERIVED,
        ):
            self._family.addItem(family_label(fam), fam.value)
        self._response = QComboBox()
        for response in (
            FilterResponse.LOW_PASS,
            FilterResponse.HIGH_PASS,
            FilterResponse.BAND_PASS,
            FilterResponse.BAND_STOP,
        ):
            self._response.addItem(response_label(response), response.value)
        self._order = QSpinBox()
        self._order.setRange(1, 21)
        self._order.setValue(7)
        self._estimate_btn = QPushButton(tr("Estimate N"))
        self._estimate_btn.setToolTip(
            tr(
                "Minimum order from Ap/As and pass/stop edges "
                "(LP/HP classical families)"
            )
        )
        self._cutoff = EngineeringLineEdit()
        self._cutoff.setText("140M")
        self._f_stop = EngineeringLineEdit()
        self._f_stop.setText("280M")
        self._f_center = EngineeringLineEdit()
        self._f_center.setText("100M")
        self._bandwidth = EngineeringLineEdit()
        self._bandwidth.setText("20M")
        self._ripple = QDoubleSpinBox()
        self._ripple.setDecimals(4)
        self._ripple.setRange(0.0001, 10.0)
        self._ripple.setValue(0.01)
        self._stop_att = QDoubleSpinBox()
        self._stop_att.setDecimals(2)
        self._stop_att.setRange(0.1, 200.0)
        self._stop_att.setValue(40.0)
        self._m_param = QDoubleSpinBox()
        self._m_param.setDecimals(4)
        self._m_param.setRange(0.01, 0.99)
        self._m_param.setValue(0.6)
        self._zs = EngineeringLineEdit()
        self._zs.setText("50")
        self._zl = EngineeringLineEdit()
        self._zl.setText("50")
        self._topology = QComboBox()
        self._populate_topologies()

        self._cutoff_label = QLabel(tr("Passband f / cutoff"))
        self._f_stop_label = QLabel(tr("Stopband f (est.)"))
        self._center_label = QLabel(tr("Center"))
        self._bw_label = QLabel(tr("Bandwidth"))
        self._ripple_label = QLabel(tr("Ripple / Ap (dB)"))
        self._stop_label = QLabel(tr("Stopband As (dB)"))
        self._m_label = QLabel(tr("m parameter"))

        order_row = QHBoxLayout()
        order_row.addWidget(self._order)
        order_row.addWidget(self._estimate_btn)

        form = QFormLayout()
        form.addRow(tr("Family"), self._family)
        form.addRow(tr("Response"), self._response)
        form.addRow(tr("Order"), order_row)
        form.addRow(self._cutoff_label, self._cutoff)
        form.addRow(self._f_stop_label, self._f_stop)
        form.addRow(self._center_label, self._f_center)
        form.addRow(self._bw_label, self._bandwidth)
        form.addRow(self._ripple_label, self._ripple)
        form.addRow(self._stop_label, self._stop_att)
        form.addRow(self._m_label, self._m_param)
        form.addRow(tr("Zsource"), self._zs)
        form.addRow(tr("Zload"), self._zl)
        form.addRow(tr("Topology"), self._topology)

        self._note = QLabel()
        self._note.setWordWrap(True)
        self._note.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._note)
        layout.addStretch(1)

        self._family.currentIndexChanged.connect(self._on_family_changed)
        self._response.currentIndexChanged.connect(self._on_response_changed)
        self._cutoff.editingFinished.connect(self.spec_changed.emit)
        self._f_stop.editingFinished.connect(self.spec_changed.emit)
        self._f_center.editingFinished.connect(self.spec_changed.emit)
        self._bandwidth.editingFinished.connect(self.spec_changed.emit)
        self._zs.editingFinished.connect(self.spec_changed.emit)
        self._zl.editingFinished.connect(self.spec_changed.emit)
        self._order.valueChanged.connect(lambda *_: self.spec_changed.emit())
        self._order.valueChanged.connect(lambda *_: self._update_note())
        self._ripple.valueChanged.connect(lambda *_: self.spec_changed.emit())
        self._stop_att.valueChanged.connect(lambda *_: self.spec_changed.emit())
        self._m_param.valueChanged.connect(lambda *_: self.spec_changed.emit())
        self._family.currentIndexChanged.connect(lambda *_: self.spec_changed.emit())
        self._response.currentIndexChanged.connect(lambda *_: self.spec_changed.emit())
        self._topology.currentIndexChanged.connect(lambda *_: self.spec_changed.emit())
        self._estimate_btn.clicked.connect(self._on_estimate_order)
        self._on_family_changed()
        self._update_freq_fields_visibility()
        self._update_note()

    def _populate_topologies(self) -> None:
        self._topology.clear()
        response = _enum_from_combo(self._response, FilterResponse)
        items: list[TopologyId]
        if response == FilterResponse.LOW_PASS:
            items = [
                TopologyId.LADDER_LP_SERIES_L_INPUT,
                TopologyId.LADDER_LP_SHUNT_C_INPUT,
            ]
        elif response == FilterResponse.HIGH_PASS:
            items = [
                TopologyId.LADDER_HP_SERIES_C_INPUT,
                TopologyId.LADDER_HP_SHUNT_L_INPUT,
            ]
        elif response == FilterResponse.BAND_PASS:
            items = [
                TopologyId.LADDER_BP_SERIES_RES_INPUT,
                TopologyId.LADDER_BP_SHUNT_RES_INPUT,
            ]
        else:
            items = [
                TopologyId.LADDER_BS_SERIES_TANK_INPUT,
                TopologyId.LADDER_BS_SHUNT_TANK_INPUT,
            ]
        for topo in items:
            self._topology.addItem(topology_label(topo), topo.value)

    def _on_family_changed(self) -> None:
        family = _enum_from_combo(self._family, ApproximationFamily)
        needs_ripple = family in (
            ApproximationFamily.CHEBYSHEV_TYPE_I,
            ApproximationFamily.ELLIPTIC,
            ApproximationFamily.BUTTERWORTH,
            ApproximationFamily.CHEBYSHEV_TYPE_II,
        )
        needs_as = family in (
            ApproximationFamily.CHEBYSHEV_TYPE_II,
            ApproximationFamily.ELLIPTIC,
            ApproximationFamily.BUTTERWORTH,
            ApproximationFamily.CHEBYSHEV_TYPE_I,
        )
        needs_m = family == ApproximationFamily.M_DERIVED
        self._ripple.setEnabled(needs_ripple)
        self._ripple_label.setEnabled(needs_ripple)
        self._stop_att.setEnabled(needs_as)
        self._stop_label.setEnabled(needs_as)
        self._m_param.setEnabled(needs_m)
        self._m_label.setEnabled(needs_m)
        can_est = supports_order_estimation(family)
        self._estimate_btn.setEnabled(can_est)
        self._f_stop.setEnabled(can_est)
        self._f_stop_label.setEnabled(can_est)
        self._update_note()
        if family == ApproximationFamily.ELLIPTIC and self._order.value() < 2:
            self._order.setValue(2)
        if family == ApproximationFamily.BUTTERWORTH and self._ripple.value() < 0.1:
            self._ripple.setValue(3.0)
        if (
            family == ApproximationFamily.CHEBYSHEV_TYPE_II
            and self._ripple.value() < 0.1
        ):
            self._ripple.setValue(3.0)
        self._update_freq_fields_visibility()

    def _update_note(self) -> None:
        family = _enum_from_combo(self._family, ApproximationFamily)
        if (
            family == ApproximationFamily.CHEBYSHEV_TYPE_I
            and self._order.value() % 2 == 0
        ):
            self._note.setText(
                tr(
                    "Even-order Chebyshev I: classical equal-ripple prototype "
                    "with an ideal output transformer (ADR-017); response and "
                    "element values match the textbook tables."
                )
            )
            self._note.setVisible(True)
        else:
            self._note.setVisible(False)

    def _on_response_changed(self) -> None:
        self._populate_topologies()
        self._update_freq_fields_visibility()

    def _update_freq_fields_visibility(self) -> None:
        response = _enum_from_combo(self._response, FilterResponse)
        is_bp_bs = response in (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP)
        self._cutoff.setVisible(not is_bp_bs)
        self._cutoff_label.setVisible(not is_bp_bs)
        self._f_stop.setVisible(not is_bp_bs)
        self._f_stop_label.setVisible(not is_bp_bs)
        self._f_center.setVisible(is_bp_bs)
        self._center_label.setVisible(is_bp_bs)
        self._bandwidth.setVisible(is_bp_bs)
        self._bw_label.setVisible(is_bp_bs)
        family = _enum_from_combo(self._family, ApproximationFamily)
        can_est = supports_order_estimation(family) and not is_bp_bs
        self._estimate_btn.setEnabled(can_est)

    def _on_estimate_order(self) -> None:
        try:
            family = _enum_from_combo(self._family, ApproximationFamily)
            response = _enum_from_combo(self._response, FilterResponse)
            f_pass = parse_si(self._cutoff.text())
            f_stop = parse_si(self._f_stop.text())
            ap = float(self._ripple.value())
            as_db = float(self._stop_att.value())
            result = estimate_minimum_order(
                family,
                response,
                f_pass_hz=f_pass,
                f_stop_hz=f_stop,
                passband_attenuation_db=ap,
                stopband_attenuation_db=as_db,
            )
        except (OrderEstimateError, SpecValidationError, ValueError) as exc:
            QMessageBox.warning(self, tr("Estimate order"), str(exc))
            return
        self._order.setValue(min(21, result.order))
        if family == ApproximationFamily.CHEBYSHEV_TYPE_II:
            self._cutoff.setText(_fmt_hz(result.f_stop_hz))
        msg = tr(
            "Minimum order N = {order}\nΩs = {ratio:.6g}\nNatural f ≈ {freq}"
            "\n\n{notes}",
            order=result.order,
            ratio=result.omega_ratio,
            freq=format_engineering(result.natural_freq_hz, "Hz"),
            notes=result.notes,
        )
        QMessageBox.information(self, tr("Estimate order"), msg)
        self.spec_changed.emit()

    def set_spec(self, spec: FilterSpec) -> None:
        self._family.blockSignals(True)
        self._response.blockSignals(True)
        self._topology.blockSignals(True)
        fi = self._family.findData(spec.family.value)
        if fi >= 0:
            self._family.setCurrentIndex(fi)
        ri = self._response.findData(spec.response.value)
        if ri >= 0:
            self._response.setCurrentIndex(ri)
        self._populate_topologies()
        ti = self._topology.findData(spec.topology_id.value)
        if ti >= 0:
            self._topology.setCurrentIndex(ti)
        self._order.setValue(spec.order)
        if spec.cutoff_hz > 0.0:
            self._cutoff.setText(_fmt_hz(spec.cutoff_hz))
        if spec.f_center_hz is not None:
            self._f_center.setText(_fmt_hz(spec.f_center_hz))
        if spec.bandwidth_hz is not None:
            self._bandwidth.setText(_fmt_hz(spec.bandwidth_hz))
        if spec.passband_ripple_db is not None:
            self._ripple.setValue(spec.passband_ripple_db)
        elif spec.family == ApproximationFamily.BUTTERWORTH:
            self._ripple.setValue(3.0)
        elif spec.family == ApproximationFamily.CHEBYSHEV_TYPE_II:
            self._ripple.setValue(3.0)
        if spec.stopband_attenuation_db is not None:
            self._stop_att.setValue(spec.stopband_attenuation_db)
        if spec.m_parameter is not None:
            self._m_param.setValue(spec.m_parameter)
        self._zs.setText(f"{spec.z_source_ohm:g}")
        self._zl.setText(f"{spec.z_load_ohm:g}")
        self._on_family_changed()
        self._update_freq_fields_visibility()
        self._update_note()
        self._family.blockSignals(False)
        self._response.blockSignals(False)
        self._topology.blockSignals(False)

    def build_spec(self) -> FilterSpec:
        family = _enum_from_combo(self._family, ApproximationFamily)
        response = _enum_from_combo(self._response, FilterResponse)
        topo_data = self._topology.currentData()
        if topo_data is None:
            topology = default_topology(response)
        else:
            topology = TopologyId(str(topo_data))
        ripple = (
            float(self._ripple.value())
            if family
            in (
                ApproximationFamily.CHEBYSHEV_TYPE_I,
                ApproximationFamily.ELLIPTIC,
            )
            else None
        )
        stop_att = (
            float(self._stop_att.value())
            if family
            in (
                ApproximationFamily.CHEBYSHEV_TYPE_II,
                ApproximationFamily.ELLIPTIC,
            )
            else None
        )
        m_param = (
            float(self._m_param.value())
            if family == ApproximationFamily.M_DERIVED
            else None
        )
        cutoff_def = default_cutoff_definition(family)
        order = int(self._order.value())
        z_source_ohm = parse_si(self._zs.text())
        z_load_ohm = parse_si(self._zl.text())
        if response in (FilterResponse.BAND_PASS, FilterResponse.BAND_STOP):
            return FilterSpec(
                family=family,
                response=response,
                order=order,
                z_source_ohm=z_source_ohm,
                z_load_ohm=z_load_ohm,
                topology_id=topology,
                cutoff_definition=cutoff_def,
                cutoff_hz=0.0,
                f_center_hz=parse_si(self._f_center.text()),
                bandwidth_hz=parse_si(self._bandwidth.text()),
                passband_ripple_db=ripple,
                stopband_attenuation_db=stop_att,
                m_parameter=m_param,
            )
        return FilterSpec(
            family=family,
            response=response,
            order=order,
            z_source_ohm=z_source_ohm,
            z_load_ohm=z_load_ohm,
            topology_id=topology,
            cutoff_definition=cutoff_def,
            cutoff_hz=parse_si(self._cutoff.text()),
            passband_ripple_db=ripple,
            stopband_attenuation_db=stop_att,
            m_parameter=m_param,
        )
