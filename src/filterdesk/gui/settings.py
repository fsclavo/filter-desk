"""Application settings with an injectable backend (QSettings by default).

Tests swap in :class:`InMemorySettingsStore` so they never touch the user's real
configuration. Keys are listed as module constants to avoid typo drift.
"""

from __future__ import annotations

from typing import Any, Protocol

from PySide6.QtCore import QByteArray, QSettings

THEME_KEY = "appearance/theme"
LANGUAGE_KEY = "appearance/language"
RECENT_KEY = "files/recent"
GEOMETRY_KEY = "window/geometry"
STATE_KEY = "window/state"


class SettingsStore(Protocol):
    """Minimal key/value store used by the GUI."""

    def get_str(self, key: str, default: str = "") -> str: ...
    def set_str(self, key: str, value: str) -> None: ...
    def get_bool(self, key: str, default: bool = False) -> bool: ...
    def set_bool(self, key: str, value: bool) -> None: ...
    def get_int(self, key: str, default: int = 0) -> int: ...
    def set_int(self, key: str, value: int) -> None: ...
    def get_list(self, key: str) -> list[str]: ...
    def set_list(self, key: str, values: list[str]) -> None: ...
    def get_bytes(self, key: str) -> bytes | None: ...
    def set_bytes(self, key: str, value: bytes) -> None: ...


class QSettingsStore:
    """``QSettings``-backed store (organisation/application set by the app)."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings()

    def get_str(self, key: str, default: str = "") -> str:
        value = self._settings.value(key, default)
        return default if value is None else str(value)

    def set_str(self, key: str, value: str) -> None:
        self._settings.setValue(key, value)

    def get_bool(self, key: str, default: bool = False) -> bool:
        return bool(self._settings.value(key, default, type=bool))

    def set_bool(self, key: str, value: bool) -> None:
        self._settings.setValue(key, value)

    def get_int(self, key: str, default: int = 0) -> int:
        value: Any = self._settings.value(key, default, type=int)
        return int(value)

    def set_int(self, key: str, value: int) -> None:
        self._settings.setValue(key, value)

    def get_list(self, key: str) -> list[str]:
        value: Any = self._settings.value(key, [])
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]

    def set_list(self, key: str, values: list[str]) -> None:
        self._settings.setValue(key, list(values))

    def get_bytes(self, key: str) -> bytes | None:
        value: Any = self._settings.value(key)
        if value is None:
            return None
        if isinstance(value, QByteArray):
            return bytes(value.data())
        if isinstance(value, (bytes, bytearray)):
            return bytes(value)
        return None

    def set_bytes(self, key: str, value: bytes) -> None:
        self._settings.setValue(key, value)


class InMemorySettingsStore:
    """Simple dict-backed store for tests."""

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self.data: dict[str, Any] = dict(initial or {})

    def get_str(self, key: str, default: str = "") -> str:
        value = self.data.get(key, default)
        return default if value is None else str(value)

    def set_str(self, key: str, value: str) -> None:
        self.data[key] = value

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.data.get(key, default)
        return default if value is None else bool(value)

    def set_bool(self, key: str, value: bool) -> None:
        self.data[key] = value

    def get_int(self, key: str, default: int = 0) -> int:
        value = self.data.get(key, default)
        return default if value is None else int(value)

    def set_int(self, key: str, value: int) -> None:
        self.data[key] = int(value)

    def get_list(self, key: str) -> list[str]:
        value = self.data.get(key, [])
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value] if value is not None else []

    def set_list(self, key: str, values: list[str]) -> None:
        self.data[key] = list(values)

    def get_bytes(self, key: str) -> bytes | None:
        value = self.data.get(key)
        return None if value is None else bytes(value)

    def set_bytes(self, key: str, value: bytes) -> None:
        self.data[key] = bytes(value)


_store: SettingsStore | None = None


def get_settings_store() -> SettingsStore:
    """Return the active settings store (lazily a ``QSettingsStore``)."""
    global _store
    if _store is None:
        _store = QSettingsStore()
    return _store


def set_settings_store(store: SettingsStore | None) -> None:
    """Replace the active store (``None`` restores the QSettings default)."""
    global _store
    _store = store


__all__ = [
    "GEOMETRY_KEY",
    "LANGUAGE_KEY",
    "RECENT_KEY",
    "STATE_KEY",
    "THEME_KEY",
    "InMemorySettingsStore",
    "QSettingsStore",
    "SettingsStore",
    "get_settings_store",
    "set_settings_store",
]
