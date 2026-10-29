"""Plot-state regression matrix across every GUI preset combination."""

from __future__ import annotations

import math

import pytest

from filterdesk.services.bands import (
    ALL_PRESETS,
    REJECTION_PRESETS,
    BandKind,
    band_preset_spec,
    band_sweep,
)


def _combinations() -> list[tuple[object, BandKind]]:
    kinds = list(BandKind)
    combos: list[tuple[object, BandKind]] = []
    for index, band in enumerate(ALL_PRESETS):
        if band in REJECTION_PRESETS:
            combos.append((band, BandKind.BSF))
        else:
            combos.append((band, kinds[index % len(kinds)]))
    return combos


def test_plot_state_is_clean_for_every_preset(monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    session = DesignSession()
    window = MainWindow(session, auto_run=False)
    fits: list[tuple[float, float]] = []

    def _capture_auto_range() -> None:
        expected = session.compute_harmonics()
        expected_hz = (
            [h.frequency_hz for h in expected.harmonics]
            if expected is not None
            else []
        )
        actual_hz = [10.0 ** line.value() for line in window._plots._harmonic_lines]
        assert actual_hz == pytest.approx(expected_hz)
        assert not any(cursor.isVisible() for cursor in window._plots._cursors)
        assert window._plots.cursor_frequency_hz() is None
        assert window._plots.frequency_range() is not None
        fits.append(window._plots.frequency_range())  # type: ignore[arg-type]

    monkeypatch.setattr(window._plots, "auto_range", _capture_auto_range)
    combos = _combinations()
    for band, kind in combos:
        sweep = band_sweep(band)
        session.set_spec(band_preset_spec(band, kind))
        session.sweep = sweep
        result = session.synthesize_and_analyze()

        for cursor in window._plots._cursors:
            cursor.setPos(math.log10(sweep.f_stop_hz * 10.0))
            cursor.setVisible(True)
        window._plots._cursor_freq_hz = sweep.f_stop_hz * 10.0
        window._fit_plots_after_analysis = True
        window._on_analyze_finished(result)

        assert window._plots.frequency_range() == pytest.approx(
            (sweep.f_start_hz, sweep.f_stop_hz)
        )

    assert len(fits) == len(combos)
    window.close()
    assert app is not None
