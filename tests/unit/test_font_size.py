"""GUI font-size presets and persistence."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QToolBar

from filterdesk.gui.fonts import (
    FontSize,
    apply_font_size,
    font_size_from_code,
    reset_font_base,
)
from filterdesk.gui.settings import (
    FONT_SIZE_KEY,
    InMemorySettingsStore,
    get_settings_store,
    set_settings_store,
)


@pytest.fixture(autouse=True)
def _restore_default_font() -> object:
    """Keep font changes scoped to this module."""
    yield None
    app = QApplication.instance()
    if isinstance(app, QApplication):
        apply_font_size(app, FontSize.DEFAULT)


def test_font_size_presets_scale_relative_to_base() -> None:
    app = QApplication.instance() or QApplication([])
    reset_font_base()
    apply_font_size(app, FontSize.DEFAULT)
    base = app.font().pointSizeF()
    assert base > 0.0

    assert apply_font_size(app, FontSize.SMALL).pointSizeF() == pytest.approx(
        base * 0.9
    )
    assert apply_font_size(app, FontSize.LARGE).pointSizeF() == pytest.approx(
        base * 1.15
    )
    assert apply_font_size(
        app, FontSize.EXTRA_LARGE
    ).pointSizeF() == pytest.approx(base * 1.3)
    assert apply_font_size(app, FontSize.DEFAULT).pointSizeF() == pytest.approx(
        base
    )
    assert app is not None


def test_font_size_from_code_falls_back_to_default() -> None:
    assert font_size_from_code("large") is FontSize.LARGE
    assert font_size_from_code("not-a-size") is FontSize.DEFAULT


def test_main_window_applies_saved_font_size() -> None:
    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    set_settings_store(
        InMemorySettingsStore({FONT_SIZE_KEY: FontSize.LARGE.value})
    )
    reset_font_base()
    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    assert window._font_size is FontSize.LARGE
    assert window._font_size_actions[FontSize.LARGE].isChecked()
    assert app.font().pointSizeF() > 0.0
    window.close()
    assert app is not None


def test_request_font_size_persists_and_warns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: messages.append(str(args[2])),
    )
    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    window._request_font_size(FontSize.EXTRA_LARGE)
    assert get_settings_store().get_str(FONT_SIZE_KEY) == (
        FontSize.EXTRA_LARGE.value
    )
    assert window._font_size_actions[FontSize.EXTRA_LARGE].isChecked()
    assert messages
    assert "Restart FilterDesk" in messages[0]
    window.close()
    assert app is not None



def test_menu_and_toolbar_follow_app_font() -> None:
    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    set_settings_store(
        InMemorySettingsStore({FONT_SIZE_KEY: FontSize.EXTRA_LARGE.value})
    )
    reset_font_base()
    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    menu_bar = window.menuBar()
    assert menu_bar.font().pointSizeF() == pytest.approx(
        app.font().pointSizeF()
    )
    assert menu_bar.sizeHint().height() >= menu_bar.fontMetrics().height()
    for action in menu_bar.actions():
        menu = action.menu()
        if menu is not None:
            assert menu.font().pointSizeF() == pytest.approx(
                app.font().pointSizeF()
            )
    toolbar = window.findChild(QToolBar, "MainToolBar")
    assert toolbar is not None
    assert toolbar.font().pointSizeF() == pytest.approx(
        app.font().pointSizeF()
    )
    window.close()
    assert app is not None


def test_preferences_submenu_holds_appearance_actions() -> None:
    from PySide6.QtWidgets import QApplication, QMenu

    from filterdesk.gui.main_window import MainWindow
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    window = MainWindow(DesignSession(), auto_run=False)
    menus = {
        action.text().replace("&", ""): action.menu()
        for action in window.menuBar().actions()
        if isinstance(action.menu(), QMenu)
    }
    edit_menu = menus["Edit"]
    assert edit_menu is not None
    preferences = next(
        action.menu()
        for action in edit_menu.actions()
        if action.text().replace("&", "") == "Preferences"
    )
    assert preferences is not None
    labels = [action.text().replace("&", "") for action in preferences.actions()]
    assert labels == ["Theme", "Font size", "Language"]
    view_menu = menus["View"]
    assert view_menu is not None
    view_labels = [action.text().replace("&", "") for action in view_menu.actions()]
    assert not any(
        label in view_labels for label in ("Theme", "Font size", "Language")
    )
    window.close()
    assert app is not None
