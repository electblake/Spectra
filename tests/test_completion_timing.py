import sys
import tkinter as tk
from unittest.mock import Mock

import pytest

from app import config, main


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.mark.parametrize("outcome", ["success", "stopped", "failed"])
def test_completion_waits_for_all_log_batches(tmp_path, monkeypatch, outcome, tk_root):
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)
    root = tk.Toplevel(tk_root)
    root.withdraw()
    with monkeypatch.context() as capture:
        capture.setattr(sys, "stdout", sys.stdout)
        gui = main.ImageSorterGUI(root)
        gui.is_processing = True
        gui.start_button.config(state=tk.DISABLED)
        gui.show_completion_dialog = Mock()
        if outcome == "stopped":
            gui.stop_event.set()
        for index in range(1000):
            gui.log(f"Renaming images {index + 1}/1000")
        gui.log("FINAL LOG ENTRY")

        complete_ui = gui._on_complete_ui

        def finish(success):
            assert gui.log_text.get("1.0", "end-1c").endswith("FINAL LOG ENTRY\n")
            complete_ui(success)
            root.quit()

        gui._on_complete_ui = finish
        gui.on_complete(outcome == "success")
        assert gui.is_processing
        assert gui.start_button.instate(["disabled"])
        gui.show_completion_dialog.assert_not_called()

        root.after(10000, root.quit)
        root.mainloop()
        assert not gui.is_processing
        assert gui.log_redirector.text_queue.empty()
        assert gui.log_text.get("1.0", "end-1c").endswith("FINAL LOG ENTRY\n")
        if outcome == "success":
            gui.show_completion_dialog.assert_called_once()
            assert gui.status_text.get() == "Media sorting complete 1/1"
        else:
            gui.show_completion_dialog.assert_not_called()
            assert gui.status_text.get() == f"Media sorting {outcome} 0/1"
        root.update()
        assert gui.log_redirector.text_queue.empty()
        for callback in root.tk.call("after", "info"):
            root.tk.call("after", "cancel", callback)
        root.destroy()


def test_completion_is_consumed_once_after_preceding_logs():
    widget = Mock()
    gui = main.ImageSorterGUI.__new__(main.ImageSorterGUI)
    gui.root = Mock()
    gui.log_redirector = main.TextRedirector(widget, "stdout", Mock())
    gui._on_complete_ui = Mock()
    for index in range(1000):
        gui.log_redirector.write(f"line {index}\n")

    gui.on_complete(True)
    gui.root.after.assert_not_called()
    for _ in range(5):
        gui.log_redirector.write_queued_text()
        gui._on_complete_ui.assert_not_called()
    assert widget.insert.call_count == 1000
    gui.log_redirector.write_queued_text()
    gui._on_complete_ui.assert_called_once_with(True)
    gui.log_redirector.write_queued_text()
    gui._on_complete_ui.assert_called_once_with(True)
    gui.root.after.assert_not_called()
