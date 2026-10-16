#!/usr/bin/env python3
"""Copy third-party license texts next to a PyInstaller bundle (Phase 11).

Usage::

    python packaging/collect_qt_licenses.py dist/FilterDesk

Collects Qt/PySide6 license files (LGPL-3.0 etc.) into ``<dest>/licenses`` and
copies ``packaging/NOTICE-third-party.md`` into ``<dest>``. Missing sources are
skipped with a warning so the build never hard-fails on license-path drift.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent

_LGPL_URL = "https://www.gnu.org/licenses/lgpl-3.0.txt"
_GPL_URL = "https://www.gnu.org/licenses/gpl-3.0.txt"


def _candidate_dirs() -> list[Path]:
    candidates: list[Path] = []
    spec = importlib.util.find_spec("PySide6")
    if spec is not None and spec.origin is not None:
        pkg = Path(spec.origin).parent
        candidates += [
            pkg / "Qt" / "LICENSES",
            pkg / "LICENSES",
            pkg / "Qt" / "lib" / "LICENSES",
        ]
    prefix = Path(sys.prefix)
    candidates += [
        prefix / "lib" / "python3.12" / "site-packages" / "PySide6" / "Qt" / "LICENSES",
    ]
    # dist-info license files, if present
    site = prefix / "lib" / "python3.12" / "site-packages"
    for dist in site.glob("pyside6*.dist-info"):
        candidates += [dist / "licenses", dist / "LICENSES"]
    return candidates


def _download(url: str, dest: Path) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=20) as response:  # noqa: S310
            dest.write_bytes(response.read())
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"warning: could not fetch {url}: {exc}", file=sys.stderr)
        return False


def main(argv: list[str]) -> int:
    dest = Path(argv[1]) if len(argv) > 1 else Path("dist/FilterDesk")
    dest.mkdir(parents=True, exist_ok=True)
    licenses_dir = dest / "licenses"
    licenses_dir.mkdir(exist_ok=True)

    copied = 0
    for directory in _candidate_dirs():
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                shutil.copy2(path, licenses_dir / path.name)
                copied += 1

    # The PySide6 wheels often ship no license text; fetch the LGPL-3.0 (and its
    # GPL-3.0 base) from the FSF as the canonical text. Best-effort.
    if not any(licenses_dir.iterdir()) or not (licenses_dir / "LGPL-3.0.txt").exists():
        _download(_LGPL_URL, licenses_dir / "LGPL-3.0.txt")
        _download(_GPL_URL, licenses_dir / "GPL-3.0.txt")

    notice = _HERE / "NOTICE-third-party.md"
    if notice.is_file():
        shutil.copy2(notice, dest / "NOTICE-third-party.md")

    if copied == 0:
        print("note: bundled Qt license files not found; fetched LGPL/GPL texts", file=sys.stderr)
    else:
        print(f"copied {copied} license file(s) to {licenses_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
