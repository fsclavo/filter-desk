"""Measured vs simulated system path comparison."""

from __future__ import annotations

import numpy as np

from filterdesk.analysis.types import AnalysisResult, SweepConfig, SweepSpacing
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.services.diplexer import DiplexerConfig, design_diplexer
from filterdesk.services.system_compare import (
    compare_system_paths,
    default_measurement_paths,
)


def _design():
    return design_diplexer(
        DiplexerConfig(
            low_cutoff_hz=30e6,
            high_cutoff_hz=40e6,
            order=5,
            family=ApproximationFamily.CHEBYSHEV_TYPE_I,
            ripple_db=0.1,
        ),
        SweepConfig(1e6, 200e6, 201, SweepSpacing.LOGARITHMIC),
    )


def _measured_from_path(design, from_port: int, to_port: int) -> AnalysisResult:
    network = design.network
    zeros = np.zeros_like(network.frequency_hz, dtype=np.complex128)
    return AnalysisResult(
        frequency_hz=network.frequency_hz,
        s11=network.s[:, from_port, from_port],
        s21=network.s[:, to_port, from_port],
        s12=network.s[:, from_port, to_port],
        s22=network.s[:, to_port, to_port],
        zin_ohm=zeros + 50.0,
        zout_ohm=zeros + 50.0,
        z0_source_ohm=50.0,
        z0_load_ohm=50.0,
        backend="measured",
    )


def test_default_paths_include_common_and_isolation() -> None:
    paths = default_measurement_paths(_design())
    labels = [path.label for path in paths]
    assert "Common → Low" in labels
    assert "Common → High" in labels
    assert "Low ↔ High" in labels


def test_identical_path_has_zero_error() -> None:
    design = _design()
    measured = _measured_from_path(design, 0, 1)
    results = compare_system_paths(design, {"Common → Low": measured})
    assert len(results) == 1
    assert results[0].compare.s21_db_rms_error < 1e-9
    assert results[0].compare.s11_db_rms_error < 1e-9
