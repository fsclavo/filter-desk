"""Monte-Carlo tolerance engine (FR-P3 core)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.circuit import Circuit, IdealCapacitor, IdealInductor
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.overlays import LimitMetric, LimitRegion
from filterdesk.domain.specs import FilterSpec
from filterdesk.montecarlo import (
    MonteCarloConfig,
    ToleranceDistribution,
    perturb_circuit,
    run_monte_carlo,
    wilson_interval,
)
from filterdesk.synthesis import synthesize


def _spec() -> FilterSpec:
    return FilterSpec(
        family=ApproximationFamily.CHEBYSHEV_TYPE_I,
        response=FilterResponse.LOW_PASS,
        order=5,
        cutoff_hz=100e6,
        cutoff_definition=CutoffDefinition.RIPPLE_EDGE,
        passband_ripple_db=0.1,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
    )


def _sweep() -> SweepConfig:
    return SweepConfig(
        f_start_hz=1e6,
        f_stop_hz=1e9,
        n_points=128,
        spacing=SweepSpacing.LOGARITHMIC,
    )


def _circuit() -> Circuit:
    return synthesize(_spec()).circuit


def _values(circuit: Circuit) -> list[float]:
    out: list[float] = []
    for el in circuit.elements:
        if isinstance(el, IdealInductor):
            out.append(el.value_h)
        elif isinstance(el, IdealCapacitor):
            out.append(el.value_f)
    return out


def _passband_limit(y_min: float) -> LimitRegion:
    return LimitRegion(
        id="pb",
        metric=LimitMetric.S21_DB,
        f_low_hz=1e6,
        f_high_hz=100e6,
        y_min=y_min,
    )


def test_uniform_perturbation_within_bounds_and_reproducible() -> None:
    circuit = _circuit()
    nominal = _values(circuit)
    config = MonteCarloConfig(n_trials=1, tolerance_pct=5.0, seed=42)
    rng = np.random.default_rng(42)
    perturbed = _values(perturb_circuit(circuit, rng, config))
    assert len(perturbed) == len(nominal)
    for base, val in zip(nominal, perturbed, strict=True):
        assert 0.95 * base <= val <= 1.05 * base
    rng2 = np.random.default_rng(42)
    perturbed2 = _values(perturb_circuit(circuit, rng2, config))
    assert perturbed == perturbed2


def test_zero_tolerance_matches_nominal() -> None:
    circuit = _circuit()
    sweep = _sweep()
    result = run_monte_carlo(
        circuit, sweep, MonteCarloConfig(n_trials=8, tolerance_pct=0.0, seed=1)
    )
    nominal = mag_db(analyze_circuit(circuit, sweep).s21)
    assert np.allclose(result.s21_db_min, nominal)
    assert np.allclose(result.s21_db_max, nominal)
    assert result.max_spread_db == pytest.approx(0.0, abs=1e-9)


def test_envelope_and_percentiles_ordering() -> None:
    result = run_monte_carlo(
        _circuit(), _sweep(), MonteCarloConfig(n_trials=64, tolerance_pct=3.0, seed=7)
    )
    assert result.n_trials == 64
    assert np.all(result.s21_db_min <= result.s21_db_max + 1e-9)
    assert np.all(result.s21_db_p05 <= result.s21_db_p50 + 1e-9)
    assert np.all(result.s21_db_p50 <= result.s21_db_p95 + 1e-9)
    assert result.max_spread_db > 0.0


def test_seed_reproducible() -> None:
    cfg = MonteCarloConfig(n_trials=32, tolerance_pct=4.0, seed=123)
    a = run_monte_carlo(_circuit(), _sweep(), cfg)
    b = run_monte_carlo(_circuit(), _sweep(), cfg)
    assert np.allclose(a.s21_db_min, b.s21_db_min)
    assert np.allclose(a.s21_db_max, b.s21_db_max)


def test_yield_all_pass_with_loose_limit() -> None:
    result = run_monte_carlo(
        _circuit(),
        _sweep(),
        MonteCarloConfig(n_trials=50, tolerance_pct=0.5, seed=3),
        limits=[_passband_limit(-3.0)],
    )
    assert result.yield_fraction == pytest.approx(1.0)
    assert result.passes == 50


def test_yield_none_without_limits() -> None:
    result = run_monte_carlo(
        _circuit(), _sweep(), MonteCarloConfig(n_trials=10, tolerance_pct=2.0, seed=0)
    )
    assert result.yield_fraction is None


def test_normal_distribution_mean_near_unity() -> None:
    circuit = _circuit()
    base = _values(circuit)
    config = MonteCarloConfig(
        n_trials=1, tolerance_pct=2.0, distribution=ToleranceDistribution.NORMAL
    )
    rng = np.random.default_rng(0)
    samples = []
    for _ in range(4000):
        vals = _values(perturb_circuit(circuit, rng, config))
        samples.extend(v / b for v, b in zip(vals, base, strict=True))
    assert float(np.mean(samples)) == pytest.approx(1.0, abs=0.01)


def test_config_validation() -> None:
    with pytest.raises(ValueError):
        MonteCarloConfig(n_trials=0)
    with pytest.raises(ValueError):
        MonteCarloConfig(tolerance_pct=-1.0)


def test_session_monte_carlo_uses_limits() -> None:
    from filterdesk.services.session import DesignSession

    session = DesignSession()
    session.set_spec(_spec())
    session.synthesize()
    session.sweep = _sweep()
    session.limits = [_passband_limit(-3.0)]
    result = session.monte_carlo(
        MonteCarloConfig(n_trials=20, tolerance_pct=0.5, seed=5)
    )
    assert result.yield_fraction == pytest.approx(1.0)


def test_wilson_interval_bounds() -> None:
    lo, hi = wilson_interval(50, 50)
    assert lo <= 1.0 and hi == pytest.approx(1.0)
    assert 0.0 <= lo <= hi <= 1.0
    with pytest.raises(ValueError):
        wilson_interval(0, 0)


def test_cli_montecarlo_human(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "montecarlo",
            "--family",
            "chebyshev_type_i",
            "--response",
            "low_pass",
            "--order",
            "5",
            "--cutoff",
            "100M",
            "--ripple",
            "0.1",
            "--points",
            "128",
            "--trials",
            "50",
            "--tol",
            "2",
            "--seed",
            "1",
        ]
    )
    assert code == 0
    assert "Monte-Carlo" in capsys.readouterr().out


def test_cli_montecarlo_json_and_yield(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    limits_path = tmp_path / "limits.json"
    limits_path.write_text(
        json.dumps(
            [
                {
                    "id": "pb",
                    "metric": "s21_db",
                    "f_low_hz": 1e6,
                    "f_high_hz": 100e6,
                    "y_min": -3.0,
                }
            ]
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "montecarlo",
            "--family",
            "chebyshev_type_i",
            "--response",
            "low_pass",
            "--order",
            "5",
            "--cutoff",
            "100M",
            "--ripple",
            "0.1",
            "--points",
            "128",
            "--trials",
            "50",
            "--tol",
            "0.5",
            "--seed",
            "1",
            "--limits",
            str(limits_path),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["distribution"] == "uniform"
    assert payload["yield"]["fraction"] == pytest.approx(1.0)
    assert "max_spread_db" in payload
