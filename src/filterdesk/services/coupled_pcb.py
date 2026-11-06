"""Manufacturing handoff for routed coupled-line layouts: DRC and Gerber."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from filterdesk.services.coupled_layout import CoupledLayout, LayoutTrace

_MARGIN_MM = 3.0


class CoupledPcbError(ValueError):
    """Raised when a routed layout cannot be exported for fabrication."""


@dataclass(frozen=True, slots=True)
class DrcRules:
    min_width_mm: float = 0.15
    min_gap_mm: float = 0.15
    min_annular_mm: float = 0.15
    board_margin_mm: float = 0.5
    board_edge_margin_mm: float = _MARGIN_MM


@dataclass(frozen=True, slots=True)
class DrcViolation:
    code: str
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class DrcReport:
    violations: tuple[DrcViolation, ...]
    rules: DrcRules

    @property
    def errors(self) -> tuple[DrcViolation, ...]:
        return tuple(v for v in self.violations if v.severity == "error")

    @property
    def warnings(self) -> tuple[DrcViolation, ...]:
        return tuple(v for v in self.violations if v.severity != "error")

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        if not self.violations:
            return "DRC: no violations"
        parts = [f"DRC: {len(self.errors)} error(s), {len(self.warnings)} warning(s)"]
        parts.extend(f"{v.code}: {v.message}" for v in self.violations)
        return "; ".join(parts)


@dataclass(frozen=True, slots=True)
class GerberSet:
    copper: str
    outline: str
    drill: str


def _point_segment_distance(
    px: float,
    py: float,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> float:
    dx = x1 - x0
    dy = y1 - y0
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - x0, py - y0)
    t = ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def _orientation(
    ax: float, ay: float, bx: float, by: float, cx: float, cy: float
) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _on_segment(
    ax: float, ay: float, bx: float, by: float, px: float, py: float
) -> bool:
    return (
        min(ax, bx) - 1e-9 <= px <= max(ax, bx) + 1e-9
        and min(ay, by) - 1e-9 <= py <= max(ay, by) + 1e-9
    )


def _segments_intersect(
    ax: float,
    ay: float,
    bx: float,
    by: float,
    cx: float,
    cy: float,
    dx: float,
    dy: float,
) -> bool:
    o1 = _orientation(ax, ay, bx, by, cx, cy)
    o2 = _orientation(ax, ay, bx, by, dx, dy)
    o3 = _orientation(cx, cy, dx, dy, ax, ay)
    o4 = _orientation(cx, cy, dx, dy, bx, by)
    if o1 * o2 < -1e-12 and o3 * o4 < -1e-12:
        return True
    if abs(o1) <= 1e-12 and _on_segment(ax, ay, bx, by, cx, cy):
        return True
    if abs(o2) <= 1e-12 and _on_segment(ax, ay, bx, by, dx, dy):
        return True
    if abs(o3) <= 1e-12 and _on_segment(cx, cy, dx, dy, ax, ay):
        return True
    if abs(o4) <= 1e-12 and _on_segment(cx, cy, dx, dy, bx, by):
        return True
    return False


def _segment_distance(a: LayoutTrace, b: LayoutTrace) -> float:
    if _segments_intersect(
        a.x0_mm,
        a.y0_mm,
        a.x1_mm,
        a.y1_mm,
        b.x0_mm,
        b.y0_mm,
        b.x1_mm,
        b.y1_mm,
    ):
        return 0.0
    return min(
        _point_segment_distance(
            a.x0_mm, a.y0_mm, b.x0_mm, b.y0_mm, b.x1_mm, b.y1_mm
        ),
        _point_segment_distance(
            a.x1_mm, a.y1_mm, b.x0_mm, b.y0_mm, b.x1_mm, b.y1_mm
        ),
        _point_segment_distance(
            b.x0_mm, b.y0_mm, a.x0_mm, a.y0_mm, a.x1_mm, a.y1_mm
        ),
        _point_segment_distance(
            b.x1_mm, b.y1_mm, a.x0_mm, a.y0_mm, a.x1_mm, a.y1_mm
        ),
    )


def check_layout_drc(
    layout: CoupledLayout, rules: DrcRules | None = None
) -> DrcReport:
    """Check routed geometry for width, gap, board-margin and routing issues."""
    selected = rules or DrcRules()
    violations: list[DrcViolation] = []
    if not layout.routed:
        violations.append(
            DrcViolation(
                "not-routed",
                "layout is not routed; select Hairpin for a connected geometry",
            )
        )
    for trace in layout.traces:
        length = math.hypot(
            trace.x1_mm - trace.x0_mm, trace.y1_mm - trace.y0_mm
        )
        if length <= 0.0:
            violations.append(
                DrcViolation(
                    "zero-length",
                    f"{trace.label}: zero-length segment",
                )
            )
        if trace.width_mm <= 0.0:
            violations.append(
                DrcViolation(
                    "zero-width",
                    f"{trace.label}: width must be positive",
                )
            )
        elif trace.width_mm < selected.min_width_mm:
            violations.append(
                DrcViolation(
                    "min-width",
                    f"{trace.label}: width {trace.width_mm:.3f} mm < "
                    f"{selected.min_width_mm:.3f} mm",
                )
            )
        half = trace.width_mm / 2.0
        left = min(trace.x0_mm, trace.x1_mm) - half
        right = max(trace.x0_mm, trace.x1_mm) + half
        bottom = min(trace.y0_mm, trace.y1_mm) - half
        top = max(trace.y0_mm, trace.y1_mm) + half
        board_left = -selected.board_edge_margin_mm
        board_bottom = -selected.board_edge_margin_mm
        board_right = layout.width_mm + selected.board_edge_margin_mm
        board_top = layout.height_mm + selected.board_edge_margin_mm
        if (
            left < board_left + selected.board_margin_mm
            or right > board_right - selected.board_margin_mm
            or bottom < board_bottom + selected.board_margin_mm
            or top > board_top - selected.board_margin_mm
        ):
            violations.append(
                DrcViolation(
                    "board-margin",
                    f"{trace.label}: outside board margin",
                )
            )

    for index, first in enumerate(layout.traces):
        for second in layout.traces[index + 1 :]:
            if first.net and first.net == second.net:
                continue
            gap = _segment_distance(first, second) - (
                first.width_mm + second.width_mm
            ) / 2.0
            if gap < selected.min_gap_mm - 1e-9:
                violations.append(
                    DrcViolation(
                        "min-gap",
                        f"{first.label}/{second.label}: gap {gap:.3f} mm < "
                        f"{selected.min_gap_mm:.3f} mm",
                    )
                )

    for via in layout.vias:
        if via.pad_diameter_mm <= 0.0 or via.drill_diameter_mm <= 0.0:
            violations.append(
                DrcViolation(
                    "via-size",
                    f"{via.label}: pad and drill must be positive",
                )
            )
            continue
        annular = (via.pad_diameter_mm - via.drill_diameter_mm) / 2.0
        if annular < selected.min_annular_mm - 1e-9:
            violations.append(
                DrcViolation(
                    "via-annular",
                    f"{via.label}: annular ring {annular:.3f} mm < "
                    f"{selected.min_annular_mm:.3f} mm",
                )
            )
        pad_half = via.pad_diameter_mm / 2.0
        board_left = -selected.board_edge_margin_mm
        board_bottom = -selected.board_edge_margin_mm
        board_right = layout.width_mm + selected.board_edge_margin_mm
        board_top = layout.height_mm + selected.board_edge_margin_mm
        if (
            via.x_mm - pad_half < board_left + selected.board_margin_mm
            or via.x_mm + pad_half > board_right - selected.board_margin_mm
            or via.y_mm - pad_half < board_bottom + selected.board_margin_mm
            or via.y_mm + pad_half > board_top - selected.board_margin_mm
        ):
            violations.append(
                DrcViolation(
                    "via-board-margin",
                    f"{via.label}: outside board margin",
                )
            )
        for trace in layout.traces:
            if via.net and via.net == trace.net:
                continue
            gap = (
                _point_segment_distance(
                    via.x_mm,
                    via.y_mm,
                    trace.x0_mm,
                    trace.y0_mm,
                    trace.x1_mm,
                    trace.y1_mm,
                )
                - pad_half
                - trace.width_mm / 2.0
            )
            if gap < selected.min_gap_mm - 1e-9:
                violations.append(
                    DrcViolation(
                        "via-trace-gap",
                        f"{via.label}/{trace.label}: gap {gap:.3f} mm < "
                        f"{selected.min_gap_mm:.3f} mm",
                    )
                )

    for index, first_via in enumerate(layout.vias):
        for second_via in layout.vias[index + 1 :]:
            gap = (
                math.hypot(
                    first_via.x_mm - second_via.x_mm,
                    first_via.y_mm - second_via.y_mm,
                )
                - (first_via.pad_diameter_mm + second_via.pad_diameter_mm) / 2.0
            )
            if gap < selected.min_gap_mm - 1e-9:
                violations.append(
                    DrcViolation(
                        "via-gap",
                        f"{first_via.label}/{second_via.label}: "
                        f"gap {gap:.3f} mm < "
                        f"{selected.min_gap_mm:.3f} mm",
                    )
                )
    return DrcReport(tuple(violations), selected)


def _coordinate(value: float) -> str:
    return str(int(round((value + _MARGIN_MM) * 1_000_000.0)))


def _aperture(width: float) -> str:
    return f"C,{width:.6f}"


def render_layout_gerber(
    layout: CoupledLayout,
    *,
    holes_mm: tuple[tuple[float, float, float], ...] = (),
) -> GerberSet:
    """Render RS-274X copper/outline Gerbers plus an Excellon drill file."""
    diameters = sorted(
        {trace.width_mm for trace in layout.traces}
        | {via.pad_diameter_mm for via in layout.vias}
    )
    codes = {diameter: 10 + index for index, diameter in enumerate(diameters)}
    copper = [
        "G04 FilterDesk routed coupled-line copper*",
        "%FSLAX46Y46*%",
        "%MOMM*%",
        "%LPD*%",
    ]
    for diameter in diameters:
        copper.append(f"%ADD{codes[diameter]}{_aperture(diameter)}*%")
    copper.append("G01*")
    for trace in layout.traces:
        copper.append(f"D{codes[trace.width_mm]}*")
        copper.append(f"X{_coordinate(trace.x0_mm)}Y{_coordinate(trace.y0_mm)}D02*")
        copper.append(f"X{_coordinate(trace.x1_mm)}Y{_coordinate(trace.y1_mm)}D01*")
    for via in layout.vias:
        copper.append(f"D{codes[via.pad_diameter_mm]}*")
        copper.append(f"X{_coordinate(via.x_mm)}Y{_coordinate(via.y_mm)}D03*")
    copper.append("M02*")

    board_w = layout.width_mm + 2.0 * _MARGIN_MM
    board_h = layout.height_mm + 2.0 * _MARGIN_MM
    outline = [
        "G04 FilterDesk routed coupled-line board outline*",
        "%FSLAX46Y46*%",
        "%MOMM*%",
        "%ADD10C,0.100000*%",
        "G01*",
        "D10*",
    ]
    corners = (
        (0.0, 0.0),
        (board_w, 0.0),
        (board_w, board_h),
        (0.0, board_h),
        (0.0, 0.0),
    )
    for index, (x, y) in enumerate(corners):
        outline.append(
            f"X{_coordinate(x)}Y{_coordinate(y)}"
            f"{'D02' if index == 0 else 'D01'}*"
        )
    outline.append("M02*")

    all_holes = tuple(
        (via.x_mm, via.y_mm, via.drill_diameter_mm) for via in layout.vias
    ) + tuple(holes_mm)
    drill = ["M48", "METRIC,TZ"]
    if all_holes:
        diameters = sorted({diameter for _, _, diameter in all_holes})
        tools = {diameter: index + 1 for index, diameter in enumerate(diameters)}
        for diameter in diameters:
            drill.append(f"T{tools[diameter]}C{diameter:.3f}")
        drill.append("%")
        for diameter in diameters:
            drill.append(f"T{tools[diameter]}")
            for x, y, hole_diameter in all_holes:
                if hole_diameter == diameter:
                    drill.append(f"X{x:.3f}Y{y:.3f}")
    else:
        drill.append("%")
    drill.append("M30")

    return GerberSet(
        copper="\n".join(copper) + "\n",
        outline="\n".join(outline) + "\n",
        drill="\n".join(drill) + "\n",
    )


def write_layout_gerber(
    layout: CoupledLayout,
    directory: Path | str,
    *,
    stem: str = "filterdesk",
    holes_mm: tuple[tuple[float, float, float], ...] = (),
) -> tuple[Path, Path, Path]:
    """Write copper, outline and drill files and return their paths."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    set_ = render_layout_gerber(layout, holes_mm=holes_mm)
    copper = target / f"{stem}-F_Cu.gbr"
    outline = target / f"{stem}-Edge_Cuts.gbr"
    drill = target / f"{stem}.drl"
    copper.write_text(set_.copper, encoding="utf-8")
    outline.write_text(set_.outline, encoding="utf-8")
    drill.write_text(set_.drill, encoding="utf-8")
    return copper, outline, drill


__all__ = [
    "CoupledPcbError",
    "DrcReport",
    "DrcRules",
    "DrcViolation",
    "GerberSet",
    "check_layout_drc",
    "render_layout_gerber",
    "write_layout_gerber",
]
