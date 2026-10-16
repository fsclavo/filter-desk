# Phase 11 — Packaging & Windows (status)

**Date:** 2026-10-15  
**Status:** Complete (Linux + Windows onedir; AppImage; Windows installer)  
**Version:** 0.6.4

## Goal

Ship self-contained desktop bundles for Linux and Windows and publish them from
GitHub Releases.

## Delivered

- **PyInstaller onedir** — `packaging/filterdesk.spec`: one `FilterDesk` launcher
  (console, GUI + CLI) plus `_internal/`. The launcher is **GUI-first** (no args →
  GUI; a Windows double-click hides the owned console). The spec collects `*.libs`
  shared objects (scipy OpenBLAS, Pillow codecs), the PySide6 `Qt/lib` +
  `Qt/plugins`, ships `pyqtgraph` as source (for the in-app SVG export patch), and
  drops host-system Qt/Shiboken binaries that would clash with the bundled Qt.
  Validated locally: `--version`, `synthesize`, `analyze --backend skrf`,
  `montecarlo`, no-args GUI, and the AppImage — all run from the frozen bundle.
- **Release workflow** — `.github/workflows/release.yml` on tags `v*` (and
  `workflow_dispatch`):
  - `linux` (ubuntu-22.04): build → licenses → smoke → `FilterDesk-linux-x86_64.tar.gz`.
  - `windows` (windows-latest): build → licenses → smoke → zip → **NSIS installer**
    `FilterDesk-<ver>-windows-x86_64-setup.exe` (Start Menu/Desktop shortcuts).
  - `appimage` (ubuntu-22.04): AppImage `FilterDesk-x86_64.AppImage`.
  - `release`: publishes a GitHub Release for the tag with all four artifacts.
- **AppImage** — `packaging/appimage/build_appimage.sh` (+ `.desktop` + icon).
- **Windows installer** — `packaging/windows/filterdesk.nsi` (NSIS, built with
  `choco install nsis`).
- **glibc baseline** — built on Ubuntu 22.04 (glibc 2.35); documented.
- **Qt LGPL-3 compliance** — `packaging/NOTICE-third-party.md` +
  `packaging/collect_qt_licenses.py` (copies Qt license files and fetches the
  canonical LGPL-3.0/GPL-3.0 texts into `<bundle>/licenses/`).
- **Docs** — `docs/packaging.md`.

## Notes / open

- The AppImage is built and attached to releases and validated locally; the
  portable `tar.gz` remains available for non-FUSE environments.
- The Windows installer/bundle is built in CI; it is smoke-run headless with
  `--version` (a real desktop double-click check is manual).

## Tests

Core suite unchanged (275 passed). Packaging assets are validated by:
- YAML parse of `.github/workflows/release.yml`;
- `py_compile` of `collect_qt_licenses.py`;
- `bash -n` of `build_appimage.sh`;
- a **local PyInstaller build** exercising the frozen binary (see above).
