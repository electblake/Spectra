import sys
import threading
import tkinter as tk
from unittest.mock import Mock

import numpy as np
import pytest
from PIL import Image

from app import config, main
from app.main import calculate_visual_features, sort_with_tight_clustering


@pytest.mark.parametrize("optimization", config.RESIZE_REDUCING_GAPS)
def test_parallel_sort_preserves_features_and_order(tmp_path, optimization):
    rng = np.random.default_rng(42)
    paths = []
    for index in range(6):
        path = tmp_path / f"{index}.png"
        Image.fromarray(rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)).save(path)
        paths.append(path)
    gap = config.RESIZE_REDUCING_GAPS[optimization]
    expected = {path: calculate_visual_features(str(path), reducing_gap=gap) for path in paths}
    serial = sort_with_tight_clustering(paths, 0.5, feature_workers=1, reducing_gap=gap)
    parallel = sort_with_tight_clustering(paths, 0.5, feature_workers=4, reducing_gap=gap)
    assert [path for path, _ in parallel] == [path for path, _ in serial]
    for path, feature in parallel:
        np.testing.assert_array_equal(feature, expected[path])
        assert feature.shape == (219,)
        assert np.isfinite(feature).all()


def test_performance_settings_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)
    defaults, loaded_path = config.read_user_settings()
    assert loaded_path is None
    assert defaults["feature_workers"] == 4
    assert defaults["video_workers"] == 1
    assert defaults["png_compress_level"] == 1
    assert defaults["resize_optimization"] == "Default"
    values = defaults | {
        "feature_workers": 2, "video_workers": 3,
        "png_compress_level": 9, "resize_optimization": "High",
    }
    config.save_user_settings(**values)
    loaded, loaded_path = config.read_user_settings()
    assert loaded == values
    assert loaded_path == tmp_path / "settings.ini"


def test_worker_spinboxes_save_reset_and_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "user_config_path", lambda *args, **kwargs: tmp_path)
    stdout, stderr = sys.stdout, sys.stderr
    root = tk.Tk()
    gui = main.ImageSorterGUI(root)
    gui.notebook.select(gui.settings_tab)
    root.update()
    performance = gui.settings_tab.feature_workers_spinbox.master
    assert [widget.cget("text") for widget in performance.winfo_children()
            if widget.winfo_class() == "TLabel" and str(widget.cget("text")).endswith(":")] == [
        "Image feature workers:", "Video frame workers:",
    ]
    assert len([widget for widget in performance.winfo_children()
                if widget.winfo_class() == "TSpinbox"]) == 2
    gui.settings_tab.feature_workers_spinbox.event_generate("<<Increment>>")
    gui.settings_tab.video_workers_spinbox.event_generate("<<Increment>>")
    root.update()
    assert gui.feature_workers.get() == 5
    assert gui.video_workers.get() == 2
    gui.folder_path.set(str(tmp_path))
    gui.dry_run.set(True)
    gui.save_settings()
    saved, _ = config.read_user_settings()
    assert saved["feature_workers"] == 5
    assert saved["video_workers"] == 2
    thread = Mock()
    monkeypatch.setattr(main.threading, "Thread", thread)
    gui.start_button.invoke()
    assert thread.call_args.kwargs["args"][5] == 5
    assert thread.call_args.kwargs["kwargs"] == {"video_workers": 2}
    gui.restore_default_settings()
    assert gui.feature_workers.get() == config.FEATURE_WORKERS
    assert gui.video_workers.get() == config.VIDEO_WORKERS
    for geometry in ("1100x700", "1600x1000"):
        root.geometry(geometry)
        root.update()
        assert gui.settings_tab.video_workers_spinbox.winfo_width() > 0
    sys.stdout, sys.stderr = stdout, stderr
    root.destroy()


@pytest.mark.parametrize("worker_count", [1, 3])
def test_video_worker_count_controls_concurrent_processes(tmp_path, monkeypatch, worker_count):
    for index in range(6):
        (tmp_path / f"{index}.mp4").write_bytes(b"video")
    context = Mock()
    connections = []
    tasks = []

    def pipe():
        connection = Mock()
        connection.send.side_effect = lambda task: tasks.append(task) if task is not None else None
        connection.poll.side_effect = lambda: len(tasks) >= worker_count
        connection.recv.return_value = (True, 10)
        connections.append(connection)
        return connection, Mock()

    context.Pipe.side_effect = pipe
    monkeypatch.setattr(main.multiprocessing, "get_context", lambda method: context)
    result = main.get_video_image_files(tmp_path, threading.Event(), video_workers=worker_count)
    assert context.Process.call_count == worker_count
    assert len(result) == 6
    assert len(tasks) == 6
    assert len({task[0] for task in tasks}) == 6
    for connection in connections:
        connection.close.assert_called_once()


def test_gui_passes_video_worker_count_to_extraction(tmp_path, monkeypatch):
    gui = main.ImageSorterGUI.__new__(main.ImageSorterGUI)
    gui.stop_event = threading.Event()
    gui.log = Mock()
    gui.on_complete = Mock()
    scan = Mock(return_value=[])
    monkeypatch.setattr(main, "get_image_files", scan)
    extraction = Mock(return_value=[])
    monkeypatch.setattr(main, "get_video_image_files", extraction)
    gui.run_sorting(str(tmp_path), 0.5, config.DEFAULT_FEATURE_WEIGHTS, 50, True, 5, 1, None, "",
                    video_workers=3)
    extraction.assert_called_once_with(str(tmp_path), gui.stop_event, 50, 1, video_workers=3)
    scan.assert_called_once_with(str(tmp_path), gui.stop_event)
