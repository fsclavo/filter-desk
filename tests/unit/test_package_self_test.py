"""Packaged-artifact self-test."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def test_package_self_test_passes_in_tree() -> None:
    from filterdesk.package_self_test import run_package_self_test

    assert run_package_self_test(quiet=True) == 0
