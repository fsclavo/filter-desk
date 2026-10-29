# Packaging & releases

FilterDesk ships as a self-contained **PyInstaller onedir** bundle: a launcher
(`FilterDesk` / `FilterDesk.exe`) plus an `_internal/` folder with Python, Qt, and
the scientific stack. The launcher is **GUI-first** (double-clicking opens the
desktop app) and also serves the CLI subcommands (`synthesize`, `analyze`,
`optimize`, `montecarlo`, …) when given arguments.

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
  `Qt/plugins`, ships `pyqtgraph` as source (for the in-app SVG export patch),
  and drops any **system** Qt/Shiboken binaries that PyInstaller might resolve
  from the host (they clash with the bundled PySide6 Qt).
- `console=True` keeps the CLI usable from a terminal; on Windows a
  double-clicked launch hides the console window it was given (a terminal shared
  with `cmd.exe` is left untouched).
- **No arguments → GUI.** `filterdesk --help` prints CLI help.

## Artifacts

| Platform | Artifact | Notes |
| --- | --- | --- |
| Windows x86_64 | `FilterDesk-<ver>-windows-x86_64-setup.exe` | **installer** (NSIS): Start Menu + Desktop shortcuts to the GUI, uninstaller |
| Windows x86_64 | `FilterDesk-windows-x86_64.zip` | portable onedir bundle |
| Linux x86_64 | `FilterDesk-x86_64.AppImage` | **single-file app**; **glibc ≥ 2.35** (built on Ubuntu 22.04) |
| Linux x86_64 | `FilterDesk-linux-x86_64.tar.gz` | portable onedir bundle |
| Debian/Ubuntu amd64 | `FilterDesk-<ver>-amd64.deb` | **system package**; installs under `/opt/filterdesk` |

### Windows installer

`packaging/windows/filterdesk.nsi` (NSIS) packages `dist\FilterDesk\` into a
per-machine installer, creating Start Menu / Desktop shortcuts that launch the
GUI and registering an uninstaller in Add/Remove Programs. Built in CI with
`choco install nsis`.

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
2. `windows` job: sync → PyInstaller → licenses → smoke → `zip` → NSIS
   **installer** → upload artifacts.
3. `appimage` job (ubuntu-22.04): builds the AppImage → upload artifact.
4. `deb` job (ubuntu-22.04): builds the onedir bundle and `.deb`, then verifies
   install/self-test/removal in a clean Ubuntu 22.04 container.
5. `release` job (`needs: [linux, windows, appimage, deb]`): downloads the
   artifacts and publishes a **GitHub Release** for the tag attaching the Windows
   installer + zip, the Linux AppImage, the tar.gz and the `.deb`, with generated
   release notes.

To cut a release (bump `pyproject.toml` + `src/filterdesk/__init__.py` first):

```bash
git tag v0.29.4
git push origin v0.29.4
```

## AppImage

`packaging/appimage/build_appimage.sh` wraps the onedir bundle into an AppDir and
runs `appimagetool` (`--appimage-extract-and-run`, no FUSE needed to build). It
needs `dist/FilterDesk/` to exist first. The desktop entry and icon live in
`packaging/appimage/`. Verified locally: the produced AppImage runs `--version`
and launches the GUI.

## Debian/Ubuntu package

`packaging/debian/build_deb.sh` turns the same onedir bundle into
`FilterDesk-<ver>-amd64.deb`. It installs the payload under
`/opt/filterdesk`, adds `/usr/bin/filterdesk`, a desktop entry and the 256 px
icon, and copies the Apache-2.0 copyright plus third-party notice into
`/usr/share/doc/filterdesk/`.

Build it after the PyInstaller and license steps:

```bash
bash packaging/debian/build_deb.sh
sudo apt install ./FilterDesk-0.29.4-amd64.deb
filterdesk --self-test
sudo apt remove filterdesk
```

The package targets Ubuntu 22.04+/Debian 12+ (glibc 2.35) and depends on the
same X/GL runtime libraries as the AppImage. `packaging/debian/verify_deb.sh`
performs the clean-container check: install, desktop/launcher assertions,
headless `--self-test`, removal and leftover-file check.

## Package acceptance

Every packaged artifact supports a headless acceptance command:

```bash
QT_QPA_PLATFORM=offscreen ./FilterDesk --self-test
```

It constructs the Qt main window, synthesizes and analyzes a reference filter,
writes and re-reads a Touchstone `.s2p`, exports a BOM CSV, and round-trips a
native project in a temporary directory. The command exits non-zero on failure.

CI runs the acceptance pass on clean GitHub runners:

- **`package-acceptance-linux`** builds the onedir bundle, runs `--self-test`
  with a temporary `HOME`/XDG tree, builds the AppImage, repeats the test via
  `--appimage-extract-and-run` (no FUSE required), then builds the `.deb` and
  verifies install/self-test/removal in a clean Ubuntu 22.04 container.
- **`package-acceptance-windows`** builds the bundle, runs `--self-test`, builds
  the NSIS installer, installs it silently, checks the installed executable,
  uninstaller and desktop shortcut, runs the installed app's `--self-test`, and
  uninstalls it again.

The jobs run for `workflow_dispatch` and pushes to `main`; release tags still use
the normal `release.yml` jobs. This covers startup, GUI construction, synthesis,
Touchstone import/export and BOM export. A final visual check of the installer
shortcut and main window on a physical Windows desktop remains a manual release
step.

## CI quality gates

`.github/workflows/test.yml` runs on every push / pull request:

- **Matrix**: `ubuntu-latest` and `windows-latest` × Python `3.11` / `3.12`
  (Ruff, Mypy, Import-linter, Pytest).
- **Coverage**: `pytest-cov` (`--cov=filterdesk`, branch coverage) with a
  `--cov-fail-under=80` gate (currently ~81 %).
- **`package-smoke`**: builds the PyInstaller onedir on `ubuntu-latest` and runs
  `FilterDesk --version` plus a headless `synthesize`, so bundling breakage is
  caught before a release tag.
- **`gui-stability`** (main pushes only): repeats the GUI/worker tests 3× to
  catch nondeterministic Qt/thread failures without slowing every pull request.

Dependency upkeep:

- `.github/dependabot.yml` — weekly PRs for `uv` (pyproject/uv.lock) and
  GitHub Actions.
- `.github/workflows/security.yml` — weekly `pip-audit` (plus manual dispatch)
  against the locked environment.

CI pins the current Node 24-based action releases (`checkout@v7.0.1`,
`setup-uv@v10.3.2`, `upload-artifact@v7.0.2`, `download-artifact@v8.0.2`,
`action-gh-release@v3.0.3`); Dependabot keeps them current.
