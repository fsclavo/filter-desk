"""PyQtGraph SVG export patch tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def test_svg_export_after_qt6_patch() -> None:
    from pyqtgraph.exporters import SVGExporter
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.panels.plot_panel import PlotPanel
    from filterdesk.gui.pyqtgraph_patches import apply_pyqtgraph_svg_exporter_qt6_patch
    from filterdesk.services.session import DesignSession

    apply_pyqtgraph_svg_exporter_qt6_patch()
    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    panel = PlotPanel()
    panel.resize(640, 400)
    panel.set_result(session.analysis)
    panel._cursors[0].setPos(float(np.log10(140e6)))
    panel._cursors[0].setVisible(True)

    out = Path(tempfile.mkdtemp()) / "plot.svg"
    SVGExporter(panel._mag.plotItem).export(fileName=str(out))
    text = out.read_text(encoding="utf-8")
    assert out.stat().st_size > 500
    assert "<svg" in text
    assert app is not None
