"""Selector/index consistency regression tests (GUI).

These guard the combo boxes that map the selected index to a value: they must
stay in sync with the list they are populated from. The air-core wire-mode
selector is covered in ``test_gui_smoke`` (it also switches a stacked widget).
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


def test_band_preset_selection_matches_items() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import BandPresetDialog
    from filterdesk.services.bands import ALL_PRESETS

    app = QApplication.instance() or QApplication([])
    dialog = BandPresetDialog()
    for index, band in enumerate(ALL_PRESETS):
        kind_index = index % len(dialog._KINDS)
        dialog._band.setCurrentIndex(index)
        dialog._kind.setCurrentIndex(kind_index)
        selected, kind = dialog.selection()
        assert selected == band
        assert kind == dialog._KINDS[kind_index][0]
    dialog.close()
    assert app is not None


def test_attenuator_kind_matches_index() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.components_std import AttenuatorKind
    from filterdesk.gui.widgets import AttenuatorDialog

    app = QApplication.instance() or QApplication([])
    dialog = AttenuatorDialog()
    expected = (AttenuatorKind.TEE, AttenuatorKind.PI)
    for index, kind in enumerate(expected):
        dialog._kind.setCurrentIndex(index)
        assert dialog._kind_value() == kind
    dialog.close()
    assert app is not None


def test_matching_topology_matches_index() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import MatchingDialog

    app = QApplication.instance() or QApplication([])
    dialog = MatchingDialog()
    for index, (topology, _label) in enumerate(dialog._TOPOS):
        dialog._topo.setCurrentIndex(index)
        assert dialog._topology() == topology
    dialog.close()
    assert app is not None


def test_toroid_core_matches_index() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import CoilCalculatorDialog

    app = QApplication.instance() or QApplication([])
    dialog = CoilCalculatorDialog()
    page = dialog.toroid
    for index, core in enumerate(page._cores):
        page._core.setCurrentIndex(index)
        assert page.selected_core() == core
    dialog.close()
    assert app is not None


def test_spec_panel_response_repopulates_topologies() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.enums import FilterResponse, TopologyId
    from filterdesk.gui.panels.spec_panel import SpecPanel

    app = QApplication.instance() or QApplication([])
    panel = SpecPanel()
    panel._response.setCurrentIndex(
        panel._response.findData(FilterResponse.BAND_PASS.value)
    )
    assert panel._topology.count() == 2
    assert (
        panel._topology.itemData(0)
        == TopologyId.LADDER_BP_SERIES_RES_INPUT.value
    )
    assert panel._cutoff.isHidden()
    assert not panel._f_center.isHidden()
    panel.close()
    assert app is not None
