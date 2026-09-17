import sys
import tkinter as tk
from unittest.mock import Mock

import pytest

from app import config, main


@pytest.fixture(scope="module")
def gui(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("prefix_settings")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)
    stdout, stderr = sys.stdout, sys.stderr
    root = tk.Tk()
    app = main.ImageSorterGUI(root)
    root.update()
    yield app
    sys.stdout, sys.stderr = stdout, stderr
    root.destroy()
    monkeypatch.undo()


@pytest.mark.parametrize(
    "enabled,level,separator,expected",
    [
        (False, -1, "_", "manual_"),
        (True, 0, "_", "Media_03_"),
        (True, -1, "_", "Parent-02_"),
        (True, -2, "_", "Grand_Parent_01_"),
        (True, -2, ".", "Grand.Parent.01."),
    ],
)
def test_folder_prefix_passed_to_sorting(gui, tmp_path, monkeypatch, enabled, level, separator, expected):
    folder = tmp_path / "Grand [Parent] 01!" / "Parent-02@" / "Media 03_é"
    folder.mkdir(parents=True)
    gui.folder_path.set(str(folder))
    gui.prefix.set("manual_")
    gui.auto_prefix.set(enabled)
    gui.prefix_folder_level.set(level)
    gui.separator.set(separator)
    thread = Mock()
    monkeypatch.setattr(main.threading, "Thread", thread)

    gui.start_sorting()

    assert thread.call_args.kwargs["args"][-1] == expected
    assert gui.prefix.get() == "manual_"
    thread.return_value.start.assert_called_once()


def test_word_selector_tracks_available_words(gui, tmp_path, monkeypatch):
    callback_error = Mock()
    monkeypatch.setattr(gui.root, "report_callback_exception", callback_error)
    gui.prefix_word.set(-1)
    gui.prefix_folder_level.set(0)
    gui.auto_prefix.set(True)
    gui.toggle_auto_prefix()
    gui.separator.set("_")
    folder = tmp_path / "Single" / "Carmen-rae #Maeken #Cacu"
    gui.folder_path.set(str(folder))
    gui.prefix_word.set(2)
    assert float(gui.prefix_word_spinbox.cget("to")) == 2
    gui.prefix_word_spinbox.event_generate("<<Increment>>")
    gui.root.update()
    assert gui.prefix_word.get() == 2
    assert gui.prefix_folder_preview.get() == "Cacu_"

    gui.prefix_folder_level.set(-1)
    assert float(gui.prefix_word_spinbox.cget("to")) == 0
    assert gui.prefix_word.get() == 0
    assert gui.prefix_folder_preview.get() == "Single_"

    gui.prefix_folder_level.set(0)
    gui.folder_path.set(str(tmp_path / "###"))
    assert float(gui.prefix_word_spinbox.cget("to")) == -1
    assert gui.prefix_word.get() == -1
    gui.prefix_word_spinbox.event_generate("<<Increment>>")
    gui.root.update()
    assert gui.prefix_word.get() == -1

    gui.folder_path.set("")
    assert gui.prefix_folder_preview.get() == ""
    callback_error.assert_not_called()


