"""Amateur band presets (Phase 12)."""

from __future__ import annotations

import pytest

from filterdesk.__main__ import main
from filterdesk.domain.enums import ApproximationFamily, FilterResponse
from filterdesk.services.bands import (
    BANDS,
    BandKind,
    band_preset_spec,
    band_sweep,
    find_band,
)


def test_find_band_variants() -> None:
    band = find_band("40m")
    assert band.name == "40 m"
    assert find_band("40").name == "40 m"
    assert find_band("40 m").name == "40 m"
    assert find_band("20M").name == "20 m"
    with pytest.raises(KeyError):
        find_band("11m")


def test_lpf_preset() -> None:
    band = find_band("40m")
    spec = band_preset_spec(band, BandKind.LPF)
    assert spec.family == ApproximationFamily.CHEBYSHEV_TYPE_I
    assert spec.response == FilterResponse.LOW_PASS
    assert spec.cutoff_hz == pytest.approx(band.high_hz * 1.1)
    assert spec.passband_ripple_db == pytest.approx(0.1)


def test_hpf_and_bpf_presets() -> None:
    band = find_band("20m")
    hp = band_preset_spec(band, BandKind.HPF)
    assert hp.response == FilterResponse.HIGH_PASS
    assert hp.cutoff_hz == pytest.approx(band.low_hz * 0.9)

    bp = band_preset_spec(band, BandKind.BPF)
    assert bp.response == FilterResponse.BAND_PASS
    assert bp.f_center_hz == pytest.approx(band.center_hz)
    assert bp.bandwidth_hz == pytest.approx((band.high_hz - band.low_hz) * 1.5)


def test_band_sweep_covers_third_harmonic() -> None:
    band = find_band("10m")
    sweep = band_sweep(band)
    assert sweep.f_stop_hz >= band.high_hz * 3.0
    assert sweep.f_start_hz <= band.low_hz


def test_cli_bands_lists(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["bands"]) == 0
    out = capsys.readouterr().out
    assert "40 m" in out and "20 m" in out


def test_cli_synthesize_band(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["synthesize", "--band", "40m"]) == 0
    assert "chebyshev_type_i" in capsys.readouterr().out


def test_cli_band_kind_bpf(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["synthesize", "--band", "20m", "--band-kind", "bpf", "--json"]
    )
    assert code == 0
    import json

    payload = json.loads(capsys.readouterr().out)
    assert payload["spec"]["response"] == "band_pass"


def test_cli_invalid_band(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["synthesize", "--band", "11m"]) == 2
    assert "error:" in capsys.readouterr().err


def test_bands_table_sane() -> None:
    assert len(BANDS) >= 10
    for band in BANDS:
        assert 0.0 < band.low_hz < band.high_hz
