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


@pytest.mark.parametrize("prefix", ["manual_", "", "Custom prefix-é_"])
@pytest.mark.parametrize("separator", ["_", "."])
def test_manual_prefix_passed_to_sorting(gui, tmp_path, monkeypatch, prefix, separator):
    folder = tmp_path / "Grand [Parent] 01!" / "Parent-02@" / "Media 03_é"
    folder.mkdir(parents=True)
    gui.folder_path.set(str(folder))
    gui.prefix_entry.delete(0, tk.END)
    gui.prefix_entry.insert(0, prefix)
    gui.separator.set(separator)
    thread = Mock()
    monkeypatch.setattr(main.threading, "Thread", thread)

    gui.start_sorting()

    assert thread.call_args.kwargs["args"][-1] == prefix
    assert gui.prefix.get() == prefix
    thread.return_value.start.assert_called_once()
