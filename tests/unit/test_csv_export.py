"""CSV / DAT trace export tests (Phase 10)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from filterdesk.__main__ import main
from filterdesk.analysis.derived import mag_db
from filterdesk.analysis.service import analyze_circuit
from filterdesk.analysis.types import AnalysisResult, SweepConfig, SweepSpacing
from filterdesk.domain.enums import (
    ApproximationFamily,
    CutoffDefinition,
    FilterResponse,
    TopologyId,
)
from filterdesk.domain.specs import FilterSpec
from filterdesk.io.csv_export import (
    COLUMNS,
    CsvExportError,
    analysis_from_touchstone,
    export_csv,
    export_dat,
)
from filterdesk.io.touchstone import read_touchstone, write_touchstone_s2p
from filterdesk.synthesis import synthesize


def _result() -> AnalysisResult:
    spec = FilterSpec(
        family=ApproximationFamily.BUTTERWORTH,
        response=FilterResponse.LOW_PASS,
        order=3,
        cutoff_hz=100e6,
        cutoff_definition=CutoffDefinition.HALF_POWER_3DB,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=TopologyId.LADDER_LP_SERIES_L_INPUT,
    )
    circuit = synthesize(spec).circuit
    sweep = SweepConfig(1e6, 1e9, 33, SweepSpacing.LOGARITHMIC)
    return analyze_circuit(circuit, sweep)


def _parse_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    lines = [
        ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    rows = [ln for ln in lines if not ln.startswith("#")]
    header = rows[0].split(",")
    return header, [r.split(",") for r in rows[1:]]


def test_export_csv_header_and_values(tmp_path: Path) -> None:
    result = _result()
    out = tmp_path / "traces.csv"
    path = export_csv(result, out, comment="hello\nworld")
    assert path == out
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# hello\n# world\n")
    header, rows = _parse_csv(out)
    assert header == list(COLUMNS)
    assert len(rows) == result.frequency_hz.shape[0]
    s21_col = header.index("s21_db")
    expected = mag_db(result.s21)[0]
    assert float(rows[0][s21_col]) == pytest.approx(expected, abs=1e-6)


def test_export_csv_custom_columns(tmp_path: Path) -> None:
    out = tmp_path / "two.csv"
    export_csv(_result(), out, columns=("frequency_hz", "s11_db"), comment="")
    header, rows = _parse_csv(out)
    assert header == ["frequency_hz", "s11_db"]
    assert all(len(r) == 2 for r in rows)


def test_export_csv_unknown_column(tmp_path: Path) -> None:
    with pytest.raises(CsvExportError):
        export_csv(_result(), tmp_path / "x.csv", columns=("nope",))
    with pytest.raises(CsvExportError):
        export_csv(_result(), tmp_path / "x.csv", columns=())


def test_export_dat(tmp_path: Path) -> None:
    result = _result()
    out = tmp_path / "trace.dat"
    export_dat(result.frequency_hz, mag_db(result.s21), out, comment="s21")
    lines = [ln for ln in out.read_text().splitlines() if not ln.startswith("#")]
    assert len(lines) == result.frequency_hz.shape[0]
    f0, v0 = lines[0].split("\t")
    assert float(f0) == pytest.approx(float(result.frequency_hz[0]))
    assert float(v0) == pytest.approx(float(mag_db(result.s21)[0]), abs=1e-6)


def test_export_dat_length_mismatch(tmp_path: Path) -> None:
    with pytest.raises(CsvExportError):
        export_dat(np.array([1.0, 2.0]), np.array([1.0]), tmp_path / "x.dat")


def test_analysis_from_touchstone_roundtrip(tmp_path: Path) -> None:
    result = _result()
    s2p = tmp_path / "ref.s2p"
    write_touchstone_s2p(result, s2p)
    data = read_touchstone(s2p)
    rebuilt = analysis_from_touchstone(data)
    assert np.allclose(rebuilt.s21, result.s21, atol=1e-9)
    assert np.allclose(rebuilt.frequency_hz, result.frequency_hz, rtol=1e-9)


def test_cli_analyze_export_csv(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "cli.csv"
    code = main(
        [
            "analyze",
            "--family",
            "butterworth",
            "--response",
            "low_pass",
            "--order",
            "3",
            "--cutoff",
            "100M",
            "--points",
            "32",
            "--export-csv",
            str(out),
        ]
    )
    capsys.readouterr()
    assert code == 0
    assert out.is_file()
    header, rows = _parse_csv(out)
    assert header == list(COLUMNS)
    assert rows


def test_cli_to_csv(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    s2p = tmp_path / "in.s2p"
    write_touchstone_s2p(_result(), s2p)
    out = tmp_path / "out.csv"
    code = main(
        ["to-csv", str(s2p), str(out), "--columns", "frequency_hz,s21_db"]
    )
    capsys.readouterr()
    assert code == 0
    header, rows = _parse_csv(out)
    assert header == ["frequency_hz", "s21_db"]
    assert rows


def test_cli_to_csv_rejects_bad_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["to-csv", str(tmp_path / "missing.s2p"), str(tmp_path / "o.csv")])
    assert code == 2
    err = capsys.readouterr().err
    assert "error:" in err
