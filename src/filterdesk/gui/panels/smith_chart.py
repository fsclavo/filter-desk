"""Interactive Smith-chart plot (Γ plane) using PyQtGraph."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from filterdesk.analysis.smith import (
    gamma_circle,
    gamma_to_z,
    nearest_gamma_index,
    smith_grid_polylines,
)
from filterdesk.domain.overlays import LimitMetric, LimitRegion, Marker
from filterdesk.domain.units import format_engineering
from filterdesk.gui.i18n import tr
from filterdesk.gui.theme import ThemeColors, apply_plot_theme

_GRID_Z = -20
_LIMIT_Z = -15

_MARKER_COLORS = (
    "#ff7f0e",
    "#17becf",
    "#bcbd22",
    "#e377c2",
    "#8c564b",
    "#7f7f7f",
    "#aec7e8",
    "#ffbb78",
)


class SmithChartWidget(QWidget):
    """Unit-disk Smith chart with S11/S22 loci, markers, and nearest-point cursor."""

    cursor_frequency_changed = Signal(float)
    markers_moving = Signal(object)  # list[Marker] while dragging
    markers_changed = Signal(object)  # list[Marker] after a drag finishes

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._freq = np.array([], dtype=float)
        self._s11 = np.array([], dtype=np.complex128)
        self._s22 = np.array([], dtype=np.complex128)
        self._z0_source = 50.0
        self._z0_load = 50.0
        self._markers: list[Marker] = []
        self._cursor_freq_hz: float | None = None
        self._marker_items: list[pg.TargetItem] = []
        self._marker_syncing = False
        self._drag_marker_index: int | None = None
        self._drag_start_freq: float | None = None

        self._plot = pg.PlotWidget(title=tr("Smith chart — S11 / S22"))
        self._plot.setAspectLocked(True)
        self._plot.showGrid(x=False, y=False)
        self._plot.setLabel("bottom", "Re(Γ)")
        self._plot.setLabel("left", "Im(Γ)")
        self._plot.setXRange(-1.15, 1.15)
        self._plot.setYRange(-1.15, 1.15)
        self._plot.getPlotItem().hideButtons()
        self._plot.addLegend(offset=(10, 10))

        self._grid_items: list[pg.PlotDataItem] = []
        self._draw_grid()

        self._limits: list[LimitRegion] = []
        self._limit_items: list[pg.PlotDataItem] = []

        self._curve_s11 = self._plot.plot(
            pen=pg.mkPen("#d62728", width=2), name="S11"
        )
        self._curve_s22 = self._plot.plot(
            pen=pg.mkPen("#1f77b4", width=2), name="S22"
        )
        dash = Qt.PenStyle.DashLine
        self._curve_s11_meas = self._plot.plot(
            pen=pg.mkPen("#d62728", width=1.3, style=dash), name=tr("S11 meas")
        )
        self._curve_s22_meas = self._plot.plot(
            pen=pg.mkPen("#1f77b4", width=1.3, style=dash), name=tr("S22 meas")
        )
        self._start_pt = pg.ScatterPlotItem(
            size=9,
            brush=pg.mkBrush("#2ca02c"),
            pen=pg.mkPen("#ffffff", width=1),
        )
        self._stop_pt = pg.ScatterPlotItem(
            size=9,
            brush=pg.mkBrush("#9467bd"),
            pen=pg.mkPen("#ffffff", width=1),
        )
        self._cursor_pt = pg.ScatterPlotItem(
            size=11,
            symbol="o",
            brush=pg.mkBrush(255, 255, 255, 0),
            pen=pg.mkPen("#cccccc", width=2, style=Qt.PenStyle.DashLine),
        )
        self._plot.addItem(self._start_pt)
        self._plot.addItem(self._stop_pt)
        self._plot.addItem(self._cursor_pt)

        self._proxy = pg.SignalProxy(
            self._plot.scene().sigMouseMoved,
            rateLimit=40,
            slot=self._on_mouse_moved,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot)

    def plot_widget(self) -> pg.PlotWidget:
        return self._plot

    def cursor_frequency_hz(self) -> float | None:
        return self._cursor_freq_hz

    def set_markers(self, markers: list[Marker]) -> None:
        self._markers = list(markers)
        self._redraw_markers()

    def set_s_params(
        self,
        frequency_hz: np.ndarray,
        s11: np.ndarray,
        s22: np.ndarray | None = None,
        *,
        z0_source_ohm: float = 50.0,
        z0_load_ohm: float = 50.0,
    ) -> None:
        self._freq = np.asarray(frequency_hz, dtype=float)
        self._s11 = np.asarray(s11, dtype=np.complex128)
        if s22 is None:
            self._s22 = np.array([], dtype=np.complex128)
        else:
            self._s22 = np.asarray(s22, dtype=np.complex128)
        self._z0_source = float(z0_source_ohm)
        self._z0_load = float(z0_load_ohm)
        if self._freq.size == 0:
            self._curve_s11.setData([], [])
            self._curve_s22.setData([], [])
            self._start_pt.setData([], [])
            self._stop_pt.setData([], [])
            self._cursor_pt.setData([], [])
            self._clear_marker_items()
            return
        self._curve_s11.setData(self._s11.real, self._s11.imag)
        if self._s22.size == self._freq.size:
            self._curve_s22.setData(self._s22.real, self._s22.imag)
        else:
            self._curve_s22.setData([], [])
        # Start/stop markers on S11 locus
        self._start_pt.setData(
            [float(self._s11.real[0])], [float(self._s11.imag[0])]
        )
        self._stop_pt.setData(
            [float(self._s11.real[-1])], [float(self._s11.imag[-1])]
        )
        self._redraw_markers()

    def set_s11(
        self,
        frequency_hz: np.ndarray,
        s11: np.ndarray,
        *,
        z0_ohm: float = 50.0,
    ) -> None:
        """Backward-compatible S11-only update."""
        self.set_s_params(
            frequency_hz, s11, None, z0_source_ohm=z0_ohm, z0_load_ohm=z0_ohm
        )

    def set_measured_s_params(
        self,
        frequency_hz: np.ndarray,
        s11: np.ndarray,
        s22: np.ndarray | None = None,
    ) -> None:
        """Overlay measured S11/S22 as dashed loci (independent of the sim)."""
        f = np.asarray(frequency_hz, dtype=float)
        if f.size == 0:
            self._curve_s11_meas.setData([], [])
            self._curve_s22_meas.setData([], [])
            return
        g11 = np.asarray(s11, dtype=np.complex128)
        self._curve_s11_meas.setData(g11.real, g11.imag)
        if s22 is not None and np.asarray(s22).size == f.size:
            g22 = np.asarray(s22, dtype=np.complex128)
            self._curve_s22_meas.setData(g22.real, g22.imag)
        else:
            self._curve_s22_meas.setData([], [])

    def set_theme(self, colors: ThemeColors) -> None:
        apply_plot_theme(self._plot, colors)

    def clear(self) -> None:
        self.set_s_params(
            np.array([]),
            np.array([], dtype=np.complex128),
            np.array([], dtype=np.complex128),
        )

    def set_limits(self, limits: list[LimitRegion]) -> None:
        self._limits = list(limits)
        self._redraw_limits()

    def _clear_limit_items(self) -> None:
        for item in self._limit_items:
            self._plot.removeItem(item)
        self._limit_items.clear()

    def _redraw_limits(self) -> None:
        self._clear_limit_items()
        pen_colors = {
            LimitMetric.S11_MAG: "#ff9900",
            LimitMetric.S22_MAG: "#9467bd",
        }
        for lim in self._limits:
            if not lim.enabled or lim.metric not in pen_colors:
                continue
            color = pen_colors[lim.metric]
            # y_max → dashed boundary; y_min → dotted inner boundary.
            boundaries = (
                (lim.y_max, Qt.PenStyle.DashLine),
                (lim.y_min, Qt.PenStyle.DotLine),
            )
            for radius, style in boundaries:
                if radius is None:
                    continue
                re, im = gamma_circle(float(radius))
                item = self._plot.plot(
                    re,
                    im,
                    pen=pg.mkPen(color, width=1.5, style=style),
                )
                item.setZValue(_LIMIT_Z)
                self._limit_items.append(item)

    def nearest_index_at_gamma(self, gamma: complex) -> int | None:
        if self._s11.size == 0:
            return None
        s22 = self._s22 if self._s22.size == self._s11.size else None
        return nearest_gamma_index(gamma, self._s11, s22)

    def readout_at_index(self, idx: int) -> str:
        f_hz = float(self._freq[idx])
        g11 = complex(self._s11[idx])
        z11_n = complex(gamma_to_z(g11))
        z11 = z11_n * self._z0_source
        parts = [
            f"f = {format_engineering(f_hz, 'Hz', digits=6)}",
            f"S11: Γ={g11.real:+.4f}{g11.imag:+.4f}j  "
            f"|Γ|={abs(g11):.4f}  "
            f"Z={z11.real:.2f}{z11.imag:+.2f}j Ω",
        ]
        if self._s22.size == self._freq.size:
            g22 = complex(self._s22[idx])
            z22_n = complex(gamma_to_z(g22))
            z22 = z22_n * self._z0_load
            parts.append(
                f"S22: Γ={g22.real:+.4f}{g22.imag:+.4f}j  "
                f"|Γ|={abs(g22):.4f}  "
                f"Z={z22.real:.2f}{z22.imag:+.2f}j Ω"
            )
        return "   ".join(parts)

    def _draw_grid(self) -> None:
        pen = pg.mkPen("#888888", width=1)
        pen_light = pg.mkPen("#aaaaaa", width=0.8)
        for i, (re, im) in enumerate(smith_grid_polylines()):
            item = self._plot.plot(
                re, im, pen=pen if i == 0 else pen_light, antialias=True
            )
            item.setZValue(-20)
            self._grid_items.append(item)
        cross_pen = pg.mkPen("#666666", width=1, style=Qt.PenStyle.DotLine)
        self._plot.plot([-1.05, 1.05], [0.0, 0.0], pen=cross_pen)
        self._plot.plot([0.0, 0.0], [-1.05, 1.05], pen=cross_pen)

    def _clear_marker_items(self) -> None:
        for item in self._marker_items:
            self._plot.removeItem(item)
        self._marker_items.clear()
        self._drag_marker_index = None
        self._drag_start_freq = None

    def _redraw_markers(self) -> None:
        self._clear_marker_items()
        if self._freq.size == 0 or not self._markers:
            return
        for i, marker in enumerate(self._markers):
            idx = int(np.argmin(np.abs(self._freq - marker.frequency_hz)))
            g = self._s11[idx]
            color = _MARKER_COLORS[i % len(_MARKER_COLORS)]
            item = pg.TargetItem(
                pos=(float(g.real), float(g.imag)),
                size=14,
                symbol="o",
                pen=pg.mkPen("#ffffff", width=1),
                brush=pg.mkBrush(color),
                hoverPen=pg.mkPen("#ffffff", width=2),
                hoverBrush=pg.mkBrush(color),
                movable=True,
                label=marker.id,
                labelOpts={"color": color, "offset": (8, 8)},
            )
            item.setZValue(10)
            item._filterdesk_marker_index = i
            item.sigPositionChanged.connect(self._on_marker_moved)
            item.sigPositionChangeFinished.connect(self._on_marker_finished)
            self._plot.addItem(item)
            self._marker_items.append(item)

    def _on_marker_moved(self, item: pg.TargetItem) -> None:
        if self._marker_syncing or self._s11.size == 0 or self._freq.size == 0:
            return
        index = getattr(item, "_filterdesk_marker_index", None)
        if not isinstance(index, int) or not (0 <= index < len(self._markers)):
            return
        if self._drag_marker_index is None:
            self._drag_marker_index = index
            self._drag_start_freq = self._markers[index].frequency_hz
        pos = item.pos()
        gamma = complex(float(pos.x()), float(pos.y()))
        # Markers live on the S11 locus
        idx = nearest_gamma_index(gamma, self._s11, None)
        freq = float(self._freq[idx])
        g = self._s11[idx]
        self._marker_syncing = True
        try:
            item.setPos(float(g.real), float(g.imag))
        finally:
            self._marker_syncing = False
        old = self._markers[index]
        self._markers[index] = Marker(
            id=old.id,
            frequency_hz=freq,
            label=old.label,
            landmark=old.landmark,
        )
        self._cursor_freq_hz = freq
        self.cursor_frequency_changed.emit(freq)
        self.markers_moving.emit(list(self._markers))

    def _on_marker_finished(self, item: pg.TargetItem) -> None:
        if self._marker_syncing:
            return
        self._on_marker_moved(item)
        index = self._drag_marker_index
        start = self._drag_start_freq
        self._drag_marker_index = None
        self._drag_start_freq = None
        if index is None or start is None or index >= len(self._markers):
            return
        new_freq = self._markers[index].frequency_hz
        if abs(new_freq - start) <= max(
            1e-12, 1e-15 * max(abs(start), abs(new_freq))
        ):
            return
        self.markers_changed.emit(list(self._markers))

    def _on_mouse_moved(self, event: object) -> None:
        if self._s11.size == 0 or self._drag_marker_index is not None:
            return
        if isinstance(event, tuple) and event:
            pos = event[0]
        else:
            pos = event
        if not hasattr(pos, "x"):
            return
        mouse_point = self._plot.plotItem.vb.mapSceneToView(pos)
        gamma = complex(float(mouse_point.x()), float(mouse_point.y()))
        idx = self.nearest_index_at_gamma(gamma)
        if idx is None:
            return
        # Place cursor on the closer of S11 / S22 at this frequency
        g11 = self._s11[idx]
        d11 = abs(complex(g11) - gamma) ** 2
        g_cur = g11
        if self._s22.size == self._s11.size:
            g22 = self._s22[idx]
            if abs(complex(g22) - gamma) ** 2 < d11:
                g_cur = g22
        self._cursor_pt.setData([float(g_cur.real)], [float(g_cur.imag)])
        f_hz = float(self._freq[idx])
        self._cursor_freq_hz = f_hz
        self.cursor_frequency_changed.emit(f_hz)
