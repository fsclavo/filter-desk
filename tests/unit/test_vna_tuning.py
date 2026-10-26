"""VNA-guided component trimming."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.service import analyze_at_frequencies, analyze_circuit
from filterdesk.analysis.types import SweepConfig
from filterdesk.domain.circuit import (
    Circuit,
    IdealCapacitor,
    IdealInductor,
    Port,
)
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.io.touchstone import write_touchstone_s2p
from filterdesk.services.vna_tuning import (
    VnaBoundMode,
    VnaTuningCancelled,
    VnaTuningConfig,
    VnaTuningError,
    fit_circuit_to_measurement,
)
from filterdesk.synthesis import synthesize

SPEC = FilterSpec(
    family=ApproximationFamily.CHEBYSHEV_TYPE_I,
    response=FilterResponse.LOW_PASS,
    order=4,
    cutoff_hz=100e6,
    z_source_ohm=50.0,
    z_load_ohm=50.0,
    topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
    cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
    passband_ripple_db=0.1,
)


def _nominal() -> Circuit:
    return synthesize(SPEC).circuit


def _measured(
    circuit: Circuit, *, scale_l: float = 1.0, scale_c: float = 1.0
) -> object:
    elements = []
    for el in circuit.elements:
        if isinstance(el, IdealInductor):
            elements.append(replace(el, value_h=el.value_h * scale_l))
        elif isinstance(el, IdealCapacitor):
            elements.append(replace(el, value_f=el.value_f * scale_c))
        else:
            elements.append(el)
    perturbed = replace(circuit, elements=elements)
    return analyze_circuit(perturbed, SweepConfig(50e6, 150e6, 101))


def _with_phase_delay(measured, delay_s: float, phase_deg: float):
    omega = 2.0 * np.pi * np.asarray(measured.frequency_hz)
    factor = np.exp(-1j * omega * delay_s + 1j * np.radians(phase_deg))
    return replace(
        measured,
        s11=measured.s11 * factor,
        s21=measured.s21 * factor,
    )


def test_phase_delay_fit_recovers_reference_plane() -> None:
    circuit = _nominal()
    measured = _with_phase_delay(_measured(circuit), 25e-9, 30.0)
    result = fit_circuit_to_measurement(
        circuit,
        measured,
        VnaTuningConfig(max_points=81, max_nfev=200, fit_phase=True),
    )
    assert result.delay_s == pytest.approx(25e-9, abs=1e-12)
    assert result.phase_s21_deg == pytest.approx(30.0, abs=0.01)
    assert result.phase_s11_deg == pytest.approx(30.0, abs=0.01)
    assert result.final_rms_db < 1e-9
    assert result.bound_mode is VnaBoundMode.LOCAL
    assert result.n_starts == 1


def test_phase_fit_improves_perturbed_measurement() -> None:
    circuit = _nominal()
    measured = _with_phase_delay(
        _measured(circuit, scale_l=1.05, scale_c=0.96), 25e-9, 30.0
    )
    result = fit_circuit_to_measurement(
        circuit,
        measured,
        VnaTuningConfig(max_points=81, max_nfev=200, fit_phase=True),
    )
    assert result.final_rms_db < result.initial_rms_db
    assert result.delay_s == pytest.approx(25e-9, abs=1e-9)


def test_wide_and_global_bound_modes() -> None:
    circuit = _nominal()
    measured = _measured(circuit, scale_l=1.5)
    wide = fit_circuit_to_measurement(
        circuit,
        measured,
        VnaTuningConfig(max_points=81, max_nfev=100, bound_mode="wide"),
    )
    assert wide.bound_mode is VnaBoundMode.WIDE
    assert wide.final_rms_db < wide.initial_rms_db
    # Wide allows values outside local ±20 %.
    assert np.any(np.abs(wide.final_values / wide.initial_values - 1.0) > 0.2)

    global_fit = fit_circuit_to_measurement(
        circuit,
        measured,
        VnaTuningConfig(
            max_points=81,
            max_nfev=80,
            bound_mode=VnaBoundMode.GLOBAL,
            global_starts=3,
        ),
    )
    assert global_fit.bound_mode is VnaBoundMode.GLOBAL
    assert global_fit.n_starts == 3
    assert global_fit.final_rms_db < global_fit.initial_rms_db


def test_fit_identical_measurement_stays_near_zero() -> None:
    circuit = _nominal()
    measured = _measured(circuit)
    result = fit_circuit_to_measurement(
        circuit,
        measured,
        VnaTuningConfig(max_points=51, max_nfev=30),
    )
    assert result.final_rms_db == pytest.approx(result.initial_rms_db, abs=1e-9)
    assert result.final_rms_db < 1e-9
    assert result.success
    assert result.frequency_hz.size == 51
    assert result.measured_s11_db.shape == result.frequency_hz.shape


def test_fit_improves_perturbed_measurement() -> None:
    circuit = _nominal()
    measured = _measured(circuit, scale_l=1.12, scale_c=0.88)
    result = fit_circuit_to_measurement(
        circuit,
        measured,
        VnaTuningConfig(max_points=81, max_nfev=80),
    )
    assert result.final_rms_db < result.initial_rms_db
    assert result.improvement_db > 0.0
    assert result.final_rms_s21_db <= result.initial_rms_s21_db
    for initial, final in zip(
        result.initial_values, result.final_values, strict=True
    ):
        assert 0.8 * initial <= final <= 1.2 * initial
    assert result.n_evaluations > 0
    assert all(value > 0.0 for value in result.final_values)


def test_fit_band_and_single_parameter_subset() -> None:
    circuit = _nominal()
    measured = _measured(circuit, scale_l=1.05)
    result = fit_circuit_to_measurement(
        circuit,
        measured,
        VnaTuningConfig(
            max_points=31,
            max_nfev=20,
            f_min_hz=70e6,
            f_max_hz=130e6,
            fit_s11=False,
        ),
        refs=[result_ref for result_ref in ["L1", "L3"]],
    )
    assert result.refs == ["L1", "L3"]
    assert np.all(result.frequency_hz >= 70e6)
    assert np.all(result.frequency_hz <= 130e6)


def test_unknown_ref_and_empty_circuit_errors() -> None:
    circuit = _nominal()
    measured = _measured(circuit)
    with pytest.raises(VnaTuningError, match="unknown tunable"):
        fit_circuit_to_measurement(
            circuit, measured, VnaTuningConfig(max_points=21), refs=["NOPE"]
        )
    with pytest.raises(VnaTuningError, match="no selected"):
        fit_circuit_to_measurement(
            Circuit(
                elements=[],
                port_in=Port("in", "in", 50.0),
                port_out=Port("out", "out", 50.0),
            ),
            measured,
            VnaTuningConfig(max_points=21),
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"bound_pct": 0.0}, "bound_pct"),
        ({"max_points": 1}, "max_points"),
        ({"max_nfev": 0}, "max_nfev"),
        ({"fit_s11": False, "fit_s21": False}, "enable"),
        ({"s11_weight": 0.0}, "weights"),
        ({"floor_db": 1.0}, "floor_db"),
        ({"f_min_hz": 2.0, "f_max_hz": 1.0}, "f_min_hz"),
        ({"bound_mode": "nope"}, "bound_mode"),
        ({"global_starts": 0}, "global_starts"),
        ({"fit_phase": True, "phase_weight": 0.0}, "phase_weight"),
        ({"fit_phase": True, "phase_min_db": 1.0}, "phase_min_db"),
        ({"fit_phase": True, "max_delay_ns": 0.0}, "max_delay_ns"),
    ],
)
def test_config_validation(kwargs, message: str) -> None:
    with pytest.raises(VnaTuningError, match=message):
        VnaTuningConfig(**kwargs)


def test_no_points_in_band_errors() -> None:
    circuit = _nominal()
    measured = _measured(circuit)
    with pytest.raises(VnaTuningError, match="fewer than two"):
        fit_circuit_to_measurement(
            circuit,
            measured,
            VnaTuningConfig(max_points=21, f_min_hz=1e12, f_max_hz=2e12),
        )


def test_cancel_callback_stops_fit() -> None:
    circuit = _nominal()
    measured = _measured(circuit)
    calls = 0

    def cancel() -> bool:
        nonlocal calls
        calls += 1
        return calls > 1

    with pytest.raises(VnaTuningCancelled, match="cancelled"):
        fit_circuit_to_measurement(
            circuit,
            measured,
            VnaTuningConfig(max_points=21),
            cancel=cancel,
        )


def test_analyze_at_frequencies_matches_sweep() -> None:
    circuit = _nominal()
    sweep = SweepConfig(50e6, 150e6, 41)
    via_sweep = analyze_circuit(circuit, sweep)
    direct = analyze_at_frequencies(circuit, via_sweep.frequency_hz)
    assert np.allclose(direct.s21, via_sweep.s21)
    assert np.allclose(direct.s11, via_sweep.s11)


def test_cli_tune_vna_json_and_text(tmp_path, capsys) -> None:
    circuit = _nominal()
    measured = _measured(circuit, scale_l=1.08, scale_c=0.94)
    path = tmp_path / "measured.s2p"
    write_touchstone_s2p(measured, path)

    base = [
        "tune-vna",
        str(path),
        "--family",
        "chebyshev_type_i",
        "--response",
        "low_pass",
        "--order",
        "4",
        "--cutoff",
        "100M",
        "--ripple",
        "0.1",
        "--bound",
        "0.2",
        "--max-points",
        "51",
        "--max-nfev",
        "40",
        "--json",
    ]
    assert main(base) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["final_rms_db"] <= payload["initial_rms_db"]
    assert payload["improvement_db"] >= 0.0
    assert len(payload["components"]) == 4
    assert payload["n_points"] == 51

    text_args = [arg for arg in base if arg != "--json"]
    assert main(text_args) == 0
    out = capsys.readouterr().out
    assert "VNA fit:" in out and "S21" in out


def test_cli_tune_vna_phase_json(tmp_path, capsys) -> None:
    circuit = _nominal()
    measured = _with_phase_delay(_measured(circuit), 25e-9, 30.0)
    path = tmp_path / "phased.s2p"
    write_touchstone_s2p(measured, path)
    assert (
        main(
            [
                "tune-vna",
                str(path),
                "--family",
                "chebyshev_type_i",
                "--response",
                "low_pass",
                "--order",
                "4",
                "--cutoff",
                "100M",
                "--ripple",
                "0.1",
                "--fit-phase",
                "--max-points",
                "51",
                "--max-nfev",
                "120",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["delay_s"] == pytest.approx(25e-9, abs=1e-12)
    assert payload["phase_s21_deg"] == pytest.approx(30.0, abs=0.01)
    assert payload["bound_mode"] == "local"


def test_cli_tune_vna_bad_file(tmp_path, capsys) -> None:
    path = tmp_path / "bad.s2p"
    path.write_text("not a touchstone\n", encoding="utf-8")
    assert (
        main(
            [
                "tune-vna",
                str(path),
                "--family",
                "butterworth",
                "--response",
                "low_pass",
                "--order",
                "3",
                "--cutoff",
                "100M",
            ]
        )
        == 2
    )
    assert "error:" in capsys.readouterr().err


def test_vna_dialog_fit(qtbot) -> None:
    from filterdesk.gui.widgets import VnaTuningDialog

    circuit = _nominal()
    measured = _measured(circuit, scale_l=1.06)
    dialog = VnaTuningDialog(circuit, measured)
    qtbot.addWidget(dialog)
    assert dialog.current_result() is None
    dialog._max_points.setValue(31)
    dialog._run_fit()
    result = dialog.current_result()
    assert result is not None
    assert result.final_rms_db <= result.initial_rms_db
    assert dialog.result_circuit() is not None
    assert dialog._apply_button.isEnabled()
    assert mag_db(np.asarray([1.0]))[0] == pytest.approx(0.0)


def test_vna_dialog_phase_and_bound_mode(qtbot) -> None:
    from filterdesk.gui.widgets import VnaTuningDialog

    circuit = _nominal()
    measured = _with_phase_delay(_measured(circuit), 25e-9, 30.0)
    dialog = VnaTuningDialog(circuit, measured)
    qtbot.addWidget(dialog)
    dialog._fit_phase.setChecked(True)
    dialog._bound_mode.setCurrentText("wide")
    dialog._max_points.setValue(31)
    dialog._run_fit()
    result = dialog.current_result()
    assert result is not None
    assert result.bound_mode is VnaBoundMode.WIDE
    assert result.delay_s == pytest.approx(25e-9, abs=1e-9)
