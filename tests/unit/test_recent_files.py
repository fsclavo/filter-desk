"""Recent-project persistence and File menu integration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from filterdesk.gui.recent_files import (  # noqa: E402
    MAX_RECENT_FILES,
    add_recent,
    clear_recent,
    load_recent,
    prune_missing,
    remove_recent,
    save_recent,
)
from filterdesk.gui.settings import InMemorySettingsStore  # noqa: E402


def _touch(path: Path) -> Path:
    path.write_text("{}", encoding="utf-8")
    return path


def test_recent_add_dedupe_limit_and_remove(tmp_path: Path) -> None:
    store = InMemorySettingsStore()
    paths = [
        _touch(tmp_path / f"p{i}.filterdesk.json") for i in range(MAX_RECENT_FILES + 2)
    ]
    for path in paths:
        add_recent(path, store)
    recent = load_recent(store)
    assert len(recent) == MAX_RECENT_FILES
    assert recent[0] == str(paths[-1].resolve())
    add_recent(paths[3], store)
    recent = load_recent(store)
    assert recent[0] == str(paths[3].resolve())
    assert len(recent) == MAX_RECENT_FILES
    remove_recent(paths[3], store)
    assert str(paths[3].resolve()) not in load_recent(store)
    clear_recent(store)
    assert load_recent(store) == []


def test_recent_prune_missing_and_normalize(tmp_path: Path) -> None:
    store = InMemorySettingsStore()
    existing = _touch(tmp_path / "exists.filterdesk.json")
    missing = tmp_path / "missing.filterdesk.json"
    save_recent(
        [str(existing), str(missing), str(existing.resolve())],
        store,
    )
    assert load_recent(store) == [str(existing.resolve()), str(missing.resolve())]
    kept, dropped = prune_missing(load_recent(store), store)
    assert kept == [str(existing.resolve())]
    assert dropped == [str(missing.resolve())]
    assert load_recent(store) == kept


def test_recent_menu_updates_on_save_and_clears(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    _ = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    window = MainWindow(session, auto_run=False)
    path = tmp_path / "myfilter.filterdesk.json"
    window._write_project(path)

    labels = [action.text() for action in window._recent_menu.actions()]
    assert any(path.name in label for label in labels)
    assert str(path.resolve()) in load_recent()

    window._clear_recent_projects()
    labels = [action.text() for action in window._recent_menu.actions()]
    assert labels == ["No recent projects"]
    assert not window._recent_menu.actions()[0].isEnabled()
    window.close()


def test_recent_menu_opens_saved_project(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    _ = QApplication.instance() or QApplication([])
    session = DesignSession()
    session.synthesize_and_analyze()
    window = MainWindow(session, auto_run=False)
    path = tmp_path / "reopen.filterdesk.json"
    window._write_project(path)
    window._session.path = None
    window._open_recent_project(str(path))
    assert window._session.path == str(path.resolve())
    assert path.stem.split(".")[0] in window.windowTitle()
    window.close()


def test_recent_menu_drops_missing_files(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    _ = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    missing = tmp_path / "gone.filterdesk.json"
    add_recent(missing)
    window._refresh_recent_menu()
    assert str(missing.resolve()) not in load_recent()
    labels = [action.text() for action in window._recent_menu.actions()]
    assert labels == ["No recent projects"]
    window.close()
