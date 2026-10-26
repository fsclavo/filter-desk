"""Validate the exported SPICE transformer model with an independent MNA solver.

The solver parses the generated netlist (R/L/C/V/E/F), stamps the AC MNA system
and compares S21 against the ABCD ladder analyzer. This checks the E/F/0V
transformer equations and the node aliasing without relying on the ABCD code.
"""

from __future__ import annotations

import cmath
import shutil
import subprocess

import numpy as np
import pytest

from filterdesk.analysis.adapters.abcd_ladder import LadderABCDAnalyzer
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.io.spice import spice_netlist
from filterdesk.synthesis import synthesize

FREQS = np.array([1e6, 10e6, 50e6, 100e6, 200e6, 1e9])


def _nodes(name: str, index: dict[str, int]) -> int:
    if name == "0":
        return -1
    if name not in index:
        index[name] = len(index)
    return index[name]


def _mna_s21(netlist: str, frequency_hz: float, zs: float, zl: float) -> complex:
    index: dict[str, int] = {}
    resistors: list[tuple[str, str, float]] = []
    inductors: list[tuple[str, str, float]] = []
    capacitors: list[tuple[str, str, float]] = []
    voltages: list[tuple[str, str, str, float]] = []
    vcvs: list[tuple[str, str, str, str, float]] = []
    cccs: list[tuple[str, str, str, float]] = []
    load_node = "0"
    source_amp = 1.0

    for raw in netlist.splitlines():
        line = raw.strip()
        if not line or line.startswith(("*", ".")):
            continue
        tok = line.split()
        name = tok[0]
        kind = name[0].upper()
        if kind == "R":
            resistors.append((tok[1], tok[2], float(tok[3])))
        elif kind == "L":
            inductors.append((tok[1], tok[2], float(tok[3])))
        elif kind == "C":
            capacitors.append((tok[1], tok[2], float(tok[3])))
        elif kind == "V":
            amp = 0.0
            for j, t in enumerate(tok[3:], start=3):
                if t.upper() == "AC":
                    amp = float(tok[j + 1])
            if len(tok) == 4 and tok[3] not in {"AC"}:
                amp = float(tok[3])
            voltages.append((name, tok[1], tok[2], amp))
            if name == "V1":
                source_amp = amp
        elif kind == "E":
            vcvs.append((name, tok[1], tok[2], tok[3], tok[4], float(tok[5])))
        elif kind == "F":
            cccs.append((name, tok[1], tok[2], tok[3], float(tok[4])))
        if name == "Rload":
            load_node = tok[1]

    # Node count: walk all referenced nodes.
    for n1, n2, _v in resistors + inductors + capacitors:
        _nodes(n1, index)
        _nodes(n2, index)
    for n1, n2, *_rest in [(v[1], v[2]) for v in voltages]:
        _nodes(n1, index)
        _nodes(n2, index)
    for _name, p, n, cp, cn, _g in vcvs:
        _nodes(p, index)
        _nodes(n, index)
        _nodes(cp, index)
        _nodes(cn, index)
    for _name, p, n, _ctrl, _g in cccs:
        _nodes(p, index)
        _nodes(n, index)

    n_nodes = len(index)
    branches = [v[0] for v in voltages] + [e[0] for e in vcvs]
    b_index = {name: n_nodes + i for i, name in enumerate(branches)}
    size = n_nodes + len(branches)
    a = np.zeros((size, size), dtype=complex)
    rhs = np.zeros(size, dtype=complex)
    omega = 2.0 * np.pi * frequency_hz

    def stamp_y(n1: str, n2: str, y: complex) -> None:
        i, j = _nodes(n1, index), _nodes(n2, index)
        if i >= 0:
            a[i, i] += y
        if j >= 0:
            a[j, j] += y
        if i >= 0 and j >= 0:
            a[i, j] -= y
            a[j, i] -= y

    for n1, n2, value in resistors:
        stamp_y(n1, n2, 1.0 / value)
    for n1, n2, value in inductors:
        stamp_y(n1, n2, 1.0 / (1j * omega * value))
    for n1, n2, value in capacitors:
        stamp_y(n1, n2, 1j * omega * value)

    for name, p, n, amp in voltages:
        bi = b_index[name]
        ip, inn = _nodes(p, index), _nodes(n, index)
        if ip >= 0:
            a[ip, bi] += 1.0
        if inn >= 0:
            a[inn, bi] -= 1.0
        if ip >= 0:
            a[bi, ip] += 1.0
        if inn >= 0:
            a[bi, inn] -= 1.0
        rhs[bi] = amp

    for name, p, n, cp, cn, gain in vcvs:
        bi = b_index[name]
        ip, inn = _nodes(p, index), _nodes(n, index)
        icp, icn = _nodes(cp, index), _nodes(cn, index)
        if ip >= 0:
            a[ip, bi] += 1.0
        if inn >= 0:
            a[inn, bi] -= 1.0
        if ip >= 0:
            a[bi, ip] += 1.0
        if inn >= 0:
            a[bi, inn] -= 1.0
        if icp >= 0:
            a[bi, icp] -= gain
        if icn >= 0:
            a[bi, icn] += gain

    for _name, p, n, ctrl, gain in cccs:
        bi = b_index[ctrl]
        ip, inn = _nodes(p, index), _nodes(n, index)
        if ip >= 0:
            a[ip, bi] += gain
        if inn >= 0:
            a[inn, bi] -= gain

    solution = np.linalg.solve(a, rhs)
    li = _nodes(load_node, index)
    vload = solution[li] if li >= 0 else 0.0
    return 2.0 * cmath.sqrt(zs / zl) * vload / source_amp


