"""Independent validation of filter synthesis (audit).

Cross-checks against scipy analog prototypes, verifies LP/HP/BP/BS transforms
against the family's own low-pass response, checks passband/stopband
specifications, order estimation and dual topologies.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import signal

from filterdesk.analysis.adapters.abcd_ladder import (
    _element_abcd,
    abcd_to_s,
    cascade_abcd,
)
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import (
    ApproximationFamily as Fam,
)
from filterdesk.domain.enums import (
    CutoffDefinition,
    TopologyId,
)
from filterdesk.domain.enums import (
    FilterResponse as Resp,
)
from filterdesk.domain.specs import (
    FilterSpec,
    SpecValidationError,
    validate_spec,
)
from filterdesk.synthesis import synthesize
from filterdesk.synthesis.order_estimate import estimate_minimum_order

FC = 100e6
F0 = 100e6
BW = 20e6
Z0 = 50.0

_TAP = {
    Resp.LOW_PASS: TopologyId.LADDER_LP_SERIES_L_INPUT,
    Resp.HIGH_PASS: TopologyId.LADDER_HP_SERIES_C_INPUT,
    Resp.BAND_PASS: TopologyId.LADDER_BP_SERIES_RES_INPUT,
    Resp.BAND_STOP: TopologyId.LADDER_BS_SERIES_TANK_INPUT,
}
_DUAL = {
    Resp.LOW_PASS: TopologyId.LADDER_LP_SHUNT_C_INPUT,
    Resp.HIGH_PASS: TopologyId.LADDER_HP_SHUNT_L_INPUT,
    Resp.BAND_PASS: TopologyId.LADDER_BP_SHUNT_RES_INPUT,
    Resp.BAND_STOP: TopologyId.LADDER_BS_SHUNT_TANK_INPUT,
}


def _spec(
    family: Fam,
    order: int,
    response: Resp,
    topology: TopologyId | None = None,
    *,
    ap: float = 0.5,
    as_db: float = 40.0,
) -> FilterSpec:
    kw = dict(
        family=family,
        response=response,
        order=order,
        z_source_ohm=Z0,
        z_load_ohm=Z0,
        topology_id=topology or _TAP[response],
    )
    if response in (Resp.LOW_PASS, Resp.HIGH_PASS):
        kw["cutoff_hz"] = FC
    else:
        kw.update(f_center_hz=F0, bandwidth_hz=BW)
    if family in (Fam.CHEBYSHEV_TYPE_I, Fam.ELLIPTIC):
        kw.update(
            cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
            passband_ripple_db=ap if family == Fam.CHEBYSHEV_TYPE_I else 0.5,
        )
    elif family == Fam.CHEBYSHEV_TYPE_II:
        kw["cutoff_definition"] = CutoffDefinition.STOPBAND_EDGE
    else:
        kw["cutoff_definition"] = CutoffDefinition.HALF_POWER_3DB
    if family in (Fam.CHEBYSHEV_TYPE_II, Fam.ELLIPTIC):
        kw["stopband_attenuation_db"] = as_db
    return FilterSpec(**kw)


def _proto_zpk(family: Fam, order: int, *, ap: float, as_db: float):
    if family == Fam.BUTTERWORTH:
        return signal.buttap(order)
    if family == Fam.CHEBYSHEV_TYPE_I:
        return signal.cheb1ap(order, ap)
    if family == Fam.CHEBYSHEV_TYPE_II:
        return signal.cheb2ap(order, as_db)
    if family == Fam.ELLIPTIC:
        return signal.ellipap(order, ap, as_db)
    raise ValueError(family)


def _ref_s21(
    family: Fam, order: int, response: Resp, f: np.ndarray, *, ap: float, as_db: float
) -> np.ndarray:
    z, p, k = _proto_zpk(family, order, ap=ap, as_db=as_db)
    w = 2 * np.pi * np.asarray(f, dtype=float)
    if response == Resp.LOW_PASS:
        z, p, k = signal.lp2lp_zpk(z, p, k, wo=2 * np.pi * FC)
    elif response == Resp.HIGH_PASS:
        z, p, k = signal.lp2hp_zpk(z, p, k, wo=2 * np.pi * FC)
    elif response == Resp.BAND_PASS:
        z, p, k = signal.lp2bp_zpk(z, p, k, wo=2 * np.pi * F0, bw=2 * np.pi * BW)
    else:
        z, p, k = signal.lp2bs_zpk(z, p, k, wo=2 * np.pi * F0, bw=2 * np.pi * BW)
    _, h = signal.freqs_zpk(z, p, k, worN=w)
    return np.asarray(h, dtype=complex)


def _grid(response: Resp, n: int = 400) -> np.ndarray:
    if response in (Resp.LOW_PASS, Resp.HIGH_PASS):
        return np.logspace(np.log10(FC / 100), np.log10(FC * 10), n)
    return np.logspace(np.log10(F0 / 10), np.log10(F0 * 10), n)


def _s21(circuit, f: np.ndarray) -> np.ndarray:
    omega = 2 * np.pi * np.asarray(f, dtype=float)
    abcd = cascade_abcd([_element_abcd(el, omega) for el in circuit.elements])
    return np.asarray(abcd_to_s(abcd, Z0, Z0)[1], dtype=complex)


def _analyze(circuit, response: Resp, n: int = 400):
    f = _grid(response, n)
    return analyze_circuit(
        circuit, SweepConfig(float(f[0]), float(f[-1]), n, SweepSpacing.LOGARITHMIC)
    )


def _db(x: np.ndarray | complex) -> np.ndarray:
    return 20.0 * np.log10(np.abs(x) + 1e-30)


@pytest.mark.parametrize(
    ("family", "order", "response"),
    [
        (Fam.BUTTERWORTH, n, r)
        for n in (3, 5, 7)
        for r in (Resp.LOW_PASS, Resp.HIGH_PASS, Resp.BAND_PASS, Resp.BAND_STOP)
    ]
    + [
        (Fam.CHEBYSHEV_TYPE_I, n, r)
        for n in (3, 5, 7)
        for r in (Resp.LOW_PASS, Resp.HIGH_PASS, Resp.BAND_PASS, Resp.BAND_STOP)
    ]
    + [
        (Fam.ELLIPTIC, n, r)
        for n in (3, 5, 7)
        for r in (Resp.LOW_PASS, Resp.HIGH_PASS, Resp.BAND_PASS, Resp.BAND_STOP)
    ],
)
def test_classical_families_match_scipy(
    family: Fam, order: int, response: Resp
) -> None:
    ap = 0.1 if family == Fam.CHEBYSHEV_TYPE_I else 0.5
    circuit = synthesize(_spec(family, order, response, ap=ap)).circuit
    analysis = _analyze(circuit, response)
    ref = _ref_s21(
        family, order, response, analysis.frequency_hz, ap=ap, as_db=40.0
    )
    got, ref_mag = np.abs(analysis.s21), np.abs(ref)
    assert np.max(np.abs(got - ref_mag)) < 1e-3
    mask = ref_mag > 1e-4
    assert np.max(np.abs(_db(got[mask]) - _db(ref_mag[mask]))) < 0.05


@pytest.mark.parametrize(
    ("family", "order", "response"),
    [
        (Fam.CHEBYSHEV_TYPE_II, n, r)
        for n in (3, 4, 5)
        for r in (Resp.LOW_PASS, Resp.HIGH_PASS, Resp.BAND_PASS, Resp.BAND_STOP)
    ],
)
def test_chebyshev2_matches_scipy(family: Fam, order: int, response: Resp) -> None:
    circuit = synthesize(_spec(family, order, response, as_db=40.0)).circuit
    analysis = _analyze(circuit, response, 600)
    ref = _ref_s21(
        family, order, response, analysis.frequency_hz, ap=0.5, as_db=40.0
    )
    got, ref_mag = np.abs(analysis.s21), np.abs(ref)
    # Absolute magnitude: deep nulls make raw dB differences misleading, while
    # the stopband-attenuation requirement is checked by the spec test below.
    assert np.max(np.abs(got - ref_mag)) < 2e-2


@pytest.mark.parametrize(
    ("family", "order"),
    [(Fam.BUTTERWORTH, 5), (Fam.CHEBYSHEV_TYPE_I, 4), (Fam.CHEBYSHEV_TYPE_I, 5)],
)
@pytest.mark.parametrize(
    "response", [Resp.HIGH_PASS, Resp.BAND_PASS, Resp.BAND_STOP]
)
def test_transforms_match_own_lowpass(family: Fam, order: int, response: Resp) -> None:
    """LP→HP/BP/BS must be exact for the family's own prototype (even included)."""
    ap = 0.1 if family == Fam.CHEBYSHEV_TYPE_I else 0.5
    lp = synthesize(_spec(family, order, Resp.LOW_PASS, ap=ap)).circuit
    circuit = synthesize(_spec(family, order, response, ap=ap)).circuit
    f = _grid(response, 300)
    if response == Resp.HIGH_PASS:
        f_lp = np.abs(FC * FC / f)
    elif response == Resp.BAND_PASS:
        x = f / F0
        f_lp = np.abs(FC * (F0 / BW) * (x - 1.0 / x))
    else:
        x = f / F0
        f_lp = np.abs(FC * (BW / F0) * x / (1.0 - x * x))
    mask = np.isfinite(f_lp) & (np.abs(f_lp) >= FC / 1e4) & (np.abs(f_lp) <= FC * 1e4)
    got = np.abs(_s21(circuit, f[mask]))
    ref = np.abs(_s21(lp, np.abs(f_lp[mask])))
    assert np.max(np.abs(got - ref)) < 1e-9


