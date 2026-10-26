"""Winding connection schematic and stylized toroid drawing (SVG).

The output is intentionally a *connection-level* drawing, not a manufacturing
photograph: it shows the winding order, tap/polarity and terminal mapping. The
physical turn layout still depends on the wire route and insulation. For TLT
kinds the drawing is a simplified behavioral representation.
"""

# SVG attribute strings are easier to audit on one line.
# ruff: noqa: E501

from __future__ import annotations

import html
from dataclasses import dataclass

from filterdesk.domain.circuit import BalunSpec


@dataclass(frozen=True, slots=True)
class WindingDiagram:
    title: str
    svg: str
    schedule: tuple[str, ...]


def _esc(text: object) -> str:
    return html.escape(str(text))


def _coil(x: float, y0: float, y1: float, turns: int, color: str) -> str:
    """Draw a compact vertical coil symbol from y0 (bottom) to y1 (top)."""
    count = max(3, min(turns, 10))
    height = y0 - y1
    step = height / count
    parts = [f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1}" stroke="{color}" stroke-width="2"/>']
    radius = min(12.0, step * 0.55)
    for index in range(count):
        cy = y0 - step * (index + 0.5)
        parts.append(
            f'<circle cx="{x}" cy="{cy:.2f}" r="{radius:.2f}" '
            f'fill="none" stroke="{color}" stroke-width="2"/>'
        )
    return "".join(parts)


