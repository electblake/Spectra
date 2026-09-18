import threading
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import Mock

from tkinter import ttk

from app import main


def test_large_discovery_reports_before_finishing(tmp_path, monkeypatch, capsys):
    entry = SimpleNamespace(name="image.jpg", path=str(tmp_path / "image.jpg"), is_file=lambda: True)

    class Entries:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def __iter__(self):
            for i in range(33000):
                if i == 500:
                    assert "500 entries checked, 500 images found" in capsys.readouterr().out
                yield entry

    monkeypatch.setattr(main.os, "scandir", lambda folder: Entries())
    assert len(main.get_image_files(tmp_path)) == 33000
    output = capsys.readouterr().out
    assert "33000 entries checked, 33000 images found" in output
    assert "Scanning image files 1/1" in output


def test_progress_transitions_and_log_batches():
    root = tk.Tk()
    root.withdraw()
    gui = main.ImageSorterGUI.__new__(main.ImageSorterGUI)
    gui.stop_event = threading.Event()
    gui.status_text = tk.StringVar(root)
    gui.progress_percent_text = tk.StringVar(root)
    gui.progress_metrics_text = tk.StringVar(root)
    gui.progress_stage = None
    gui.progress = ttk.Progressbar(root)
    gui.update_status_from_output("Scanning image files...", 0.0)
    assert str(gui.progress["mode"]) == "indeterminate"
    assert gui.progress_percent_text.get() == "…"
    gui.update_status_from_output("Processing visual features 0/33000", 1.0)
    gui.update_status_from_output("Processing visual features 500/33000", 11.0)
    assert str(gui.progress["mode"]) == "determinate"
    assert gui.progress["value"] == 500
    assert gui.progress_percent_text.get() == "2%"
    assert gui.progress_metrics_text.get() == "50.0 items/s  10m 50s"
    gui.update_status_from_output("Clustering images 0/1", 12.0)
    assert str(gui.progress["mode"]) == "indeterminate"
    assert gui.progress_metrics_text.get() == "— items/s  — s"
    gui.update_status_from_output("Clustering images 1/1", 14.0)
    assert str(gui.progress["mode"]) == "determinate"
    assert gui.progress_percent_text.get() == "100%"
    assert gui.progress_metrics_text.get() == "0.5 items/s  0s"
    gui.update_status_from_output("Sorting images in cluster 1/10", 15.0)
    gui.update_status_from_output("Sorting images in cluster 10/10", 18.0)
    assert gui.progress_metrics_text.get() == "3.0 items/s  0s"
    gui.update_status_from_output("Sorting images in cluster 1/10", 19.0)
    assert gui.progress_metrics_text.get() == "— items/s  — s"
    root.destroy()

    widget = Mock()
    redirector = main.TextRedirector(widget, "stdout", Mock())
    for i in range(33000):
        redirector.write(f"Processing visual features {i + 1}/33000")
    redirector.write_queued_text()
    assert widget.insert.call_count == 200
    assert redirector.text_queue.qsize() == 32800
    assert widget.after.call_count == 2


def test_progress_uses_worker_timestamp(monkeypatch):
    monkeypatch.setattr(main.time, "perf_counter", lambda: 12.5)
    callback = Mock()
    redirector = main.TextRedirector(Mock(), "stdout", callback)
    redirector.write("Processing visual features 1/10")
    monkeypatch.setattr(main.time, "perf_counter", lambda: 100.0)
    redirector.write_queued_text()
    callback.assert_called_once_with("Processing visual features 1/10", 12.5)


def test_folder_selection_dispatches_scan(monkeypatch, tmp_path):
    gui = main.ImageSorterGUI.__new__(main.ImageSorterGUI)
    gui.folder_path = Mock()
    gui.include_videos = Mock()
    gui.include_videos.get.return_value = True
    monkeypatch.setattr(main.filedialog, "askdirectory", lambda **kwargs: str(tmp_path))
    thread = Mock()
    monkeypatch.setattr(main.threading, "Thread", thread)
    gui.browse_folder()
    assert thread.call_args.kwargs["target"] == gui.scan_folder
    assert thread.call_args.kwargs["args"] == (str(tmp_path), True)
    thread.return_value.start.assert_called_once()