@pytest.mark.parametrize("order", [3, 4, 5, 6, 8])
def test_chebyshev1_ripple_meets_spec(order: int) -> None:
    ap = 0.1
    circuit = synthesize(
        _spec(Fam.CHEBYSHEV_TYPE_I, order, Resp.LOW_PASS, ap=ap)
    ).circuit
    f = np.logspace(np.log10(FC / 1000), np.log10(FC), 12000)
    db = _db(_s21(circuit, f))
    assert db.max() == pytest.approx(0.0, abs=0.01)
    assert db.min() == pytest.approx(-ap, abs=0.01)


@pytest.mark.parametrize("order", [3, 4, 5])
def test_chebyshev2_stopband_meets_spec(order: int) -> None:
    as_db = 40.0
    circuit = synthesize(
        _spec(Fam.CHEBYSHEV_TYPE_II, order, Resp.LOW_PASS, as_db=as_db)
    ).circuit
    f = np.logspace(np.log10(FC), np.log10(FC * 20), 4000)
    assert _db(_s21(circuit, f)).min() <= -as_db + 0.05
    f_pass = np.logspace(np.log10(FC / 1000), np.log10(FC / 2), 2000)
    assert np.max(_db(_s21(circuit, f_pass))) <= 0.05


@pytest.mark.parametrize("order", [3, 5, 7])
def test_elliptic_odd_meets_spec(order: int) -> None:
    ap, as_db = 0.5, 40.0
    circuit = synthesize(
        _spec(Fam.ELLIPTIC, order, Resp.LOW_PASS, ap=ap, as_db=as_db)
    ).circuit
    f_pass = np.logspace(np.log10(FC / 1000), np.log10(FC), 8000)
    db_pass = _db(_s21(circuit, f_pass))
    assert db_pass.max() == pytest.approx(0.0, abs=0.01)
    assert db_pass.min() == pytest.approx(-ap, abs=0.01)
    # Find the reference stopband edge (first crossing -As) and check beyond it.
    z, p, k = signal.ellipap(order, ap, as_db)
    ws = np.logspace(0, 1.5, 20000)
    _, h = signal.freqs_zpk(z, p, k, worN=ws)
    edge = ws[np.argmax(_db(h) <= -as_db)]
    f_stop = np.logspace(np.log10(edge * FC), np.log10(FC * 20), 4000)
    assert _db(_s21(circuit, f_stop)).min() <= -as_db + 0.05


