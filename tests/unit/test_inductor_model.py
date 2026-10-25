"""Real inductor model: Q(f), SRF, DC-bias and persistence."""

from __future__ import annotations

import math

import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.adapters.abcd_ladder import element_impedance_ohm
from filterdesk.components_std import nonidealize_circuit, set_element_parasitics
from filterdesk.domain.circuit import (
    Circuit,
    IdealInductor,
    NonIdealInductor,
    Port,
    WindingSpec,
)
from filterdesk.domain.enums import ElementRole
from filterdesk.domain.project import circuit_from_mapping, circuit_to_mapping
from filterdesk.io.build_sheet import build_sheet_rows


def _ports() -> tuple[Port, Port]:
    return (
        Port(name="port1", node="in", impedance_ohm=50.0),
        Port(name="port2", node="out", impedance_ohm=50.0),
    )


def _inductor(**kwargs: object) -> NonIdealInductor:
    base: dict[str, object] = {
        "id": "L1",
        "value_h": 1e-6,
        "node_a": "in",
        "node_b": "out",
        "role": ElementRole.SERIES,
    }
    base.update(kwargs)
    return NonIdealInductor(**base)  # type: ignore[arg-type]


def _circuit(element: NonIdealInductor) -> Circuit:
    port_in, port_out = _ports()
    return Circuit(elements=[element], port_in=port_in, port_out=port_out)


def test_default_model_backward_compatible() -> None:
    el = _inductor(series_resistance_ohm=0.5, parallel_capacitance_f=1e-12)
    frequency = 10e6
    omega = 2.0 * math.pi * frequency
    expected = 1.0 / (
        1.0 / (0.5 + 1j * omega * 1e-6) + 1.0 / (1.0 / (1j * omega * 1e-12))
    )
    assert element_impedance_ohm(el, frequency) == pytest.approx(expected)


def test_q_sets_reference_resistance() -> None:
    el = _inductor(q_ref=50.0, q_frequency_hz=10e6)
    expected_r = 2.0 * math.pi * 10e6 * 1e-6 / 50.0
    assert el.reference_resistance_ohm == pytest.approx(expected_r)
    z = element_impedance_ohm(el, 10e6)
    assert z.imag / z.real == pytest.approx(50.0)


def test_skin_model_raises_resistance_with_frequency() -> None:
    el = _inductor(
        q_ref=50.0, q_frequency_hz=10e6, loss_model="dc_skin"
    )
    f_ref = 10e6
    r_ref = element_impedance_ohm(el, f_ref).real
    r_up = element_impedance_ohm(el, 4.0 * f_ref).real
    assert r_up == pytest.approx(2.0 * r_ref)


def test_srf_sets_parallel_resonance() -> None:
    srf = 10e6
    el = _inductor(series_resistance_ohm=0.01, srf_hz=srf)
    expected_cp = 1.0 / ((2.0 * math.pi * srf) ** 2 * 1e-6)
    assert el.effective_parallel_capacitance_f == pytest.approx(expected_cp)
    assert el.self_resonant_frequency_hz == pytest.approx(srf)
    z_srf = element_impedance_ohm(el, srf)
    z_half = element_impedance_ohm(el, srf / 2.0)
    assert abs(z_srf) > 10.0 * abs(z_half)


def test_dc_bias_derates_inductance() -> None:
    el = _inductor(dc_current_a=2.0, saturation_current_a=2.0)
    assert el.dc_bias_factor == pytest.approx(0.5)
    assert el.effective_inductance_h == pytest.approx(0.5e-6)
    assert _inductor().dc_bias_factor == pytest.approx(1.0)


def test_model_validation() -> None:
    with pytest.raises(ValueError):
        _inductor(loss_model="bogus")
    with pytest.raises(ValueError):
        _inductor(q_ref=0.0)
    with pytest.raises(ValueError):
        _inductor(srf_hz=-1.0)
    with pytest.raises(ValueError):
        _inductor(saturation_current_a=0.0)
    with pytest.raises(ValueError):
        _inductor(dc_current_a=-1.0)


