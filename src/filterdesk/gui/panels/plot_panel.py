"""Response plots using PyQtGraph with cursor, markers, limits, and Smith."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from filterdesk.analysis.derived import group_delay_s, mag_db, vswr
from filterdesk.analysis.types import AnalysisResult
from filterdesk.domain.overlays import LimitMetric, LimitRegion, Marker
from filterdesk.domain.units import format_engineering
from filterdesk.gui.panels.smith_chart import SmithChartWidget

if TYPE_CHECKING:
    from filterdesk.montecarlo import MonteCarloResult


def _plain_decimal(value: float) -> str:
    """Format a tick without scientific notation (unit lives in the axis label)."""
    if not np.isfinite(value):
        return ""
    if value == 0.0:
        return "0"
    mag = abs(value)
    if mag >= 100.0:
        text = f"{value:.0f}"
    elif mag >= 10.0:
        text = f"{value:.1f}"
    elif mag >= 1.0:
        text = f"{value:.2f}"
    elif mag >= 0.1:
        text = f"{value:.2f}"
    else:
        text = f"{value:.3f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


class FreqAxisItem(pg.AxisItem):  # type: ignore[misc]
    """Log-frequency axis: SI-prefixed unit in the label, plain tick numbers."""

    def logTickStrings(
        self, values: list[float], scale: float, spacing: float
    ) -> list[str]:
        del spacing
        return [
            _plain_decimal((10.0 ** float(v)) * float(scale)) for v in values
        ]


def _freq_plot(title: str) -> pg.PlotWidget:
    plot = pg.PlotWidget(
        title=title,
        axisItems={"bottom": FreqAxisItem(orientation="bottom")},
    )
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.setLabel("bottom", "Frequency", units="Hz")
    return plot


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


class PlotPanel(QWidget):
    cursor_frequency_changed = Signal(float)  # Hz at last mouse snap
    markers_changed = Signal(object)  # list[Marker] after a drag finishes

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)
        self._result: AnalysisResult | None = None
        self._measured: AnalysisResult | None = None
        self._measured_name = ""
        self._show_measured = True
        self._mc_result: MonteCarloResult | None = None
        self._show_mc = True
        self._harmonic_freqs: list[float] = []
        self._harmonic_lines: list[pg.InfiniteLine] = []
        self._show_harmonics = True
        self._freq = np.array([], dtype=float)
        self._s21_db = np.array([], dtype=float)
        self._s11_db = np.array([], dtype=float)
        self._vswr = np.array([], dtype=float)
        self._gd = np.array([], dtype=float)
        self._cursor_freq_hz: float | None = None
        self._markers: list[Marker] = []
        self._limits: list[LimitRegion] = []
        self._marker_items: list[list[pg.InfiniteLine]] = []
        self._limit_items: list[tuple[pg.PlotWidget, pg.GraphicsObject]] = []
        self._marker_syncing = False
        self._drag_marker_index: int | None = None
        self._drag_start_freq: float | None = None

        self._tabs = QTabWidget()
        self._mag = _freq_plot("|S21| / |S11| (dB)")
        self._mag.setLabel("left", "Magnitude", units="dB")
        self._mag.addLegend()
        self._curve_s21 = self._mag.plot(pen=pg.mkPen("#1f77b4", width=2), name="S21")
        self._curve_s11 = self._mag.plot(pen=pg.mkPen("#d62728", width=2), name="S11")
        dash = Qt.PenStyle.DashLine
        self._curve_s21_meas = self._mag.plot(
            pen=pg.mkPen("#1f77b4", width=1.4, style=dash), name="S21 meas"
        )
        self._curve_s11_meas = self._mag.plot(
            pen=pg.mkPen("#d62728", width=1.4, style=dash), name="S11 meas"
        )
        self._curve_mc_min = self._mag.plot(
            pen=pg.mkPen("#7f7f7f", width=1, style=dash)
        )
        self._curve_mc_max = self._mag.plot(
            pen=pg.mkPen("#7f7f7f", width=1, style=dash)
        )
        self._mc_fill = pg.FillBetweenItem(
            self._curve_mc_min,
            self._curve_mc_max,
            brush=pg.mkBrush(127, 127, 127, 55),
        )
        self._mag.addItem(self._mc_fill)

        self._vswr_plot = _freq_plot("VSWR")
        self._vswr_plot.setLabel("left", "VSWR")
        self._curve_vswr = self._vswr_plot.plot(pen=pg.mkPen("#2ca02c", width=2))
        self._curve_vswr_meas = self._vswr_plot.plot(
            pen=pg.mkPen("#2ca02c", width=1.4, style=dash)
        )

        self._gd_plot = _freq_plot("Group delay")
        self._gd_plot.setLabel("left", "Group delay", units="s")
        self._curve_gd = self._gd_plot.plot(pen=pg.mkPen("#9467bd", width=2))

        self._smith = SmithChartWidget()
        self._smith.cursor_frequency_changed.connect(self._on_smith_cursor)
        self._smith.markers_moving.connect(self._on_smith_markers_moving)
        self._smith.markers_changed.connect(self._on_smith_markers_changed)

        self._plots = (self._mag, self._vswr_plot, self._gd_plot)
        self._cursors: list[pg.InfiniteLine] = []
        for plot in self._plots:
            plot.setLogMode(x=True, y=False)
            vline = pg.InfiniteLine(
                angle=90,
                movable=False,
                pen=pg.mkPen("#cccccc", width=1, style=Qt.PenStyle.DashLine),
            )
            vline.setVisible(False)
            plot.addItem(vline)
            self._cursors.append(vline)
            proxy = pg.SignalProxy(
                plot.scene().sigMouseMoved,
                rateLimit=40,
                slot=lambda evt, p=plot: self._on_mouse_moved(p, evt),
            )
            plot._filterdesk_proxy = proxy

        self._tabs.addTab(self._mag, "Magnitude")
        self._tabs.addTab(self._vswr_plot, "VSWR")
        self._tabs.addTab(self._gd_plot, "Group delay")
        self._tabs.addTab(self._smith, "Smith")

        self._readout = QLabel(
            "Move the mouse over a plot to read frequency and values "
            "(snaps to nearest sweep point). Drag marker lines (or Smith "
            "spots) to move; bind a marker to a landmark to retune by dragging. "
            "Use Markers / Limits docks to pin."
        )
        self._readout.setWordWrap(True)
        self._readout.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(self._readout)

    def cursor_frequency_hz(self) -> float | None:
        return self._cursor_freq_hz

    def set_markers(self, markers: list[Marker]) -> None:
        self._markers = list(markers)
        self._redraw_markers()
        self._smith.set_markers(markers)

    def set_limits(self, limits: list[LimitRegion]) -> None:
        self._limits = list(limits)
        self._redraw_limits()
        self._smith.set_limits(limits)

    def set_measured(self, result: AnalysisResult | None, name: str = "") -> None:
        self._measured = result
        self._measured_name = name or ""
        self._update_measured()

    def set_measured_visible(self, visible: bool) -> None:
        self._show_measured = bool(visible)
        self._update_measured()

    def has_measured(self) -> bool:
        return self._measured is not None

    def set_monte_carlo(self, result: MonteCarloResult | None) -> None:
        self._mc_result = result
        self._update_monte_carlo()

    def set_monte_carlo_visible(self, visible: bool) -> None:
        self._show_mc = bool(visible)
        self._update_monte_carlo()

    def has_monte_carlo(self) -> bool:
        return self._mc_result is not None

    def set_harmonics(self, frequencies_hz: list[float]) -> None:
        self._harmonic_freqs = list(frequencies_hz)
        self._redraw_harmonics()

    def set_harmonics_visible(self, visible: bool) -> None:
        self._show_harmonics = bool(visible)
        self._redraw_harmonics()

    def _redraw_harmonics(self) -> None:
        for line in self._harmonic_lines:
            self._mag.removeItem(line)
        self._harmonic_lines.clear()
        if not self._show_harmonics:
            return
        pen = pg.mkPen("#ff9f1c", width=1, style=Qt.PenStyle.DotLine)
        for freq in self._harmonic_freqs:
            if not np.isfinite(freq) or freq <= 0.0:
                continue
            line = pg.InfiniteLine(angle=90, movable=False, pen=pen)
            line.setPos(float(np.log10(freq)))  # magnitude plot uses a log x-axis
            self._mag.addItem(line)
            self._harmonic_lines.append(line)

    def _update_monte_carlo(self) -> None:
        empty = np.array([], dtype=float)
        mc = self._mc_result
        if mc is None or not self._show_mc:
            self._curve_mc_min.setData(empty, empty)
            self._curve_mc_max.setData(empty, empty)
            self._mc_fill.setVisible(False)
            return
        f = np.asarray(mc.frequency_hz, dtype=float)
        self._curve_mc_min.setData(f, np.asarray(mc.s21_db_min, dtype=float))
        self._curve_mc_max.setData(f, np.asarray(mc.s21_db_max, dtype=float))
        self._mc_fill.setVisible(True)

    def _mc_readout_bits(self, freq_hz: float) -> str:
        """Cursor readout segment for the Monte-Carlo envelope at ``freq_hz``."""
        mc = self._mc_result
        if mc is None or not self._show_mc:
            return ""
        f_mc = np.asarray(mc.frequency_hz, dtype=float)
        if not f_mc.size:
            return ""
        j = int(np.argmin(np.abs(f_mc - freq_hz)))
        lo = float(mc.s21_db_min[j])
        hi = float(mc.s21_db_max[j])
        return (
            f"   | MC S21 {lo:.3f} … {hi:.3f} dB "
            f"(spread {hi - lo:.3f}, "
            f"p05…p95 {float(mc.s21_db_p05[j]):.3f}…"
            f"{float(mc.s21_db_p95[j]):.3f})"
        )

    def _update_measured(self) -> None:
        empty = np.array([], dtype=float)
        measured = self._measured
        if measured is None or not self._show_measured:
            self._curve_s21_meas.setData(empty, empty)
            self._curve_s11_meas.setData(empty, empty)
            self._curve_vswr_meas.setData(empty, empty)
            self._smith.set_measured_s_params(empty, empty, None)
            return
        fm = np.asarray(measured.frequency_hz, dtype=float)
        self._curve_s21_meas.setData(fm, np.asarray(mag_db(measured.s21)))
        self._curve_s11_meas.setData(fm, np.asarray(mag_db(measured.s11)))
        self._curve_vswr_meas.setData(fm, np.asarray(vswr(measured)))
        self._smith.set_measured_s_params(fm, measured.s11, measured.s22)

    def set_result(self, result: AnalysisResult | None) -> None:
        self._result = result
        if result is None:
            empty = np.array([])
            self._freq = empty
            self._s21_db = empty
            self._s11_db = empty
            self._vswr = empty
            self._gd = empty
            self._curve_s21.setData(empty, empty)
            self._curve_s11.setData(empty, empty)
            self._curve_vswr.setData(empty, empty)
            self._curve_gd.setData(empty, empty)
            self._smith.clear()
            for cursor in self._cursors:
                cursor.setVisible(False)
            self._readout.setText("No analysis result.")
            self._redraw_markers()
            self._redraw_limits()
            self._update_measured()
            return

        f = np.asarray(result.frequency_hz, dtype=float)
        self._freq = f
        self._s21_db = np.asarray(mag_db(result.s21), dtype=float)
        self._s11_db = np.asarray(mag_db(result.s11), dtype=float)
        self._vswr = np.asarray(vswr(result), dtype=float)
        self._gd = np.asarray(
            group_delay_s(result.frequency_hz, result.s21), dtype=float
        )
        self._curve_s21.setData(f, self._s21_db)
        self._curve_s11.setData(f, self._s11_db)
        self._curve_vswr.setData(f, self._vswr)
        self._curve_gd.setData(f, self._gd)
        self._smith.set_s_params(
            f,
            result.s11,
            result.s22,
            z0_source_ohm=result.z0_source_ohm,
            z0_load_ohm=result.z0_load_ohm,
        )
        self._smith.set_markers(self._markers)
        readout = (
            "Move the mouse over a plot to read frequency and values "
            "(snaps to nearest sweep point). Drag marker lines or Smith "
            "spots to move them; bind a marker to a landmark (cutoff / f_center "
            "/ bandwidth) in the Markers dock to retune the design by dragging. "
            "Smith: S11 red, S22 blue; green/purple = S11 start/stop."
        )
        if self._measured is not None and self._show_measured:
            label = self._measured_name or "measured"
            readout += f"  Dashed = {label} overlay."
        if self._mc_result is not None and self._show_mc:
            readout += "  Grey band = Monte-Carlo envelope (hover for min…max)."
        self._readout.setText(readout)
        self._redraw_markers()
        self._redraw_limits()
        self._update_measured()

    def _x_pos(self, freq_hz: float, plot: pg.PlotWidget) -> float:
        log_x = bool(plot.getPlotItem().getAxis("bottom").logMode)
        return float(np.log10(freq_hz)) if log_x else float(freq_hz)

    def _view_x_to_freq(self, x_view: float, plot: pg.PlotWidget) -> float | None:
        log_x = bool(plot.getPlotItem().getAxis("bottom").logMode)
        freq = 10.0**x_view if log_x else x_view
        if not np.isfinite(freq) or freq <= 0.0:
            return None
        if self._freq.size:
            idx = int(np.argmin(np.abs(self._freq - freq)))
            return float(self._freq[idx])
        return float(freq)

    def _plot_for_line(self, line: pg.InfiniteLine) -> pg.PlotWidget:
        scene = line.scene()
        for plot in self._plots:
            if plot.scene() is scene:
                return plot
        return self._plots[0]

    def _sync_cartesian_marker_positions(self, markers: list[Marker]) -> None:
        self._markers = list(markers)
        if len(self._marker_items) != len(self._markers):
            self._redraw_markers()
            return
        self._marker_syncing = True
        try:
            for index, marker in enumerate(self._markers):
                for plot, line in zip(
                    self._plots, self._marker_items[index], strict=True
                ):
                    line.setPos(self._x_pos(marker.frequency_hz, plot))
        finally:
            self._marker_syncing = False

    def _on_smith_markers_moving(self, markers: object) -> None:
        if self._marker_syncing:
            return
        assert isinstance(markers, list)
        self._sync_cartesian_marker_positions(markers)

    def _on_smith_markers_changed(self, markers: object) -> None:
        if self._marker_syncing:
            return
        assert isinstance(markers, list)
        self._sync_cartesian_marker_positions(markers)
        self.markers_changed.emit(list(self._markers))

    def _apply_marker_frequency(self, index: int, freq_hz: float) -> None:
        old = self._markers[index]
        self._markers[index] = Marker(
            id=old.id,
            frequency_hz=freq_hz,
            label=old.label,
            landmark=old.landmark,
        )
        self._marker_syncing = True
        try:
            for plot, line in zip(
                self._plots, self._marker_items[index], strict=True
            ):
                line.setPos(self._x_pos(freq_hz, plot))
        finally:
            self._marker_syncing = False
        self._smith.set_markers(self._markers)
        self._cursor_freq_hz = freq_hz
        self.cursor_frequency_changed.emit(freq_hz)

    def _on_marker_line_moved(self, line: pg.InfiniteLine) -> None:
        if self._marker_syncing:
            return
        index = getattr(line, "_filterdesk_marker_index", None)
        if not isinstance(index, int) or not (0 <= index < len(self._markers)):
            return
        if self._drag_marker_index is None:
            self._drag_marker_index = index
            self._drag_start_freq = self._markers[index].frequency_hz
        plot = self._plot_for_line(line)
        freq = self._view_x_to_freq(float(line.value()), plot)
        if freq is None:
            return
        self._apply_marker_frequency(index, freq)

    def _on_marker_line_finished(self, line: pg.InfiniteLine) -> None:
        if self._marker_syncing:
            return
        self._on_marker_line_moved(line)
        index = self._drag_marker_index
        start = self._drag_start_freq
        self._drag_marker_index = None
        self._drag_start_freq = None
        if index is None or start is None:
            return
        if index >= len(self._markers):
            return
        new_freq = self._markers[index].frequency_hz
        if abs(new_freq - start) <= max(1e-12, 1e-15 * max(abs(start), abs(new_freq))):
            return
        self.markers_changed.emit(list(self._markers))

    def _redraw_markers(self) -> None:
        for group in self._marker_items:
            for item in group:
                for plot in self._plots:
                    plot.removeItem(item)
        self._marker_items.clear()
        self._drag_marker_index = None
        self._drag_start_freq = None
        for i, marker in enumerate(self._markers):
            color = _MARKER_COLORS[i % len(_MARKER_COLORS)]
            lines: list[pg.InfiniteLine] = []
            for plot in self._plots:
                line = pg.InfiniteLine(
                    pos=self._x_pos(marker.frequency_hz, plot),
                    angle=90,
                    movable=True,
                    pen=pg.mkPen(color, width=1.5),
                    label=marker.id if plot is self._mag else None,
                    labelOpts={"position": 0.92, "color": color},
                )
                line._filterdesk_marker_index = i
                line.sigPositionChanged.connect(self._on_marker_line_moved)
                line.sigPositionChangeFinished.connect(
                    self._on_marker_line_finished
                )
                plot.addItem(line)
                lines.append(line)
            self._marker_items.append(lines)

    def _redraw_limits(self) -> None:
        for plot, item in self._limit_items:
            plot.removeItem(item)
        self._limit_items.clear()
        for lim in self._limits:
            if not lim.enabled:
                continue
            if lim.metric in (LimitMetric.S21_DB, LimitMetric.S11_DB):
                plot = self._mag
                x0 = self._x_pos(lim.f_low_hz, plot)
                x1 = self._x_pos(lim.f_high_hz, plot)
                region = pg.LinearRegionItem(
                    values=(x0, x1),
                    movable=False,
                    brush=pg.mkBrush(255, 200, 0, 40),
                    pen=pg.mkPen("#ffbb00", width=1),
                )
                region.setZValue(-10)
                plot.addItem(region)
                self._limit_items.append((plot, region))
                for y in (lim.y_max, lim.y_min):
                    if y is None:
                        continue
                    h = pg.InfiniteLine(
                        pos=y,
                        angle=0,
                        movable=False,
                        pen=pg.mkPen("#ff9900", width=1, style=Qt.PenStyle.DotLine),
                    )
                    plot.addItem(h)
                    self._limit_items.append((plot, h))
            elif lim.metric == LimitMetric.VSWR:
                plot = self._vswr_plot
                x0 = self._x_pos(lim.f_low_hz, plot)
                x1 = self._x_pos(lim.f_high_hz, plot)
                region = pg.LinearRegionItem(
                    values=(x0, x1),
                    movable=False,
                    brush=pg.mkBrush(255, 200, 0, 40),
                )
                plot.addItem(region)
                self._limit_items.append((plot, region))
                for y in (lim.y_max, lim.y_min):
                    if y is None:
                        continue
                    h = pg.InfiniteLine(
                        pos=y,
                        angle=0,
                        movable=False,
                        pen=pg.mkPen("#ff9900", width=1, style=Qt.PenStyle.DotLine),
                    )
                    plot.addItem(h)
                    self._limit_items.append((plot, h))

    def _on_smith_cursor(self, f_hz: float) -> None:
        self._cursor_freq_hz = float(f_hz)
        self.cursor_frequency_changed.emit(float(f_hz))
        if self._freq.size == 0:
            return
        idx = int(np.argmin(np.abs(self._freq - f_hz)))
        x_cursor = float(np.log10(self._freq[idx]))
        for cursor in self._cursors:
            cursor.setPos(x_cursor)
            cursor.setVisible(True)
        self._readout.setText(self._smith.readout_at_index(idx))

    def _on_mouse_moved(self, plot: pg.PlotWidget, event: object) -> None:
        if self._freq.size == 0:
            return
        if isinstance(event, tuple) and event:
            pos = event[0]
        else:
            pos = event
        if not hasattr(pos, "x"):
            return
        mouse_point = plot.plotItem.vb.mapSceneToView(pos)
        x_view = float(mouse_point.x())
        log_x = bool(plot.getPlotItem().getAxis("bottom").logMode)
        freq = 10.0**x_view if log_x else x_view
        if not np.isfinite(freq) or freq <= 0.0:
            return
        idx = int(np.argmin(np.abs(self._freq - freq)))
        f_hz = float(self._freq[idx])
        self._cursor_freq_hz = f_hz
        self.cursor_frequency_changed.emit(f_hz)
        x_cursor = float(np.log10(f_hz)) if log_x else f_hz
        for cursor in self._cursors:
            cursor.setPos(x_cursor)
            cursor.setVisible(True)

        s21 = float(self._s21_db[idx])
        s11 = float(self._s11_db[idx])
        vs = float(self._vswr[idx])
        gd = float(self._gd[idx])
        mc_bits = self._mc_readout_bits(f_hz)
        marker_bits = ""
        if self._markers:
            parts = [
                f"{m.id}@{format_engineering(m.frequency_hz, 'Hz', digits=4)}"
                for m in self._markers
            ]
            marker_bits = "   | markers: " + ", ".join(parts)
        self._readout.setText(
            f"f = {format_engineering(f_hz, 'Hz', digits=6)}   "
            f"S21 = {s21:.3f} dB   "
            f"S11 = {s11:.3f} dB   "
            f"VSWR = {vs:.3f}   "
            f"GD = {format_engineering(gd, 's', digits=4)}"
            f"{mc_bits}"
            f"{marker_bits}"
        )