@pytest.mark.parametrize("order", [2, 4, 6])
def test_even_order_elliptic_is_rejected(order: int) -> None:
    spec = _spec(Fam.ELLIPTIC, order, Resp.LOW_PASS, ap=0.5, as_db=40.0)
    with pytest.raises(SpecValidationError, match="odd orders"):
        validate_spec(spec)


@pytest.mark.parametrize(
    ("family", "response"),
    [
        (Fam.BUTTERWORTH, Resp.LOW_PASS),
        (Fam.BUTTERWORTH, Resp.HIGH_PASS),
        (Fam.BUTTERWORTH, Resp.BAND_PASS),
        (Fam.BUTTERWORTH, Resp.BAND_STOP),
        (Fam.CHEBYSHEV_TYPE_I, Resp.LOW_PASS),
        (Fam.CHEBYSHEV_TYPE_I, Resp.BAND_PASS),
        (Fam.CHEBYSHEV_TYPE_II, Resp.LOW_PASS),
        (Fam.ELLIPTIC, Resp.LOW_PASS),
    ],
)
def test_dual_topology_same_response(family: Fam, response: Resp) -> None:
    ap = 0.1 if family == Fam.CHEBYSHEV_TYPE_I else 0.5
    a = synthesize(_spec(family, 5, response, _TAP[response], ap=ap)).circuit
    b = synthesize(_spec(family, 5, response, _DUAL[response], ap=ap)).circuit
    f = _grid(response, 200)
    assert np.max(np.abs(_s21(a, f) - _s21(b, f))) < 1e-9


