"""Guided tutorial content and dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from filterdesk.gui.i18n import Language, set_language
from filterdesk.gui.tutorials import TUTORIALS, TutorialDialog


def test_tutorial_catalog_is_bilingual_and_complete() -> None:
    assert len(TUTORIALS) >= 3
    assert len({tutorial.title for tutorial in TUTORIALS}) == len(TUTORIALS)
    for tutorial in TUTORIALS:
        assert tutorial.title_es
        assert "<ol>" in tutorial.html
        assert "<ol>" in tutorial.html_es
        assert tutorial.commands


def test_tutorial_dialog_shows_content_and_copies_commands() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = TutorialDialog()
    assert dialog._list.count() == len(TUTORIALS)
    assert dialog._browser.toHtml()
    dialog._copy_commands()
    assert QApplication.clipboard().text() == TUTORIALS[0].commands[0]
    dialog.close()
    assert app is not None


def test_tutorial_titles_follow_language() -> None:
    app = QApplication.instance() or QApplication([])
    try:
        set_language(Language.ES)
        dialog = TutorialDialog()
        assert dialog._list.item(0).text() == TUTORIALS[0].title_es
        dialog.close()
    finally:
        set_language(Language.EN)
    assert app is not None