def _spec(zs: float, zl: float, *, order: int = 3) -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.BUTTERWORTH,
        response=FilterResponse.LOW_PASS,
        order=order,
        cutoff_hz=100e6,
        z_source_ohm=zs,
        z_load_ohm=zl,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )


@pytest.mark.parametrize(("zs", "zl"), [(50.0, 50.0), (50.0, 75.0), (75.0, 50.0)])
def test_spice_transformer_model_matches_abcd(zs: float, zl: float) -> None:
    circuit = synthesize(_spec(zs, zl)).circuit
    netlist = spice_netlist(circuit)
    sweep = SweepConfig(
        float(FREQS[0]),
        float(FREQS[-1]),
        FREQS.size,
        SweepSpacing.LOGARITHMIC,
    )
    abcd = LadderABCDAnalyzer().analyze(circuit, sweep)
    for f, expected in zip(abcd.frequency_hz, abcd.s21, strict=True):
        got = _mna_s21(netlist, float(f), zs, zl)
        assert abs(got - expected) < 1e-8


def test_spice_transformer_model_with_ngspice(tmp_path) -> None:
    if shutil.which("ngspice") is None:
        pytest.skip("ngspice is not installed")
    circuit = synthesize(_spec(50.0, 75.0)).circuit
    net = spice_netlist(circuit, ac=SweepConfig(1e6, 1e9, 21, SweepSpacing.LOGARITHMIC))
    # ``.backanno`` is an LTspice convenience directive; ngspice rejects it.
    net = net.replace(".backanno\n", "").replace(
        ".end", ".print ac v(T1_s)\n.end"
    )
    path = tmp_path / "t1.cir"
    path.write_text(net, encoding="utf-8")
    output = subprocess.run(
        ["ngspice", "-b", str(path)], check=True, capture_output=True, text=True
    )
    text = output.stdout
    assert "v(t1_s)" in text.lower()
    samples: list[tuple[float, complex]] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0].isdigit():
            samples.append(
                (
                    float(parts[1]),
                    complex(float(parts[2].rstrip(",")), float(parts[3])),
                )
            )
    freqs = np.asarray([sample[0] for sample in samples])
    abcd = LadderABCDAnalyzer().analyze_at_frequencies(circuit, freqs)
    assert len(samples) > 20
    for (_freq, vload), expected in zip(samples, abcd.s21, strict=True):
        # v(T1_s) is the load voltage; S21 = 2*sqrt(zs/zl)*Vload/Vsource.
        got = 2.0 * np.sqrt(50.0 / 75.0) * vload
        assert abs(got - expected) < 1e-4
