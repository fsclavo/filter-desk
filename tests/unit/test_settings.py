"""Application settings stores."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from filterdesk.gui.settings import (
    InMemorySettingsStore,
    QSettingsStore,
    get_settings_store,
    set_settings_store,
)


def test_in_memory_roundtrip() -> None:
    store = InMemorySettingsStore()
    assert store.get_str("missing", "dv") == "dv"
    assert store.get_int("missing", 7) == 7
    assert store.get_bool("missing", True) is True
    assert store.get_list("missing") == []
    assert store.get_bytes("missing") is None

    store.set_str("s", "hola")
    store.set_int("i", 42)
    store.set_bool("b", True)
    store.set_list("l", ["a", "b"])
    store.set_bytes("x", b"\x00\x01\x02")

    assert store.get_str("s") == "hola"
    assert store.get_int("i") == 42
    assert store.get_bool("b") is True
    assert store.get_list("l") == ["a", "b"]
    assert store.get_bytes("x") == b"\x00\x01\x02"


def test_in_memory_list_from_scalar() -> None:
    store = InMemorySettingsStore({"k": "one"})
    assert store.get_list("k") == ["one"]


def test_qsettings_store_roundtrip(tmp_path: Path) -> None:
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    store = QSettingsStore(settings)
    store.set_str("s", "hola")
    store.set_int("i", 42)
    store.set_bool("b", True)
    store.set_list("l", ["a", "b"])
    store.set_bytes("x", b"\x00\x01\x02")
    settings.sync()

    assert store.get_str("s") == "hola"
    assert store.get_int("i") == 42
    assert store.get_bool("b") is True
    assert store.get_list("l") == ["a", "b"]
    assert store.get_bytes("x") == b"\x00\x01\x02"
    assert store.get_str("missing", "dv") == "dv"


def test_active_store_is_replaceable() -> None:
    original = get_settings_store()
    try:
        fake = InMemorySettingsStore()
        set_settings_store(fake)
        assert get_settings_store() is fake
    finally:
        set_settings_store(original)
