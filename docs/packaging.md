# Packaging & releases

FilterDesk ships as a self-contained **PyInstaller onedir** bundle: a launcher
(`FilterDesk` / `FilterDesk.exe`) plus an `_internal/` folder with Python, Qt, and
the scientific stack. The same binary serves both the GUI (`filterdesk gui`) and
the CLI subcommands (`synthesize`, `analyze`, `optimize`, `montecarlo`, …).

## Build locally

```bash
# from the repository root, with the project environment synced
python -m pip install pyinstaller
python -m PyInstaller packaging/filterdesk.spec --noconfirm

# copy licenses next to the bundle
python packaging/collect_qt_licenses.py dist/FilterDesk

# smoke test (no display needed)
QT_QPA_PLATFORM=offscreen ./dist/FilterDesk/FilterDesk --version
```

Notes:

- The spec (`packaging/filterdesk.spec`) explicitly collects `*.libs` shared
  objects (scipy OpenBLAS, Pillow image codecs) and the PySide6 `Qt/lib` +
  `Qt/plugins`, and drops any **system** Qt/Shiboken binaries that PyInstaller
  might resolve from the host (they clash with the bundled PySide6 Qt).
- `console=True` keeps the CLI usable; the GUI opens from the same launcher.

## Artifacts

| Platform | Artifact | Notes |
| --- | --- | --- |
| Linux x86_64 | `FilterDesk-linux-x86_64.tar.gz` | onedir bundle; **glibc ≥ 2.35** (built on Ubuntu 22.04) |
| Windows x86_64 | `FilterDesk-windows-x86_64.zip` | onedir bundle |
| Linux x86_64 | `FilterDesk-x86_64.AppImage` | best-effort (`packaging/appimage/build_appimage.sh`) |

### glibc baseline

Linux bundles are built on **`ubuntu-22.04`** (glibc **2.35**). They run on
Ubuntu 22.04+ and equivalent distributions. Older glibc hosts are not supported.

## Licenses (Qt LGPL-3.0)

FilterDesk is Apache-2.0. It dynamically links **Qt via PySide6 (LGPL-3.0)**.

`packaging/collect_qt_licenses.py` copies any Qt license files found in the
environment and fetches the canonical **LGPL-3.0** and **GPL-3.0** texts from the
FSF into `<bundle>/licenses/`, and copies `NOTICE-third-party.md` next to the
executable. The NOTICE states the LGPL obligations and the written offer for Qt
source. Because Qt is dynamically linked and left replaceable, distributing under
LGPL-3.0 is compliant.

## Releases (GitHub Actions)

`.github/workflows/release.yml` runs on **tags `v*`** (and `workflow_dispatch`):

1. `linux` job (ubuntu-22.04): sync → PyInstaller → licenses → smoke →
   `tar.gz` → upload artifact.
2. `windows` job: sync → PyInstaller → licenses → smoke → `zip` → upload.
3. `appimage` job (ubuntu-22.04, `continue-on-error`): builds the AppImage.
4. `release` job: downloads the artifacts and publishes a **GitHub Release** for
   the tag with the `tar.gz` and `zip` attached and generated release notes.

To cut a release:

```bash
git tag v0.6.0
git push origin v0.6.0
```

Bump the version in `pyproject.toml` and `src/filterdesk/__init__.py` first.

## AppImage (best-effort)

`packaging/appimage/build_appimage.sh` wraps the onedir bundle into an AppDir and
runs `appimagetool`. It needs `dist/FilterDesk/` to exist first. The desktop entry
and icon live in `packaging/appimage/`.
