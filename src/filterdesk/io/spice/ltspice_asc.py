"""LTspice ``.asc`` schematic export from a canonical :class:`Circuit` (Phase 10).

Generates a graphical schematic that LTspice opens directly. Connectivity uses
net-label ``FLAG`` items placed exactly on component pins (same-named flags are
one net), so no fragile wire routing is required. Ideal L/C/R and LC arms are
supported; the source/load terminations are added automatically.
"""

from __future__ import annotations

from pathlib import Path

from filterdesk.analysis.types import SweepConfig
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
from filterdesk.io.spice import SpiceExportError

#: Pin offsets (local, R0) from the standard LTspice symbols.
_PINS: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "ind": ((16, 16), (16, 96)),
    "res": ((16, 16), (16, 96)),
    "cap": ((16, 0), (16, 64)),
    "voltage": ((0, 16), (0, 96)),
}

_GRID = 16
_Y = 128
_STEP = 112  # horizontal spacing between placed symbols


def _value(value: float) -> str:
    return f"{value:.10g}"


class _Layout:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.x = 96

    def _pin_world(self, symbol: str, cx: int, cy: int) -> list[tuple[int, int]]:
        (ax, ay), (bx, by) = _PINS[symbol]
        return [(cx + ax, cy + ay), (cx + bx, cy + by)]

    def place(
        self, symbol: str, name: str, value: str, net_a: str, net_b: str
    ) -> None:
        cx, cy = self.x, _Y
        self.x += _STEP
        self.lines.append(f"SYMBOL {symbol} {cx} {cy} R0")
        self.lines.append("WINDOW 0 0 0 Left 2")
        self.lines.append(f"SYMATTR InstName {name}")
        self.lines.append(f"SYMATTR Value {value}")
        (p0, p1) = self._pin_world(symbol, cx, cy)
        self.lines.append(f"FLAG {p0[0]} {p0[1]} {net_a}")
        self.lines.append(f"FLAG {p1[0]} {p1[1]} {net_b}")


def ltspice_asc(
    circuit: Circuit,
    *,
    title: str = "FilterDesk export",
    ac: SweepConfig | None = None,
) -> str:
    """Return an LTspice ``.asc`` schematic for ``circuit``."""
    if not circuit.elements:
        raise SpiceExportError("circuit has no elements")

    balun = circuit.output_balun
    ratio = balun.turns_ratio if balun is not None else circuit.output_transformer_ratio
    has_transformer = ratio != 1.0 or balun is not None
    load_net = (
        "0" if circuit.port_out.node == circuit.ground else circuit.port_out.node
    )
    if balun is not None:
        alias = {load_net: "BAL1_p"}
    elif has_transformer:
        alias = {load_net: "T1_p"}
    else:
        alias = {}

    def net(name: str) -> str:
        if name == circuit.ground:
            return "0"
        return alias.get(name, name)

    in_net = net(circuit.port_in.node)
    if balun is not None:
        out_net = "BAL1_sense"
    else:
        out_net = "T1_s" if has_transformer else load_net

    layout = _Layout()
    lines: list[str] = ["Version 4", "SHEET 1 1200 820"]

    # Terminations: V1 (AC 1) -> Rsource -> ladder -> Rload -> ground.
    layout.place("voltage", "V1", "AC 1", "src", "0")
    zs = circuit.port_in.impedance_ohm
    layout.place("res", "Rsource", _value(zs), "src", in_net)

    for el in circuit.elements:
        if isinstance(el, (IdealInductor, NonIdealInductor)):
            layout.place(
                "ind", el.id, _value(el.value_h), net(el.node_a), net(el.node_b)
            )
        elif isinstance(el, (IdealCapacitor, NonIdealCapacitor)):
            layout.place(
                "cap", el.id, _value(el.value_f), net(el.node_a), net(el.node_b)
            )
        elif isinstance(el, IdealResistor):
            layout.place(
                "res", el.id, _value(el.value_ohm), net(el.node_a), net(el.node_b)
            )
        elif isinstance(el, IdealSeriesLC):
            mid = f"n_{el.id}"
            layout.place("ind", f"{el.id}L", _value(el.value_h), net(el.node_a), mid)
            layout.place("cap", f"{el.id}C", _value(el.value_f), mid, net(el.node_b))
        elif isinstance(el, IdealParallelLC):
            n0, n1 = net(el.node_a), net(el.node_b)
            layout.place("ind", f"{el.id}L", _value(el.value_h), n0, n1)
            layout.place("cap", f"{el.id}C", _value(el.value_f), n0, n1)
        else:
            raise SpiceExportError(
                f"LTspice .asc export does not support {type(el).__name__}"
            )

    zl = circuit.port_out.impedance_ohm
    layout.place("res", "Rload", _value(zl), out_net, "0")

    lines.extend(layout.lines)

    if balun is not None:
        gain = _value(1.0 / ratio)
        lines.append(
            f"TEXT 96 704 Left 2 !E_BAL1 BAL1_s 0 BAL1_p 0 {gain}"
        )
        lines.append(
            "TEXT 96 736 Left 2 !V_BAL1sense BAL1_s BAL1_sense 0"
        )
        lines.append(
            f"TEXT 96 768 Left 2 !F_BAL1 BAL1_p 0 V_BAL1sense {gain}"
        )
        if balun.kind != "ideal":
            lines.append(
                "TEXT 96 800 Left 2 ;BAL1 leakage/core loss not exported"
            )
    elif has_transformer:
        gain = _value(1.0 / ratio)
        lines.append(
            f"TEXT 96 704 Left 2 !E_T1 {load_net} 0 T1_p 0 {gain}"
        )
        lines.append(
            f"TEXT 96 736 Left 2 !V_T1sense {load_net} T1_s 0"
        )
        lines.append(
            f"TEXT 96 768 Left 2 !F_T1 T1_p 0 V_T1sense {gain}"
        )

    directive = ".ac dec 101 1meg 1g"
    if ac is not None:
        directive = (
            f".ac dec {ac.n_points} {_value(ac.f_start_hz)} {_value(ac.f_stop_hz)}"
        )
    lines.append(f"TEXT 96 640 Left 2 !{directive}")
    lines.append(f"TEXT 96 672 Left 2 ;{title}")
    return "\n".join(lines) + "\n"


def write_ltspice_asc(
    circuit: Circuit,
    path: Path | str,
    *,
    title: str = "FilterDesk export",
    ac: SweepConfig | None = None,
) -> Path:
    """Write an LTspice ``.asc`` schematic to ``path``."""
    out = Path(path)
    out.write_text(ltspice_asc(circuit, title=title, ac=ac), encoding="utf-8")
    return out


__all__ = ["ltspice_asc", "write_ltspice_asc"]
