"""GUI translation catalogue and language switching."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from filterdesk.domain.enums import (
    ApproximationFamily,
    ElementRole,
    FilterResponse,
    TopologyId,
)
from filterdesk.gui.i18n import (
    _ES,
    Language,
    family_label,
    response_label,
    role_label,
    set_language,
    topology_label,
    tr,
)

GUI_ROOT = Path(__file__).resolve().parents[2] / "src" / "filterdesk" / "gui"


@pytest.fixture(autouse=True)
def _english() -> object:
    set_language(Language.EN)
    yield None
    set_language(Language.EN)


def _used_keys() -> set[str]:
    keys: set[str] = set()
    for path in GUI_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name != "tr" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                keys.add(first.value)
    return keys


def test_catalog_covers_used_keys() -> None:
    missing = sorted(key for key in _used_keys() if key not in _ES)
    assert not missing, f"missing Spanish translations: {missing}"


def test_catalog_values_nonempty() -> None:
    assert all(value.strip() for value in _ES.values())


def test_tr_switch_and_fallback() -> None:
    assert tr("Family") == "Family"
    set_language(Language.ES)
    assert tr("Family") == "Familia"
    assert tr("Not a real key") == "Not a real key"
    assert tr("Saved {path}", path="/tmp/x") == "Guardado en /tmp/x"


def test_enum_labels_have_spanish() -> None:
    set_language(Language.ES)
    assert family_label(ApproximationFamily.ELLIPTIC) == "Elíptico"
    assert response_label(FilterResponse.HIGH_PASS) == "Paso alto"
    assert topology_label(TopologyId.LADDER_LP_SERIES_L_INPUT) == "Entrada L serie"
    assert role_label(ElementRole.SHUNT) == "paralelo"
