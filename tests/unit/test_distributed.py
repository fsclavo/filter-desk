"""Distributed microstrip elements, BOM/project support and LP synthesis."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from filterdesk.analysis.adapters.abcd_ladder import _element_abcd
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.circuit import (
    Circuit,
    MicrostripLineElement,
    MicrostripStubElement,
    Port,
)
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    MicrostripStubKind,
    TopologyId,
)
from filterdesk.domain.project import circuit_from_mapping, circuit_to_mapping
from filterdesk.domain.specs import FilterSpec
from filterdesk.io.build_sheet import build_sheet_rows, render_bom_csv
from filterdesk.io.qucs import qucs_schematic
from filterdesk.io.spice import SpiceExportError, spice_netlist
from filterdesk.synthesis import synthesize
from filterdesk.synthesis.distributed import (
    DistributedSynthesisError,
    design_distributed_lowpass,
)

C0 = 299_792_458.0


def _spec(
    family: ApproximationFamily = ApproximationFamily.BUTTERWORTH,
    *,
    order: int = 3,
    response: FilterResponse = FilterResponse.LOW_PASS,
) -> FilterSpec:
    kwargs: dict[str, object] = {}
    if family == ApproximationFamily.CHEBYSHEV_TYPE_I:
        kwargs["passband_ripple_db"] = 0.1
    elif family == ApproximationFamily.CHEBYSHEV_TYPE_II:
        kwargs["stopband_attenuation_db"] = 30.0
    return FilterSpec(
        family=family,
        response=response,
        order=order,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=(
            TopologyId.LADDER_HP_SERIES_C_INPUT
            if response == FilterResponse.HIGH_PASS
            else TopologyId.LADDER_LP_SERIES_L_INPUT
        ),
        cutoff_definition=(
            CutoffDefinition.RIPPLE_EDGE
            if family == ApproximationFamily.CHEBYSHEV_TYPE_I
            else (
                CutoffDefinition.STOPBAND_EDGE
                if family == ApproximationFamily.CHEBYSHEV_TYPE_II
                else CutoffDefinition.HALF_POWER_3DB
            )
        ),
        cutoff_hz=100e6,
        **kwargs,
    )


def _ports() -> tuple[Port, Port]:
    return Port("P1", "in", 50.0), Port("P2", "out", 50.0)


def test_microstrip_line_abcd_matches_matched_quarter_wave() -> None:
    f0 = 1e9
    eeff = 4.0
    length = C0 / (f0 * math.sqrt(eeff)) / 4.0
    p_in, p_out = _ports()
    line = MicrostripLineElement(
        id="TL1",
        z0_ohm=50.0,
        length_m=length,
        eeff=eeff,
        node_a="in",
        node_b="out",
    )
    circuit = Circuit([line], p_in, p_out)
    sweep = SweepConfig(f_start_hz=f0 * 0.99, f_stop_hz=f0 * 1.01, n_points=3)
    result = analyze_circuit(circuit, sweep)
    center = result.frequency_hz.size // 2
    assert abs(result.s11[center]) < 1e-12
    assert abs(abs(result.s21[center]) - 1.0) < 1e-12


def test_short_and_open_stub_input_impedance() -> None:
    f0 = 1e9
    length = C0 / f0 / 8.0  # 45 electrical degrees at f0
    omega = np.array([2.0 * np.pi * f0])
    for kind, expected in (
        (MicrostripStubKind.SHORT, 1j * 50.0),
        (MicrostripStubKind.OPEN, -1j * 50.0),
    ):
        stub = MicrostripStubElement(
            id="ST1",
            z0_ohm=50.0,
            length_m=length,
            eeff=1.0,
            stub_kind=kind,
            node_a="in",
            node_b="gnd",
        )
        abcd = _element_abcd(stub, omega)[0]
        zin = 1.0 / complex(abcd[1, 0])
        assert zin == pytest.approx(expected, abs=1e-9)


def test_distributed_circuit_cross_checks_abcd_and_skrf() -> None:
    design = design_distributed_lowpass(_spec(), "FR4")
    sweep = SweepConfig(
        f_start_hz=10e6,
        f_stop_hz=300e6,
        n_points=101,
        spacing=SweepSpacing.LOGARITHMIC,
    )
    abcd = analyze_circuit(design.circuit, sweep, backend="abcd")
    skrf = analyze_circuit(design.circuit, sweep, backend="skrf")
    assert np.allclose(abcd.s21, skrf.s21, rtol=1e-7, atol=1e-9)
    assert np.allclose(abcd.s11, skrf.s11, rtol=1e-7, atol=1e-9)


def test_distributed_circuit_project_round_trip() -> None:
    design = design_distributed_lowpass(_spec(), "RO4350B")
    mapping = circuit_to_mapping(design.circuit)
    restored = circuit_from_mapping(mapping)
    assert len(restored.elements) == len(design.circuit.elements)
    for original, copy in zip(design.circuit.elements, restored.elements, strict=True):
        assert type(original) is type(copy)
        assert original.id == copy.id
        if isinstance(original, MicrostripLineElement):
            assert isinstance(copy, MicrostripLineElement)
            assert original.z0_ohm == pytest.approx(copy.z0_ohm)
            assert original.length_m == pytest.approx(copy.length_m)
    assert mapping["elements"][0]["type"] == "microstrip_line"


def test_distributed_bom_has_geometry_columns() -> None:
    design = design_distributed_lowpass(_spec(), "FR4")
    rows = build_sheet_rows(design.circuit)
    assert len(rows) == 3
    assert all(row.kind == "microstrip_line" for row in rows)
    assert rows[0].substrate == "FR4"
    assert rows[0].width_mm > 0.0
    assert rows[0].length_mm > 0.0
    assert rows[0].angle_deg == pytest.approx(30.0)
    csv_text = render_bom_csv(rows)
    header = csv_text.splitlines()[0]
    assert "substrate" in header
    assert "width_mm" in header
    assert "length_mm" in header


def test_distributed_lowpass_tracks_lumped_response() -> None:
    spec = _spec()
    design = design_distributed_lowpass(spec, "FR4")
    lumped = synthesize(spec).circuit
    sweep = SweepConfig(
        f_start_hz=10e6,
        f_stop_hz=300e6,
        n_points=400,
        spacing=SweepSpacing.LOGARITHMIC,
    )
    f = sweep.frequencies_hz()
    dist_db = 20.0 * np.log10(
        np.maximum(np.abs(analyze_circuit(design.circuit, sweep).s21), 1e-15)
    )
    lumped_db = 20.0 * np.log10(
        np.maximum(np.abs(analyze_circuit(lumped, sweep).s21), 1e-15)
    )
    passband = (f >= 10e6) & (f <= 100e6)
    assert np.max(np.abs(dist_db[passband] - lumped_db[passband])) <= 1.0
    at_2fc = int(np.argmin(np.abs(f - 200e6)))
    assert dist_db[at_2fc] <= lumped_db[at_2fc] + 6.0


def test_distributed_rejects_unsupported_requests() -> None:
    with pytest.raises(DistributedSynthesisError, match="order <= 3"):
        design_distributed_lowpass(_spec(order=4), "FR4")
    with pytest.raises(DistributedSynthesisError, match="low-pass"):
        design_distributed_lowpass(_spec(response=FilterResponse.HIGH_PASS), "FR4")
    with pytest.raises(DistributedSynthesisError, match="Chebyshev-I"):
        design_distributed_lowpass(
            _spec(family=ApproximationFamily.CHEBYSHEV_TYPE_II), "FR4"
        )


def test_distributed_spice_export_and_qucs_guard() -> None:
    design = design_distributed_lowpass(_spec(), "FR4")
    text = spice_netlist(design.circuit)
    assert "TTL1 in 0 " in text
    assert "Z0=" in text and "TD=" in text
    assert "microstrip loss" in text
    with pytest.raises(SpiceExportError, match="does not support"):
        qucs_schematic(design.circuit)


def test_stub_bom_and_project_support() -> None:
    stub = MicrostripStubElement(
        id="ST1",
        z0_ohm=50.0,
        length_m=0.02,
        eeff=1.0,
        stub_kind=MicrostripStubKind.SHORT,
        node_a="in",
        node_b="gnd",
        substrate="FR4",
        width_mm=3.0,
        angle_deg=90.0,
    )
    p_in, p_out = _ports()
    circuit = Circuit([stub], p_in, p_out)
    rows = build_sheet_rows(circuit)
    assert rows[0].kind == "microstrip_stub"
    assert rows[0].stub_kind == "short"
    restored = circuit_from_mapping(circuit_to_mapping(circuit))
    assert isinstance(restored.elements[0], MicrostripStubElement)
    assert restored.elements[0].stub_kind is MicrostripStubKind.SHORT


def test_distributed_cli_exports(
    capsys: pytest.CaptureFixture[str], tmp_path: object
) -> None:
    from pathlib import Path

    from filterdesk.__main__ import main

    root = Path(str(tmp_path))
    s2p = root / "dist.s2p"
    bom = root / "dist.csv"
    code = main(
        [
            "distributed",
            "--family",
            "butterworth",
            "--response",
            "low_pass",
            "--order",
            "3",
            "--cutoff",
            "100M",
            "--export-s2p",
            str(s2p),
            "--export-build-sheet",
            str(bom),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["lines"]) == 3
    assert s2p.exists() and bom.exists()
