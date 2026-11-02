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


@dataclass(frozen=True, slots=True)
class CoupledLayout:
    mode: LayoutMode
    width_mm: float
    height_mm: float
    traces: tuple[LayoutTrace, ...]
    section_lengths_mm: tuple[float, ...]
    warnings: tuple[str, ...] = ()
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
            LayoutTrace(0.0, y, length, y, width, f"S{section.index}a")
        )
        traces.append(
            LayoutTrace(
                0.0,
                y + width + gap,
                length,
                y + width + gap,
                width,
                f"S{section.index}b",
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
    spacing = width + gap
    traces: list[LayoutTrace] = []
    for index in range(design.config.order):
        x_left = index * spacing
        x_right = x_left + width + gap
        traces.append(
            LayoutTrace(x_left, 0.0, x_left, arm, width, f"R{index + 1}a")
        )
        traces.append(
            LayoutTrace(
                x_right, 0.0, x_right, arm, width, f"R{index + 1}b"
            )
        )
        traces.append(
            LayoutTrace(
                x_left, arm, x_right, arm, width, f"R{index + 1}bend"
            )
        )
    return CoupledLayout(
        mode=LayoutMode.HAIRPIN,
        width_mm=(design.config.order - 1) * spacing + width + gap + width,
        height_mm=arm,
        traces=tuple(traces),
        section_lengths_mm=lengths,
        warnings=(
            "Conceptual hairpin sketch only: uniform average width/gap, "
            "idealized bends and no routing/discontinuity/EM model.",
        ),
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
    for index in range(design.config.order):
        x = index * spacing
        top = index % 2 == 0
        traces.append(
            LayoutTrace(
                x,
                0.0 if top else length,
                x,
                length if top else 0.0,
                width,
                f"R{index + 1}",
            )
        )
    return CoupledLayout(
        mode=LayoutMode.INTERDIGITAL,
        width_mm=(design.config.order - 1) * spacing + 2.0 * width,
        height_mm=length,
        traces=tuple(traces),
        section_lengths_mm=lengths,
        warnings=(
            "Conceptual interdigital sketch only: uniform average width/gap, "
            "no shorting vias, bends, discontinuities or EM model.",
        ),
        meta={"average_width_mm": width, "average_gap_mm": gap},
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
    "build_coupled_layout",
    "render_coupled_layout_svg",
]
