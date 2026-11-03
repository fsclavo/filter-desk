"""Bundled example component-library JSON with manufacturer curves."""

from __future__ import annotations

import json
from pathlib import Path

from filterdesk.__main__ import main
from filterdesk.components_std import read_component_library


def _example() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "component_library_models.json"
    )


def test_example_library_has_real_q_curves() -> None:
    parts = read_component_library(_example())
    assert len(parts) == 10
    inductors = [part for part in parts if part.kind == "inductor"]
    assert len(inductors) == 5
    assert all(part.model is not None for part in inductors)
    for part in inductors:
        assert part.model is not None
        assert part.model.q_points
        frequencies = [point.frequency_hz for point in part.model.q_points]
        assert frequencies == sorted(frequencies)
        assert part.model.confidence == "datasheet"
        assert "coilcraft" in part.model.source.lower()
    capacitors = [part for part in parts if part.kind == "capacitor"]
    assert capacitors
    assert all(part.model is None for part in capacitors)


def test_example_library_cli_json(capsys) -> None:
    assert (
        main(
            [
                "components",
                "--library",
                str(_example()),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 10
    modelled = [part for part in payload["parts"] if part["model"] is not None]
    assert len(modelled) == 5
    assert modelled[0]["model"]["q_points"]
