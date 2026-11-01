"""Built-in example projects used by the guided tutorials."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from filterdesk.domain.project import Project, project_from_mapping
from filterdesk.services.system_project import SystemProject, read_system_project


@dataclass(frozen=True, slots=True)
class BuiltinExample:
    id: str
    title: str
    title_es: str
    kind: str
    filename: str

    def __post_init__(self) -> None:
        if self.kind not in {"filter", "system"}:
            raise ValueError(f"unsupported example kind: {self.kind!r}")


BUILTIN_EXAMPLES: tuple[BuiltinExample, ...] = (
    BuiltinExample(
        "rx40m",
        "40 m receiver preselector",
        "Preselector de recepción de 40 m",
        "filter",
        "rx40m_preselector.filterdesk.json",
    ),
    BuiltinExample(
        "tx80m",
        "80 m 100 W transmitter low-pass",
        "Paso-bajo de transmisión de 80 m y 100 W",
        "filter",
        "tx80m_lpf.filterdesk.json",
    ),
    BuiltinExample(
        "diplexer2m",
        "2 m LPF + HPF diplexer",
        "Diplexer LPF + HPF de 2 m",
        "system",
        "diplexer_2m.fdsys.json",
    ),
)


def get_example(example_id: str) -> BuiltinExample:
    for example in BUILTIN_EXAMPLES:
        if example.id == example_id:
            return example
    raise KeyError(f"unknown built-in example: {example_id!r}")


def examples_dir() -> Path:
    """Return the bundled examples directory (source tree or frozen bundle)."""
    candidates = [Path(__file__).resolve().parent.parent / "assets" / "examples"]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(str(meipass)) / "filterdesk" / "assets" / "examples")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("built-in examples directory is missing")


def example_path(example: BuiltinExample) -> Path:
    path = examples_dir() / example.filename
    if not path.is_file():
        raise FileNotFoundError(f"built-in example is missing: {path}")
    return path


def load_filter_example(example: BuiltinExample) -> Project:
    if example.kind != "filter":
        raise ValueError(f"{example.id!r} is not a filter example")
    data = json.loads(example_path(example).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"example root must be a JSON object: {example.filename}")
    return project_from_mapping(data)


def load_system_example(example: BuiltinExample) -> SystemProject:
    if example.kind != "system":
        raise ValueError(f"{example.id!r} is not a system example")
    return read_system_project(example_path(example))


__all__ = [
    "BUILTIN_EXAMPLES",
    "BuiltinExample",
    "example_path",
    "examples_dir",
    "get_example",
    "load_filter_example",
    "load_system_example",
]
