import builtins
import multiprocessing
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from PIL import Image

from app import config, main


@pytest.mark.parametrize("media", [False, True])
@pytest.mark.parametrize("stage", ["Preparing", "Renaming"])
def test_stop_restores_original_names_and_contents(tmp_path, monkeypatch, media, stage):
    # Final names overlap the originals, exercising rename cycles during cancellation.
    originals = [tmp_path / name for name in ("2.png", "3.png", "1.png")]
    for index, path in enumerate(originals):
        path.write_bytes(bytes([index]))
    expected = {path.name: path.read_bytes() for path in originals}
    stop = threading.Event()
    real_print = builtins.print

    def print_and_stop(*args, **kwargs):
        real_print(*args, **kwargs)
        if args and str(args[0]).startswith(stage):
            stop.set()

    monkeypatch.setattr(builtins, "print", print_and_stop)
    items = [(path, np.zeros(1)) for path in originals]
    if media:
        main.rename_media(items, tmp_path, backup=False, stop_event=stop)
    else:
        main.rename_images(items, backup=False, stop_event=stop)
    assert stop.is_set()
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == expected


def test_sorting_process_preserves_results(tmp_path):
    paths = []
    for index, color in enumerate(("red", "blue", "green")):
        path = tmp_path / f"{index}.png"
        Image.new("RGB", (30, 30), color).save(path)
        paths.append(path)
    expected = main.sort_with_tight_clustering(paths, 0.5)
    actual = main.sort_with_tight_clustering(paths, 0.5, stop_event=threading.Event())
    assert [path for path, _ in actual] == [path for path, _ in expected]
    for (_, feature), (_, expected_feature) in zip(actual, expected):
        np.testing.assert_array_equal(feature, expected_feature)


@pytest.mark.parametrize("stage", [
    "Processing visual features 0/",
    "Calculating visual similarity 0/",
    "Clustering images 0/",
    "Sorting images in cluster 1/",
])
def test_stop_interrupts_analysis_and_reaps_worker(tmp_path, monkeypatch, stage):
    path = tmp_path / "image.png"
    Image.new("RGB", (100, 100), "red").save(path)
    stop = threading.Event()
    children_before = {child.pid for child in multiprocessing.active_children()}
    real_print = builtins.print
    stopped_at = []

    def print_and_stop(*args, **kwargs):
        real_print(*args, **kwargs)
        if args and stage in str(args[0]):
            stopped_at.append(time.monotonic())
            stop.set()

    monkeypatch.setattr(builtins, "print", print_and_stop)
    result = main.sort_with_tight_clustering([path] * 2000, 0.5, stop_event=stop)
    assert stopped_at
    assert time.monotonic() - stopped_at[0] < 3
    assert result == []
    assert {child.pid for child in multiprocessing.active_children()} == children_before
    assert path.exists()


def test_stop_during_video_wait_cleans_worker_and_grabs(tmp_path, monkeypatch):
    (tmp_path / "video.mp4").write_bytes(b"video")
    stop = threading.Event()
    connection = Mock()

    def poll(timeout=0):
        stop.set()
        return False

    connection.poll.side_effect = poll
    context = Mock()
    context.Pipe.return_value = (connection, Mock())
    monkeypatch.setattr(main.multiprocessing, "get_context", lambda method: context)
    assert main.get_video_image_files(tmp_path, stop) == []
    context.Process.return_value.terminate.assert_called_once()
    context.Process.return_value.join.assert_called_once()
    connection.close.assert_called_once()
    assert not (tmp_path / main.VIDEO_GRABS_FOLDER).exists()


def test_gui_does_not_rename_after_analysis_is_stopped(tmp_path, monkeypatch):
    gui = main.ImageSorterGUI.__new__(main.ImageSorterGUI)
    gui.stop_event = threading.Event()
    gui.log = Mock()
    gui.on_complete = Mock()
    monkeypatch.setattr(main, "get_image_files", lambda *args: [Path("image.png")])

    def stop_analysis(*args, **kwargs):
        gui.stop_event.set()
        return []

    monkeypatch.setattr(main, "sort_with_tight_clustering", stop_analysis)
    rename = Mock()
    monkeypatch.setattr(main, "rename_images", rename)
    gui.run_sorting(str(tmp_path), 0.5, main.DEFAULT_FEATURE_WEIGHTS, 50, False, 1, 1, None, "")
    rename.assert_not_called()
    gui.on_complete.assert_called_once_with(False)


def test_pre_stopped_scan_and_sort_do_no_work(tmp_path):
    stop = threading.Event()
    stop.set()
    (tmp_path / "image.png").write_bytes(b"image")
    assert main.get_image_files(tmp_path, stop) == []
    assert main.get_video_image_files(tmp_path, stop) == []
    assert main.sort_with_tight_clustering([tmp_path / "image.png"], stop_event=stop) == []


def test_stop_button_returns_gui_to_idle(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)
    stdout, stderr = sys.stdout, sys.stderr
    root = tk.Tk()
    gui = main.ImageSorterGUI(root)
    path = tmp_path / "image.png"
    Image.new("RGB", (100, 100), "red").save(path)
    monkeypatch.setattr(main, "get_image_files", lambda *args: [path] * 2000)
    gui.folder_path.set(str(tmp_path))
    gui.include_videos.set(False)
    gui.dry_run.set(True)
    gui.show_completion_dialog = Mock()
    callback_errors = Mock()
    root.report_callback_exception = callback_errors
    for geometry in ("1100x700", "1600x1000"):
        root.geometry(geometry)
        root.update()
    gui.start_button.invoke()

    deadline = time.monotonic() + 15
    stopped = False

    def check_stop():
        nonlocal stopped
        if not stopped and "Processing visual features" in gui.status_text.get():
            gui.stop_button.invoke()
            stopped = True
        if not gui.is_processing or time.monotonic() >= deadline:
            root.quit()
        else:
            root.after(10, check_stop)

    root.after(10, check_stop)
    root.mainloop()
    sys.stdout, sys.stderr = stdout, stderr
    assert stopped
    assert not gui.is_processing
    assert gui.start_button.instate(["!disabled"])
    assert gui.stop_button.instate(["disabled"])
    gui.update_status_from_output("Processing visual features 100/2000", time.perf_counter())
    assert gui.status_text.get() == "Media sorting stopped 0/1"
    gui.show_completion_dialog.assert_not_called()
    callback_errors.assert_not_called()
    root.destroy()