def _schematic(
    kind: str,
    topology: str,
    np: int,
    ns: int,
    z_unbal: float,
    z_bal: float,
    line_z0: float,
) -> list[str]:
    parts: list[str] = [
        '<rect x="30" y="40" width="390" height="330" rx="12" '
        'fill="none" stroke="#555" stroke-width="1.5"/>',
        '<text x="225" y="68" text-anchor="middle" font-size="16" '
        'font-family="sans-serif" fill="#111">Electrical connection</text>',
    ]
    if kind == "guanella":
        ratio = max(1, round(ns / max(np, 1)))
        parts += [
            f'<text x="225" y="94" text-anchor="middle" font-size="13" '
            f'font-family="sans-serif" fill="#444">Guanella TLT: '
            f'{ratio} line(s), input parallel / output series</text>',
            '<line x1="75" y1="270" x2="75" y2="120" stroke="#111" stroke-width="2"/>',
            '<line x1="375" y1="270" x2="375" y2="120" stroke="#111" stroke-width="2"/>',
            '<line x1="75" y1="270" x2="375" y2="270" stroke="#1565c0" stroke-width="2"/>',
            '<circle cx="75" cy="270" r="5" fill="#111"/>',
            '<circle cx="375" cy="120" r="5" fill="#111"/>',
            f'<text x="75" y="295" text-anchor="middle" font-size="12" '
            f'font-family="sans-serif" fill="#111">IN {z_unbal:g}Ω</text>',
            f'<text x="375" y="105" text-anchor="middle" font-size="12" '
            f'font-family="sans-serif" fill="#111">OUT {z_bal:g}Ω</text>',
        ]
        count = max(1, min(ratio, 4))
        for i in range(count):
            y = 140 + i * 38
            parts += [
                f'<rect x="120" y="{y - 13}" width="210" height="26" rx="6" '
                'fill="#f5f5f5" stroke="#1565c0" stroke-width="1.5"/>',
                f'<text x="225" y="{y + 5}" text-anchor="middle" font-size="11" '
                f'font-family="sans-serif" fill="#111">TL{i + 1} Z0 '
                f'{line_z0:g}Ω</text>',
                f'<line x1="75" y1="{y}" x2="120" y2="{y}" stroke="#1565c0" '
                'stroke-width="2"/>',
                f'<line x1="330" y1="{y}" x2="375" y2="{y}" stroke="#1565c0" '
                'stroke-width="2"/>',
            ]
        parts.append(
            '<text x="225" y="330" text-anchor="middle" font-size="11" '
            'font-family="sans-serif" fill="#555">input bus left, series '
            'output bus right</text>'
        )
    elif kind == "ruthroff":
        parts += [
            '<text x="225" y="94" text-anchor="middle" font-size="13" '
            'font-family="sans-serif" fill="#444">Ruthroff TLT: transformer '
            '+ transmission line</text>',
            '<rect x="65" y="125" width="120" height="110" rx="8" '
            'fill="#f5f5f5" stroke="#1565c0" stroke-width="2"/>',
            '<text x="125" y="165" text-anchor="middle" font-size="12" '
            'font-family="sans-serif" fill="#111">1:2</text>',
            '<text x="125" y="185" text-anchor="middle" font-size="11" '
            'font-family="sans-serif" fill="#111">transformer</text>',
            '<rect x="265" y="145" width="120" height="70" rx="8" '
            'fill="#f5f5f5" stroke="#c62828" stroke-width="2"/>',
            f'<text x="325" y="175" text-anchor="middle" font-size="12" '
            f'font-family="sans-serif" fill="#111">TL Z0 {line_z0:g}Ω</text>',
            '<line x1="65" y1="175" x2="35" y2="175" stroke="#111" stroke-width="2"/>',
            '<line x1="185" y1="175" x2="265" y2="175" stroke="#c62828" stroke-width="2"/>',
            '<line x1="385" y1="175" x2="415" y2="175" stroke="#111" stroke-width="2"/>',
            '<line x1="185" y1="215" x2="265" y2="215" stroke="#1565c0" stroke-width="2"/>',
            '<circle cx="35" cy="175" r="5" fill="#111"/>',
            '<circle cx="415" cy="175" r="5" fill="#111"/>',
            f'<text x="35" y="200" text-anchor="middle" font-size="12" '
            f'font-family="sans-serif" fill="#111">IN {z_unbal:g}Ω</text>',
            f'<text x="415" y="160" text-anchor="middle" font-size="12" '
            f'font-family="sans-serif" fill="#111">OUT {z_bal:g}Ω</text>',
            '<text x="225" y="300" text-anchor="middle" font-size="11" '
            'font-family="sans-serif" fill="#555">verify the Ruthroff '
            'crossover/polarity for the chosen build</text>',
        ]
    elif kind == "choke":
        parts += [
            '<text x="225" y="94" text-anchor="middle" font-size="13" '
            'font-family="sans-serif" fill="#444">Choke (bifilar common-mode)'
            '</text>',
            '<line x1="70" y1="170" x2="135" y2="170" stroke="#1565c0" stroke-width="3"/>',
            '<line x1="70" y1="230" x2="135" y2="230" stroke="#c62828" stroke-width="3"/>',
            '<line x1="135" y1="170" x2="325" y2="170" stroke="#1565c0" stroke-width="3"/>',
            '<line x1="135" y1="230" x2="325" y2="230" stroke="#c62828" stroke-width="3"/>',
            '<line x1="325" y1="170" x2="390" y2="170" stroke="#1565c0" stroke-width="3"/>',
            '<line x1="325" y1="230" x2="390" y2="230" stroke="#c62828" stroke-width="3"/>',
            '<circle cx="230" cy="200" r="38" fill="none" stroke="#555" stroke-width="2"/>',
            '<text x="230" y="205" text-anchor="middle" font-size="11" '
            'font-family="sans-serif" fill="#555">CMC</text>',
            f'<text x="70" y="155" text-anchor="middle" font-size="12" '
            f'font-family="sans-serif" fill="#111">IN {z_unbal:g}Ω</text>',
            f'<text x="390" y="155" text-anchor="middle" font-size="12" '
            f'font-family="sans-serif" fill="#111">OUT {z_bal:g}Ω</text>',
            '<text x="225" y="300" text-anchor="middle" font-size="11" '
            'font-family="sans-serif" fill="#555">differential pass-through; '
            'common-mode impedance is not shown</text>',
        ]
    elif topology == "autotransformer":
        parts.append(_coil(220, 300, 120, ns, "#1565c0"))
        tap_y = 300 - (300 - 120) * (np / max(ns, 1))
        parts += [
            f'<line x1="220" y1="{tap_y:.2f}" x2="120" y2="{tap_y:.2f}" '
            'stroke="#1565c0" stroke-width="2"/>',
            f'<circle cx="220" cy="{tap_y:.2f}" r="5" fill="#1565c0"/>',
            '<line x1="220" y1="300" x2="120" y2="300" stroke="#1565c0" stroke-width="2"/>',
            '<line x1="220" y1="120" x2="340" y2="120" stroke="#1565c0" stroke-width="2"/>',
            '<line x1="120" y1="300" x2="120" y2="335" stroke="#111" stroke-width="2"/>',
            '<line x1="340" y1="120" x2="340" y2="90" stroke="#111" stroke-width="2"/>',
            '<circle cx="120" cy="335" r="5" fill="#111"/>',
            '<circle cx="340" cy="90" r="5" fill="#111"/>',
            f'<text x="120" y="360" text-anchor="middle" font-size="13" '
            f'font-family="sans-serif" fill="#111">COMMON / IN {z_unbal:g}Ω</text>',
            f'<text x="120" y="{tap_y + 20:.2f}" text-anchor="end" font-size="12" '
            f'font-family="sans-serif" fill="#1565c0">TAP ({np}T)</text>',
            f'<text x="340" y="80" text-anchor="middle" font-size="13" '
            f'font-family="sans-serif" fill="#111">OUT {z_bal:g}Ω</text>',
            f'<text x="242" y="220" font-size="12" font-family="sans-serif" '
            f'fill="#1565c0">{ns}T total</text>',
        ]
    else:
        parts += [
            _coil(175, 300, 130, np, "#1565c0"),
            _coil(285, 300, 100, ns, "#c62828"),
            '<circle cx="175" cy="130" r="4" fill="#1565c0"/>',
            '<circle cx="285" cy="100" r="4" fill="#c62828"/>',
            '<line x1="175" y1="300" x2="95" y2="300" stroke="#111" stroke-width="2"/>',
            '<line x1="175" y1="130" x2="95" y2="130" stroke="#1565c0" stroke-width="2"/>',
            '<line x1="285" y1="300" x2="365" y2="300" stroke="#111" stroke-width="2"/>',
            '<line x1="285" y1="100" x2="365" y2="100" stroke="#c62828" stroke-width="2"/>',
            f'<text x="175" y="335" text-anchor="middle" font-size="13" '
            f'font-family="sans-serif" fill="#111">P {np}T / {z_unbal:g}Ω</text>',
            f'<text x="285" y="75" text-anchor="middle" font-size="13" '
            f'font-family="sans-serif" fill="#111">S {ns}T / {z_bal:g}Ω</text>',
            '<text x="230" y="220" text-anchor="middle" font-size="12" '
            'font-family="sans-serif" fill="#111">dots = polarity</text>',
        ]
    return parts


