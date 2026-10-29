"""Four-port mixed-mode S-parameter transform and CLI."""

from __future__ import annotations

import json

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.four_port import FourPortError, mixed_mode_4port


def _thru_pairs() -> np.ndarray:
    s = np.zeros((1, 4, 4), dtype=complex)
    s[0, 2, 0] = 1.0
    s[0, 3, 1] = 1.0
    s[0, 0, 2] = 1.0
    s[0, 1, 3] = 1.0
    return s


def test_ideal_differential_and_common_thru() -> None:
    report = mixed_mode_4port(_thru_pairs(), [100e6])
    assert report.sdd[0, 1, 0] == pytest.approx(1.0)
    assert report.scc[0, 1, 0] == pytest.approx(1.0)
    assert np.allclose(report.sdc, 0.0)
    assert np.allclose(report.scd, 0.0)
    assert report.z0_diff_ohm == pytest.approx(100.0)
    assert report.z0_common_ohm == pytest.approx(25.0)


def test_crossed_outputs_flip_differential_sign() -> None:
    s = np.zeros((1, 4, 4), dtype=complex)
    s[0, 3, 0] = 1.0
    s[0, 2, 1] = 1.0
    s[0, 0, 3] = 1.0
    s[0, 1, 2] = 1.0
    report = mixed_mode_4port(s, [100e6])
    assert report.sdd[0, 1, 0] == pytest.approx(-1.0)
    assert report.scc[0, 1, 0] == pytest.approx(1.0)


def test_transform_matches_matrix_definition() -> None:
    rng = np.random.default_rng(7)
    s = rng.normal(size=(5, 4, 4)) + 1j * rng.normal(size=(5, 4, 4))
    report = mixed_mode_4port(s, np.geomspace(1e6, 1e9, 5))
    root = 1.0 / np.sqrt(2.0)
    m = np.array(
        [
            [root, -root, 0.0, 0.0],
            [0.0, 0.0, root, -root],
            [root, root, 0.0, 0.0],
            [0.0, 0.0, root, root],
        ]
    )
    expected = np.einsum("ij,njk,lk->nil", m, s, m)
    assert np.allclose(report.s_mm, expected)
    assert np.allclose(report.sdd, expected[:, :2, :2])
    assert np.allclose(report.sdc, expected[:, :2, 2:])
    assert np.allclose(report.scd, expected[:, 2:, :2])
    assert np.allclose(report.scc, expected[:, 2:, 2:])


@pytest.mark.parametrize(
    ("s", "freq", "z0", "message"),
    [
        (np.zeros((1, 3, 3)), [1e6], 50.0, "shape"),
        (np.zeros((1, 4, 4)), [0.0], 50.0, "frequency"),
        (np.zeros((1, 4, 4)), [1e6], 0.0, "z0"),
    ],
)
def test_validation(s, freq, z0: float, message: str) -> None:
    with pytest.raises(FourPortError, match=message):
        mixed_mode_4port(s, freq, z0_ohm=z0)


def test_cli_mixed_mode_json(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    values = [100e6]
    for row in np.eye(4).reshape(-1):
        values.extend((float(row.real), float(row.imag)))
    path = tmp_path / "device.s4p"
    path.write_text(
        "# HZ S RI R 50\n" + " ".join(f"{value:.12g}" for value in values) + "\n",
        encoding="utf-8",
    )
    assert main(["mixed-mode", str(path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["n_ports"] == 4
    assert payload["z0_diff_ohm"] == pytest.approx(100.0)
    assert payload["z0_common_ohm"] == pytest.approx(25.0)
    assert payload["frequency_hz"] == pytest.approx([100e6])
    assert len(payload["sdd"]) == 1


def test_gui_dialog_loads_4port(tmp_path) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import FourPortMixedModeDialog

    app = QApplication.instance() or QApplication([])
    values = [100e6]
    for row in np.eye(4).reshape(-1):
        values.extend((float(row.real), float(row.imag)))
    path = tmp_path / "device.s4p"
    path.write_text(
        "# HZ S RI R 50\n" + " ".join(f"{value:.12g}" for value in values) + "\n",
        encoding="utf-8",
    )
    dialog = FourPortMixedModeDialog()
    assert dialog.load_path(path)
    assert dialog._table.rowCount() == 1
    assert "4-port" in dialog._summary.text()
    assert dialog._table.horizontalHeaderItem(1).text() == "Sdd21 (dB)"
    dialog.close()
    assert app is not None


def test_gui_dialog_plot_populates(tmp_path) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.widgets import FourPortMixedModeDialog

    app = QApplication.instance() or QApplication([])
    values = [100e6]
    for row in np.eye(4).reshape(-1):
        values.extend((float(row.real), float(row.imag)))
    path = tmp_path / "device.s4p"
    path.write_text(
        "# HZ S RI R 50\n" + " ".join(f"{value:.12g}" for value in values) + "\n",
        encoding="utf-8",
    )
    dialog = FourPortMixedModeDialog()
    assert dialog.load_path(path)
    for curve in (
        dialog._curve_sdd,
        dialog._curve_sdc,
        dialog._curve_scd,
        dialog._curve_scc,
    ):
        data = curve.getData()
        assert data[0] is not None and data[0].size == 1
    assert dialog._view_tabs.count() == 2
    dialog.close()
    assert app is not None
