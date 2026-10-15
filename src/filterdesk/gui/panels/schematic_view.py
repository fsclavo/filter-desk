"""Ladder schematic view with selectable elements."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QContextMenuEvent,
    QFont,
    QPainter,
    QPalette,
    QPen,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

from filterdesk.domain.circuit import (
    Circuit,
    Element,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealSeriesLC,
)
from filterdesk.domain.enums import ElementRole
from filterdesk.domain.units import format_engineering

_PITCH_SIMPLE = 160.0
_PITCH_RESONATOR = 220.0
_LINE_Y = 110.0
_MARGIN_X = 90.0
_HIGHLIGHT = QColor("#e8a838")


def _base_element_id(ref: str) -> str:
    """Map table refs ``X1.L`` / ``X1.Ls`` / ``C3`` → schematic id."""
    for suffix in (".Ls", ".Cs", ".Lp", ".Cp", ".L", ".C"):
        if ref.endswith(suffix):
            return ref[: -len(suffix)]
    return ref


def _is_composite_lc(el: object) -> bool:
    return isinstance(
        el, (IdealSeriesLC, IdealParallelLC, IdealBruneLC, IdealDualBruneLC)
    )


class _LadderView(QGraphicsView):
    """QGraphicsView that reports right-clicks (QGraphicsView consumes the
    generic ``customContextMenuRequested`` signal, so we handle it directly)."""

    context_requested = Signal(QPoint)  # viewport-local position

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        self.context_requested.emit(event.pos())
        event.accept()


class ElementGroup(QGraphicsItemGroup):
    """Selectable schematic symbol for one ladder element."""

    def __init__(self, element_id: str) -> None:
        super().__init__()
        self.element_id = element_id
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self._normal_pen = QPen(QColor("#ffffff"), 2)
        self._items: list[QGraphicsLineItem] = []

    def set_pens(self, normal: QPen) -> None:
        self._normal_pen = QPen(normal)
        self.apply_highlight(False)

    def track(self, item: QGraphicsLineItem) -> None:
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self._items.append(item)
        self.addToGroup(item)

    def apply_highlight(self, on: bool) -> None:
        pen = QPen(_HIGHLIGHT, 3) if on else QPen(self._normal_pen)
        for item in self._items:
            item.setPen(pen)


class SchematicPanel(QWidget):
    """Read-only ladder schematic; click an element to select it."""

    element_selected = Signal(str)  # base element id (e.g. X3, C1)
    context_menu_requested = Signal(str, QPoint)  # element id, global position

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view = _LadderView()
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setFrameShape(QGraphicsView.Shape.NoFrame)
        self._view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._view.setMinimumHeight(220)
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._view.context_requested.connect(self._on_context_menu_requested)
        self._scene = QGraphicsScene(self)
        self._view.setScene(self._scene)
        self._circuit: Circuit | None = None
        self._groups: dict[str, ElementGroup] = {}
        self._block_sel = False
        self._highlighted: str | None = None
        self._scene.selectionChanged.connect(self._on_selection_changed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)
        self._apply_theme_colors()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange and self._circuit is not None:
            self._apply_theme_colors()
            self.set_circuit(self._circuit)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_view()

    def _fg_color(self) -> QColor:
        return self.palette().color(QPalette.ColorRole.Text)

    def _bg_color(self) -> QColor:
        return self.palette().color(QPalette.ColorRole.Base)

    def _apply_theme_colors(self) -> None:
        bg = self._bg_color()
        fg = self._fg_color()
        self._scene.setBackgroundBrush(QBrush(bg))
        self._view.setBackgroundBrush(QBrush(bg))
        pal = self._view.palette()
        pal.setColor(QPalette.ColorRole.Base, bg)
        pal.setColor(QPalette.ColorRole.Window, bg)
        pal.setColor(QPalette.ColorRole.Text, fg)
        pal.setColor(QPalette.ColorRole.WindowText, fg)
        self._view.setPalette(pal)

    def _fit_view(self) -> None:
        rect = self._scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
        if rect.isEmpty() or not self._view.viewport().isVisible():
            return
        self._view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def set_highlighted(self, element_id: str | None) -> None:
        """Highlight a base element id (from table selection)."""
        eid = None if element_id is None else _base_element_id(element_id)
        self._highlighted = eid
        self._block_sel = True
        self._scene.clearSelection()
        if eid is not None and eid in self._groups:
            self._groups[eid].setSelected(True)
        self._block_sel = False
        self._refresh_highlight_pens()

    def set_circuit(self, circuit: Circuit | None) -> None:
        prev = self._highlighted
        self._circuit = circuit
        self._apply_theme_colors()
        self._block_sel = True
        self._scene.clear()
        self._groups.clear()
        self._block_sel = False
        fg = self._fg_color()
        pen = QPen(fg, 2)
        brush = QBrush(fg)
        label_font = QFont("Sans Serif", 10)

        if circuit is None or not circuit.elements:
            placeholder = QGraphicsSimpleTextItem("No circuit — click Synthesize")
            placeholder.setBrush(brush)
            placeholder.setFont(QFont("Sans Serif", 11))
            self._scene.addItem(placeholder)
            self._fit_view()
            return

        has_resonator = any(_is_composite_lc(el) for el in circuit.elements)
        pitch = _PITCH_RESONATOR if has_resonator else _PITCH_SIMPLE
        x = _MARGIN_X
        y = _LINE_Y

        src = QGraphicsSimpleTextItem(f"Zs = {circuit.port_in.impedance_ohm:g} Ω")
        src.setBrush(brush)
        src.setFont(label_font)
        src.setPos(x - 60, y - 78)
        self._scene.addItem(src)

        if circuit.elements[0].role == ElementRole.SHUNT:
            stub = QGraphicsLineItem(x - 40, y, x, y)
            stub.setPen(pen)
            self._scene.addItem(stub)

        for el in circuit.elements:
            if el.role == ElementRole.SERIES:
                x = self._draw_series_arm(el, x, y, pitch, pen, brush, label_font)
            else:
                self._draw_shunt_arm(el, x, y, pen, brush, label_font)

        tail = QGraphicsLineItem(x, y, x + 44, y)
        tail.setPen(pen)
        self._scene.addItem(tail)

        load = QGraphicsSimpleTextItem(f"Zl = {circuit.port_out.impedance_ohm:g} Ω")
        load.setBrush(brush)
        load.setFont(label_font)
        load.setPos(x + 52, y - 78)
        self._scene.addItem(load)

        bounds = self._scene.itemsBoundingRect()
        self._scene.setSceneRect(bounds.adjusted(-30, -24, 30, 24))
        self._fit_view()
        self._view.centerOn(QPointF(bounds.center().x(), bounds.center().y()))
        if prev is not None:
            self.set_highlighted(prev)

    def _new_group(self, el: Element, pen: QPen) -> ElementGroup:
        group = ElementGroup(el.id)
        group.set_pens(pen)
        self._scene.addItem(group)
        self._groups[el.id] = group
        return group

    def _add_hit_area(
        self, group: ElementGroup, x: float, y: float, w: float, h: float
    ) -> None:
        hit = QGraphicsRectItem(x, y, w, h)
        hit.setPen(QPen(Qt.PenStyle.NoPen))
        # Tiny alpha so the rect still receives mouse events.
        hit.setBrush(QBrush(QColor(127, 127, 127, 1)))
        hit.setZValue(-1)
        hit.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        group.addToGroup(hit)

    def _draw_series_arm(
        self,
        el: Element,
        x: float,
        y: float,
        pitch: float,
        pen: QPen,
        brush: QBrush,
        label_font: QFont,
    ) -> float:
        x0 = x
        x1 = x + pitch
        mid = 0.5 * (x0 + x1)
        gap = 72.0 if _is_composite_lc(el) else 44.0
        left_end = mid - gap / 2
        right_start = mid + gap / 2

        left = QGraphicsLineItem(x0, y, left_end, y)
        left.setPen(pen)
        self._scene.addItem(left)
        right = QGraphicsLineItem(right_start, y, x1, y)
        right.setPen(pen)
        self._scene.addItem(right)

        group = self._new_group(el, pen)
        self._draw_series_symbol(group, el, mid, y, left_end, right_start, pen)
        self._add_hit_area(group, left_end - 4, y - 36, gap + 8, 72)

        text = QGraphicsSimpleTextItem(self._label_for(el))
        text.setBrush(brush)
        text.setFont(label_font)
        text.setPos(mid - text.boundingRect().width() / 2, y - 72)
        self._scene.addItem(text)
        return x1

    def _draw_shunt_arm(
        self,
        el: Element,
        x: float,
        y: float,
        pen: QPen,
        brush: QBrush,
        label_font: QFont,
    ) -> None:
        group = self._new_group(el, pen)
        # Short stub from signal line into the shunt branch (not through components).
        stub = QGraphicsLineItem(x, y, x, y + 14)
        stub.setPen(pen)
        group.track(stub)

        self._draw_shunt_symbol(group, el, x, y, pen)

        gy = y + 88
        for half, dy in ((16.0, 0.0), (11.0, 5.0), (6.0, 10.0)):
            gnd = QGraphicsLineItem(x - half, gy + dy, x + half, gy + dy)
            gnd.setPen(pen)
            self._scene.addItem(gnd)

        self._add_hit_area(group, x - 36, y + 8, 72, 78)

        text = QGraphicsSimpleTextItem(self._label_for(el))
        text.setBrush(brush)
        text.setFont(label_font)
        text.setPos(x - text.boundingRect().width() / 2, gy + 18)
        self._scene.addItem(text)

    def _label_for(self, el: object) -> str:
        if isinstance(el, IdealCapacitor):
            return f"{el.id}  {format_engineering(el.value_f, 'F', digits=4)}"
        if isinstance(el, IdealInductor):
            return f"{el.id}  {format_engineering(el.value_h, 'H', digits=4)}"
        if isinstance(el, (IdealSeriesLC, IdealParallelLC)):
            join = "+" if isinstance(el, IdealSeriesLC) else "||"
            return (
                f"{el.id}  {format_engineering(el.value_h, 'H', digits=3)}"
                f" {join} {format_engineering(el.value_f, 'F', digits=3)}"
            )
        if isinstance(el, IdealBruneLC):
            return f"{el.id}  Brune (+)"
        if isinstance(el, IdealDualBruneLC):
            return f"{el.id}  Brune (||)"
        return str(getattr(el, "id", "?"))

    def _draw_series_symbol(
        self,
        group: ElementGroup,
        el: object,
        mid: float,
        y: float,
        left_end: float,
        right_start: float,
        pen: QPen,
    ) -> None:
        if isinstance(el, IdealCapacitor):
            for dx in (-5.0, 5.0):
                plate = QGraphicsLineItem(mid + dx, y - 16, mid + dx, y + 16)
                plate.setPen(pen)
                group.track(plate)
            # Connect gap ends to plates.
            for x_end, dx in ((left_end, -5.0), (right_start, 5.0)):
                lead = QGraphicsLineItem(x_end, y, mid + dx, y)
                lead.setPen(pen)
                group.track(lead)
        elif isinstance(el, IdealInductor):
            self._draw_coil(group, mid - 16, y, pen)
            lead_l = QGraphicsLineItem(left_end, y, mid - 16, y)
            lead_r = QGraphicsLineItem(mid + 16, y, right_start, y)
            lead_l.setPen(pen)
            lead_r.setPen(pen)
            group.track(lead_l)
            group.track(lead_r)
        elif isinstance(el, IdealSeriesLC):
            # Series L then C in the gap (no through-wire).
            coil_x = mid - 34
            self._draw_coil(group, coil_x, y, pen)
            lead0 = QGraphicsLineItem(left_end, y, coil_x, y)
            lead0.setPen(pen)
            group.track(lead0)
            mid_wire = QGraphicsLineItem(coil_x + 32, y, mid + 4, y)
            mid_wire.setPen(pen)
            group.track(mid_wire)
            for dx in (8.0, 18.0):
                plate = QGraphicsLineItem(mid + dx, y - 16, mid + dx, y + 16)
                plate.setPen(pen)
                group.track(plate)
            lead1 = QGraphicsLineItem(mid + 18, y, right_start, y)
            lead1.setPen(pen)
            group.track(lead1)
        elif isinstance(el, IdealParallelLC):
            # Parallel LC between gap ends — two paths, no center short.
            top_y = y - 22
            bot_y = y + 22
            v_l = QGraphicsLineItem(left_end, top_y, left_end, bot_y)
            v_r = QGraphicsLineItem(right_start, top_y, right_start, bot_y)
            v_l.setPen(pen)
            v_r.setPen(pen)
            group.track(v_l)
            group.track(v_r)
            # Top: inductor
            self._draw_coil(group, mid - 16, top_y, pen)
            t0 = QGraphicsLineItem(left_end, top_y, mid - 16, top_y)
            t1 = QGraphicsLineItem(mid + 16, top_y, right_start, top_y)
            t0.setPen(pen)
            t1.setPen(pen)
            group.track(t0)
            group.track(t1)
            # Bottom: capacitor
            for dx in (-5.0, 5.0):
                plate = QGraphicsLineItem(mid + dx, bot_y - 12, mid + dx, bot_y + 12)
                plate.setPen(pen)
                group.track(plate)
            b0 = QGraphicsLineItem(left_end, bot_y, mid - 5, bot_y)
            b1 = QGraphicsLineItem(mid + 5, bot_y, right_start, bot_y)
            b0.setPen(pen)
            b1.setPen(pen)
            group.track(b0)
            group.track(b1)
        elif isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
            box = QGraphicsRectItem(
                left_end + 2, y - 18, right_start - left_end - 4, 36
            )
            box.setPen(pen)
            group.addToGroup(box)
            lead_l = QGraphicsLineItem(left_end, y, left_end + 2, y)
            lead_r = QGraphicsLineItem(right_start - 2, y, right_start, y)
            lead_l.setPen(pen)
            lead_r.setPen(pen)
            group.track(lead_l)
            group.track(lead_r)
        else:
            self._draw_coil(group, mid - 16, y, pen)

    def _draw_shunt_symbol(
        self, group: ElementGroup, el: object, x: float, y: float, pen: QPen
    ) -> None:
        if isinstance(el, IdealCapacitor):
            for dy in (28.0, 36.0):
                plate = QGraphicsLineItem(x - 14, y + dy, x + 14, y + dy)
                plate.setPen(pen)
                group.track(plate)
            lead = QGraphicsLineItem(x, y + 14, x, y + 28)
            tail = QGraphicsLineItem(x, y + 36, x, y + 78)
            lead.setPen(pen)
            tail.setPen(pen)
            group.track(lead)
            group.track(tail)
        elif isinstance(el, IdealInductor):
            self._draw_coil_vertical(group, x, y + 18, pen)
            lead = QGraphicsLineItem(x, y + 14, x, y + 18)
            tail = QGraphicsLineItem(x, y + 46, x, y + 78)
            lead.setPen(pen)
            tail.setPen(pen)
            group.track(lead)
            group.track(tail)
        elif isinstance(el, IdealSeriesLC):
            # L then C to ground — path segments only, no full short.
            self._draw_coil_vertical(group, x, y + 16, pen)
            lead = QGraphicsLineItem(x, y + 14, x, y + 16)
            lead.setPen(pen)
            group.track(lead)
            mid = QGraphicsLineItem(x, y + 44, x, y + 50)
            mid.setPen(pen)
            group.track(mid)
            for dy in (50.0, 58.0):
                plate = QGraphicsLineItem(x - 14, y + dy, x + 14, y + dy)
                plate.setPen(pen)
                group.track(plate)
            tail = QGraphicsLineItem(x, y + 58, x, y + 78)
            tail.setPen(pen)
            group.track(tail)
        elif isinstance(el, IdealParallelLC):
            # Two parallel branches node→gnd.
            xl, xr = x - 16.0, x + 16.0
            fork = QGraphicsLineItem(xl, y + 14, xr, y + 14)
            fork.setPen(pen)
            group.track(fork)
            self._draw_coil_vertical(group, xl, y + 18, pen)
            for dy in (28.0, 36.0):
                plate = QGraphicsLineItem(xr - 12, y + dy, xr + 12, y + dy)
                plate.setPen(pen)
                group.track(plate)
            join_y = y + 52
            j0 = QGraphicsLineItem(xl, y + 46, xl, join_y)
            j1 = QGraphicsLineItem(xr, y + 36, xr, join_y)
            bar = QGraphicsLineItem(xl, join_y, xr, join_y)
            tail = QGraphicsLineItem(x, join_y, x, y + 78)
            for item in (j0, j1, bar, tail):
                item.setPen(pen)
                group.track(item)
        elif isinstance(el, (IdealBruneLC, IdealDualBruneLC)):
            box = QGraphicsRectItem(x - 22, y + 18, 44, 48)
            box.setPen(pen)
            group.addToGroup(box)
            lead = QGraphicsLineItem(x, y + 14, x, y + 18)
            tail = QGraphicsLineItem(x, y + 66, x, y + 78)
            lead.setPen(pen)
            tail.setPen(pen)
            group.track(lead)
            group.track(tail)
        else:
            self._draw_coil_vertical(group, x, y + 18, pen)

    def _draw_coil(
        self, group: ElementGroup, x: float, y: float, pen: QPen
    ) -> None:
        for i in range(4):
            line = QGraphicsLineItem(x + i * 8, y - 10, x + i * 8 + 8, y + 10)
            line.setPen(pen)
            group.track(line)

    def _draw_coil_vertical(
        self, group: ElementGroup, x: float, y: float, pen: QPen
    ) -> None:
        for i in range(4):
            line = QGraphicsLineItem(x - 10, y + i * 7, x + 10, y + i * 7 + 7)
            line.setPen(pen)
            group.track(line)

    def _on_selection_changed(self) -> None:
        if self._block_sel:
            return
        selected_id: str | None = None
        for item in self._scene.selectedItems():
            if isinstance(item, ElementGroup):
                selected_id = item.element_id
                break
            parent = item.parentItem()
            if isinstance(parent, ElementGroup):
                selected_id = parent.element_id
                break
        self._highlighted = selected_id
        self._refresh_highlight_pens()
        if selected_id is not None:
            self.element_selected.emit(selected_id)

    def _refresh_highlight_pens(self) -> None:
        for eid, group in self._groups.items():
            group.apply_highlight(eid == self._highlighted)

    def _group_for_item(self, item: QGraphicsItem | None) -> ElementGroup | None:
        while item is not None:
            if isinstance(item, ElementGroup):
                return item
            item = item.parentItem()
        return None

    def _on_context_menu_requested(self, pos: QPoint) -> None:
        group = self._group_for_item(self._view.itemAt(pos))
        if group is None:
            return
        self.set_highlighted(group.element_id)
        global_pos = self._view.viewport().mapToGlobal(pos)
        self.context_menu_requested.emit(group.element_id, global_pos)
