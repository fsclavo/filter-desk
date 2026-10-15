"""B4.1 — Touchstone reader."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from filterdesk.io.touchstone import (
    TouchstoneError,
    parse_touchstone,
    ports_from_filename,
    read_touchstone,
    write_touchstone_s1p,
    write_touchstone_s2p,
)
from filterdesk.services.session import DesignSession


def _analyzed_session() -> DesignSession:
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.analysis is not None
    return session


def test_s2p_roundtrip(tmp_path: Path) -> None:
    session = _analyzed_session()
    result = session.analysis
    assert result is not None
    path = tmp_path / "design.s2p"
    write_touchstone_s2p(result, path)
    data = read_touchstone(path)

    assert data.n_ports == 2
    assert data.n_points == result.frequency_hz.shape[0]
    assert data.z0_ohm == pytest.approx(result.z0_source_ohm)
    np.testing.assert_allclose(data.frequency_hz, result.frequency_hz, rtol=1e-9)
    for (i, j), expected in (
        ((1, 1), result.s11),
        ((2, 1), result.s21),
        ((1, 2), result.s12),
        ((2, 2), result.s22),
    ):
        np.testing.assert_allclose(
            data.s_param(i, j), expected, rtol=1e-9, atol=1e-12
        )


def test_s1p_roundtrip(tmp_path: Path) -> None:
    session = _analyzed_session()
    result = session.analysis
    assert result is not None
    path = tmp_path / "reflect.s1p"
    write_touchstone_s1p(result, path)
    data = read_touchstone(path)
    assert data.n_ports == 1
    np.testing.assert_allclose(data.s_param(1, 1), result.s11, rtol=1e-9)
    with pytest.raises(TouchstoneError):
        data.to_analysis_result()


def test_ma_format() -> None:
    text = "# HZ S MA R 50\n1e6 0.5 90 0.1 0 0 0 0.5 -90\n"
    data = parse_touchstone(text)
    assert data.data_format == "MA"
    assert data.z0_ohm == 50.0
    np.testing.assert_allclose(data.s[0, 0, 0], 0.5j, atol=1e-12)
    np.testing.assert_allclose(data.s[0, 1, 0], 0.1 + 0j, atol=1e-12)
    np.testing.assert_allclose(data.s[0, 0, 1], 0.0 + 0j, atol=1e-12)
    np.testing.assert_allclose(data.s[0, 1, 1], -0.5j, atol=1e-12)


def test_db_format() -> None:
    text = "# HZ S DB R 50\n1e6 0 0 20 0 0 0 0 0\n"
    data = parse_touchstone(text)
    assert data.data_format == "DB"
    # 0 dB → |S| = 1; 20 dB → |S| = 10.
    np.testing.assert_allclose(data.s[0, 0, 0], 1.0 + 0j, rtol=1e-12)
    np.testing.assert_allclose(data.s[0, 1, 0], 10.0 + 0j, rtol=1e-12)


def test_wrapped_records_and_comments() -> None:
    text = (
        "! a comment\n"
        "# HZ S RI R 75\n"
        "1e6 0.1 0.2 0.3 0.4\n"
        "0.5 0.6 0.7 0.8\n"
    )
    data = parse_touchstone(text)
    assert data.n_points == 1
    assert data.z0_ohm == 75.0
    assert data.comments == ["a comment"]
    # Column order S11 S21 S12 S22.
    np.testing.assert_allclose(data.s_param(1, 1), [0.1 + 0.2j])
    np.testing.assert_allclose(data.s_param(2, 1), [0.3 + 0.4j])
    np.testing.assert_allclose(data.s_param(1, 2), [0.5 + 0.6j])
    np.testing.assert_allclose(data.s_param(2, 2), [0.7 + 0.8j])


def test_frequency_unit_scaling() -> None:
    text = "# MHZ S RI R 50\n10 1 0 0 0 0 0 0 0\n"
    data = parse_touchstone(text)
    assert data.frequency_hz[0] == pytest.approx(10e6)


def test_ports_from_filename() -> None:
    assert ports_from_filename("amp.S2P") == 2
    assert ports_from_filename("one.s1p") == 1
    assert ports_from_filename("plain.txt") is None


def test_infer_ports_from_width() -> None:
    text = "# HZ S RI R 50\n1e6 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0\n"
    data = parse_touchstone(text)  # no filename hint → infer 3 ports
    assert data.n_ports == 3


def test_to_analysis_result() -> None:
    text = "# HZ S RI R 50\n1e6 0.5 0 0.5 0 0.5 0 0.25 0\n"
    data = parse_touchstone(text)
    result = data.to_analysis_result()
    assert result.backend == "touchstone"
    zin_expected = 50.0 * (1.0 + 0.5) / (1.0 - 0.5)
    np.testing.assert_allclose(result.zin_ohm, [zin_expected], rtol=1e-12)
    np.testing.assert_allclose(result.s21, [0.5 + 0j], atol=1e-12)


def test_errors() -> None:
    with pytest.raises(TouchstoneError):
        parse_touchstone("# HZ Y RI R 50\n1e6 0 0 0 0 0 0 0 0\n")
    with pytest.raises(TouchstoneError):
        parse_touchstone("# HZ S RI R 50\n")
    with pytest.raises(TouchstoneError):
        parse_touchstone("# HZ S RI R 50\n1e6 0 0 0 0 0 0 0\n", n_ports=2)
    with pytest.raises(TouchstoneError):
        parse_touchstone("# HZ S RI R 50\n1e6 0 oops 0 0 0 0 0 0\n")


def test_session_set_measured(tmp_path: Path) -> None:
    session = _analyzed_session()
    result = session.analysis
    assert result is not None
    path = tmp_path / "m.s2p"
    write_touchstone_s2p(result, path)
    data = read_touchstone(path)
    session.set_measured(data.to_analysis_result(), "m.s2p")
    assert session.measured is not None
    assert session.measured_name == "m.s2p"
    session.set_measured(None)
    assert session.measured is None
    assert session.measured_name is None
