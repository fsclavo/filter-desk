"""SPICE / LTspice netlist export from a canonical :class:`Circuit` (Phase 10).

Emits a flat SPICE netlist (LTspice-compatible) with an AC source, source/load
resistances and one line per primitive. LC/Brune arms and non-ideal elements are
expanded into primitives with internal nodes.
"""

from __future__ import annotations

from pathlib import Path

from filterdesk.analysis.types import SweepConfig
from filterdesk.domain.circuit import (
    Circuit,
    Element,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealResistor,
    IdealSeriesLC,
    NonIdealCapacitor,
    NonIdealInductor,
)


class SpiceExportError(ValueError):
    """Raised when a circuit cannot be represented as a SPICE netlist."""


def _fmt(value: float) -> str:
    return f"{value:.10g}"


class _Nodes:
    """Allocates unique internal node names."""

    def __init__(self, circuit: Circuit) -> None:
        self._ground = circuit.ground
        self._counter = 0

    def net(self, name: str) -> str:
        return "0" if name == self._ground else name

    def fresh(self) -> str:
        self._counter += 1
        return f"nc{self._counter}"


def _expand(el: Element, nodes: _Nodes) -> list[str]:
    a = nodes.net(el.node_a)
    b = nodes.net(el.node_b)
    lines: list[str] = []
    if isinstance(el, IdealResistor):
        lines.append(f"R{el.id} {a} {b} {_fmt(el.value_ohm)}")
    elif isinstance(el, IdealInductor):
        lines.append(f"L{el.id} {a} {b} {_fmt(el.value_h)}")
    elif isinstance(el, IdealCapacitor):
        lines.append(f"C{el.id} {a} {b} {_fmt(el.value_f)}")
    elif isinstance(el, IdealSeriesLC):
        mid = nodes.fresh()
        lines.append(f"L{el.id}L {a} {mid} {_fmt(el.value_h)}")
        lines.append(f"C{el.id}C {mid} {b} {_fmt(el.value_f)}")
    elif isinstance(el, IdealParallelLC):
        lines.append(f"L{el.id}L {a} {b} {_fmt(el.value_h)}")
        lines.append(f"C{el.id}C {a} {b} {_fmt(el.value_f)}")
    elif isinstance(el, IdealBruneLC):
        m1 = nodes.fresh()
        m2 = nodes.fresh()
        lines.append(f"L{el.id}Ls {a} {m1} {_fmt(el.series_l_h)}")
        lines.append(f"C{el.id}Cs {m1} {m2} {_fmt(el.series_c_f)}")
        lines.append(f"L{el.id}Lp {m2} {b} {_fmt(el.parallel_l_h)}")
        lines.append(f"C{el.id}Cp {m2} {b} {_fmt(el.parallel_c_f)}")
    elif isinstance(el, IdealDualBruneLC):
        m1 = nodes.fresh()
        lines.append(f"L{el.id}Ls {a} {m1} {_fmt(el.series_l_h)}")
        lines.append(f"C{el.id}Cs {m1} {b} {_fmt(el.series_c_f)}")
        lines.append(f"L{el.id}Lp {a} {b} {_fmt(el.parallel_l_h)}")
        lines.append(f"C{el.id}Cp {a} {b} {_fmt(el.parallel_c_f)}")
    elif isinstance(el, NonIdealInductor):
        if el.series_resistance_ohm > 0.0:
            mid = nodes.fresh()
            lines.append(f"L{el.id} {a} {mid} {_fmt(el.value_h)}")
            lines.append(f"R{el.id}r {mid} {b} {_fmt(el.series_resistance_ohm)}")
        else:
            lines.append(f"L{el.id} {a} {b} {_fmt(el.value_h)}")
        if el.parallel_capacitance_f > 0.0:
            lines.append(f"C{el.id}cp {a} {b} {_fmt(el.parallel_capacitance_f)}")
    elif isinstance(el, NonIdealCapacitor):
        mid = nodes.fresh()
        lines.append(f"C{el.id} {a} {mid} {_fmt(el.value_f)}")
        cur = mid
        if el.esl_h > 0.0:
            nxt = nodes.fresh()
            lines.append(f"L{el.id}l {cur} {nxt} {_fmt(el.esl_h)}")
            cur = nxt
        lines.append(f"R{el.id}r {cur} {b} {_fmt(el.esr_ohm)}")
    else:
        raise SpiceExportError(f"unsupported element: {type(el).__name__}")
    return lines


def spice_netlist(
    circuit: Circuit,
    *,
    title: str = "FilterDesk export",
    ac: SweepConfig | None = None,
    source_name: str = "V1",
) -> str:
    """Return an LTspice-compatible SPICE netlist for ``circuit``."""
    if not circuit.elements:
        raise SpiceExportError("circuit has no elements")
    nodes = _Nodes(circuit)
    lines: list[str] = [f"* {title}"]
    in_net = nodes.net(circuit.port_in.node)
    out_net = nodes.net(circuit.port_out.node)

    src_net = f"{source_name}_src"
    zs = circuit.port_in.impedance_ohm
    if zs > 0.0:
        lines.append(f"{source_name} {src_net} 0 AC 1")
        lines.append(f"R{source_name}s {src_net} {in_net} {_fmt(zs)}")
    else:
        lines.append(f"{source_name} {in_net} 0 AC 1")

    for el in circuit.elements:
        lines.extend(_expand(el, nodes))

    zl = circuit.port_out.impedance_ohm
    if zl > 0.0:
        lines.append(f"Rload {out_net} 0 {_fmt(zl)}")

    if ac is not None:
        lines.append(
            f".ac dec {ac.n_points} {_fmt(ac.f_start_hz)} {_fmt(ac.f_stop_hz)}"
        )
    lines.append(".backanno")
    lines.append(".end")
    return "\n".join(lines) + "\n"


def write_spice_netlist(
    circuit: Circuit,
    path: Path | str,
    *,
    title: str = "FilterDesk export",
    ac: SweepConfig | None = None,
    source_name: str = "V1",
) -> Path:
    """Write an LTspice-compatible SPICE netlist to ``path``."""
    out = Path(path)
    out.write_text(
        spice_netlist(circuit, title=title, ac=ac, source_name=source_name),
        encoding="utf-8",
    )
    return out


__all__ = [
    "SpiceExportError",
    "spice_netlist",
    "write_spice_netlist",
]
