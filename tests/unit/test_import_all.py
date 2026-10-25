"""Import every submodule to catch import-time errors / cycles."""

from __future__ import annotations

import importlib
import pkgutil

import filterdesk


def test_all_modules_import() -> None:
    failures: list[str] = []

    def _record(name: str) -> None:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: {exc!r}")

    for module in pkgutil.walk_packages(
        filterdesk.__path__, prefix=f"{filterdesk.__name__}."
    ):
        _record(module.name)

    assert not failures, "modules failed to import:\n" + "\n".join(failures)
