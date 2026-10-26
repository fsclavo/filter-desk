"""Qucs ``.sch`` schematic export from a canonical :class:`Circuit` (Phase 10).

Best-effort: emits Qucs' XML schematic with components, wires and S-parameter
test ports for a series/shunt ladder. Pin offsets follow the standard Qucs
symbols (R/C/L ports at ±30 px; ``GND``/``Port`` centred); wire endpoints touch
component pins so Qucs connects them geometrically.
"""

from __future__ import annotations

from pathlib import Path

from filterdesk.domain.circuit import (
    Circuit,
    IdealCapacitor,
    IdealInductor,
    IdealParallelLC,
    IdealResistor,
    IdealSeriesLC,
    NonIdealCapacitor,
    NonIdealInductor,
)
from filterdesk.domain.enums import ElementRole
from filterdesk.io.spice import SpiceExportError

_RAIL_Y = 100
_X_START = 100
_PIN = 30  # R/C/L default port offset (px)
_SHUNT_DROP = 30  # wire from rail to shunt top pin
_SHUNT_LEN = 60  # shunt symbol spans ±30

#: Property tails after the quoted value (Temperature/Symbol per Qucs symbols).
_TAIL: dict[str, str] = {
    "R": '"26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0',
    "C": '"0" 0 "neutral" 0',
    "L": '"0" 0 "neutral" 0',
}


def _value(value: float) -> str:
    return f"{value:.10g}"


class _Builder:
    def __init__(self) -> None:
        self.components: list[str] = []
        self.wires: list[str] = []
        self.x = _X_START

    def _comp(
        self, ctype: str, name: str, x: int, y: int, rotate: int, value: str
    ) -> None:
        self.components.append(
            f'<{ctype} {name} 1 {x} {y} 18 -26 0 {rotate} "{value}" 1 {_TAIL[ctype]}>'
        )

    def _wire(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self.wires.append(f'<{x1} {y1} {x2} {y2} "" 0 0 0 "">')

    def place_series(self, ctype: str, name: str, value: str) -> None:
        cx = self.x + _PIN
        # Left pin lands on the current node (no wire needed); right pin becomes
        # the next node.
        self._comp(ctype, name, cx, _RAIL_Y, 0, value)
        self.x = cx + _PIN

    def place_shunt(self, ctype: str, name: str, value: str) -> None:
        cx = self.x
        top = _RAIL_Y + _SHUNT_DROP
        bottom = top + _SHUNT_LEN
        self._wire(cx, _RAIL_Y, cx, top)
        self._comp(ctype, name, cx, top + _SHUNT_LEN // 2, 1, value)
        self._wire(cx, bottom, cx, bottom + 20)
        self.components.append(f"<GND * 1 {cx} {bottom + 20} 0 0 0 0>")


def qucs_schematic(
    circuit: Circuit,
    *,
    title: str = "FilterDesk export",
    z0_ohm: float = 50.0,
) -> str:
    """Return a Qucs ``.sch`` schematic for ``circuit`` (best-effort)."""
    if not circuit.elements:
        raise SpiceExportError("circuit has no elements")
    if circuit.output_transformer_ratio != 1.0:
        raise SpiceExportError(
            "ideal output transformer export is not implemented yet"
        )
    del title, z0_ohm  # reserved for a future simulation block; API symmetry

    b = _Builder()
    b.components.append(f'<Port P1 1 {_X_START} {_RAIL_Y} -23 12 0 0 "1" 1 "analog" 0>')

    for el in circuit.elements:
        if isinstance(el, (IdealInductor, NonIdealInductor)):
            ctype, value = "L", el.value_h
        elif isinstance(el, (IdealCapacitor, NonIdealCapacitor)):
            ctype, value = "C", el.value_f
        elif isinstance(el, IdealResistor):
            ctype, value = "R", el.value_ohm
        elif isinstance(el, IdealSeriesLC):
            b.place_series("L", f"{el.id}L", _value(el.value_h))
            b.place_series("C", f"{el.id}C", _value(el.value_f))
            continue
        elif isinstance(el, IdealParallelLC):
            b.place_series("L", f"{el.id}L", _value(el.value_h))
            b.place_shunt("C", f"{el.id}C", _value(el.value_f))
            continue
        else:
            raise SpiceExportError(
                f"Qucs .sch export does not support {type(el).__name__}"
            )
        if el.role == ElementRole.SERIES:
            b.place_series(ctype, el.id, _value(value))
        else:
            b.place_shunt(ctype, el.id, _value(value))

    b.components.append(f'<Port P2 1 {b.x} {_RAIL_Y} 4 -44 0 2 "2" 1 "analog" 0>')

    return "\n".join(
        [
            "<Qucs Schematic 0.0.19>",
            "<Properties>",
            "  <View=0,0,800,800,1,0,0>",
            "</Properties>",
            "<Components>",
            *[f"  {c}" for c in b.components],
            "</Components>",
            "<Wires>",
            *[f"  {w}" for w in b.wires],
            "</Wires>",
        ]
    ) + "\n"


def write_qucs_schematic(
    circuit: Circuit,
    path: Path | str,
    *,
    title: str = "FilterDesk export",
    z0_ohm: float = 50.0,
) -> Path:
    out = Path(path)
    out.write_text(
        qucs_schematic(circuit, title=title, z0_ohm=z0_ohm), encoding="utf-8"
    )
    return out


__all__ = ["qucs_schematic", "write_qucs_schematic"]
