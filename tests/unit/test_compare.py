"""B4.2 — simulated vs measured comparison service."""

from __future__ import annotations

import numpy as np
import pytest

from filterdesk.analysis.types import AnalysisResult, SweepConfig, SweepSpacing
from filterdesk.services.compare import (
    CompareError,
    compare_results,
    measured_at_frequency,
    wrap_degrees,
)
from filterdesk.services.session import DesignSession


def _analyzed_session() -> DesignSession:
    session = DesignSession()
    session.synthesize_and_analyze()
    assert session.analysis is not None
    return session


def _copy(result: AnalysisResult) -> AnalysisResult:
    return AnalysisResult(
        frequency_hz=result.frequency_hz.copy(),
        s11=result.s11.copy(),
        s21=result.s21.copy(),
        s12=result.s12.copy(),
        s22=result.s22.copy(),
        zin_ohm=result.zin_ohm.copy(),
        zout_ohm=result.zout_ohm.copy(),
        z0_source_ohm=result.z0_source_ohm,
        z0_load_ohm=result.z0_load_ohm,
        backend=result.backend,
    )


def test_identical_results_have_zero_error() -> None:
    result = _analyzed_session().analysis
    assert result is not None
    cmp = compare_results(result, _copy(result))
    assert cmp.n_points == result.frequency_hz.shape[0]
    assert cmp.s21_db_rms_error == pytest.approx(0.0, abs=1e-9)
    assert cmp.s21_db_max_error == pytest.approx(0.0, abs=1e-9)
    assert cmp.s11_db_rms_error == pytest.approx(0.0, abs=1e-9)


def test_perturbation_reports_known_delta() -> None:
    result = _analyzed_session().analysis
    assert result is not None
    measured = _copy(result)
    # x10 in magnitude = +20 dB on S21 everywhere → error = -20 dB per point.
    measured.s21 = measured.s21 * 10.0
    cmp = compare_results(result, measured)
    assert cmp.s21_db_rms_error == pytest.approx(20.0, rel=1e-9)
    assert cmp.s21_db_max_error == pytest.approx(20.0, rel=1e-9)
    assert cmp.s11_db_max_error == pytest.approx(0.0, abs=1e-9)


def test_partial_overlap_uses_simulated_grid() -> None:
    result = _analyzed_session().analysis
    assert result is not None
    measured = _copy(result)
    # Restrict measured to the upper half of the band.
    half = result.frequency_hz.shape[0] // 2
    measured.frequency_hz = measured.frequency_hz[half:]
    measured.s11 = measured.s11[half:]
    measured.s21 = measured.s21[half:]
    measured.s12 = measured.s12[half:]
    measured.s22 = measured.s22[half:]
    measured.zin_ohm = measured.zin_ohm[half:]
    measured.zout_ohm = measured.zout_ohm[half:]

    cmp = compare_results(result, measured)
    assert cmp.f_min_hz == pytest.approx(float(result.frequency_hz[half]))
    assert cmp.f_max_hz == pytest.approx(float(result.frequency_hz[-1]))
    assert cmp.n_points == result.frequency_hz.shape[0] - half
    assert cmp.s21_db_max_error == pytest.approx(0.0, abs=1e-9)


def test_non_overlapping_raises() -> None:
    session = _analyzed_session()
    result = session.analysis
    assert result is not None
    measured = _copy(result)
    measured.frequency_hz = result.frequency_hz + 1e12
    with pytest.raises(CompareError):
        compare_results(result, measured)


def test_measured_interpolation_between_points() -> None:
    # Coarse measured grid, finer simulated grid → linear-in-log interp.
    sim_f = np.array([1e6, 10e6, 100e6], dtype=float)
    one = np.ones(3, dtype=np.complex128)
    sim = AnalysisResult(
        frequency_hz=sim_f,
        s11=np.full(3, 0.5 + 0j),
        s21=one,
        s12=one,
        s22=np.full(3, 0.5 + 0j),
        zin_ohm=one,
        zout_ohm=one,
        z0_source_ohm=50.0,
        z0_load_ohm=50.0,
    )
    mea_f = np.array([1e6, 100e6], dtype=float)
    mea = AnalysisResult(
        frequency_hz=mea_f,
        s11=np.full(2, 0.5 + 0j),
        s21=np.array([1.0, 0.1], dtype=np.complex128),
        s12=np.ones(2, dtype=np.complex128),
        s22=np.full(2, 0.5 + 0j),
        zin_ohm=np.ones(2, dtype=np.complex128),
        zout_ohm=np.ones(2, dtype=np.complex128),
        z0_source_ohm=50.0,
        z0_load_ohm=50.0,
    )
    cmp = compare_results(sim, mea)
    # At 10 MHz (log-midpoint) |S21| hits the mean of 0 dB and -20 dB.
    assert cmp.s21_db_sim[1] == pytest.approx(0.0, abs=1e-9)
    assert cmp.s21_db_mea[1] == pytest.approx(-10.0, rel=1e-9)


def test_coarse_measured_passes_through_sweep_config() -> None:
    cfg = SweepConfig(1e6, 100e6, n_points=64, spacing=SweepSpacing.LOGARITHMIC)
    assert cfg.frequencies_hz().shape[0] == 64


def test_measured_at_frequency_interpolation_and_limits() -> None:
    freq = np.array([90e6, 100e6, 110e6], dtype=float)
    s11 = np.full(3, 0.2 + 0j, dtype=np.complex128)
    s21 = np.array([1.0 + 0j, 0.5 + 0.5j, 0.0 + 1.0j], dtype=np.complex128)
    measured = AnalysisResult(
        frequency_hz=freq,
        s11=s11,
        s21=s21,
        s12=s21.copy(),
        s22=s11.copy(),
        zin_ohm=np.full(3, 50.0 + 0j),
        zout_ohm=np.full(3, 50.0 + 0j),
        z0_source_ohm=50.0,
        z0_load_ohm=50.0,
    )
    exact = measured_at_frequency(measured, 100e6)
    assert exact is not None
    assert exact.s21_db == pytest.approx(-3.0102999566, rel=1e-8)
    assert exact.s11_db == pytest.approx(-13.979400086, rel=1e-8)
    assert exact.vswr == pytest.approx(1.5, rel=1e-12)
    assert measured_at_frequency(measured, 80e6) is None
    assert measured_at_frequency(measured, 120e6) is None


def test_measured_phase_interpolation_uses_unwrapped_angle() -> None:
    freq = np.array([90e6, 110e6], dtype=float)
    s11 = np.full(2, 0.1 + 0j, dtype=np.complex128)
    s21 = np.array([np.exp(1j * np.deg2rad(170.0)), np.exp(1j * np.deg2rad(-170.0))])
    measured = AnalysisResult(
        frequency_hz=freq,
        s11=s11,
        s21=s21,
        s12=s21.copy(),
        s22=s11.copy(),
        zin_ohm=np.full(2, 50.0 + 0j),
        zout_ohm=np.full(2, 50.0 + 0j),
        z0_source_ohm=50.0,
        z0_load_ohm=50.0,
    )
    sample = measured_at_frequency(measured, float(np.sqrt(90e6 * 110e6)))
    assert sample is not None
    assert sample.phase_s21_deg == pytest.approx(180.0, abs=1e-9)


def test_wrap_degrees() -> None:
    assert wrap_degrees(0.0) == pytest.approx(0.0)
    assert wrap_degrees(181.0) == pytest.approx(-179.0)
    assert wrap_degrees(-181.0) == pytest.approx(179.0)
    assert wrap_degrees(360.0) == pytest.approx(0.0)
