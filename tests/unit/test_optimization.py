"""Component-value optimizer against limit regions (FR-P4)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.overlays import LimitMetric, LimitRegion
from filterdesk.domain.specs import FilterSpec
from filterdesk.optimization import (
    OptimizationCancelled,
    OptimizationConfig,
    OptimizationError,
    OptimizeMethod,
    PassbandRipple,
    ReturnLoss,
    StopbandAttenuation,
    apply_values,
    combined_residuals,
    limit_residuals,
    objective_residuals,
    optimize_circuit,
    relative_bounds,
    residual_norm,
    tunable_params,
)
from filterdesk.services.session import DesignSession
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


def _tight_passband(y_min: float = -0.02) -> LimitRegion:
    return LimitRegion(
        id="pb",
        metric=LimitMetric.S21_DB,
        f_low_hz=1e6,
        f_high_hz=100e6,
        y_min=y_min,
    )


def test_tunable_params_lp() -> None:
    circuit = synthesize(_spec()).circuit
    params = tunable_params(circuit)
    assert [p.ref for p in params] == ["L1", "C2", "L3", "C4", "L5"]
    assert all(p.value > 0 for p in params)


def test_apply_values_changes_only_target() -> None:
    circuit = synthesize(_spec()).circuit
    params = tunable_params(circuit)
    x0 = np.asarray([p.value for p in params])
    same = apply_values(circuit, params, x0)
    for orig, back in zip(circuit.elements, same.elements, strict=True):
        assert type(orig) is type(back)
    changed = apply_values(circuit, params, x0 * np.asarray([2, 1, 1, 1, 1]))
    assert changed.elements[0].value_h == pytest.approx(  # type: ignore[union-attr]
        circuit.elements[0].value_h * 2  # type: ignore[union-attr]
    )
    assert changed.elements[1].value_f == pytest.approx(  # type: ignore[union-attr]
        circuit.elements[1].value_f  # type: ignore[union-attr]
    )


def test_relative_bounds() -> None:
    bounds = relative_bounds(np.array([100.0, 200.0]), 0.1)
    assert bounds.lower.tolist() == pytest.approx([90.0, 180.0])
    assert bounds.upper.tolist() == pytest.approx([110.0, 220.0])


def test_limit_residuals_satisfied_and_violated() -> None:
    circuit = synthesize(_spec()).circuit
    sweep = _sweep()
    result = analyze_circuit(circuit, sweep)
    loose = limit_residuals(result, [_tight_passband(-3.0)])
    assert loose.size > 0
    assert residual_norm(loose) == pytest.approx(0.0)
    tight = limit_residuals(result, [_tight_passband(-0.02)])
    assert residual_norm(tight) > 0.0
    assert limit_residuals(result, []).size == 0


@pytest.mark.parametrize(
    "method", [OptimizeMethod.LEAST_SQUARES, OptimizeMethod.NELDER_MEAD]
)
def test_optimize_reduces_cost(method: OptimizeMethod) -> None:
    circuit = synthesize(_spec()).circuit
    sweep = _sweep()
    limits = [_tight_passband(-0.02)]
    config = OptimizationConfig(method=method, bound_pct=0.5, max_iter=300)
    result = optimize_circuit(circuit, sweep, limits, config)
    assert result.final_cost < result.initial_cost
    assert result.n_evaluations >= 1
    assert len(result.refs) == 5
    assert len(result.circuit.elements) == len(circuit.elements)


@pytest.mark.parametrize(
    "method",
    [OptimizeMethod.DIFFERENTIAL_EVOLUTION, OptimizeMethod.DUAL_ANNEALING],
)
def test_optimize_global_never_worse(method: OptimizeMethod) -> None:
    circuit = synthesize(_spec()).circuit
    sweep = _sweep()
    limits = [_tight_passband(-0.02)]
    config = OptimizationConfig(method=method, bound_pct=0.5, max_iter=60, seed=1)
    result = optimize_circuit(circuit, sweep, limits, config)
    assert result.final_cost <= result.initial_cost + 1e-12


def test_optimize_differential_evolution_improves() -> None:
    config = OptimizationConfig(
        method=OptimizeMethod.DIFFERENTIAL_EVOLUTION,
        bound_pct=0.5,
        max_iter=80,
        seed=1,
    )
    result = optimize_circuit(
        synthesize(_spec()).circuit, _sweep(), [_tight_passband(-0.02)], config
    )
    assert result.final_cost < result.initial_cost


def test_objective_residuals() -> None:
    circuit = synthesize(_spec()).circuit
    result = analyze_circuit(circuit, _sweep())

    ripple = objective_residuals(result, [PassbandRipple(1e6, 100e6)])
    assert ripple.size == 1 and ripple[0] > 0.0  # non-zero passband ripple
    # A band with no samples yields a zero penalty.
    empty = objective_residuals(result, [PassbandRipple(9e9, 9.5e9)])
    assert empty[0] == pytest.approx(0.0)

    assert objective_residuals(
        result, [StopbandAttenuation(150e6, 1e9, 1.0)]
    )[0] == pytest.approx(0.0)  # already far above 1 dB
    assert objective_residuals(
        result, [StopbandAttenuation(150e6, 1e9, 500.0)]
    )[0] > 0.0

    assert objective_residuals(result, [ReturnLoss(1e6, 100e6, -60.0)])[
        0
    ] == pytest.approx(0.0)
    assert objective_residuals(result, [ReturnLoss(1e6, 100e6, 60.0)])[0] > 0.0


def test_combined_residuals_concatenates() -> None:
    circuit = synthesize(_spec()).circuit
    result = analyze_circuit(circuit, _sweep())
    limits = [_tight_passband(-3.0)]  # satisfied
    limits_only = combined_residuals(result, limits, [])
    both = combined_residuals(result, limits, [PassbandRipple(1e6, 100e6)])
    assert both.size == limits_only.size + 1


def test_optimize_objectives_only_reduces_cost() -> None:
    circuit = synthesize(_spec()).circuit
    config = OptimizationConfig(
        method=OptimizeMethod.NELDER_MEAD,
        bound_pct=0.3,
        max_iter=200,
        objectives=(PassbandRipple(1e6, 100e6),),
    )
    result = optimize_circuit(circuit, _sweep(), [], config)
    assert result.final_cost < result.initial_cost


def test_cli_optimize_objective(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "optimize",
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
            "--objective",
            "passband:1M:100M",
            "--method",
            "nelder_mead",
            "--bound",
            "0.3",
            "--max-iter",
            "100",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["final_cost"] <= payload["initial_cost"]


def test_cli_optimize_rejects_bad_objective(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "optimize",
            "--family",
            "butterworth",
            "--response",
            "low_pass",
            "--order",
            "3",
            "--cutoff",
            "100M",
            "--objective",
            "bogus:1M",
        ]
    )
    assert code == 2
    assert "error:" in capsys.readouterr().err


def test_optimize_requires_enabled_limits() -> None:
    circuit = synthesize(_spec()).circuit
    with pytest.raises(OptimizationError):
        optimize_circuit(circuit, _sweep(), [])


def test_config_validation() -> None:
    with pytest.raises(OptimizationError):
        OptimizationConfig(bound_pct=-0.1)
    with pytest.raises(OptimizationError):
        OptimizationConfig(max_iter=0)


def test_session_optimize_does_not_mutate() -> None:
    session = DesignSession()
    session.set_spec(_spec())
    session.synthesize()
    session.sweep = _sweep()
    session.limits = [_tight_passband(-0.02)]
    assert session.circuit is not None
    before = [p.value for p in tunable_params(session.circuit)]
    result = session.optimize(
        OptimizationConfig(method=OptimizeMethod.NELDER_MEAD, max_iter=200)
    )
    assert result.final_cost <= result.initial_cost
    after = [p.value for p in tunable_params(session.circuit)]
    assert after == before


def test_cli_optimize(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    limits_path = tmp_path / "limits.json"
    limits_path.write_text(
        json.dumps(
            [
                {
                    "id": "pb",
                    "metric": "s21_db",
                    "f_low_hz": 1e6,
                    "f_high_hz": 100e6,
                    "y_min": -0.02,
                }
            ]
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "optimize",
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
            "--limits",
            str(limits_path),
            "--method",
            "nelder_mead",
            "--bound",
            "0.5",
            "--max-iter",
            "200",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["method"] == "nelder_mead"
    assert payload["final_cost"] <= payload["initial_cost"]
    assert len(payload["components"]) == 5


def test_optimize_cancel_raises() -> None:
    with pytest.raises(OptimizationCancelled):
        optimize_circuit(
            synthesize(_spec()).circuit,
            _sweep(),
            [_tight_passband()],
            OptimizationConfig(max_iter=3),
            cancel=lambda: True,
        )
