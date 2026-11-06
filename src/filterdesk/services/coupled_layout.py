"""Conceptual layout sketches for coupled-line bandpass filters.

These are to-scale trace sketches built from the synthesized section width,
gap and quarter-wave length. They are not routed fabrication layouts: bends,
discontinuities, open-end effects, dispersion and EM coupling are not modeled.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from html import escape

from filterdesk.services.coupled_line import CoupledLineBpfDesign

_C0 = 299_792_458.0


class CoupledLayoutError(ValueError):
    """Raised when a layout sketch cannot be built."""


class LayoutMode(StrEnum):
    EDGE = "edge"
    HAIRPIN = "hairpin"
    INTERDIGITAL = "interdigital"


@dataclass(frozen=True, slots=True)
class LayoutTrace:
    x0_mm: float
    y0_mm: float
    x1_mm: float
    y1_mm: float
    width_mm: float
    label: str
    net: str = ""


@dataclass(frozen=True, slots=True)
class LayoutVia:
    x_mm: float
    y_mm: float
    pad_diameter_mm: float
    drill_diameter_mm: float
    label: str
    net: str = ""


@dataclass(frozen=True, slots=True)
class CoupledLayout:
    mode: LayoutMode
    width_mm: float
    height_mm: float
    traces: tuple[LayoutTrace, ...]
    section_lengths_mm: tuple[float, ...]
    vias: tuple[LayoutVia, ...] = ()
    warnings: tuple[str, ...] = ()
    routed: bool = False
    meta: dict[str, object] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"{self.mode.value} layout sketch: "
            f"{self.width_mm:.2f} x {self.height_mm:.2f} mm, "
            f"{len(self.traces)} traces"
        )


def _section_lengths(design: CoupledLineBpfDesign) -> tuple[float, ...]:
    lengths: list[float] = []
    for section in design.sections:
        if section.eeff_even is None or section.eeff_odd is None:
            raise CoupledLayoutError(
                "section geometry is missing; design with a substrate first"
            )
        eeff = (section.eeff_even + section.eeff_odd) / 2.0
        lengths.append(
            _C0
            / (4.0 * design.config.center_hz * math.sqrt(eeff))
            * 1000.0
        )
    return tuple(lengths)


def _edge_layout(
    design: CoupledLineBpfDesign, lengths: tuple[float, ...]
) -> CoupledLayout:
    traces: list[LayoutTrace] = []
    y = 0.0
    max_width = 0.0
    max_x = 0.0
    for section, length in zip(design.sections, lengths, strict=True):
        width = section.width_mm or 0.0
        gap = section.gap_mm or 0.0
        if width <= 0.0 or gap <= 0.0:
            raise CoupledLayoutError("section width/gap is missing")
        max_width = max(max_width, width)
        max_x = max(max_x, length)
        traces.append(
            LayoutTrace(
                0.0, y, length, y, width, f"S{section.index}a",
                net=f"S{section.index}a",
            )
        )
        traces.append(
            LayoutTrace(
                0.0,
                y + width + gap,
                length,
                y + width + gap,
                width,
                f"S{section.index}b",
                net=f"S{section.index}b",
            )
        )
        y += 2.0 * width + gap + 3.0
    return CoupledLayout(
        mode=LayoutMode.EDGE,
        width_mm=max_x,
        height_mm=max(y - 3.0, max_width),
        traces=tuple(traces),
        section_lengths_mm=lengths,
        warnings=(
            "Conceptual section sketch only: sections are drawn separately and "
            "are not connected or routed.",
        ),
    )


def _hairpin_layout(
    design: CoupledLineBpfDesign, lengths: tuple[float, ...]
) -> CoupledLayout:
    sections = design.sections
    widths = [s.width_mm or 0.0 for s in sections]
    gaps = [s.gap_mm or 0.0 for s in sections]
    if any(value <= 0.0 for value in widths + gaps):
        raise CoupledLayoutError("section width/gap is missing")
    width = sum(widths) / len(widths)
    gap = sum(gaps) / len(gaps)
    lambda_half = 2.0 * sum(lengths) / len(lengths)
    bend = width + gap
    arm = max((lambda_half - bend) / 2.0, 0.0)
    # Adjacent resonators need one gap between their facing arms, so the
    # pitch is twice the arm-to-arm spacing.
    spacing = 2.0 * (width + gap)
    traces: list[LayoutTrace] = []
    for index in range(design.config.order):
        x_left = index * spacing
        x_right = x_left + width + gap
        net = f"R{index + 1}"
        traces.append(
            LayoutTrace(
                x_left, 0.0, x_left, arm, width, f"R{index + 1}a", net=net
            )
        )
        traces.append(
            LayoutTrace(
                x_right, 0.0, x_right, arm, width, f"R{index + 1}b", net=net
            )
        )
        traces.append(
            LayoutTrace(
                x_left, arm, x_right, arm, width, f"R{index + 1}bend", net=net
            )
        )
    return CoupledLayout(
        mode=LayoutMode.HAIRPIN,
        width_mm=(design.config.order - 1) * spacing + width + gap + width,
        height_mm=arm,
        traces=tuple(traces),
        section_lengths_mm=lengths,
        warnings=(
            "Routed hairpin geometry handoff: uniform average width/gap, "
            "idealized bends and no discontinuity/EM model.",
        ),
        routed=True,
        meta={"arm_mm": arm, "bend_mm": bend, "average_width_mm": width},
    )


def _interdigital_layout(
    design: CoupledLineBpfDesign, lengths: tuple[float, ...]
) -> CoupledLayout:
    sections = design.sections
    widths = [s.width_mm or 0.0 for s in sections]
    gaps = [s.gap_mm or 0.0 for s in sections]
    if any(value <= 0.0 for value in widths + gaps):
        raise CoupledLayoutError("section width/gap is missing")
    width = sum(widths) / len(widths)
    gap = sum(gaps) / len(gaps)
    length = sum(lengths) / len(lengths)
    spacing = width + gap
    traces: list[LayoutTrace] = []
    vias: list[LayoutVia] = []
    via_drill = 0.3
    via_pad = max(width, 0.8)
    for index in range(design.config.order):
        x = index * spacing
        top = index % 2 == 0
        net = f"R{index + 1}"
        traces.append(
            LayoutTrace(
                x,
                0.0 if top else length,
                x,
                length if top else 0.0,
                width,
                net,
                net=net,
            )
        )
        vias.append(
            LayoutVia(
                x,
                length if top else 0.0,
                via_pad,
                via_drill,
                f"R{index + 1}via",
                net=net,
            )
        )
    return CoupledLayout(
        mode=LayoutMode.INTERDIGITAL,
        width_mm=(design.config.order - 1) * spacing + 2.0 * width,
        height_mm=length,
        traces=tuple(traces),
        section_lengths_mm=lengths,
        vias=tuple(vias),
        warnings=(
            "Interdigital via-routed geometry handoff: uniform average "
            "width/gap, idealized shorting vias and no via/EM model.",
        ),
        routed=True,
        meta={
            "average_width_mm": width,
            "average_gap_mm": gap,
            "via_drill_mm": via_drill,
            "via_pad_mm": via_pad,
        },
    )


def build_coupled_layout(
    design: CoupledLineBpfDesign, mode: LayoutMode | str = LayoutMode.EDGE
) -> CoupledLayout:
    """Build a conceptual to-scale sketch from a synthesized BPF."""
    if design.substrate is None:
        raise CoupledLayoutError(
            "layout needs a substrate; design the filter with geometry first"
        )
    selected = LayoutMode(str(mode))
    lengths = _section_lengths(design)
    if selected is LayoutMode.EDGE:
        return _edge_layout(design, lengths)
    if selected is LayoutMode.HAIRPIN:
        return _hairpin_layout(design, lengths)
    return _interdigital_layout(design, lengths)


def render_coupled_layout_dxf(layout: CoupledLayout) -> str:
    """Render a minimal ASCII DXF (mm) for external EM/PCB import."""
    margin = 3.0
    board_w = layout.width_mm + 2.0 * margin
    board_h = layout.height_mm + 2.0 * margin

    def solid(trace: LayoutTrace) -> list[str]:
        dx = trace.x1_mm - trace.x0_mm
        dy = trace.y1_mm - trace.y0_mm
        half = trace.width_mm / 2.0
        if abs(dx) >= abs(dy):
            x0, x1 = trace.x0_mm + margin, trace.x1_mm + margin
            y = trace.y0_mm + margin + half
            corners = [
                (x0, y - half),
                (x1, y - half),
                (x1, y + half),
                (x0, y + half),
            ]
        else:
            y0, y1 = trace.y0_mm + margin, trace.y1_mm + margin
            x = trace.x0_mm + margin + half
            corners = [
                (x - half, y0),
                (x - half, y1),
                (x + half, y1),
                (x + half, y0),
            ]
        out = ["0", "SOLID", "8", "TOP_COPPER"]
        for index, (x, y) in enumerate(corners):
            out.extend([str(10 + index), f"{x:.6f}", str(20 + index), f"{y:.6f}"])
        return out

    lines = [
        "999",
        "FilterDesk conceptual coupled-line layout - not EM-validated",
        "0",
        "SECTION",
        "2",
        "HEADER",
        "9",
        "$ACADVER",
        "1",
        "AC1009",
        "9",
        "$INSUNITS",
        "70",
        "4",
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "TABLES",
        "0",
        "TABLE",
        "2",
        "LAYER",
        "70",
        "2",
        "0",
        "LAYER",
        "2",
        "TOP_COPPER",
        "70",
        "0",
        "62",
        "1",
        "6",
        "CONTINUOUS",
        "0",
        "LAYER",
        "2",
        "BOARD_OUTLINE",
        "70",
        "0",
        "62",
        "7",
        "6",
        "CONTINUOUS",
        "0",
        "ENDTAB",
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "ENTITIES",
    ]
    for trace in layout.traces:
        lines.extend(solid(trace))
    # Board outline as four LINE entities.
    for x0, y0, x1, y1 in (
        (0.0, 0.0, board_w, 0.0),
        (board_w, 0.0, board_w, board_h),
        (board_w, board_h, 0.0, board_h),
        (0.0, board_h, 0.0, 0.0),
    ):
        lines.extend(
            [
                "0",
                "LINE",
                "8",
                "BOARD_OUTLINE",
                "10",
                f"{x0:.6f}",
                "20",
                f"{y0:.6f}",
                "11",
                f"{x1:.6f}",
                "21",
                f"{y1:.6f}",
            ]
        )
    lines.extend(["0", "ENDSEC", "0", "EOF"])
    return "\n".join(lines) + "\n"


def render_coupled_layout_svg(layout: CoupledLayout) -> str:
    """Render a simple standalone SVG with mm units."""
    margin = 3.0
    width = max(layout.width_mm + 2.0 * margin, 1.0)
    height = max(layout.height_mm + 2.0 * margin, 1.0)
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width:.3f}mm" height="{height:.3f}mm" '
            f'viewBox="0 0 {width:.3f} {height:.3f}">'
        ),
        '<rect width="100%" height="100%" fill="#f8f8f8"/>',
        f'<text x="{margin:.3f}" y="{margin:.6f}" font-size="1.8" '
        f'font-family="sans-serif" fill="#222">{escape(layout.summary())}</text>',
    ]
    for trace in layout.traces:
        parts.append(
            f'<line x1="{trace.x0_mm + margin:.4f}" '
            f'y1="{trace.y0_mm + margin * 2:.4f}" '
            f'x2="{trace.x1_mm + margin:.4f}" '
            f'y2="{trace.y1_mm + margin * 2:.4f}" '
            f'stroke="#b87333" stroke-width="{trace.width_mm:.4f}" '
            f'stroke-linecap="butt"/>'
        )
    parts.append(
        f'<text x="{margin:.3f}" y="{height - 1.0:.4f}" '
        f'font-size="1.4" font-family="sans-serif" fill="#555">'
        "Conceptual sketch - not EM-validated</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


__all__ = [
    "CoupledLayout",
    "CoupledLayoutError",
    "LayoutMode",
    "LayoutTrace",
    "LayoutVia",
    "build_coupled_layout",
    "render_coupled_layout_dxf",
    "render_coupled_layout_svg",
]
