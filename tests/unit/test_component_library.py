"""Curated component catalog and JSON round-trip."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from filterdesk.__main__ import main
from filterdesk.components_std import (
    STARTER_PARTS,
    ComponentLibraryError,
    LibraryPart,
    library_from_mapping,
    library_to_mapping,
    nearest_part,
    read_component_library,
    search_parts,
    write_component_library,
)


def test_starter_catalog_has_real_capacitors_and_inductors() -> None:
    assert len(STARTER_PARTS) >= 10
    caps = search_parts(STARTER_PARTS, kind="capacitor")
    inds = search_parts(STARTER_PARTS, kind="inductor")
    assert caps and inds
    assert any(part.mpn == "GRM1885C1H101JA01D" for part in caps)
    assert any(part.mpn == "0603CS-10NXJRW" for part in inds)
    assert all(part.source.startswith("https://") for part in STARTER_PARTS)


def test_search_and_nearest() -> None:
    result = search_parts(STARTER_PARTS, kind="capacitor", query="100pF")
    assert [part.value_si for part in result] == [100e-12]
    assert search_parts(STARTER_PARTS, query="coilcraft")
    nearest = nearest_part(STARTER_PARTS, kind="inductor", value_si=24e-9)
    assert nearest is not None
    assert nearest.value_si == pytest.approx(22e-9)


def test_library_json_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "components.json"
    assert write_component_library(STARTER_PARTS, path) == path
    loaded = read_component_library(path)
    assert loaded == STARTER_PARTS
    assert library_from_mapping(library_to_mapping(STARTER_PARTS)) == STARTER_PARTS


def test_library_validation(tmp_path: Path) -> None:
    with pytest.raises(ComponentLibraryError, match="format"):
        library_from_mapping({"format": "wrong", "version": 1})
    with pytest.raises(ComponentLibraryError, match="parts"):
        library_from_mapping({"format": "filterdesk.components", "version": 1})
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"format": "filterdesk.components", "version": 1}))
    with pytest.raises(ComponentLibraryError, match="parts"):
        read_component_library(bad)
    with pytest.raises(ComponentLibraryError, match="kind"):
        LibraryPart("x", "M", "MPN", "resistor", 1.0, "Ohm", "0603")


def test_cli_components_list_search_and_export(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["components", "--kind", "capacitor", "--search", "100pF", "--json"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["parts"][0]["mpn"] == "GRM1885C1H101JA01D"
    export = tmp_path / "library.json"
    assert main(["components", "--export", str(export), "--json"]) == 0
    capsys.readouterr()
    assert export.is_file()
    assert read_component_library(export) == STARTER_PARTS


def test_cli_component_curve_import(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    library = tmp_path / "components.json"
    write_component_library(STARTER_PARTS, library)
    curve = tmp_path / "q_curve.csv"
    curve.write_text("1M,100\n10M,50\n", encoding="utf-8")
    output = tmp_path / "updated.json"
    code = main(
        [
            "component-curve",
            "--library",
            str(library),
            "--part",
            "0603CS-10NXJRW",
            "--curve",
            "q",
            "--csv",
            str(curve),
            "--output",
            str(output),
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["part"] == "0603CS-10NXJRW"
    assert payload["curve"] == "q"
    assert payload["points"] == 2
    loaded = read_component_library(output)
    part = next(item for item in loaded if item.mpn == "0603CS-10NXJRW")
    assert part.model is not None
    assert len(part.model.q_points) == 2
    assert part.model.q_points[0].frequency_hz == pytest.approx(1e6)


def test_starter_0603cs_q_curves_match_datasheet() -> None:
    inductors = [
        part
        for part in STARTER_PARTS
        if part.mpn.startswith("0603CS-")
    ]
    assert len(inductors) == 18
    assert all(part.model is not None for part in inductors)
    assert all(
        part.model is not None and "0603cs.pdf" in part.model.source.lower()
        for part in inductors
    )

    part = next(item for item in inductors if item.mpn == "0603CS-33NXJRW")
    assert part.model is not None
    assert [point.frequency_hz for point in part.model.q_points] == [
        250e6,
        900e6,
        1.7e9,
    ]
    assert [point.value for point in part.model.q_points] == [40.0, 67.0, 42.0]
