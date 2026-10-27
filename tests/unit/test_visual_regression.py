"""Image-level visual regression for the Smith chart export."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from filterdesk.analysis.types import AnalysisResult  # noqa: E402
from filterdesk.plotting.smith_export import export_smith_chart  # noqa: E402

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "visual regression is a Linux offscreen baseline; Windows uses package smoke"
    ),
)

BASELINE = Path(__file__).resolve().parents[1] / "golden" / "visual" / "smith_basic.png"


def _result() -> AnalysisResult:
    freq = np.array([1e6, 2e6, 3e6], dtype=float)
    s11 = np.array([0.1 + 0.0j, 0.2 + 0.1j, 0.0 + 0.3j], dtype=np.complex128)
    s21 = np.array([0.9 + 0.0j, 0.8 + 0.0j, 0.7 + 0.0j], dtype=np.complex128)
    s22 = np.array([-0.1 + 0.0j, -0.15 + 0.05j, 0.05 - 0.2j], dtype=np.complex128)
    zin = np.full(3, 50.0 + 0.0j, dtype=np.complex128)
    return AnalysisResult(
        frequency_hz=freq,
        s11=s11,
        s21=s21,
        s12=s21.copy(),
        s22=s22,
        zin_ohm=zin,
        zout_ohm=zin.copy(),
        z0_source_ohm=50.0,
        z0_load_ohm=50.0,
        backend="test",
    )


def test_smith_export_matches_visual_baseline(tmp_path: Path) -> None:
    assert BASELINE.is_file()
    actual_path = tmp_path / "smith.png"
    export_smith_chart(_result(), actual_path, dpi=100)
    actual = np.asarray(Image.open(actual_path).convert("RGB"), dtype=np.float32)
    expected = np.asarray(Image.open(BASELINE).convert("RGB"), dtype=np.float32)
    assert actual.shape == expected.shape
    difference = np.abs(actual - expected)
    mean_abs = float(np.mean(difference))
    changed = float(np.mean(np.max(difference, axis=2) > 12.0))
    assert mean_abs < 1.0
    assert changed < 0.02
