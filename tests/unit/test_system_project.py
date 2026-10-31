"""Versioned .fdsys.json system project round-trip."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from filterdesk.analysis.types import SweepConfig, SweepSpacing
from filterdesk.components_std import ESeries
from filterdesk.domain.enums import ApproximationFamily
from filterdesk.services.system_parasitics import SystemParasiticsConfig
from filterdesk.services.system_project import (
    SystemBand,
    SystemProject,
    SystemProjectError,
    read_system_project,
    system_project_from_mapping,
    system_project_to_mapping,
    write_system_project,
)


def _base(**overrides: object) -> SystemProject:
    values: dict[str, object] = {
        "kind": "lp-hp",
        "order": 5,
        "family": ApproximationFamily.CHEBYSHEV_TYPE_I,
        "ripple_db": 0.1,
        "stopband_attenuation_db": None,
        "z0_ohm": 50.0,
        "sweep": SweepConfig(1e6, 200e6, 1001, SweepSpacing.LOGARITHMIC),
        "snap_series": ESeries.E24,
        "parasitics": SystemParasiticsConfig(
            inductor_q=100.0,
            capacitor_esr_ohm=0.1,
            capacitor_esl_h=1e-9,
        ),
        "low_cutoff_hz": 30e6,
        "high_cutoff_hz": 40e6,
    }
    values.update(overrides)
    return SystemProject(**values)  # type: ignore[arg-type]


def test_round_trip_all_kinds(tmp_path: Path) -> None:
    projects = (
        _base(),
        _base(
            kind="bp-bp",
            low_cutoff_hz=None,
            high_cutoff_hz=None,
            bands=(
                SystemBand("low", 14e6, 0.3e6),
                SystemBand("high", 21e6, 0.5e6),
            ),
        ),
        _base(
            kind="duplexer",
            low_cutoff_hz=None,
            high_cutoff_hz=None,
            tx_center_hz=145e6,
            tx_bandwidth_hz=1e6,
            rx_center_hz=147e6,
            rx_bandwidth_hz=1e6,
        ),
        _base(
            kind="triplexer",
            low_cutoff_hz=None,
            high_cutoff_hz=None,
            bands=(
                SystemBand("low", 14e6, 0.3e6),
                SystemBand("mid", 21e6, 0.5e6),
                SystemBand("high", 28e6, 0.5e6),
            ),
        ),
        _base(
            kind="multiplexer",
            low_cutoff_hz=None,
            high_cutoff_hz=None,
            bands=(
                SystemBand("low", 14e6, 0.3e6),
                SystemBand("mid", 21e6, 0.5e6),
                SystemBand("high", 28e6, 0.5e6),
                SystemBand("top", 35e6, 0.5e6),
            ),
        ),
    )
    for index, project in enumerate(projects):
        path = tmp_path / f"system{index}.fdsys.json"
        assert write_system_project(project, path) == path
        loaded = read_system_project(path)
        assert loaded == project
        assert system_project_from_mapping(
            system_project_to_mapping(project)
        ) == project


def test_project_rejects_invalid_format_and_kind(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"format": "wrong", "version": 1}), encoding="utf-8")
    with pytest.raises(SystemProjectError, match="format"):
        read_system_project(path)
    with pytest.raises(SystemProjectError, match="kind"):
        _base(kind="unknown")
    with pytest.raises(SystemProjectError, match="cutoff"):
        _base(low_cutoff_hz=None)
    with pytest.raises(SystemProjectError, match="bands"):
        _base(kind="triplexer", low_cutoff_hz=None, high_cutoff_hz=None)
