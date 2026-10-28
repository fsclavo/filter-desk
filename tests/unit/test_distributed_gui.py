"""GUI integration for distributed microstrip elements."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def _spec() -> object:
    from filterdesk.domain.enums import (
        ApproximationFamily,
        CutoffDefinition,
        FilterResponse,
        TopologyId,
    )
    from filterdesk.domain.specs import FilterSpec

    return FilterSpec(
        family=ApproximationFamily.BUTTERWORTH,
        response=FilterResponse.LOW_PASS,
        order=3,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
        cutoff_hz=100e6,
    )


def test_distributed_dialog_builds_preview() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import DistributedSynthesisDialog

    _ = QApplication.instance() or QApplication([])
    dialog = DistributedSynthesisDialog(_spec())  # type: ignore[arg-type]
    design = dialog.design()
    assert design is not None
    assert len(design.circuit.elements) == 3
    assert "TL1" in dialog._preview.text()
    assert "Z0=" in dialog._preview.text()
    dialog.close()


def test_component_table_and_schematic_accept_distributed() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.panels.component_table import ComponentTablePanel
    from filterdesk.gui.panels.schematic_view import SchematicPanel
    from filterdesk.synthesis.distributed import design_distributed_lowpass

    _ = QApplication.instance() or QApplication([])
    design = design_distributed_lowpass(_spec(), "FR4")  # type: ignore[arg-type]

    table = ComponentTablePanel()
    table.set_circuit(design.circuit)
    assert table._table.rowCount() == 3
    assert table._table.item(0, 2).text() == "microstrip_line"
    assert not (
        table._table.item(0, 3).flags()
        & __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.ItemFlag.ItemIsEditable
    )

    schematic = SchematicPanel()
    schematic.set_circuit(design.circuit)
    assert set(schematic._groups) == {"TL1", "TL2", "TL3"}

    table.close()
    schematic.close()


def test_filter_confidence_adds_distributed() -> None:
    from filterdesk.confidence import filter_confidence_items
    from filterdesk.synthesis.distributed import design_distributed_lowpass

    design = design_distributed_lowpass(_spec(), "FR4")  # type: ignore[arg-type]
    keys = {item.key for item in filter_confidence_items(design.circuit)}
    assert "distributed" in keys


def test_transformer_dialog_exports_ruthroff_spice(tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication, QFileDialog

    from filterdesk.gui.widgets import TransformerDialog

    _ = QApplication.instance() or QApplication([])
    dialog = TransformerDialog()
    dialog._kind.setCurrentText("ruthroff")
    dialog._z_low.setText("50")
    dialog._z_high.setText("200")
    dialog._frequency.setText("3.5M")
    dialog._frequency_max.setText("30M")
    dialog._power.setText("5")
    dialog._line_z0.setText("100")
    dialog._line_length.setText("0.5")
    dialog._recompute()
    assert dialog._export_tlt_button.isEnabled()

    target = tmp_path / "ruthroff.cir"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "")),
    )
    dialog._export_tlt_spice()
    assert target.is_file()
    assert "TL1 in 0 0 outm" in target.read_text(encoding="utf-8")
    dialog.close()
