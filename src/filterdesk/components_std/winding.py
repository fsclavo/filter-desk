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
import math
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
) -> list[str]:
    parts: list[str] = [
        '<rect x="30" y="40" width="390" height="330" rx="12" '
        'fill="none" stroke="#555" stroke-width="1.5"/>',
        '<text x="225" y="68" text-anchor="middle" font-size="16" '
        'font-family="sans-serif" fill="#111">Electrical connection</text>',
    ]
    if topology == "autotransformer":
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
    elif topology == "isolated":
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
    else:
        parts += [
            '<rect x="115" y="120" width="220" height="100" rx="10" '
            'fill="#f5f5f5" stroke="#444" stroke-width="2"/>',
            f'<text x="225" y="158" text-anchor="middle" font-size="15" '
            f'font-family="sans-serif" fill="#111">{_esc(kind.upper())}</text>',
            f'<text x="225" y="182" text-anchor="middle" font-size="12" '
            f'font-family="sans-serif" fill="#444">{np}T : {ns}T</text>',
            f'<text x="225" y="204" text-anchor="middle" font-size="12" '
            f'font-family="sans-serif" fill="#444">{z_unbal:g}Ω ↔ {z_bal:g}Ω</text>',
            '<line x1="115" y1="170" x2="55" y2="170" stroke="#111" stroke-width="2"/>',
            '<line x1="335" y1="170" x2="395" y2="170" stroke="#111" stroke-width="2"/>',
            '<text x="55" y="155" text-anchor="middle" font-size="12" '
            'font-family="sans-serif" fill="#111">IN</text>',
            '<text x="395" y="155" text-anchor="middle" font-size="12" '
            'font-family="sans-serif" fill="#111">OUT</text>',
            '<text x="225" y="270" text-anchor="middle" font-size="12" '
            'font-family="sans-serif" fill="#444">TLT / choke connection '
            '(behavioral; not a full crossover drawing)</text>',
        ]
    return parts


def _toroid(
    kind: str,
    topology: str,
    np: int,
    ns: int,
    total: int,
    core: str,
) -> list[str]:
    parts: list[str] = [
        '<rect x="440" y="40" width="430" height="330" rx="12" '
        'fill="none" stroke="#555" stroke-width="1.5"/>',
        '<text x="655" y="68" text-anchor="middle" font-size="16" '
        'font-family="sans-serif" fill="#111">Winding on toroid</text>',
        '<ellipse cx="655" cy="220" rx="150" ry="88" fill="#fafafa" '
        'stroke="#333" stroke-width="3"/>',
        '<ellipse cx="655" cy="220" rx="82" ry="38" fill="#ffffff" '
        'stroke="#333" stroke-width="3"/>',
    ]
    loops = max(8, min(total, 24))
    for index in range(loops):
        angle = 2.0 * math.pi * index / loops
        x0 = 655 + 150 * math.cos(angle)
        y0 = 220 + 88 * math.sin(angle)
        x1 = 655 + 82 * math.cos(angle)
        y1 = 220 + 38 * math.sin(angle)
        color = "#1565c0"
        if topology == "isolated" and index % 2:
            color = "#c62828"
        parts.append(
            f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" '
            f'y2="{y1:.2f}" stroke="{color}" stroke-width="4" '
            'stroke-linecap="round"/>'
        )
    if topology == "autotransformer":
        angle = 2.0 * math.pi * min(np / max(ns, 1), 1.0)
        tx = 655 + 116 * math.cos(angle)
        ty = 220 + 63 * math.sin(angle)
        parts.append(
            f'<circle cx="{tx:.2f}" cy="{ty:.2f}" r="7" fill="#ff9800" '
            'stroke="#333" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{tx + 12:.2f}" y="{ty - 8:.2f}" font-size="12" '
            f'font-family="sans-serif" fill="#e65100">TAP {np}T</text>'
        )
    label = f"{core or 'core'}: {np}T + {ns - np if topology == 'isolated' else 0}T" if topology == "isolated" else f"{core or 'core'}: {total}T, tap {np}T"
    parts += [
        f'<text x="655" y="342" text-anchor="middle" font-size="12" '
        f'font-family="sans-serif" fill="#111">{_esc(label)}</text>',
        f'<text x="655" y="360" text-anchor="middle" font-size="11" '
        f'font-family="sans-serif" fill="#666">{_esc(kind)} / {_esc(topology)}</text>',
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
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 420" '
        'width="900" height="420">',
        '<rect width="900" height="420" fill="#ffffff"/>',
        f'<text x="450" y="25" text-anchor="middle" font-size="18" '
        f'font-family="sans-serif" fill="#111">{_esc(title)}</text>',
        *_schematic(kind, topology, n_primary, n_secondary, z_unbalanced_ohm, z_balanced_ohm),
        *_toroid(kind, topology, n_primary, n_secondary, total, core),
        '</svg>',
    ]
    schedule: list[str] = []
    if topology == "autotransformer":
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