@pytest.mark.parametrize(
    ("family", "response", "kwargs"),
    [
        (Fam.BUTTERWORTH, Resp.LOW_PASS, {}),
        (Fam.BUTTERWORTH, Resp.HIGH_PASS, {}),
        (Fam.BUTTERWORTH, Resp.BAND_PASS, {}),
        (Fam.CHEBYSHEV_TYPE_I, Resp.LOW_PASS, {"ap": 0.1}),
        (Fam.CHEBYSHEV_TYPE_I, Resp.BAND_PASS, {"ap": 0.1}),
        (Fam.CHEBYSHEV_TYPE_II, Resp.LOW_PASS, {"as_db": 40.0}),
        (Fam.ELLIPTIC, Resp.LOW_PASS, {"ap": 0.5, "as_db": 40.0}),
    ],
)
def test_order_estimation_matches_scipy(
    family: Fam, response: Resp, kwargs: dict[str, float]
) -> None:
    if response in (Resp.LOW_PASS, Resp.HIGH_PASS):
        fp, fs = np.array([1e6]), np.array([2e6])
        if response == Resp.HIGH_PASS:
            fp, fs = fs, fp
        ours = estimate_minimum_order(
            family,
            response,
            f_pass_hz=float(fp[0]),
            f_stop_hz=float(fs[0]),
            passband_attenuation_db=kwargs.get("ap", 0.5),
            stopband_attenuation_db=kwargs.get("as_db", 40.0),
        ).order
    else:
        fp = np.array([1e6, 2e6])
        fs = np.array([0.8e6, 2.5e6])
        ours = estimate_minimum_order(
            family,
            response,
            f_pass_low_hz=float(fp[0]),
            f_pass_high_hz=float(fp[1]),
            f_stop_low_hz=float(fs[0]),
            f_stop_high_hz=float(fs[1]),
            passband_attenuation_db=kwargs.get("ap", 0.5),
            stopband_attenuation_db=kwargs.get("as_db", 40.0),
        ).order
    wp, ws = 2 * np.pi * fp, 2 * np.pi * fs
    ap = kwargs.get("ap", 0.5)
    as_db = kwargs.get("as_db", 40.0)
    fn = {
        Fam.BUTTERWORTH: signal.buttord,
        Fam.CHEBYSHEV_TYPE_I: signal.cheb1ord,
        Fam.CHEBYSHEV_TYPE_II: signal.cheb2ord,
        Fam.ELLIPTIC: signal.ellipord,
    }[family]
    ref, _ = fn(wp, ws, ap, as_db, analog=True)
    assert ours == int(ref)


def test_asymmetric_z_element_scaling_uses_geometric_mean() -> None:
    spec_eq = FilterSpec(
        family=Fam.BUTTERWORTH,
        response=Resp.LOW_PASS,
        order=3,
        cutoff_hz=1e6,
        z_source_ohm=Z0,
        z_load_ohm=Z0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )
    spec_asym = FilterSpec(
        family=Fam.BUTTERWORTH,
        response=Resp.LOW_PASS,
        order=3,
        cutoff_hz=1e6,
        z_source_ohm=50.0,
        z_load_ohm=75.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
    )
    eq = synthesize(spec_eq).circuit
    asym = synthesize(spec_asym).circuit
    z0_eq = math.sqrt(50.0 * 50.0)
    z0_asym = math.sqrt(50.0 * 75.0)
    for a, b in zip(eq.elements, asym.elements, strict=True):
        ratio = z0_asym / z0_eq
        if hasattr(a, "value_h") and hasattr(b, "value_h"):
            assert b.value_h == pytest.approx(a.value_h * ratio, rel=1e-12)
        if hasattr(a, "value_f") and hasattr(b, "value_f"):
            assert b.value_f == pytest.approx(a.value_f / ratio, rel=1e-12)
