"""Semantic/visual QA for schematic and exported diagrams."""

from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def _schematic_circuit() -> object:
    from filterdesk.services.bands import BandKind, band_preset_spec, find_band
    from filterdesk.synthesis import synthesize

    return synthesize(band_preset_spec(find_band("40m"), BandKind.BPF)).circuit


def test_schematic_geometry_labels_and_render() -> None:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication, QGraphicsSimpleTextItem

    from filterdesk.gui.panels.schematic_view import SchematicPanel

    app = QApplication.instance() or QApplication([])
    circuit = _schematic_circuit()
    panel = SchematicPanel()
    panel.resize(900, 300)
    panel.set_circuit(circuit)  # type: ignore[arg-type]
    panel.show()
    app.processEvents()

    ids = {element.id for element in circuit.elements}  # type: ignore[attr-defined]
    assert set(panel._groups) == ids
    scene_rect = panel._scene.sceneRect()
    rects: list[tuple[str, QRectF]] = []
    for element_id, group in panel._groups.items():
        rect = group.sceneBoundingRect()
        assert not rect.isEmpty()
        assert scene_rect.contains(rect)
        rects.append((element_id, rect))
    for i, (id_a, rect_a) in enumerate(rects):
        for id_b, rect_b in rects[i + 1 :]:
            assert not rect_a.intersects(rect_b), f"schematic overlap: {id_a}/{id_b}"

    labels = [
        item.text()
        for item in panel._scene.items()
        if isinstance(item, QGraphicsSimpleTextItem)
    ]
    for element_id in ids:
        assert any(label.startswith(element_id) for label in labels)
    assert any(label.startswith("Zs =") for label in labels)
    assert any(label.startswith("Zl =") for label in labels)

    image = QImage(900, 300, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    panel._scene.render(painter)
    painter.end()
    background = panel._scene.backgroundBrush().color()
    non_background = 0
    for x in range(0, image.width(), 8):
        for y in range(0, image.height(), 8):
            if image.pixelColor(x, y) != background:
                non_background += 1
    assert non_background > 100
    panel.close()


def test_plot_and_smith_svg_have_axes_labels_and_geometry(tmp_path: Path) -> None:
    from pyqtgraph.exporters import SVGExporter
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.panels.plot_panel import PlotPanel
    from filterdesk.gui.pyqtgraph_patches import apply_pyqtgraph_svg_exporter_qt6_patch
    from filterdesk.plotting.smith_export import export_smith_chart
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    apply_pyqtgraph_svg_exporter_qt6_patch()
    session = DesignSession()
    result = session.synthesize_and_analyze()
    panel = PlotPanel()
    panel.set_result(result)
    panel.resize(1000, 500)
    app.processEvents()

    plot_svg = tmp_path / "magnitude.svg"
    SVGExporter(panel._mag.plotItem).export(fileName=str(plot_svg))
    plot_text = plot_svg.read_text(encoding="utf-8")
    assert "<svg" in plot_text
    assert "S21" in plot_text and "S11" in plot_text
    assert "Frequency" in plot_text
    assert plot_text.count("<polyline") > 30

    smith_svg = tmp_path / "smith.svg"
    export_smith_chart(result, smith_svg)
    smith_text = smith_svg.read_text(encoding="utf-8")
    assert "<svg" in smith_text
    assert "Smith chart" in smith_text
    assert "S11" in smith_text and "S22" in smith_text
    assert "Re(" in smith_text and "Im(" in smith_text
    root = ElementTree.fromstring(smith_text)
    assert len(root.findall(".//{http://www.w3.org/2000/svg}path")) > 20
    panel.close()
