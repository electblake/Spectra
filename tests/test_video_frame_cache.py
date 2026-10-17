import builtins
import threading
from unittest.mock import Mock

from PIL import Image

from app import main
from app.workers import video_frames


def make_video(path, color):
    Image.new("RGB", (16, 16), color).save(path, format="GIF")


def test_cached_rerun_starts_no_workers(tmp_path, monkeypatch):
    source = tmp_path / "media"
    source.mkdir()
    video = source / "clip.gif"
    make_video(video, "red")
    frames = main.get_video_image_files(source, threading.Event())
    original_bytes = frames[0].read_bytes()
    context = Mock()
    monkeypatch.setattr(main.multiprocessing, "get_context", context)

    assert main.get_video_image_files(source, threading.Event(), frame_percentage=90) == frames
    context.assert_not_called()
    assert frames[0].read_bytes() == original_bytes
    assert frames[0].is_relative_to(tmp_path / "cache")
    assert list(source.iterdir()) == [video]
    assert video_frames.video_frame_source(frames[0], source) == video


def test_same_name_in_different_folders_has_separate_cache(tmp_path):
    frames = []
    for name, color in (("one", "red"), ("two", "blue")):
        source = tmp_path / name
        source.mkdir()
        make_video(source / "clip.gif", color)
        frames.extend(main.get_video_image_files(source, threading.Event()))
    assert frames[0] != frames[1]
    with Image.open(frames[0]) as first, Image.open(frames[1]) as second:
        assert first.convert("RGB").getpixel((0, 0)) == (255, 0, 0)
        assert second.convert("RGB").getpixel((0, 0)) == (0, 0, 255)


def test_cancelled_run_keeps_completed_grabs_for_resume(tmp_path, monkeypatch):
    source = tmp_path / "media"
    source.mkdir()
    for name in ("one.gif", "two.gif"):
        make_video(source / name, "red")
    stop = threading.Event()
    original_print = builtins.print

    def stop_after_first(*args, **kwargs):
        original_print(*args, **kwargs)
        if args and args[0] == "Extracting video frames 1/2":
            stop.set()

    monkeypatch.setattr(builtins, "print", stop_after_first)
    assert main.get_video_image_files(source, stop) == []
    cached, pending = video_frames.prepare_video_frames(list(source.iterdir()))
    assert len(cached) == len(pending) == 1
    cached_time = cached[0].stat().st_mtime_ns
    # An unfinished write must not be treated as a completed grab.
    unfinished = video_frames.video_frame_path(pending[0]).with_suffix(".interrupted.tmp")
    unfinished.write_bytes(b"partial")
    assert video_frames.prepare_video_frames(list(source.iterdir())) == (cached, pending)

    stop.clear()
    frames = main.get_video_image_files(source, stop)
    assert len(frames) == 2
    assert cached[0].stat().st_mtime_ns == cached_time
    assert len(list(source.iterdir())) == 2
