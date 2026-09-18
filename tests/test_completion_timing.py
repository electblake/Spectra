import sys
import tkinter as tk
from unittest.mock import Mock

import pytest

from app import config, main


@pytest.mark.parametrize("outcome", ["success", "stopped", "failed"])
def test_completion_waits_for_all_log_batches(tmp_path, monkeypatch, outcome):
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)
    root = tk.Tk()
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

        gui.on_complete(outcome == "success")
        root.update()
        assert gui.is_processing
        assert gui.start_button.instate(["disabled"])
        gui.show_completion_dialog.assert_not_called()

        def check_completion():
            if gui.is_processing:
                root.after(10, check_completion)
            else:
                root.quit()

        root.after(10, check_completion)
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
        root.destroy()
