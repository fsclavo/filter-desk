"""Recent-project list persisted in the application settings store."""

from __future__ import annotations

import os
from pathlib import Path

from filterdesk.gui.settings import RECENT_KEY, SettingsStore, get_settings_store

MAX_RECENT_FILES = 10


def _path_key(path: str | Path) -> str:
    return os.path.normcase(str(Path(path).expanduser().resolve()))


def normalize_recent(path: str | Path) -> str:
    """Return the stable absolute form stored in settings."""
    return str(Path(path).expanduser().resolve())


def load_recent(store: SettingsStore | None = None) -> list[str]:
    """Load the recent list, dropping empty/duplicate entries."""
    target = store or get_settings_store()
    seen: set[str] = set()
    out: list[str] = []
    for raw in target.get_list(RECENT_KEY):
        if not raw.strip():
            continue
        path = normalize_recent(raw)
        key = _path_key(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
        if len(out) >= MAX_RECENT_FILES:
            break
    return out


def save_recent(paths: list[str], store: SettingsStore | None = None) -> None:
    target = store or get_settings_store()
    target.set_list(RECENT_KEY, list(paths[:MAX_RECENT_FILES]))


def add_recent(path: str | Path, store: SettingsStore | None = None) -> list[str]:
    """Move ``path`` to the front of the recent list and persist it."""
    target = store or get_settings_store()
    new_path = normalize_recent(path)
    new_key = _path_key(new_path)
    paths = [item for item in load_recent(target) if _path_key(item) != new_key]
    paths.insert(0, new_path)
    paths = paths[:MAX_RECENT_FILES]
    save_recent(paths, target)
    return paths


def remove_recent(path: str | Path, store: SettingsStore | None = None) -> list[str]:
    target = store or get_settings_store()
    key = _path_key(path)
    paths = [item for item in load_recent(target) if _path_key(item) != key]
    save_recent(paths, target)
    return paths


def clear_recent(store: SettingsStore | None = None) -> None:
    target = store or get_settings_store()
    save_recent([], target)


def prune_missing(
    paths: list[str], store: SettingsStore | None = None
) -> tuple[list[str], list[str]]:
    """Split into existing and missing paths; optionally persist the survivors."""
    existing = [path for path in paths if Path(path).is_file()]
    missing = [path for path in paths if not Path(path).is_file()]
    if missing:
        save_recent(existing, store or get_settings_store())
    return existing, missing


__all__ = [
    "MAX_RECENT_FILES",
    "add_recent",
    "clear_recent",
    "load_recent",
    "normalize_recent",
    "prune_missing",
    "remove_recent",
    "save_recent",
]
