"""Mixed-mode 3-port boundary model."""

from __future__ import annotations

import numpy as np
import pytest

from filterdesk.analysis.adapters.abcd_ladder import abcd_to_s, transformer_abcd
from filterdesk.analysis.mixed_mode import MixedModeError, mixed_mode_balun
from filterdesk.domain.circuit import BalunSpec


def test_ideal_balun_mixed_mode_blocks_are_consistent() -> None:
    spec = BalunSpec(
        kind="ideal",
        turns_ratio=0.5,
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=200.0,
    )
    freq = np.array([1e6, 10e6, 100e6])
    result = mixed_mode_balun(spec, freq)
    s11, s21, s12, s22 = abcd_to_s(transformer_abcd(0.5, freq.size), 50.0, 200.0)
    assert np.allclose(result.sdd[:, 0, 0], s11)
    assert np.allclose(result.sdd[:, 1, 0], s21)
    assert np.allclose(result.sdd[:, 0, 1], s12)
    assert np.allclose(result.sdd[:, 1, 1], s22)
    assert np.allclose(result.scc, 1.0)
    assert np.allclose(result.sdc, 0.0)
    assert np.allclose(result.scd, 0.0)
    assert result.z0_input_ohm == pytest.approx(50.0)
    assert result.z0_diff_ohm == pytest.approx(200.0)
    assert result.z0_common_ohm == pytest.approx(100.0)


def test_choke_common_mode_transition() -> None:
    spec = BalunSpec(
        kind="choke",
        turns_ratio=1.0,
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=50.0,
        magnetizing_inductance_h=1e-5,
    )
    result = mixed_mode_balun(spec, np.array([1e3, 1e6, 100e6]))
    assert result.scc[0].real < -0.9
    assert result.scc[1].real > 0.2
    assert result.scc[2].real > 0.99
    assert abs(result.scc[0]) <= 1.0 + 1e-12


def test_mixed_mode_validation() -> None:
    spec = BalunSpec(
        kind="choke",
        turns_ratio=1.0,
        z_unbalanced_ohm=50.0,
        z_balanced_ohm=50.0,
    )
    with pytest.raises(MixedModeError, match="frequencies"):
        mixed_mode_balun(spec, [])
    with pytest.raises(MixedModeError, match="reference"):
        mixed_mode_balun(spec, [1e6], z0_input_ohm=0.0)
