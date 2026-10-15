"""Spec panel combo / enum handling tests."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def test_spec_panel_build_roundtrip() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.domain.enums import (
        ApproximationFamily,
        FilterResponse,
        TopologyId,
    )
    from filterdesk.domain.specs import FilterSpec
    from filterdesk.gui.panels.spec_panel import SpecPanel
    from filterdesk.services.session import default_milestone_spec

    app = QApplication.instance() or QApplication([])
    panel = SpecPanel()
    panel.set_spec(default_milestone_spec())
    spec = panel.build_spec()
    assert spec.family == ApproximationFamily.CHEBYSHEV_TYPE_I
    assert spec.response == FilterResponse.HIGH_PASS
    assert spec.topology_id == TopologyId.LADDER_HP_SERIES_C_INPUT
    assert spec.order == 7
    assert abs(spec.cutoff_hz - 140e6) < 1.0

    # Butterworth path
    panel.set_spec(
        FilterSpec(
            family=ApproximationFamily.BUTTERWORTH,
            response=FilterResponse.LOW_PASS,
            order=5,
            cutoff_hz=1e6,
            z_source_ohm=50.0,
            z_load_ohm=50.0,
            topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
            cutoff_definition=__import__(
                "filterdesk.domain.enums", fromlist=["CutoffDefinition"]
            ).CutoffDefinition.HALF_POWER_3DB,
        )
    )
    spec2 = panel.build_spec()
    assert spec2.family == ApproximationFamily.BUTTERWORTH
    assert spec2.passband_ripple_db is None
    assert app is not None
