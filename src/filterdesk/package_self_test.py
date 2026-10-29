"""Headless acceptance test for packaged FilterDesk artifacts.

The frozen bundle cannot rely on pytest.  This routine exercises the same
high-value paths a release checker uses: Qt/GUI construction, synthesis and
analysis, Touchstone round-trip, BOM export and native project round-trip.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def run_package_self_test(*, quiet: bool = False) -> int:
    """Run the packaged-artifact smoke test. Return a process exit code."""
    try:
        from PySide6.QtWidgets import QApplication

        from filterdesk.gui.main_window import MainWindow
        from filterdesk.io.build_sheet import write_build_sheet
        from filterdesk.io.native import load_project, save_project
        from filterdesk.io.touchstone import read_touchstone, write_touchstone_s2p
        from filterdesk.services.session import DesignSession

        app = QApplication.instance() or QApplication([])
        session = DesignSession()
        result = session.synthesize_and_analyze()
        assert session.circuit is not None
        assert result.frequency_hz.size > 1

        window = MainWindow(session, auto_run=False)
        window.show()
        app.processEvents()
        window._session.dirty = False
        window.close()
        app.processEvents()

        with TemporaryDirectory(prefix="filterdesk-selftest-") as tmp:
            root = Path(tmp)
            s2p_path = root / "response.s2p"
            write_touchstone_s2p(result, s2p_path, comment="package self-test")
            measured = read_touchstone(s2p_path)
            round_trip = measured.to_analysis_result()
            assert round_trip.frequency_hz.size == result.frequency_hz.size

            bom_path = write_build_sheet(
                session.circuit,
                root / "bom.csv",
                spec=session.spec,
            )
            assert bom_path.stat().st_size > 0

            project_path = root / "selftest.filterdesk.json"
            save_project(session.to_project(), project_path)
            loaded = load_project(project_path)
            assert loaded.specification is not None
            assert loaded.circuit is not None

        if not quiet:
            print("package self-test: OK")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"package self-test failed: {exc}", file=sys.stderr)
        return 1


__all__ = ["run_package_self_test"]
