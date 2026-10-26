"""Post-synthesis specification compliance checks."""

from __future__ import annotations

from dataclasses import replace

import pytest

from filterdesk.analysis.compliance import check_spec_compliance
from filterdesk.domain.enums import (
    ApproximationFamily as Fam,
)
from filterdesk.domain.enums import (
    CutoffDefinition as Cut,
)
from filterdesk.domain.enums import (
    FilterResponse as Resp,
)
from filterdesk.domain.enums import (
    TopologyId as Topo,
)
from filterdesk.domain.specs import FilterSpec, SpecValidationError
from filterdesk.synthesis import synthesize

FC = 100e6
F0 = 100e6
BW = 20e6

_TOPOLOGY = {
    Resp.LOW_PASS: Topo.LADDER_LP_SERIES_L_INPUT,
    Resp.HIGH_PASS: Topo.LADDER_HP_SERIES_C_INPUT,
    Resp.BAND_PASS: Topo.LADDER_BP_SERIES_RES_INPUT,
    Resp.BAND_STOP: Topo.LADDER_BS_SERIES_TANK_INPUT,
}


def _spec(
    family: Fam,
    order: int,
    response: Resp,
    *,
    ap: float = 0.5,
    as_db: float = 40.0,
    zs: float = 50.0,
    zl: float = 50.0,
    cutoff: float = FC,
) -> FilterSpec:
    kw = dict(
        family=family,
        response=response,
        order=order,
        z_source_ohm=zs,
        z_load_ohm=zl,
        topology_id=_TOPOLOGY[response],
    )
    if response in (Resp.LOW_PASS, Resp.HIGH_PASS):
        kw["cutoff_hz"] = cutoff
    else:
        kw.update(f_center_hz=F0, bandwidth_hz=BW)
    if family in (Fam.CHEBYSHEV_TYPE_I, Fam.ELLIPTIC):
        kw.update(cutoff_definition=Cut.RIPPLE_EDGE, passband_ripple_db=ap)
    elif family == Fam.CHEBYSHEV_TYPE_II:
        kw["cutoff_definition"] = Cut.STOPBAND_EDGE
    else:
        kw["cutoff_definition"] = Cut.HALF_POWER_3DB
    if family in (Fam.CHEBYSHEV_TYPE_II, Fam.ELLIPTIC):
        kw["stopband_attenuation_db"] = as_db
    if family == Fam.M_DERIVED:
        kw["m_parameter"] = 0.6
    return FilterSpec(**kw)


@pytest.mark.parametrize("response", list(Resp))
@pytest.mark.parametrize(
    ("family", "order"),
    [
        (Fam.BUTTERWORTH, 3),
        (Fam.BUTTERWORTH, 5),
        (Fam.CHEBYSHEV_TYPE_I, 3),
        (Fam.CHEBYSHEV_TYPE_I, 4),
        (Fam.CHEBYSHEV_TYPE_II, 3),
        (Fam.CHEBYSHEV_TYPE_II, 4),
        (Fam.ELLIPTIC, 3),
        (Fam.ELLIPTIC, 5),
        (Fam.BESSEL, 3),
        (Fam.BESSEL, 5),
        (Fam.GAUSSIAN, 3),
        (Fam.LEGENDRE, 3),
        (Fam.CONSTANT_K, 3),
        (Fam.M_DERIVED, 3),
    ],
)
def test_supported_designs_meet_spec(
    family: Fam, order: int, response: Resp
) -> None:
    ap = 0.1 if family == Fam.CHEBYSHEV_TYPE_I else 0.5
    spec = _spec(family, order, response, ap=ap)
    report = check_spec_compliance(spec, synthesize(spec).circuit, points=1200)
    assert report.ok, report.issues


def test_high_orders_compliance() -> None:
    for family, order in (
        (Fam.CHEBYSHEV_TYPE_I, 8),
        (Fam.CHEBYSHEV_TYPE_I, 10),
        (Fam.ELLIPTIC, 7),
        (Fam.ELLIPTIC, 9),
    ):
        spec = _spec(
            family,
            order,
            Resp.LOW_PASS,
            ap=0.1 if family == Fam.CHEBYSHEV_TYPE_I else 0.5,
        )
        report = check_spec_compliance(spec, synthesize(spec).circuit, points=2500)
        assert report.ok, (family, order, report.issues)


def test_notes_for_documented_approximations() -> None:
    even_cheb = _spec(Fam.CHEBYSHEV_TYPE_I, 4, Resp.LOW_PASS, ap=0.1)
    report = check_spec_compliance(
        even_cheb, synthesize(even_cheb).circuit, points=1200
    )
    assert any("modified equal-termination" in note for note in report.notes)

    asym = _spec(Fam.BUTTERWORTH, 3, Resp.LOW_PASS, zl=75.0)
    report = check_spec_compliance(asym, synthesize(asym).circuit, points=1200)
    assert any("ideal output transformer" in note for note in report.notes)

    image = _spec(Fam.CONSTANT_K, 3, Resp.LOW_PASS)
    report = check_spec_compliance(image, synthesize(image).circuit, points=1200)
    assert any("Image-parameter" in note for note in report.notes)
    assert report.ok


def test_wrong_circuit_fails_compliance() -> None:
    spec = _spec(Fam.BUTTERWORTH, 3, Resp.LOW_PASS, cutoff=200e6)
    circuit = synthesize(_spec(Fam.BUTTERWORTH, 3, Resp.LOW_PASS, cutoff=100e6)).circuit
    report = check_spec_compliance(spec, circuit, points=1200)
    assert not report.ok
    assert report.issues


def test_even_order_elliptic_rejected_before_check() -> None:
    spec = _spec(Fam.ELLIPTIC, 4, Resp.LOW_PASS)
    circuit = synthesize(_spec(Fam.BUTTERWORTH, 3, Resp.LOW_PASS)).circuit
    with pytest.raises(SpecValidationError, match="odd orders"):
        check_spec_compliance(spec, circuit)


def test_cli_check_flag(capsys: pytest.CaptureFixture[str]) -> None:
    import json

    from filterdesk.__main__ import main

    assert (
        main(
            [
                "analyze",
                "--family",
                "butterworth",
                "--response",
                "low_pass",
                "--order",
                "5",
                "--cutoff",
                "100M",
                "--points",
                "64",
                "--check",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["compliance"]["ok"] is True

    assert (
        main(
            [
                "synthesize",
                "--family",
                "butterworth",
                "--response",
                "low_pass",
                "--order",
                "5",
                "--cutoff",
                "100M",
                "--check",
            ]
        )
        == 0
    )
    assert "Spec compliance: PASS" in capsys.readouterr().out


def test_gui_compliance_action(monkeypatch: pytest.MonkeyPatch) -> None:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize()
    window = MainWindow(session, auto_run=False)
    infos: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: infos.append(args) or QMessageBox.StandardButton.Ok,
    )
    window._run_compliance_check()
    assert "PASS" in window._status.text()
    assert infos

    warnings: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: warnings.append(args) or QMessageBox.StandardButton.Ok,
    )
    session.spec = replace(session.spec, cutoff_hz=session.spec.cutoff_hz * 0.5)
    window._run_compliance_check()
    assert "FAIL" in window._status.text()
    assert warnings
    window.close()
    assert app is not None