def winding_diagram(
    *,
    kind: str,
    topology: str,
    n_primary: int,
    n_secondary: int,
    total_turns: int,
    core: str = "",
    z_unbalanced_ohm: float = 0.0,
    z_balanced_ohm: float = 0.0,
    line_z0_ohm: float = 0.0,
    line_length_m: float = 0.0,
) -> WindingDiagram:
    """Return a connection schematic + stylized toroid SVG and instructions."""
    if n_primary < 1 or n_secondary < 1:
        raise ValueError("winding turns must be >= 1")
    total = total_turns or (
        n_secondary if topology == "autotransformer" else n_primary + n_secondary
    )
    title = f"{kind} {n_primary}:{n_secondary} on {core or 'toroid'}"
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 460 420" '
        'width="460" height="420">',
        '<rect width="460" height="420" fill="#ffffff"/>',
        f'<text x="230" y="25" text-anchor="middle" font-size="18" '
        f'font-family="sans-serif" fill="#111">{_esc(title)}</text>',
        *_schematic(
            kind,
            topology,
            n_primary,
            n_secondary,
            z_unbalanced_ohm,
            z_balanced_ohm,
            line_z0_ohm,
        ),
        '</svg>',
    ]
    schedule: list[str] = []
    if kind == "guanella":
        ratio = max(1, round(n_secondary / max(n_primary, 1)))
        schedule += [
            f"Guanella TLT: {ratio} transmission line(s), Z0 {line_z0_ohm:g} Ω.",
            "Connect the line inputs in parallel and the line outputs in series.",
            f"Input {z_unbalanced_ohm:g} Ω / output {z_balanced_ohm:g} Ω; "
            "follow the validated crossover layout.",
        ]
    elif kind == "ruthroff":
        schedule += [
            f"Ruthroff TLT: transformer + transmission line, Z0 {line_z0_ohm:g} Ω.",
            "Use the Ruthroff crossover/polarity for the actual build; this is "
            "not the Guanella parallel/series connection.",
        ]
    elif kind == "choke":
        schedule += [
            f"1:1 bifilar common-mode choke: {n_primary} turns per wire.",
            "The differential signal passes through; the common-mode impedance "
            "is not represented in the differential 2-port.",
        ]
    elif topology == "autotransformer":
        schedule += [
            f"Autotransformer: wind {total} turns on {core or 'the core'}.",
            f"Count from the start and bring out a tap at turn {n_primary}.",
            f"Input across START-TAP ({z_unbalanced_ohm:g} Ω); output across "
            f"START-FINISH ({z_balanced_ohm:g} Ω). START is common.",
            "Autotransformer: no galvanic isolation; observe the common ground.",
        ]
    elif topology == "isolated":
        schedule += [
            f"Isolated: wind primary {n_primary} turns and secondary "
            f"{n_secondary} turns on {core or 'the core'}.",
            "Mark the start of both windings as the dotted/polarity terminal.",
            f"Total copper turns: {total}.",
        ]
    else:
        schedule += [
            f"{kind}: behavioral connection for {n_primary}:{n_secondary}.",
            "Follow the validated TLT/choke layout (twisted pair/coax, crossover "
            "and common-mode return); this drawing is not an EM layout.",
        ]
    if kind in {"guanella", "ruthroff"}:
        schedule.append(
            f"TLT line model: Z0 {line_z0_ohm:g} Ω, length {line_length_m * 1000:.1f} mm "
            "(blank length = quarter-wave at band center)."
        )
    if kind == "choke":
        schedule.append(
            "Common-mode choke: differential signal sees a through connection; "
            "the common-mode impedance is not shown in the differential 2-port."
        )
    return WindingDiagram(title=title, svg="\n".join(svg), schedule=tuple(schedule))


def winding_diagram_for_spec(spec: BalunSpec) -> WindingDiagram:
    """Build a diagram from a persisted output-balun specification."""
    secondary = (
        spec.total_turns - (spec.turns or 0)
        if spec.topology == "isolated" and spec.total_turns
        else spec.total_turns
    )
    return winding_diagram(
        kind=spec.kind,
        topology=spec.topology,
        n_primary=max(1, spec.turns or 1),
        n_secondary=max(1, secondary),
        total_turns=spec.total_turns or secondary,
        core=spec.core,
        z_unbalanced_ohm=spec.z_unbalanced_ohm,
        z_balanced_ohm=spec.z_balanced_ohm,
        line_z0_ohm=spec.z0_line_ohm,
        line_length_m=spec.length_m,
    )


__all__ = ["WindingDiagram", "winding_diagram", "winding_diagram_for_spec"]
