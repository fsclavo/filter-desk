"""Release/meta consistency checks."""

from __future__ import annotations

import tomllib
from pathlib import Path

import filterdesk

ROOT = Path(__file__).resolve().parents[2]


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_version_matches_pyproject() -> None:
    assert filterdesk.__version__ == _pyproject()["project"]["version"]


def test_console_script_points_at_main() -> None:
    scripts = _pyproject()["project"]["scripts"]
    assert scripts["filterdesk"] == "filterdesk.__main__:main"
