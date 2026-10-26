"""Balun/unun design, boundary model and BOM integration."""

from __future__ import annotations

import json

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.adapters.abcd_ladder import (
    LadderABCDAnalyzer,
    abcd_to_s,
    balun_abcd,
)
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig
from filterdesk.components_std import (
    BalunError,
    BalunKind,
    design_balun,
    design_balun_options,
    find_core,
)
from filterdesk.domain.circuit import BalunSpec, Circuit, IdealResistor, Port
from filterdesk.domain.project import circuit_from_mapping, circuit_to_mapping
from filterdesk.io.build_sheet import build_sheet_rows
from filterdesk.io.qucs import qucs_schematic
from filterdesk.io.spice import ltspice_asc, spice_netlist


def _core():
    return find_core("FT240-43")


def test_guanella_design_1_to_4() -> None:
    design = design_balun(
        _core(),
        kind=BalunKind.GUANELLA,
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=200.0,
        f_min_hz=3.5e6,
        f_max_hz=30e6,
        power_w=100.0,
    )
    assert design.turns_ratio == pytest.approx(0.5)
    assert design.n_primary == 3
    assert design.n_secondary == 6
    assert design.actual_turns_ratio == pytest.approx(0.5)
    assert design.magnetizing_inductance_h > 0.0
    assert design.leakage_inductance_h > 0.0
    assert design.z0_line_ohm == pytest.approx(100.0)
    assert design.length_m > 0.0
    assert design.bsat_margin is not None and design.bsat_margin > 1.0
    assert design.fit.fits
    assert any("behavioral" in note for note in design.notes)
    spec = design.to_spec()
    assert spec.kind == "guanella"
    assert spec.turns_ratio == pytest.approx(0.5)
    assert spec.core == "FT240-43"


def test_balun_topology_and_winding_options() -> None:
    auto = design_balun_options(
        _core(),
        kind="unun",
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=2500.0,
        f_min_hz=7e6,
        f_max_hz=28e6,
        power_w=100.0,
        topology="autotransformer",
    )
    assert [(d.n_primary, d.n_secondary, d.total_turns) for d in auto] == [
        (2, 14, 14),
        (3, 21, 21),
        (4, 28, 28),
    ]
    assert auto[2].hf_caution
    isolated = design_balun_options(
        _core(),
        kind="unun",
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=2500.0,
        f_min_hz=7e6,
        f_max_hz=28e6,
        power_w=100.0,
        topology="isolated",
    )
    assert [d.total_turns for d in isolated] == [16, 24, 32]
    assert isolated[0].to_spec().topology == "isolated"


def test_choke_requires_equal_impedances() -> None:
    design = design_balun(
        _core(),
        kind="choke",
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=50.0,
        f_min_hz=1e6,
        f_max_hz=30e6,
        power_w=100.0,
    )
    assert design.turns_ratio == pytest.approx(1.0)
    assert design.common_mode_impedance_ohm > 0.0
    assert any("common-mode" in note for note in design.notes)
    with pytest.raises(BalunError, match="equal impedances"):
        design_balun(
            _core(),
            kind="choke",
            z_unbalanced_ohm=50.0,
            z_balanced_ohm=200.0,
            f_min_hz=1e6,
            f_max_hz=30e6,
            power_w=100.0,
        )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"z_unbalanced_ohm": 0.0}, "z_unbalanced"),
        ({"f_max_hz": 1e6}, "f_max_hz"),
        ({"coupling": 1.0}, "coupling"),
        ({"tan_delta": 1.0}, "tan_delta"),
        ({"winding_capacitance_f": -1.0}, "capacitance"),
        ({"line_loss_db_per_m": -1.0}, "line loss"),
    ],
)
def test_invalid_design(kwargs, message: str) -> None:
    base = {
        "kind": "unun",
        "z_unbalanced_ohm": 50.0,
        "z_balanced_ohm": 200.0,
        "f_min_hz": 3.5e6,
        "f_max_hz": 30e6,
        "power_w": 100.0,
    }
    base.update(kwargs)
    with pytest.raises(BalunError, match=message):
        design_balun(_core(), **base)