def test_project_roundtrip_preserves_model() -> None:
    winding = WindingSpec(
        kind="toroid",
        core="T50-2",
        material="2",
        turns=12,
        wire_awg=26,
        wire_bare_mm=0.4,
        wire_overall_mm=0.43,
    )
    el = _inductor(
        series_resistance_ohm=0.2,
        parallel_capacitance_f=1e-12,
        q_ref=80.0,
        q_frequency_hz=7.1e6,
        srf_hz=300e6,
        loss_model="dc_skin",
        dc_current_a=1.5,
        saturation_current_a=5.0,
        winding=winding,
    )
    restored = circuit_from_mapping(circuit_to_mapping(_circuit(el)))
    result = restored.elements[0]
    assert isinstance(result, NonIdealInductor)
    assert result.q_ref == pytest.approx(80.0)
    assert result.q_frequency_hz == pytest.approx(7.1e6)
    assert result.srf_hz == pytest.approx(300e6)
    assert result.loss_model == "dc_skin"
    assert result.dc_current_a == pytest.approx(1.5)
    assert result.saturation_current_a == pytest.approx(5.0)
    assert result.winding == winding


def test_nonidealize_circuit_accepts_real_model() -> None:
    port_in, port_out = _ports()
    circuit = Circuit(
        elements=[
            IdealInductor("L1", 1e-6, "in", "out", ElementRole.SERIES)
        ],
        port_in=port_in,
        port_out=port_out,
    )
    converted = nonidealize_circuit(
        circuit,
        inductor_q=40.0,
        q_frequency_hz=10e6,
        inductor_srf_hz=300e6,
        inductor_loss_model="dc_skin",
        inductor_dc_current_a=1.0,
        inductor_i_sat_a=4.0,
    )
    element = converted.elements[0]
    assert isinstance(element, NonIdealInductor)
    assert element.q_ref == pytest.approx(40.0)
    assert element.srf_hz == pytest.approx(300e6)
    assert element.loss_model == "dc_skin"
    assert element.dc_current_a == pytest.approx(1.0)
    assert element.saturation_current_a == pytest.approx(4.0)


def test_set_element_parasitics_preserves_extended_fields() -> None:
    winding = WindingSpec(kind="air", turns=5, wire_awg=20)
    el = _inductor(
        series_resistance_ohm=0.1,
        srf_hz=200e6,
        dc_current_a=0.5,
        saturation_current_a=3.0,
        winding=winding,
    )
    updated = set_element_parasitics(
        _circuit(el), "L1", series_resistance_ohm=0.3
    )
    result = updated.elements[0]
    assert isinstance(result, NonIdealInductor)
    assert result.series_resistance_ohm == pytest.approx(0.3)
    assert result.srf_hz == pytest.approx(200e6)
    assert result.dc_current_a == pytest.approx(0.5)
    assert result.saturation_current_a == pytest.approx(3.0)
    assert result.winding == winding


def test_build_sheet_includes_winding() -> None:
    winding = WindingSpec(
        kind="toroid", core="T50-2", turns=12, wire_awg=26
    )
    el = _inductor(series_resistance_ohm=0.2, winding=winding)
    row = build_sheet_rows(_circuit(el))[0]
    assert row.core == "T50-2"
    assert row.turns == 12
    assert row.wire_awg == 26
    assert row.dcr_ohm == pytest.approx(0.2)


def test_cli_analyze_real_inductor_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "analyze",
            "--family",
            "chebyshev_type_i",
            "--response",
            "low_pass",
            "--order",
            "3",
            "--cutoff",
            "100M",
            "--ripple",
            "0.1",
            "--points",
            "64",
            "--inductor-srf",
            "500M",
            "--inductor-loss-model",
            "dc_skin",
            "--inductor-dc-current",
            "1",
            "--inductor-i-sat",
            "4",
            "--json",
        ]
    )
    assert code == 0
    capsys.readouterr()
