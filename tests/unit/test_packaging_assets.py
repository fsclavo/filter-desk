"""Packaging / CI asset integrity (no build required)."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_pyinstaller_spec_parses() -> None:
    src = (ROOT / "packaging" / "filterdesk.spec").read_text(encoding="utf-8")
    ast.parse(src)  # syntactically valid Python spec
    assert "FilterDesk" in src


def test_workflows_present_and_structured() -> None:
    for name in ("test.yml", "release.yml"):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "jobs:" in text and "runs-on:" in text


def test_release_workflow_builds_all_artifacts() -> None:
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    for token in ("linux", "windows", "appimage", "release"):
        assert token in text
    assert "softprops/action-gh-release" in text


def test_nsis_installer_script() -> None:
    text = (ROOT / "packaging" / "windows" / "filterdesk.nsi").read_text("utf-8")
    assert "OutFile" in text and "Section" in text and "CreateShortcut" in text


def test_appimage_assets() -> None:
    appimage = ROOT / "packaging" / "appimage"
    assert (appimage / "build_appimage.sh").is_file()
    assert (appimage / "filterdesk.desktop").is_file()
    assert (appimage / "filterdesk.png").stat().st_size > 0


def test_license_collector_present() -> None:
    script = (ROOT / "packaging" / "collect_qt_licenses.py").read_text("utf-8")
    ast.parse(script)
    assert (ROOT / "packaging" / "NOTICE-third-party.md").is_file()