def test_ideal_balun_abcd_matches_impedance_ratio() -> None:
    spec = BalunSpec(kind="ideal", turns_ratio=0.5)
    freq = np.array([1e6, 10e6, 100e6])
    s11, s21, _, _ = abcd_to_s(balun_abcd(spec, freq), 50.0, 200.0)
    assert np.allclose(s11, 0.0, atol=1e-12)
    assert np.allclose(np.abs(s21), 1.0, atol=1e-12)


def _circuit(balun: BalunSpec | None = None) -> Circuit:
    return Circuit(
        elements=[IdealResistor("R1", 0.0, "in", "out")],
        port_in=Port("in", "in", 50.0),
        port_out=Port("out", "out", 200.0),
        output_balun=balun,
    )


def test_balun_in_ladder_and_project_roundtrip() -> None:
    balun = design_balun(
        _core(),
        kind="unun",
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=200.0,
        f_min_hz=3.5e6,
        f_max_hz=30e6,
        power_w=100.0,
    ).to_spec()
    circuit = _circuit(balun)
    restored = circuit_from_mapping(circuit_to_mapping(circuit))
    assert restored.output_balun is not None
    assert restored.output_balun.kind == "unun"
    assert restored.output_balun.turns_ratio == pytest.approx(balun.turns_ratio)
    assert restored.output_balun.core == "FT240-43"
    assert restored.output_balun.topology == "autotransformer"
    assert restored.output_balun.total_turns == balun.total_turns

    result = LadderABCDAnalyzer().analyze(circuit, SweepConfig(1e6, 100e6, 16))
    reference = LadderABCDAnalyzer().analyze(
        Circuit(
            elements=circuit.elements,
            port_in=circuit.port_in,
            port_out=circuit.port_out,
        ),
        SweepConfig(1e6, 100e6, 16),
    )
    expected = reference.s21 * np.exp(0j)
    # The balun is not ideal with losses, but the S21 magnitude must stay
    # finite and the output is transformed rather than a through connection.
    assert np.all(np.isfinite(result.s21))
    assert not np.allclose(np.abs(result.s21), np.abs(expected))


def test_skrf_and_abcd_include_balun() -> None:
    balun = BalunSpec(
        kind="guanella",
        turns_ratio=0.5,
        z0_line_ohm=100.0,
        length_m=0.05,
        velocity_factor=0.7,
        leakage_h=1e-7,
        core_loss_ohm=5000.0,
        shunt_c_f=2e-12,
    )
    circuit = _circuit(balun)
    sweep = SweepConfig(1e6, 100e6, 31)
    abcd = analyze_circuit(circuit, sweep, backend="abcd")
    skrf = analyze_circuit(circuit, sweep, backend="skrf")
    assert np.allclose(abcd.s21, skrf.s21, rtol=1e-9, atol=1e-12)
    assert np.allclose(abcd.s11, skrf.s11, rtol=1e-9, atol=1e-12)


def test_balun_exports_use_bal1() -> None:
    spec = BalunSpec(
        kind="unun",
        turns_ratio=0.5,
        leakage_h=1e-7,
        core_loss_ohm=5000.0,
        core="FT240-43",
        turns=3,
        wire_awg=21,
    )
    circuit = _circuit(spec)
    net = spice_netlist(circuit)
    assert "E_BAL1 BAL1_s 0" in net
    assert "L_BAL1lk BAL1_p BAL1_x" in net
    assert "R_BAL1core BAL1_x 0" in net
    assert "Rload BAL1_sense 0 200" in net
    assert "E_T1" not in net
    asc = ltspice_asc(circuit)
    assert "E_BAL1 BAL1_s 0 BAL1_p 0" in asc
    assert "Rload" in asc and "BAL1_sense" in asc
    qucs = qucs_schematic(circuit)
    assert "<Tr BAL1" in qucs


