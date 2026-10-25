"""Design parameter sweeps."""

from __future__ import annotations

import json

import pytest

from filterdesk.__main__ import main
from filterdesk.domain.enums import (
    ApproximationFamily,
    FilterResponse,
)
from filterdesk.domain.specs import (
    FilterSpec,
    default_cutoff_definition,
    default_topology,
)
from filterdesk.services.design_sweep import (
    DesignSweepConfig,
    DesignSweepError,
    SweepAxis,
    default_bands,
    default_sweep,
    parse_values,
    run_design_sweep,
)


def _spec(
    *,
    family: ApproximationFamily = ApproximationFamily.CHEBYSHEV_TYPE_I,
    response: FilterResponse = FilterResponse.LOW_PASS,
    order: int = 3,
    cutoff_hz: float = 100e6,
    ripple: float | None = 0.1,
    stop_att: float | None = None,
) -> FilterSpec:
    return FilterSpec(
        family=family,
        response=response,
        order=order,
        cutoff_hz=cutoff_hz,
        cutoff_definition=default_cutoff_definition(family),
        passband_ripple_db=ripple,
        stopband_attenuation_db=stop_att,
        z_source_ohm=50.0,
        z_load_ohm=50.0,
        topology_id=default_topology(response),
    )


def _config(
    base: FilterSpec,
    axis: SweepAxis,
    values: tuple[float | str, ...],
    points: int = 128,
) -> DesignSweepConfig:
    return DesignSweepConfig(base_spec=base, axis=axis, values=values, points=points)


def test_order_sweep_component_count_and_attenuation() -> None:
    rows = run_design_sweep(_config(_spec(), SweepAxis.ORDER, (3, 5, 7)))
    assert all(row.ok for row in rows)
    assert [row.n_components for row in rows] == [3, 5, 7]
    attenuations = [
        row.metrics.stopband_attenuation_db for row in rows if row.metrics
    ]
    assert attenuations == sorted(attenuations)
    assert all(row.metrics is not None for row in rows)


def test_even_order_chebyshev_has_note() -> None:
    rows = run_design_sweep(_config(_spec(), SweepAxis.ORDER, (3, 4)))
    assert rows[1].ok is True
    assert rows[1].note is not None
    assert "Even-order" in rows[1].note


def test_even_order_elliptic_is_flagged() -> None:
    base = _spec(
        family=ApproximationFamily.ELLIPTIC,
        order=3,
        ripple=0.1,
        stop_att=40.0,
    )
    rows = run_design_sweep(_config(base, SweepAxis.ORDER, (3, 4, 5)))
    assert rows[0].ok and rows[2].ok
    assert rows[1].ok is False
    assert "even-order" in (rows[1].error or "")


def test_family_sweep_normalises_fields() -> None:
    base = _spec(order=5, ripple=0.1)
    rows = run_design_sweep(
        _config(
            base,
            SweepAxis.FAMILY,
            (
                "butterworth",
                "chebyshev_type_i",
                "bessel",
                "elliptic",
            ),
        )
    )
    assert all(row.ok for row in rows)
    specs = [row.spec for row in rows if row.spec is not None]
    assert [spec.family.value for spec in specs] == [
        "butterworth",
        "chebyshev_type_i",
        "bessel",
        "elliptic",
    ]
    assert specs[0].passband_ripple_db is None
    assert specs[0].stopband_attenuation_db is None


def test_default_bands_lowpass_and_highpass() -> None:
    low = _spec()
    passband, stopband = default_bands(low)
    assert passband == (low.cutoff_hz / 20.0, low.cutoff_hz)
    assert stopband == (low.cutoff_hz * 2.0, low.cutoff_hz * 20.0)

    high = _spec(response=FilterResponse.HIGH_PASS)
    passband, stopband = default_bands(high)
    assert passband[0] == high.cutoff_hz
    assert stopband[1] == high.cutoff_hz / 2.0


def test_default_sweep_spans_the_band() -> None:
    sweep = default_sweep(_spec(), 64)
    assert sweep.f_start_hz < sweep.f_stop_hz
    assert sweep.n_points == 64


def test_parse_values_respects_axis() -> None:
    assert parse_values(SweepAxis.ORDER, "3, 5,7") == (3, 5, 7)
    assert parse_values(SweepAxis.FAMILY, "butterworth, bessel") == (
        "butterworth",
        "bessel",
    )
    assert parse_values(SweepAxis.CUTOFF, "100M,150M") == (100e6, 150e6)
    assert parse_values(SweepAxis.RIPPLE, "0.1,0.5") == (0.1, 0.5)
    with pytest.raises(DesignSweepError):
        parse_values(SweepAxis.ORDER, "  ")


def test_sweep_validation() -> None:
    with pytest.raises(DesignSweepError):
        run_design_sweep(_config(_spec(), SweepAxis.ORDER, ()))
    with pytest.raises(DesignSweepError):
        run_design_sweep(_config(_spec(), SweepAxis.ORDER, (3,), points=1))


def test_cli_sweep(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "sweep",
            "--axis",
            "order",
            "--values",
            "3,5",
            "--family",
            "chebyshev_type_i",
            "--response",
            "low_pass",
            "--order",
            "3",
            "--cutoff",
            "100M",
            "--ripple",
            "0.1",
            "--points",
            "64",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Design sweep" in out
    assert "yes" in out


def test_cli_sweep_json_and_csv(
    capsys: pytest.CaptureFixture[str], tmp_path
) -> None:
    out = tmp_path / "sweep.csv"
    code = main(
        [
            "sweep",
            "--axis",
            "order",
            "--values",
            "3,5",
            "--family",
            "chebyshev_type_i",
            "--response",
            "low_pass",
            "--order",
            "3",
            "--cutoff",
            "100M",
            "--ripple",
            "0.1",
            "--points",
            "64",
            "--csv",
            str(out),
            "--json",
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["axis"] == "order"
    assert len(payload["rows"]) == 2
    assert out.is_file()
    header = out.read_text(encoding="utf-8").splitlines()[0]
    assert header.startswith("value,ok,error,n_components")


def test_cli_sweep_invalid_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "sweep",
            "--axis",
            "order",
            "--values",
            "abc",
            "--family",
            "butterworth",
            "--response",
            "low_pass",
            "--order",
            "3",
            "--cutoff",
            "100M",
        ]
    )
    assert code == 2
    assert "error:" in capsys.readouterr().err
