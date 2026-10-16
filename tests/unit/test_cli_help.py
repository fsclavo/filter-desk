"""CLI surface smoke: every subcommand answers --help."""

from __future__ import annotations

import pytest

from filterdesk.__main__ import main

COMMANDS = [
    "synthesize",
    "analyze",
    "snap",
    "montecarlo",
    "optimize",
    "to-csv",
    "estimate-order",
    "touchstone-info",
    "compare",
    "bands",
    "attenuator",
    "match",
    "gui",
]


@pytest.mark.parametrize("command", COMMANDS)
def test_subcommand_help(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main([command, "--help"])
    assert exc.value.code == 0
    assert "usage:" in capsys.readouterr().out


def test_top_level_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for command in COMMANDS:
        assert command in out


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "filterdesk" in capsys.readouterr().out
