# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FilterDesk (onedir).

Build from the repository root:

    pyinstaller packaging/filterdesk.spec --noconfirm

Produces ``dist/FilterDesk/`` with the ``FilterDesk`` launcher (console=True so
``--version`` and the CLI subcommands work; the GUI opens from the same binary).
"""

import os
import sys
from pathlib import Path

import numpy
from PyInstaller.utils.hooks import collect_data_files

# Keep Qt from trying to initialise a real platform while PyInstaller imports
# submodules in isolated subprocesses (headless CI has no display).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 - SPECPATH injected by PyInstaller
_ICON = ROOT / "packaging" / "windows" / "filterdesk.ico"

datas = []
binaries = []
hiddenimports = ["filterdesk", "skrf", "pyqtgraph"]
# PySide6 modules imported dynamically by pyqtgraph / matplotlib backends.
hiddenimports += [
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtPrintSupport",
    "PySide6.QtXml",
]
# Data files only — do NOT collect_all()/collect_submodules(), which would import
# pyqtgraph.examples (initialises Qt and aborts the isolated collector).
datas += collect_data_files("skrf")
datas += collect_data_files("pyqtgraph")
# Bundled application icon (used by the GUI window/taskbar and About box).
datas.append((str(ROOT / "src" / "filterdesk" / "assets"), "filterdesk/assets"))

# Several wheels ship their native shared objects in sibling ``*.libs``
# directories (scipy.libs/libscipy_openblas*.so, PIL.libs/libtiff*.so, …);
# PyInstaller does not pick these up automatically, so add them explicitly at
# the bundle root.
_site = Path(numpy.__file__).resolve().parent.parent
for libs in sorted(_site.glob("*.libs")):
    for entry in sorted(libs.iterdir()):
        if entry.is_file():
            binaries.append((str(entry), "."))

# PySide6 6.12 ships the Qt shared libraries under ``PySide6/Qt/lib`` and the
# Qt plugins under ``PySide6/Qt/plugins``; recent PyInstaller hooks do not always
# copy them, so collect them explicitly.
import PySide6  # noqa: E402
import shiboken6  # noqa: E402

_pyside = Path(PySide6.__file__).resolve().parent
_qt_lib = _pyside / "Qt" / "lib"
if _qt_lib.is_dir():
    for entry in sorted(_qt_lib.iterdir()):
        if entry.is_file():
            binaries.append((str(entry), "PySide6/Qt/lib"))
_qt_plugins = _pyside / "Qt" / "plugins"
if _qt_plugins.is_dir():
    datas.append((str(_qt_plugins), "PySide6/Qt/plugins"))
for entry in sorted(_pyside.glob("libpyside6*.so*")):
    binaries.append((str(entry), "PySide6"))
_shiboken = Path(shiboken6.__file__).resolve().parent
for entry in sorted(_shiboken.glob("libshiboken6*.so*")):
    binaries.append((str(entry), "shiboken6"))

a = Analysis(  # noqa: F821
    [str(ROOT / "src" / "filterdesk" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Ship pyqtgraph as source so FilterDesk's ``inspect.getsource`` SVG patch
    # (pyqtgraph_patches) works inside the frozen bundle.
    module_collection_mode={"pyqtgraph": "py"},
    excludes=[
        "tkinter",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.Qt3DCore",
        "PySide6.QtMultimedia",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
)

# Drop any host-system Qt/ICU/Shiboken binaries that PyInstaller may have
# resolved from the OS (they mismatch the bundled PySide6 Qt and cause private
# symbol clashes). Bundled PySide6 libs keep a ``PySide6/...`` destination.
_qt_prefixes = ("libQt6", "libicu", "libpyside", "libshiboken")
a.binaries = [  # noqa: F821
    entry for entry in a.binaries if "/" in entry[0] or not entry[0].startswith(_qt_prefixes)  # noqa: F821
]

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FilterDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=str(_ICON) if sys.platform == "win32" and _ICON.is_file() else None,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FilterDesk",
)
