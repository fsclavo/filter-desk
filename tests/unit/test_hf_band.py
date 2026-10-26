"""HF receive-band product workflow."""

from __future__ import annotations

import pytest

from filterdesk.domain.enums import FilterResponse
from filterdesk.services.bands import find_band
from filterdesk.services.hf_band import (
    HfBandDesignError,
    HfBandRequest,
    design_hf_band_filter,
)


def _band(name: str):
    return find_band(name)


def test_40m_design_selects_lowest_working_order() -> None:
    request = HfBandRequest(_band("40 m"), min_stopband_attenuation_db=30.0)
    design = design_hf_band_filter(request)
    assert design.ok
    assert design.selected is not None
    assert design.selected.order == 6
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


@pytest.mark.parametrize("name", ["160 m", "80 m", "20 m", "10 m"])
def test_other_bands_have_candidates(name: str) -> None:
    design = design_hf_band_filter(
        HfBandRequest(_band(name), min_stopband_attenuation_db=30.0)
    )
    assert design.selected is not None
    assert design.selected.stopband_ok
    assert design.selected.passband_ok


def test_order_limit_reports_no_solution() -> None:
    design = design_hf_band_filter(
        HfBandRequest(
            _band("20 m"),
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
        ({"max_insertion_loss_db": 0.0}, "insertion"),
        ({"min_stopband_attenuation_db": 0.0}, "stopband"),
        ({"stopband_guard": 1.0}, "guard"),
        ({"max_order": 1}, "max_order"),
    ],
)
def test_request_validation(kwargs, message: str) -> None:
    base = {"band": _band("40 m")}
    base.update(kwargs)
    with pytest.raises(HfBandDesignError, match=message):
        HfBandRequest(**base)


def test_wizard_dialog(qtbot) -> None:
    from filterdesk.gui.widgets import HfBandWizardDialog

    dialog = HfBandWizardDialog()
    qtbot.addWidget(dialog)
    design = dialog.current_design()
    assert design is not None and design.ok
    assert dialog.result_spec() is not None
    assert dialog.result_band() is not None
    assert dialog._table.rowCount() == len(design.candidates)
    assert dialog._apply_button.isEnabled()
    dialog._min_stop.setText("200")
    dialog._run_design()
    assert not dialog._apply_button.isEnabled()


def test_design_menu_has_hf_wizard() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    design = next(
        a.menu() for a in window.menuBar().actions() if "&Design" in a.text()
    )
    labels = [a.text().replace("&", "") for a in design.actions()]
    assert any("HF band filter wizard" in label for label in labels)
    window.close()
    assert app is not None