def test_folder_prefix_controls(gui):
    gui.prefix_folder_level.set(0)
    gui.folder_path.set("C:/Media Folder")
    gui.auto_prefix.set(False)
    gui.toggle_auto_prefix()
    assert gui.prefix_folder_spinbox.instate(["disabled"])
    assert gui.prefix_word_spinbox.instate(["disabled"])
    gui.auto_prefix.set(True)
    gui.toggle_auto_prefix()
    assert gui.prefix_entry.instate(["disabled"])
    assert gui.prefix_folder_spinbox.instate(["readonly", "!disabled"])
    assert gui.prefix_word_spinbox.instate(["readonly", "!disabled"])
    gui.prefix_word_spinbox.event_generate("<<Decrement>>")
    gui.root.update()
    assert gui.prefix_word.get() == -1
    gui.prefix_word_spinbox.event_generate("<<Increment>>")
    gui.root.update()
    assert gui.prefix_word.get() == 0
    gui.prefix_word.set(-1)

    gui.prefix_folder_spinbox.event_generate("<<Increment>>")
    gui.root.update()
    assert gui.prefix_folder_level.get() == 0
    gui.prefix_folder_spinbox.event_generate("<<Decrement>>")
    gui.root.update()
    assert gui.prefix_folder_level.get() == -1
    gui.prefix_folder_spinbox.insert(0, "1")
    assert gui.prefix_folder_level.get() == -1

    for geometry in ("1100x700", "1600x1000"):
        gui.root.geometry(geometry)
        gui.root.update()
        assert gui.prefix_folder_spinbox.winfo_width() > 0

    gui.auto_prefix.set(False)
    gui.toggle_auto_prefix()
    assert gui.prefix_entry.instate(["!disabled"])
    assert gui.prefix_folder_spinbox.instate(["disabled"])
    assert gui.prefix_word_spinbox.instate(["disabled"])


@pytest.mark.parametrize("folder_name", ["Carmen-rae #Maeken #Cacu", "Carmen-rae __#Maeken___ #Cacu"])
@pytest.mark.parametrize(
    "word,expected",
    [(-1, "Carmen-rae.Maeken.Cacu."), (0, "Carmen-rae."), (1, "Maeken."), (2, "Cacu.")],
)
def test_prefix_word_preview_and_sorting(gui, tmp_path, monkeypatch, folder_name, word, expected):
    gui.prefix_word.set(-1)
    gui.prefix_folder_level.set(0)
    folder = tmp_path / folder_name
    folder.mkdir()
    gui.folder_path.set(str(folder))
    gui.auto_prefix.set(True)
    gui.separator.set(".")
    gui.prefix_word.set(word)
    thread = Mock()
    monkeypatch.setattr(main.threading, "Thread", thread)

    assert gui.prefix_folder_preview.get() == expected
    gui.start_sorting()
    assert thread.call_args.kwargs["args"][-1] == expected


def test_displayed_preview_through_folder_and_word_changes(gui, monkeypatch):
    callback_error = Mock()
    monkeypatch.setattr(gui.root, "report_callback_exception", callback_error)
    gui.folder_path.set("")
    gui.separator.set("_")
    gui.auto_prefix.set(True)
    gui.toggle_auto_prefix()
    label = next(
        widget for widget in gui.prefix_folder_spinbox.master.winfo_children()
        if widget.winfo_class() == "TLabel"
        and str(widget.cget("textvariable")) == str(gui.prefix_folder_preview)
    )
    gui.folder_path.set("C:/Single/Carmen-rae #Maeken #Cacu")
    gui.root.update()
    assert label.cget("text") == "Carmen-rae_Maeken_Cacu_"
    for expected in ("Carmen-rae_", "Maeken_", "Cacu_", "Cacu_"):
        gui.prefix_word_spinbox.event_generate("<<Increment>>")
        gui.root.update()
        assert label.cget("text") == expected
    for expected in ("Single_", "_", "_"):
        gui.prefix_folder_spinbox.event_generate("<<Decrement>>")
        gui.root.update()
        assert label.cget("text") == expected
    assert gui.prefix_folder_level.get() == -2
    gui.prefix_folder_spinbox.event_generate("<<Increment>>")
    gui.root.update()
    assert label.cget("text") == "Single_"
    gui.prefix_folder_spinbox.event_generate("<<Increment>>")
    gui.root.update()
    assert label.cget("text") == "Carmen-rae_Maeken_Cacu_"
    gui.separator.set(".")
    gui.root.update()
    assert label.cget("text") == "Carmen-rae.Maeken.Cacu."
    gui.prefix_folder_level.set(-2)
    gui.folder_path.set("C:/")
    gui.root.update()
    assert gui.prefix_folder_level.get() == 0
    gui.folder_path.set("C:/New Folder")
    gui.root.update()
    assert label.cget("text") == "New.Folder."
    callback_error.assert_not_called()
