"""Guided tutorial content and dialog."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from filterdesk.domain.enums import FilterResponse
from filterdesk.gui.i18n import Language, set_language
from filterdesk.gui.tutorials import TUTORIALS, TutorialDialog
from filterdesk.services.examples import (
    BUILTIN_EXAMPLES,
    get_example,
    load_filter_example,
    load_system_example,
)
from filterdesk.services.system_project import SystemProject


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


def test_tutorial_examples_are_bundled_and_load() -> None:
    ids = {example.id for example in BUILTIN_EXAMPLES}
    assert {tutorial.example for tutorial in TUTORIALS} <= ids
    for example in BUILTIN_EXAMPLES:
        if example.kind == "filter":
            project = load_filter_example(example)
            assert project.specification is not None
            assert project.circuit is not None
        else:
            project = load_system_example(example)
            assert project.kind == "lp-hp"
            assert project.low_cutoff_hz == 144e6
            assert project.high_cutoff_hz == 148e6


def test_tutorial_dialog_emits_example_request() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = TutorialDialog()
    received: list[str] = []
    dialog.example_requested.connect(received.append)
    dialog._open_example()
    assert received == ["rx40m"]
    dialog.close()
    assert app is not None


def test_open_filter_tutorial_example(monkeypatch: pytest.MonkeyPatch) -> None:
    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    window = mw.MainWindow(DesignSession(), auto_run=False)
    monkeypatch.setattr(window, "_run_analyze", lambda: None)
    window._open_tutorial_example("rx40m")
    assert window._session.spec is not None
    assert window._session.spec.response is FilterResponse.BAND_PASS
    assert window._session.title.startswith("Tutorial 1")
    window.close()
    assert app is not None


def test_open_system_tutorial_example(monkeypatch: pytest.MonkeyPatch) -> None:
    from filterdesk.gui import main_window as mw
    from filterdesk.services.session import DesignSession

    app = QApplication.instance() or QApplication([])
    seen: list[SystemProject | None] = []

    class _FakeDialog:
        def __init__(
            self, parent: object = None, project: SystemProject | None = None
        ) -> None:
            seen.append(project)

        def exec(self) -> None:
            return None

    monkeypatch.setattr(mw, "DiplexerDialog", _FakeDialog)
    window = mw.MainWindow(DesignSession(), auto_run=False)
    window._open_tutorial_example("diplexer2m")
    assert seen
    assert seen[0] is not None
    assert seen[0].kind == "lp-hp"
    window.close()
    assert app is not None


def test_diplexer_dialog_opens_builtin_example() -> None:
    from filterdesk.gui.widgets import DiplexerDialog

    app = QApplication.instance() or QApplication([])
    example = get_example("diplexer2m")
    dialog = DiplexerDialog(project=load_system_example(example))
    assert dialog._mode.currentData() == "lp-hp"
    assert dialog._project_path.text() == "built-in example"
    assert dialog.current_design() is not None
    dialog.close()
    assert app is not None