def test_balun_component_table_row() -> None:
    spec = BalunSpec(kind="guanella", turns_ratio=0.5)
    circuit = _circuit(spec)
    table = {row["ref"]: row for row in circuit.component_table()}
    assert table["BAL1"]["type"] == "balun"
    assert table["BAL1"]["turns_ratio"] == pytest.approx(0.5)


def test_output_transformer_and_balun_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="cannot both"):
        Circuit(
            elements=[IdealResistor("R1", 0.0, "in", "out")],
            port_in=Port("in", "in", 50.0),
            port_out=Port("out", "out", 50.0),
            output_transformer_ratio=0.8,
            output_balun=BalunSpec(),
        )


def test_balun_bom_and_cli(tmp_path, capsys) -> None:
    design = design_balun(
        _core(),
        kind="guanella",
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=200.0,
        f_min_hz=3.5e6,
        f_max_hz=30e6,
        power_w=100.0,
    )
    circuit = _circuit(design.to_spec())
    rows = build_sheet_rows(circuit)
    balun_rows = [row for row in rows if row.ref == "BAL1"]
    assert len(balun_rows) == 1
    assert balun_rows[0].kind == "balun"
    assert balun_rows[0].value_text == f"{design.actual_turns_ratio:.4g}:1"
    assert balun_rows[0].core == "FT240-43"
    assert balun_rows[0].turns == design.n_primary

    assert (
        main(
            [
                "balun",
                "--kind",
                "guanella",
                "--z-unbalanced",
                "50",
                "--z-balanced",
                "200",
                "--core",
                "FT240-43",
                "--f-min",
                "3.5M",
                "--f-max",
                "30M",
                "--power",
                "100",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "guanella"
    assert payload["turns_ratio"] == pytest.approx(0.5)
    assert payload["length_m"] > 0.0


def test_balun_cli_error(capsys) -> None:
    assert (
        main(
            [
                "balun",
                "--kind",
                "choke",
                "--z-unbalanced",
                "50",
                "--z-balanced",
                "200",
                "--core",
                "FT240-43",
            ]
        )
        == 2
    )
    assert "error:" in capsys.readouterr().err


def test_main_window_applies_and_removes_balun(monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication, QDialog

    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    class ApplyDialog:
        def __init__(self, parent=None) -> None:
            del parent

        def exec(self):
            return QDialog.DialogCode.Accepted

        def remove_requested(self) -> bool:
            return False

        def balun_spec(self) -> BalunSpec:
            return BalunSpec(
                kind="unun",
                topology="autotransformer",
                turns_ratio=0.5,
                total_turns=8,
                core="FT140-43",
                turns=4,
                wire_awg=21,
            )

    class RemoveDialog(ApplyDialog):
        def remove_requested(self) -> bool:
            return True

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = mw.MainWindow(session, auto_run=False)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    monkeypatch.setattr(mw, "TransformerDialog", ApplyDialog)
    window._run_transformer()
    assert session.circuit is not None
    assert session.circuit.output_balun is not None
    assert session.circuit.output_balun.total_turns == 8
    monkeypatch.setattr(mw, "TransformerDialog", RemoveDialog)
    window._run_transformer()
    assert session.circuit.output_balun is None
    window.close()
    assert app is not None


def test_balun_dialog(qtbot) -> None:
    from filterdesk.gui.widgets import TransformerDialog

    dialog = TransformerDialog()
    qtbot.addWidget(dialog)
    design = dialog.current_design()
    assert design is not None
    assert design.kind is BalunKind.UNUN
    spec = dialog.balun_spec()
    assert spec is not None
    dialog._kind.setCurrentText("guanella")
    dialog._recompute()
    design = dialog.current_design()
    assert design is not None and design.kind is BalunKind.GUANELLA
    assert design.length_m > 0.0
