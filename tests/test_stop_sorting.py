import builtins
import multiprocessing
import threading
import time
from unittest.mock import Mock

import numpy as np
import pytest
from PIL import Image

from app import main


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


def test_stop_during_video_wait_cleans_worker(tmp_path, monkeypatch):
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
    assert not (tmp_path / ".spectra_video_grabs").exists()




def test_pre_stopped_scan_and_sort_do_no_work(tmp_path):
    stop = threading.Event()
    stop.set()
    (tmp_path / "image.png").write_bytes(b"image")
    assert main.get_image_files(tmp_path, stop) == []
    assert main.get_video_image_files(tmp_path, stop) == []
    assert main.sort_with_tight_clustering([tmp_path / "image.png"], stop_event=stop) == []
