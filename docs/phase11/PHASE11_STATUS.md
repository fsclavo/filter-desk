# Phase 11 — Packaging & Windows (status)

**Date:** 2026-10-15  
**Status:** Complete (Linux + Windows onedir; AppImage best-effort)  
**Version:** 0.5.11

## Goal

Ship self-contained desktop bundles for Linux and Windows and publish them from
GitHub Releases.

## Delivered

- **PyInstaller onedir** — `packaging/filterdesk.spec`: one `FilterDesk` launcher
  (console, GUI + CLI) plus `_internal/`. The spec collects `*.libs` shared
  objects (scipy OpenBLAS, Pillow codecs), the PySide6 `Qt/lib` + `Qt/plugins`,
  and drops host-system Qt/Shiboken binaries that would clash with the bundled
  Qt. Validated locally: `--version`, `synthesize`, `analyze --backend skrf`,
  `montecarlo`, and `gui` (offscreen) all run from the frozen bundle.
- **Release workflow** — `.github/workflows/release.yml` on tags `v*` (and
  `workflow_dispatch`):
  - `linux` (ubuntu-22.04): build → licenses → smoke → `FilterDesk-linux-x86_64.tar.gz`.
  - `windows` (windows-latest): build → licenses → smoke → `FilterDesk-windows-x86_64.zip`.
  - `appimage` (ubuntu-22.04, `continue-on-error`): best-effort AppImage.
  - `release`: publishes a GitHub Release for the tag with the tar.gz + zip.
- **AppImage** — `packaging/appimage/build_appimage.sh` (+ `.desktop` + icon).
- **glibc baseline** — built on Ubuntu 22.04 (glibc 2.35); documented.
- **Qt LGPL-3 compliance** — `packaging/NOTICE-third-party.md` +
  `packaging/collect_qt_licenses.py` (copies Qt license files and fetches the
  canonical LGPL-3.0/GPL-3.0 texts into `<bundle>/licenses/`).
- **Docs** — `docs/packaging.md`.

## Notes / open

- AppImage is best-effort (not a release blocker); the portable `tar.gz` is the
  primary Linux artifact.
- Windows bundle is built but not smoke-run on a real Windows desktop here (CI
  runs it headless with `--version`).

## Tests

Core suite unchanged (275 passed). Packaging assets are validated by:
- YAML parse of `.github/workflows/release.yml`;
- `py_compile` of `collect_qt_licenses.py`;
- `bash -n` of `build_appimage.sh`;
- a **local PyInstaller build** exercising the frozen binary (see above).
