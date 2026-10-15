"""Matplotlib Smith-chart export tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from filterdesk.analysis.types import AnalysisResult
from filterdesk.domain.overlays import Marker
from filterdesk.plotting.smith_export import export_smith_chart, render_smith_figure


def _tiny_result() -> AnalysisResult:
    f = np.array([1e6, 2e6, 3e6], dtype=float)
    s11 = np.array([0.1 + 0.0j, 0.2 + 0.1j, 0.0 + 0.3j], dtype=np.complex128)
    s21 = np.array([0.9 + 0.0j, 0.8 + 0.0j, 0.7 + 0.0j], dtype=np.complex128)
    s22 = np.array([-0.1 + 0.0j, -0.15 + 0.05j, 0.05 - 0.2j], dtype=np.complex128)
    zin = np.full(3, 50.0 + 0.0j, dtype=np.complex128)
    return AnalysisResult(
        frequency_hz=f,
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


def test_render_smith_figure_has_axes() -> None:
    fig = render_smith_figure(_tiny_result())
    try:
        assert len(fig.axes) == 1
        assert fig.axes[0].lines  # grid + loci
    finally:
        from matplotlib import pyplot as plt

        plt.close(fig)


@pytest.mark.parametrize("suffix", [".png", ".svg", ".pdf"])
def test_export_smith_writes_file(tmp_path: Path, suffix: str) -> None:
    out = tmp_path / f"smith{suffix}"
    path = export_smith_chart(
        _tiny_result(),
        out,
        markers=[Marker(id="m1", frequency_hz=2e6, label="mid")],
    )
    assert path == out
    assert out.is_file()
    assert out.stat().st_size > 200


def test_export_smith_rejects_bad_suffix(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        export_smith_chart(_tiny_result(), tmp_path / "smith.bin")
