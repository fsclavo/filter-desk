"""SPICE / LTspice netlist export from a canonical :class:`Circuit` (Phase 10).

Emits a flat SPICE netlist (LTspice-compatible) with an AC source, source/load
resistances and one line per primitive. LC/Brune arms and non-ideal elements are
expanded into primitives with internal nodes.
"""

from __future__ import annotations

import math
from pathlib import Path

from filterdesk.analysis.types import SweepConfig
from filterdesk.domain.circuit import (
    BalunSpec,
    Circuit,
    Element,
    IdealBruneLC,
    IdealCapacitor,
    IdealDualBruneLC,
    IdealInductor,
    IdealParallelLC,
    IdealResistor,
    IdealSeriesLC,
    MicrostripLineElement,
    MicrostripStubElement,
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
        self.alias: dict[str, str] = {}

    def net(self, name: str) -> str:
        if name == self._ground:
            return "0"
        return self.alias.get(name, name)

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
    elif isinstance(el, MicrostripLineElement):
        delay_s = el.length_m * math.sqrt(el.eeff) / 299_792_458.0
        lines.append(f"T{el.id} {a} 0 {b} 0 Z0={_fmt(el.z0_ohm)} TD={delay_s:.12g}")
        lines.append(
            f"* {el.id} microstrip loss {el.loss_db_per_m:g} dB/m ignored by T"
        )
    elif isinstance(el, MicrostripStubElement):
        far = nodes.fresh()
        delay_s = el.length_m * math.sqrt(el.eeff) / 299_792_458.0
        lines.append(
            f"T{el.id} {a} {b} {far} {b} Z0={_fmt(el.z0_ohm)} TD={delay_s:.12g}"
        )
        if el.stub_kind.value == "open":
            lines.append(f"R{el.id}open {far} {b} 1e12")
        else:
            lines.append(f"R{el.id}short {far} {b} 1e-6")
        lines.append(
            f"* {el.id} microstrip stub loss {el.loss_db_per_m:g} dB/m ignored by T"
        )
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
    load_net = nodes.net(circuit.port_out.node)
    balun = circuit.output_balun
    ratio = balun.turns_ratio if balun is not None else circuit.output_transformer_ratio
    has_transformer = ratio != 1.0 or balun is not None
    if balun is not None:
        nodes.alias[load_net] = "BAL1_p"
    elif has_transformer:
        nodes.alias[load_net] = "T1_p"

    src_net = f"{source_name}_src"
    zs = circuit.port_in.impedance_ohm
    if zs > 0.0:
        lines.append(f"{source_name} {src_net} 0 AC 1")
        lines.append(f"R{source_name}s {src_net} {in_net} {_fmt(zs)}")
    else:
        lines.append(f"{source_name} {in_net} 0 AC 1")

    for el in circuit.elements:
        lines.extend(_expand(el, nodes))

    if balun is not None:
        # Boundary balun/unun: ideal transformer plus optional series leakage,
        # shunt core loss and winding capacitance. The TLT line section is not
        # represented by this controlled-source export.
        lines.append(f"* output balun BAL1 ({balun.kind}, {ratio:.6g}:1)")
        control = "BAL1_p"
        if balun.kind != "ideal" and balun.leakage_h > 0.0:
            control = "BAL1_x"
            lines.append(f"L_BAL1lk BAL1_p {control} {_fmt(balun.leakage_h)}")
        if balun.kind != "ideal" and balun.core_loss_ohm is not None:
            lines.append(f"R_BAL1core {control} 0 {_fmt(balun.core_loss_ohm)}")
        lines.append(f"E_BAL1 BAL1_s 0 {control} 0 {_fmt(1.0 / ratio)}")
        lines.append("V_BAL1sense BAL1_s BAL1_sense 0")
        lines.append(f"F_BAL1 {control} 0 V_BAL1sense {_fmt(1.0 / ratio)}")
        out_net = "BAL1_sense"
        if balun.kind != "ideal" and balun.shunt_c_f > 0.0:
            lines.append(f"C_BAL1w {out_net} 0 {_fmt(balun.shunt_c_f)}")
        if balun.kind in {"guanella", "ruthroff"}:
            lines.append("* BAL1 TLT TEM line is not exported to SPICE")
    elif has_transformer:
        # Ideal transformer (common ground) via VCVS + CCCS and a 0 V sense
        # source: V(load) = V(primary)/n and I(primary) = I(load)/n.
        lines.append(f"* ideal output transformer T1 ({ratio:.6g}:1)")
        lines.append(f"E_T1 {load_net} 0 T1_p 0 {_fmt(1.0 / ratio)}")
        lines.append(f"V_T1sense {load_net} T1_s 0")
        lines.append(f"F_T1 T1_p 0 V_T1sense {_fmt(1.0 / ratio)}")
        out_net = "T1_s"
    else:
        out_net = load_net

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


def _guanella_spice_netlist(
    balun: BalunSpec,
    *,
    title: str,
    ac: SweepConfig | None,
) -> str:
    lines = balun.guanella_line_count
    if lines is None:
        raise SpiceExportError(
            "TLT SPICE export currently supports integer-ratio Guanella only"
        )
    if lines < 1:
        raise SpiceExportError("Guanella TLT must have at least one line")
    delay_s = balun.length_m / (balun.velocity_factor * 299_792_458.0)
    out_nodes = ["outp", *[f"mid{i}" for i in range(1, lines)], "outm"]
    net: list[str] = [f"* {title}", f"* {lines}-line Guanella, differential output"]
    net.append("V1 in_src 0 AC 1")
    net.append(f"RV1s in_src in {_fmt(balun.z_unbalanced_ohm)}")
    for index in range(lines):
        net.append(
            f"TL{index + 1} in 0 {out_nodes[index]} {out_nodes[index + 1]} "
            f"Z0={_fmt(balun.z0_line_ohm)} TD={delay_s:.12g}"
        )
    center = out_nodes[lines // 2]
    if balun.magnetizing_inductance_h > 0.0:
        net.append(f"Lcm {center} 0 {_fmt(balun.magnetizing_inductance_h)}")
    if balun.core_loss_ohm is not None and balun.core_loss_ohm > 0.0:
        net.append(f"Rcm {center} 0 {_fmt(balun.core_loss_ohm)}")
    net.append(f"Rload outp outm {_fmt(balun.z_balanced_ohm)}")
    if ac is not None:
        net.append(f".ac dec {ac.n_points} {_fmt(ac.f_start_hz)} {_fmt(ac.f_stop_hz)}")
        net.append(".print ac v(outp) v(outm)")
    net.append(".end")
    return "\n".join(net) + "\n"


def _ruthroff_spice_netlist(
    balun: BalunSpec,
    *,
    title: str,
    ac: SweepConfig | None,
) -> str:
    """Return a Ruthroff 1:4 voltage-balun test netlist.

    The single TEM line is bootstrap-connected: port 1 is ``in`` to ground and
    port 2 is ground to ``outm``. The floating load sits between ``in`` and
    ``outm``, so the output is differential while the source remains
    ground-referenced. This is the step-up (50 -> 200 ohm) orientation.
    """
    if abs(balun.turns_ratio - 0.5) > 1e-6:
        raise SpiceExportError(
            "Ruthroff SPICE export currently supports the 1:4 step-up "
            "orientation (turns_ratio = 0.5)"
        )
    if balun.length_m <= 0.0:
        raise SpiceExportError("Ruthroff TLT needs a positive line length")
    delay_s = balun.length_m / (balun.velocity_factor * 299_792_458.0)
    net: list[str] = [
        f"* {title}",
        "* Ruthroff 1:4 voltage balun, bootstrap connection",
        "* output floats between in and outm",
    ]
    net.append("V1 in_src 0 AC 1")
    net.append(f"RV1s in_src in {_fmt(balun.z_unbalanced_ohm)}")
    net.append(f"TL1 in 0 0 outm Z0={_fmt(balun.z0_line_ohm)} TD={delay_s:.12g}")
    net.append(f"Rload in outm {_fmt(balun.z_balanced_ohm)}")
    if ac is not None:
        net.append(f".ac dec {ac.n_points} {_fmt(ac.f_start_hz)} {_fmt(ac.f_stop_hz)}")
        net.append(".print ac v(in) v(outm)")
    net.append(".end")
    return "\n".join(net) + "\n"


def tlt_spice_netlist(
    balun: BalunSpec,
    *,
    title: str = "FilterDesk TLT",
    ac: SweepConfig | None = None,
) -> str:
    """Return a TLT test netlist (Guanella or Ruthroff 1:4).

    Guanella uses N parallel-input/series-output lines and a common-mode choke
    shunt at the output centre. Ruthroff uses one bootstrap TEM line and a
    floating load. Lossless ``T`` elements are used; conductor/dielectric loss
    is not represented.
    """
    if balun.kind == "guanella":
        return _guanella_spice_netlist(balun, title=title, ac=ac)
    if balun.kind == "ruthroff":
        return _ruthroff_spice_netlist(balun, title=title, ac=ac)
    raise SpiceExportError("TLT SPICE export supports Guanella and Ruthroff 1:4 only")


def write_tlt_spice_netlist(
    balun: BalunSpec,
    path: Path | str,
    *,
    title: str = "FilterDesk TLT",
    ac: SweepConfig | None = None,
) -> Path:
    out = Path(path)
    out.write_text(tlt_spice_netlist(balun, title=title, ac=ac), encoding="utf-8")
    return out


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


# Imported after the functions above to avoid a circular import (ltspice_asc
# imports SpiceExportError from this module).
from filterdesk.io.spice.ltspice_asc import (  # noqa: E402
    ltspice_asc,
    write_ltspice_asc,
)

__all__ = [
    "SpiceExportError",
    "ltspice_asc",
    "spice_netlist",
    "tlt_spice_netlist",
    "write_ltspice_asc",
    "write_spice_netlist",
    "write_tlt_spice_netlist",
]
