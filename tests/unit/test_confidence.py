"""Model confidence registry, GUI badge/dialog and BOM assumptions."""

from __future__ import annotations

from pathlib import Path

import pytest

from filterdesk.confidence import (
    ITEMS,
    ConfidenceLevel,
    assumptions_for_circuit,
    confidence_for,
)
from filterdesk.domain.circuit import BalunSpec, Circuit, IdealResistor, Port
from filterdesk.io.build_sheet import write_build_sheet


def _circuit(balun: BalunSpec | None = None) -> Circuit:
    return Circuit(
        elements=[IdealResistor("R1", 50.0, "in", "out")],
        port_in=Port("in", "in", 50.0),
        port_out=Port("out", "out", 50.0),
        output_balun=balun,
    )


def test_registry_has_expected_levels() -> None:
    assert len(ITEMS) >= 10
    assert confidence_for("synthesis").level is ConfidenceLevel.VALIDATED
    assert confidence_for("vna").level is ConfidenceLevel.EXPERIMENTAL
    assert confidence_for("thermal").level is ConfidenceLevel.ESTIMATED
    assert confidence_for("distributed").level is ConfidenceLevel.NOT_EVALUATED
    with pytest.raises(KeyError):
        confidence_for("nope")


def test_assumptions_plain_and_balun() -> None:
    plain = assumptions_for_circuit(_circuit())
    assert any("ideal R/L/C" in item for item in plain)
    balun = BalunSpec(
        kind="unun",
        topology="autotransformer",
        turns_ratio=0.5,
        total_turns=8,
        turns=4,
        core="FT140-43",
    )
    with_balun = assumptions_for_circuit(_circuit(balun))
    assert any("BAL1" in item for item in with_balun)


def test_confidence_badge_and_dialog(qtbot) -> None:
    from filterdesk.gui.widgets import ConfidenceBadge, ConfidenceDialog

    badge = ConfidenceBadge("microstrip")
    qtbot.addWidget(badge)
    assert badge.item is not None
    assert badge.item.level is ConfidenceLevel.ESTIMATED
    assert "estimated" in badge.text().lower()
    tip = badge.toolTip().lower()
    assert "quasi-static" in tip or "hammerstad" in tip
    badge.set_key("vna")
    assert badge.item is not None
    assert badge.item.level is ConfidenceLevel.EXPERIMENTAL

    dialog = ConfidenceDialog()
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Model confidence"


def test_build_sheet_has_assumptions(tmp_path: Path) -> None:
    circuit = _circuit()
    md = tmp_path / "build.md"
    write_build_sheet(circuit, md)
    text = md.read_text(encoding="utf-8")
    assert "## Assumptions" in text
    assert "ideal R/L/C" in text

    html = tmp_path / "build.html"
    write_build_sheet(circuit, html)
    assert "<h2>Assumptions</h2>" in html.read_text(encoding="utf-8")


def test_help_menu_has_confidence() -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    menus = {
        a.text(): a.menu() for a in window.menuBar().actions() if a.menu()
    }
    help_menu = menus.get("&Help")
    assert help_menu is not None
    assert any("confidence" in a.text().lower() for a in help_menu.actions())
    window.close()
    assert app is not None
