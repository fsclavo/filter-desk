"""Unified band-filter wizard: quick presets and guided order search."""

from __future__ import annotations

import pytest

from filterdesk.domain.enums import FilterResponse
from filterdesk.services.bands import (
    ALL_PRESETS,
    BandKind,
    band_preset_spec,
    find_band,
)
from filterdesk.services.hf_band import (
    BandFilterDesignError,
    BandFilterRequest,
    design_band_filter,
)


def _band(name: str):
    return find_band(name)


def test_40m_bpf_selects_lowest_odd_order() -> None:
    request = BandFilterRequest(_band("40 m"), BandKind.BPF)
    design = design_band_filter(request)
    assert design.ok
    assert design.selected is not None
    assert design.selected.order == 7
    assert design.selected.passband_ok
    assert design.selected.stopband_ok
    assert design.selected.spec.response is FilterResponse.BAND_PASS
    assert design.selected.spec.f_center_hz == pytest.approx(
        _band("40 m").center_hz
    )
    assert design.selected.spec.bandwidth_hz == pytest.approx(
        (_band("40 m").high_hz - _band("40 m").low_hz) * 1.2
    )
    assert design.analysis is not None
    assert design.notes


def test_40m_bpf_has_no_ideal_output_transformer() -> None:
    from filterdesk.synthesis import synthesize

    design = design_band_filter(BandFilterRequest(_band("40 m"), BandKind.BPF))
    assert design.selected is not None
    circuit = synthesize(design.selected.spec).circuit
    assert circuit.output_transformer_ratio == 1.0
    assert circuit.output_balun is None


@pytest.mark.parametrize("band", ALL_PRESETS)
@pytest.mark.parametrize("kind", list(BandKind))
def test_every_band_and_kind_has_a_solution(band, kind: BandKind) -> None:
    design = design_band_filter(BandFilterRequest(band, kind))
    assert design.selected is not None
    assert design.selected.passband_ok
    assert design.selected.stopband_ok
    responses = {
        BandKind.LPF: FilterResponse.LOW_PASS,
        BandKind.HPF: FilterResponse.HIGH_PASS,
        BandKind.BPF: FilterResponse.BAND_PASS,
        BandKind.BSF: FilterResponse.BAND_STOP,
    }
    assert design.selected.spec.response is responses[kind]


def test_lpf_reports_harmonic_rejection() -> None:
    design = design_band_filter(BandFilterRequest(_band("40 m"), BandKind.LPF))
    assert design.selected is not None
    candidate = design.selected
    assert candidate.harmonic_2f_db is not None
    assert candidate.harmonic_3f_db is not None
    assert candidate.harmonic_2f_db < -20.0
    assert candidate.harmonic_3f_db < candidate.harmonic_2f_db
    assert any("harmonic" in note for note in design.notes)


def test_bsf_uses_allocation_as_stopband() -> None:
    band = _band("AM broadcast")
    design = design_band_filter(BandFilterRequest(band, BandKind.BSF))
    assert design.selected is not None
    assert design.selected.spec.response is FilterResponse.BAND_STOP
    assert design.selected.order % 2 == 1
    assert design.selected.stopband_low_db is not None
    assert design.selected.stopband_high_db is not None
    assert design.selected.stopband_low_db <= -30.0
    assert design.selected.stopband_high_db <= -30.0


def test_order_limit_reports_no_solution() -> None:
    design = design_band_filter(
        BandFilterRequest(
            _band("20 m"),
            BandKind.BPF,
            min_stopband_attenuation_db=80.0,
            max_order=3,
        )
    )
    assert not design.ok
    assert design.selected is None
    assert any("no order" in note for note in design.notes)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"z_source_ohm": 0.0}, "impedances"),
        ({"passband_ripple_db": 0.0}, "ripple"),
        ({"max_insertion_loss_db": 0.01}, "insertion loss"),
        ({"min_stopband_attenuation_db": 0.0}, "stopband"),
        ({"stopband_guard": 1.0}, "guard"),
        ({"max_order": 1}, "max_order"),
        (
            {"kind": BandKind.LPF, "pass_edge_hz": 10e6, "stop_edge_hz": 9e6},
            "stop edge",
        ),
        (
            {"kind": BandKind.HPF, "pass_edge_hz": 10e6, "stop_edge_hz": 11e6},
            "stop edge",
        ),
    ],
)
def test_request_validation(kwargs, message: str) -> None:
    base = {"band": _band("40 m"), "kind": BandKind.BPF}
    base.update(kwargs)
    with pytest.raises(BandFilterDesignError, match=message):
        BandFilterRequest(**base)


def test_default_lpf_hpf_edges() -> None:
    band = _band("40 m")
    lpf = BandFilterRequest(band, BandKind.LPF)
    assert lpf.pass_edge == pytest.approx(band.high_hz)
    assert lpf.stop_edge == pytest.approx(band.high_hz * 1.5)
    hpf = BandFilterRequest(band, BandKind.HPF)
    assert hpf.pass_edge == pytest.approx(band.low_hz)
    assert hpf.stop_edge == pytest.approx(band.low_hz / 1.5)


def test_wizard_quick_and_guided_modes(qtbot) -> None:
    from filterdesk.gui.widgets import BandFilterWizardDialog

    dialog = BandFilterWizardDialog()
    qtbot.addWidget(dialog)
    assert dialog._mode.currentIndex() == 0
    assert dialog.result_spec() == band_preset_spec(_band("40 m"), BandKind.LPF)
    assert dialog._apply_button.isEnabled()

    dialog._mode.setCurrentIndex(1)
    design = dialog.current_design()
    assert design is not None and design.ok
    assert dialog.result_spec() is not None
    assert dialog.result_band() == _band("40 m")
    assert dialog._table.rowCount() == len(design.candidates)
    assert dialog._apply_button.isEnabled()

    dialog._min_stop.setText("200")
    dialog._run_design()
    assert not dialog._apply_button.isEnabled()

    dialog._min_stop.setText("30")
    am_index = dialog._band.findText("AM broadcast")
    dialog._band.setCurrentIndex(am_index)
    dialog._kind.setCurrentIndex(3)
    design = dialog.current_design()
    assert design is not None and design.ok
    assert dialog.result_spec() is not None
    assert dialog.result_spec().response is FilterResponse.BAND_STOP


def test_design_menu_has_unified_wizard() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    design = next(
        a.menu() for a in window.menuBar().actions() if "&Design" in a.text()
    )
    labels = [a.text().replace("&", "") for a in design.actions()]
    assert any("Band filter wizard" in label for label in labels)
    assert not any("Band preset" in label for label in labels)
    assert not any("HF band filter wizard" in label for label in labels)
    window.close()
    assert app is not None
